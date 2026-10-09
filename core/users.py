import os
import re
import sqlite3
import hashlib
import secrets
import time
import logging
import random
from datetime import datetime
from config import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(DATA_DIR, "users.db")

PHONE_RE = re.compile(r'^1[3-9]\d{9}$')
EMAIL_RE = re.compile(r'^[\w.+-]+@[\w-]+\.[\w.-]+$')

CODE_EXPIRE_SECONDS = 300
CODE_RESEND_COOLDOWN = 60
MAX_CODE_ATTEMPTS = 5


def _get_sms_config():
    return {
        "provider": os.getenv("SMS_PROVIDER", "none").lower(),
        "access_key": os.getenv("SMS_ACCESS_KEY", ""),
        "secret": os.getenv("SMS_SECRET", ""),
        "sign": os.getenv("SMS_SIGN", "云镜AI"),
        "template": os.getenv("SMS_TEMPLATE", ""),
    }


def _generate_code() -> str:
    return str(random.randint(100000, 999999))


def _send_via_aliyun(phone, code, cfg):
    try:
        import hmac
        import base64
        import urllib.parse
        import urllib.request
        import uuid

        access_key = cfg["access_key"]
        secret = cfg["secret"]
        sign = cfg["sign"]
        template = cfg["template"]

        params = {
            "PhoneNumbers": phone,
            "SignName": sign,
            "TemplateCode": template,
            "TemplateParam": f'{{"code":"{code}"}}',
            "OutId": str(uuid.uuid4()),
        }

        sorted_keys = sorted(params.keys())
        query_str = "&".join(f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(params[k]), safe='')}" for k in sorted_keys)
        string_to_sign = "GET&%2F&" + urllib.parse.quote(query_str, safe='')
        sign = base64.b64encode(hmac.new((secret + "&").encode(), string_to_sign.encode(), hashlib.sha1).digest()).decode()

        url = f"https://dysmsapi.aliyuncs.com/?{query_str}&Signature={urllib.parse.quote(sign, safe='')}&Action=SendSms&Version=2017-05-25&Format=JSON&AccessKeyId={access_key}&SignatureMethod=HMAC-SHA1&SignatureVersion=1.0&SignatureNonce={uuid.uuid4()}&Timestamp={datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}"

        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=10).read().decode()
        logger.info(f"Aliyun SMS response: {resp}")
        return True
    except Exception as e:
        logger.error(f"Aliyun SMS failed: {e}")
        return False


def _send_via_tencent(phone, code, cfg):
    try:
        import hashlib
        import urllib.parse
        import urllib.request
        import hmac

        secret_id = cfg["access_key"]
        secret_key = cfg["secret"]
        sign = cfg["sign"]
        template = cfg["template"]

        params = {
            "SdkAppId": template,
            "PhoneNumber": f"+86{phone}",
            "SignName": sign,
            "TemplateID": "1",
            "TemplateParamSet": f'["{code}"]',
            "SessionContext": "",
            "ExtendCode": "",
        }

        logger.info(f"Tencent SMS (mock): phone={phone}, code={code}")
        return True
    except Exception as e:
        logger.error(f"Tencent SMS failed: {e}")
        return False


def _send_via_sms(phone, code, cfg):
    provider = cfg["provider"]
    if provider == "aliyun":
        return _send_via_aliyun(phone, code, cfg)
    elif provider == "tencent":
        return _send_via_tencent(phone, code, cfg)
    else:
        logger.warning(f"SMS not configured (provider={provider}). Dev mode: code={code} for {phone}")
        return True


def send_code(target: str, purpose: str = "login") -> dict:
    target = target.strip()
    if not target:
        return {"success": False, "error": "请输入手机号或邮箱"}

    auth_type = _detect_type(target)
    if auth_type not in ('phone', 'email'):
        return {"success": False, "error": "请输入有效的手机号或邮箱"}

    conn = _get_conn()
    now = int(time.time())
    try:
        row = conn.execute(
            "SELECT * FROM verification_codes WHERE target = ? AND purpose = ? ORDER BY created_at DESC LIMIT 1",
            (target, purpose)
        ).fetchone()

        if row and (now - row["created_at"]) < CODE_RESEND_COOLDOWN:
            wait = CODE_RESEND_COOLDOWN - (now - row["created_at"])
            conn.close()
            return {"success": False, "error": f"请在 {wait} 秒后重试", "cooldown": wait}

        code = _generate_code()
        expires_at = now + CODE_EXPIRE_SECONDS

        cfg = _get_sms_config()
        sent = False
        if auth_type == 'phone':
            sent = _send_via_sms(target, code, cfg)
        else:
            sent = True
            logger.warning(f"Email send not implemented. Dev mode: code={code} for email={target}")

        if not sent:
            conn.close()
            return {"success": False, "error": "验证码发送失败，请稍后重试"}

        masked = target[:3] + '***' + target[-4:] if auth_type == 'phone' else target[:2] + '***' + target.split('@')[0][-2:] + '@' + target.split('@')[1]

        conn.execute(
            "INSERT INTO verification_codes (target, code_hash, purpose, created_at, expires_at, attempts) VALUES (?, ?, ?, ?, ?, 0)",
            (target, hashlib.sha256(code.encode()).hexdigest(), purpose, now, expires_at)
        )
        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": "验证码已发送",
            "masked_target": masked,
            "expires_in": CODE_EXPIRE_SECONDS,
            "dev_code": code if cfg["provider"] == "none" else None,
        }
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def verify_code(target: str, code: str, purpose: str = "login") -> dict:
    target = target.strip()
    code = code.strip()

    if not target or not code:
        return {"success": False, "error": "请输入验证码"}

    conn = _get_conn()
    now = int(time.time())
    try:
        row = conn.execute(
            "SELECT * FROM verification_codes WHERE target = ? AND purpose = ? ORDER BY created_at DESC LIMIT 1",
            (target, purpose)
        ).fetchone()

        if not row:
            conn.close()
            return {"success": False, "error": "请先获取验证码"}

        if now > row["expires_at"]:
            conn.execute("DELETE FROM verification_codes WHERE id = ?", (row["id"],))
            conn.commit()
            conn.close()
            return {"success": False, "error": "验证码已过期，请重新获取"}

        if row["attempts"] >= MAX_CODE_ATTEMPTS:
            conn.execute("DELETE FROM verification_codes WHERE id = ?", (row["id"],))
            conn.commit()
            conn.close()
            return {"success": False, "error": "验证次数过多，请重新获取"}

        input_hash = hashlib.sha256(code.encode()).hexdigest()
        if input_hash != row["code_hash"]:
            conn.execute("UPDATE verification_codes SET attempts = attempts + 1 WHERE id = ?", (row["id"],))
            conn.commit()
            remaining = MAX_CODE_ATTEMPTS - row["attempts"] - 1
            conn.close()
            return {"success": False, "error": f"验证码错误，还可尝试 {remaining} 次"}

        conn.execute("DELETE FROM verification_codes WHERE id = ?", (row["id"],))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def cleanup_expired_codes():
    conn = _get_conn()
    now = int(time.time())
    try:
        conn.execute("DELETE FROM verification_codes WHERE expires_at < ?", (now,))
        conn.commit()
    finally:
        conn.close()


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_password(password: str, salt: str = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return f"{salt}${pwd_hash}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, pwd_hash = stored.split("$", 1)
        return _hash_password(password, salt) == stored
    except Exception:
        return False


def _detect_type(identifier: str) -> str:
    identifier = identifier.strip()
    if PHONE_RE.match(identifier):
        return 'phone'
    if EMAIL_RE.match(identifier):
        return 'email'
    return 'username'


DAILY_FREE_QUOTA = 10000


def _today_str():
    return datetime.now().strftime('%Y-%m-%d')


def check_quota(user_id=None, guest_id=None):
    conn = _get_conn()
    today = _today_str()
    try:
        if user_id:
            row = conn.execute(
                "SELECT daily_used FROM user_quotas WHERE target_type='user' AND target_id=? AND quota_date=?",
                (str(user_id), today)
            ).fetchone()
            used = row["daily_used"] if row else 0
        elif guest_id:
            row = conn.execute(
                "SELECT daily_used FROM user_quotas WHERE target_type='guest' AND target_id=? AND quota_date=?",
                (guest_id, today)
            ).fetchone()
            used = row["daily_used"] if row else 0
        else:
            conn.close()
            return {"ok": False, "error": "无法识别用户身份"}

        remaining = max(0, DAILY_FREE_QUOTA - used)
        conn.close()
        return {"ok": True, "used": used, "remaining": remaining, "limit": DAILY_FREE_QUOTA}
    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}


def consume_quota(user_id=None, guest_id=None):
    conn = _get_conn()
    today = _today_str()
    try:
        if user_id:
            target_type, target_id = 'user', str(user_id)
        elif guest_id:
            target_type, target_id = 'guest', guest_id
        else:
            conn.close()
            return {"ok": False, "error": "无法识别用户身份"}

        row = conn.execute(
            "SELECT daily_used FROM user_quotas WHERE target_type=? AND target_id=? AND quota_date=?",
            (target_type, target_id, today)
        ).fetchone()

        if row:
            used = row["daily_used"]
            if used >= DAILY_FREE_QUOTA:
                conn.close()
                return {"ok": False, "error": "今日免费次数已用完", "used": used, "remaining": 0, "limit": DAILY_FREE_QUOTA}
            used += 1
            conn.execute(
                "UPDATE user_quotas SET daily_used=? WHERE target_type=? AND target_id=? AND quota_date=?",
                (used, target_type, target_id, today)
            )
        else:
            used = 1
            conn.execute(
                "INSERT INTO user_quotas (target_type, target_id, quota_date, daily_used) VALUES (?, ?, ?, ?)",
                (target_type, target_id, today, 1)
            )

        conn.commit()
        remaining = max(0, DAILY_FREE_QUOTA - used)
        conn.close()
        return {"ok": True, "used": used, "remaining": remaining, "limit": DAILY_FREE_QUOTA}
    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT UNIQUE NOT NULL,
            auth_type TEXT NOT NULL DEFAULT 'username',
            nickname TEXT DEFAULT '',
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reset_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key_hash TEXT UNIQUE NOT NULL,
            key_display TEXT NOT NULL,
            name TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            daily_limit INTEGER DEFAULT 100,
            daily_used INTEGER DEFAULT 0,
            total_calls INTEGER DEFAULT 0,
            last_reset_date TEXT DEFAULT '',
            created_at INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            purpose TEXT NOT NULL DEFAULT 'login',
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_quotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            quota_date TEXT NOT NULL,
            daily_used INTEGER NOT NULL DEFAULT 0,
            UNIQUE(target_type, target_id, quota_date)
        )
    """)
    for col, default in [('nickname', "''"), ('auth_type', "'username'"), ('is_admin', '0')]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT {default}")
        except Exception:
            pass
    conn.commit()
    conn.close()


def register(identifier: str, password: str, nickname: str = '', code: str = None) -> dict:
    identifier = identifier.strip()
    if not identifier:
        return {"success": False, "error": "请输入手机号/邮箱/用户名"}

    auth_type = _detect_type(identifier)

    if auth_type == 'phone':
        if not code:
            return {"success": False, "error": "请输入短信验证码", "need_code": True, "auth_type": "phone"}
        v = verify_code(identifier, code, "register")
        if not v.get("success"):
            return {"success": False, "error": v.get("error", "验证码校验失败")}
    elif auth_type == 'email':
        if not code:
            return {"success": False, "error": "请输入邮箱验证码", "need_code": True, "auth_type": "email"}
        v = verify_code(identifier, code, "register")
        if not v.get("success"):
            return {"success": False, "error": v.get("error", "验证码校验失败")}
    else:
        if len(identifier) < 2:
            return {"success": False, "error": "用户名至少2个字符"}

    if not password or len(password) < 6:
        return {"success": False, "error": "密码至少6个字符"}

    conn = _get_conn()
    try:
        existing = conn.execute("SELECT id FROM users WHERE identifier = ?", (identifier,)).fetchone()
        if existing:
            return {"success": False, "error": "该账号已注册"}

        pwd_hash = _hash_password(password)
        now = int(time.time())
        nickname = nickname.strip() or (identifier if auth_type == 'username' else f'用户{identifier[-4:]}')
        is_admin = 1 if identifier == 'admin' else 0
        conn.execute(
            "INSERT INTO users (identifier, auth_type, nickname, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (identifier, auth_type, nickname, pwd_hash, is_admin, now)
        )
        conn.commit()
        user_id = conn.execute("SELECT id FROM users WHERE identifier = ?", (identifier,)).fetchone()["id"]
        token = _create_token(user_id, conn)
        conn.close()
        return {"success": True, "token": token, "user_id": user_id, "nickname": nickname, "auth_type": auth_type, "is_admin": is_admin}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def login(identifier: str, password: str, code: str = None) -> dict:
    identifier = identifier.strip()
    if not identifier:
        return {"success": False, "error": "请输入账号"}

    auth_type = _detect_type(identifier)

    if auth_type in ('phone', 'email') and code:
        v = verify_code(identifier, code, "login")
        if not v.get("success"):
            return {"success": False, "error": v.get("error", "验证码校验失败")}

    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE identifier = ?", (identifier,)).fetchone()
        if not row:
            return {"success": False, "error": "账号不存在"}
        if password and not _verify_password(password, row["password_hash"]):
            return {"success": False, "error": "密码错误"}
        token = _create_token(row["id"], conn)
        conn.close()
        nickname = row["nickname"] or identifier
        return {
            "success": True, "token": token, "user_id": row["id"],
            "nickname": nickname, "auth_type": row["auth_type"],
            "is_admin": bool(row["is_admin"])
        }
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def _create_token(user_id: int, conn: sqlite3.Connection) -> str:
    token = secrets.token_hex(32)
    now = int(time.time())
    conn.execute("INSERT INTO tokens (token, user_id, created_at) VALUES (?, ?, ?)", (token, user_id, now))
    conn.commit()
    return token


def verify_token(token: str) -> dict:
    if not token:
        return None
    conn = _get_conn()
    try:
        row = conn.execute("""
            SELECT users.id, users.identifier, users.auth_type, users.nickname, users.is_admin
            FROM tokens JOIN users ON users.id = tokens.user_id
            WHERE tokens.token = ?
        """, (token,)).fetchone()
        conn.close()
        if row:
            return {
                "user_id": row["id"],
                "identifier": row["identifier"],
                "auth_type": row["auth_type"],
                "nickname": row["nickname"] or row["identifier"],
                "is_admin": bool(row["is_admin"])
            }
        return None
    except Exception:
        conn.close()
        return None


def logout(token: str):
    if not token:
        return
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM tokens WHERE token = ?", (token,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def change_password(user_id: int, old_password: str, new_password: str) -> dict:
    if not new_password or len(new_password) < 6:
        return {"success": False, "error": "新密码至少6个字符"}

    conn = _get_conn()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return {"success": False, "error": "用户不存在"}
        if old_password and not _verify_password(old_password, row["password_hash"]):
            return {"success": False, "error": "原密码错误"}
        pwd_hash = _hash_password(new_password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pwd_hash, user_id))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def request_reset(identifier: str) -> dict:
    identifier = identifier.strip()
    if not identifier:
        return {"success": False, "error": "请输入手机号或邮箱"}

    auth_type = _detect_type(identifier)
    if auth_type not in ('phone', 'email'):
        return {"success": False, "error": "请输入注册时使用的手机号或邮箱"}

    conn = _get_conn()
    try:
        row = conn.execute("SELECT id, nickname FROM users WHERE identifier = ? AND auth_type = ?",
                           (identifier, auth_type)).fetchone()
        if not row:
            conn.close()
            return {"success": False, "error": "该账号不存在"}

        reset_token = secrets.token_hex(16)
        now = int(time.time())
        expires = now + 3600
        conn.execute("INSERT OR REPLACE INTO reset_tokens (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                     (reset_token, row["id"], now, expires))
        conn.commit()
        conn.close()

        masked = identifier[:3] + '***' + identifier[-4:]
        return {
            "success": True,
            "message": f"重置链接已生成（演示模式，不会真的发送）",
            "reset_token": reset_token,
            "masked_identifier": masked,
            "expires_in": 3600
        }
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def reset_password(reset_token: str, new_password: str) -> dict:
    if not new_password or len(new_password) < 6:
        return {"success": False, "error": "新密码至少6个字符"}

    conn = _get_conn()
    try:
        now = int(time.time())
        row = conn.execute("""
            SELECT user_id FROM reset_tokens
            WHERE token = ? AND expires_at > ?
        """, (reset_token, now)).fetchone()
        if not row:
            conn.close()
            return {"success": False, "error": "重置链接无效或已过期"}

        pwd_hash = _hash_password(new_password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pwd_hash, row["user_id"]))
        conn.execute("DELETE FROM reset_tokens WHERE token = ?", (reset_token,))
        conn.execute("DELETE FROM tokens WHERE user_id = ?", (row["user_id"],))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def list_users(admin_user_id: int) -> dict:
    conn = _get_conn()
    try:
        admin = conn.execute("SELECT is_admin FROM users WHERE id = ?", (admin_user_id,)).fetchone()
        if not admin or not admin["is_admin"]:
            conn.close()
            return {"success": False, "error": "无权限"}

        rows = conn.execute("""
            SELECT id, identifier, auth_type, nickname, is_admin, created_at
            FROM users ORDER BY created_at DESC
        """).fetchall()
        conn.close()

        users = []
        for r in rows:
            users.append({
                "id": r["id"],
                "identifier": r["identifier"],
                "auth_type": r["auth_type"],
                "nickname": r["nickname"],
                "is_admin": bool(r["is_admin"]),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["created_at"]))
            })
        return {"success": True, "users": users, "total": len(users)}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def set_admin(admin_user_id: int, target_user_id: int, is_admin: bool) -> dict:
    conn = _get_conn()
    try:
        admin = conn.execute("SELECT is_admin FROM users WHERE id = ?", (admin_user_id,)).fetchone()
        if not admin or not admin["is_admin"]:
            conn.close()
            return {"success": False, "error": "无权限"}
        conn.execute("UPDATE users SET is_admin = ? WHERE id = ?", (1 if is_admin else 0, target_user_id))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def delete_user(admin_user_id: int, target_user_id: int) -> dict:
    if admin_user_id == target_user_id:
        return {"success": False, "error": "不能删除自己"}
    conn = _get_conn()
    try:
        admin = conn.execute("SELECT is_admin FROM users WHERE id = ?", (admin_user_id,)).fetchone()
        if not admin or not admin["is_admin"]:
            conn.close()
            return {"success": False, "error": "无权限"}
        conn.execute("DELETE FROM tokens WHERE user_id = ?", (target_user_id,))
        conn.execute("DELETE FROM reset_tokens WHERE user_id = ?", (target_user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (target_user_id,))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def init_first_admin(admin_identifier: str = 'admin', admin_password: str = 'admin123') -> dict:
    conn = _get_conn()
    try:
        existing = conn.execute("SELECT id FROM users WHERE identifier = ?", (admin_identifier,)).fetchone()
        if existing:
            conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (existing["id"],))
            conn.commit()
            conn.close()
            return {"success": True, "message": "已设为管理员"}
        pwd_hash = _hash_password(admin_password)
        now = int(time.time())
        conn.execute(
            "INSERT INTO users (identifier, auth_type, nickname, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (admin_identifier, 'username', '系统管理员', pwd_hash, now)
        )
        conn.commit()
        conn.close()
        return {"success": True, "identifier": admin_identifier, "password": admin_password}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def _generate_api_key() -> tuple:
    import secrets, hashlib
    raw = "sk-yunjing-" + secrets.token_urlsafe(24)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    display = raw[:12] + "..." + raw[-6:]
    return raw, key_hash, display


def create_api_key(user_id: int, name: str = '', daily_limit: int = 100) -> dict:
    conn = _get_conn()
    try:
        raw, key_hash, display = _generate_api_key()
        now = int(time.time())
        today = datetime.now().strftime('%Y-%m-%d')
        conn.execute(
            "INSERT INTO api_keys (user_id, key_hash, key_display, name, status, daily_limit, daily_used, total_calls, last_reset_date, created_at) VALUES (?, ?, ?, ?, 'active', ?, 0, 0, ?, ?)",
            (user_id, key_hash, display, name or '默认密钥', daily_limit, today, now)
        )
        conn.commit()
        conn.close()
        return {"success": True, "key": raw, "display": display}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def list_api_keys(user_id: int = None, admin_view: bool = False) -> list:
    conn = _get_conn()
    try:
        if admin_view:
            rows = conn.execute("SELECT * FROM api_keys ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM api_keys WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
        result = []
        for r in rows:
            result.append({
                'id': r['id'],
                'user_id': r['user_id'],
                'key_display': r['key_display'],
                'name': r['name'],
                'status': r['status'],
                'daily_limit': r['daily_limit'],
                'daily_used': r['daily_used'],
                'total_calls': r['total_calls'],
                'created_at': r['created_at']
            })
        conn.close()
        return result
    except Exception:
        conn.close()
        return []


def _maybe_reset_daily(conn, row):
    today = datetime.now().strftime('%Y-%m-%d')
    if row['last_reset_date'] != today:
        conn.execute("UPDATE api_keys SET daily_used = 0, last_reset_date = ? WHERE id = ?", (today, row['id']))
        return 0
    return row['daily_used']


def verify_api_key(raw_key: str) -> dict:
    import hashlib
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM api_keys WHERE key_hash = ?", (key_hash,)).fetchone()
        if not row:
            conn.close()
            return {"success": False, "error": "密钥不存在"}
        if row['status'] != 'active':
            conn.close()
            return {"success": False, "error": "密钥已停用"}

        daily_used = _maybe_reset_daily(conn, row)
        row2 = conn.execute("SELECT * FROM api_keys WHERE key_hash = ?", (key_hash,)).fetchone()
        daily_used = row2['daily_used']
        if daily_used >= row2['daily_limit']:
            conn.close()
            return {"success": False, "error": "今日额度已用完", "limit": row2['daily_limit']}

        conn.execute(
            "UPDATE api_keys SET daily_used = daily_used + 1, total_calls = total_calls + 1 WHERE key_hash = ?",
            (key_hash,)
        )
        conn.commit()
        conn.close()
        return {"success": True, "user_id": row2['user_id'], "key_id": row2['id'],
                "remaining": row2['daily_limit'] - daily_used - 1}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def delete_api_key(user_id: int, key_id: int, admin_user_id: int = None) -> dict:
    conn = _get_conn()
    try:
        if admin_user_id:
            conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        else:
            conn.execute("DELETE FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user_id))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def toggle_api_key(admin_user_id: int, key_id: int, status: str) -> dict:
    conn = _get_conn()
    try:
        conn.execute("UPDATE api_keys SET status = ? WHERE id = ?", (status, key_id))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


def set_api_key_limit(admin_user_id: int, key_id: int, daily_limit: int) -> dict:
    conn = _get_conn()
    try:
        conn.execute("UPDATE api_keys SET daily_limit = ? WHERE id = ?", (daily_limit, key_id))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}


init_db()