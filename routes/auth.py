from flask import Blueprint, request, jsonify, render_template_string
import traceback

from core.users import (
    register, login, verify_token, logout,
    change_password, request_reset, reset_password,
    list_users, set_admin, delete_user, init_first_admin,
    create_api_key, list_api_keys, verify_api_key,
    delete_api_key, toggle_api_key, set_api_key_limit,
    send_code, verify_code
)

auth_bp = Blueprint('auth', __name__)


def _get_user():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    return verify_token(token)


@auth_bp.route('/api/send_code', methods=['POST'])
def api_send_code():
    data = request.json or {}
    target = data.get('target', '')
    purpose = data.get('purpose', 'login')
    result = send_code(target, purpose)
    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 400


@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    data = request.json or {}
    identifier = data.get('identifier', '')
    password = data.get('password', '')
    nickname = data.get('nickname', '')
    code = data.get('code', '') or None
    result = register(identifier, password, nickname, code)
    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 400


@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    data = request.json or {}
    identifier = data.get('identifier', '')
    password = data.get('password', '')
    code = data.get('code', '') or None
    result = login(identifier, password, code)
    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 401


@auth_bp.route('/api/me', methods=['GET'])
def api_me():
    user = _get_user()
    if user:
        return jsonify({'success': True, 'user': user})
    return jsonify({'success': False}), 401


@auth_bp.route('/api/logout', methods=['POST'])
def api_logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    logout(token)
    return jsonify({'success': True})


@auth_bp.route('/api/change_password', methods=['POST'])
def api_change_password():
    user = _get_user()
    if not user:
        return jsonify({'success': False, 'error': '未登录'}), 401
    data = request.json or {}
    old_pwd = data.get('old_password', '')
    new_pwd = data.get('new_password', '')
    result = change_password(user['user_id'], old_pwd, new_pwd)
    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 400


@auth_bp.route('/api/reset_request', methods=['POST'])
def api_reset_request():
    data = request.json or {}
    identifier = data.get('identifier', '')
    result = request_reset(identifier)
    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 400


@auth_bp.route('/api/reset_password', methods=['POST'])
def api_reset_password():
    data = request.json or {}
    reset_token = data.get('reset_token', '')
    new_password = data.get('new_password', '')
    result = reset_password(reset_token, new_password)
    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 400


@auth_bp.route('/api/admin/users', methods=['GET'])
def api_admin_users():
    user = _get_user()
    if not user or not user.get('is_admin'):
        return jsonify({'success': False, 'error': '需要管理员权限'}), 403
    result = list_users(user['user_id'])
    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 400


@auth_bp.route('/api/admin/users/<int:target_id>/set_admin', methods=['POST'])
def api_admin_set(target_id):
    user = _get_user()
    if not user or not user.get('is_admin'):
        return jsonify({'success': False, 'error': '需要管理员权限'}), 403
    data = request.json or {}
    is_admin = data.get('is_admin', True)
    result = set_admin(user['user_id'], target_id, is_admin)
    return jsonify(result)


@auth_bp.route('/api/admin/users/<int:target_id>', methods=['DELETE'])
def api_admin_delete(target_id):
    user = _get_user()
    if not user or not user.get('is_admin'):
        return jsonify({'success': False, 'error': '需要管理员权限'}), 403
    result = delete_user(user['user_id'], target_id)
    return jsonify(result)


@auth_bp.route('/api/admin/init', methods=['POST'])
def api_admin_init():
    data = request.json or {}
    identifier = data.get('identifier', 'admin')
    password = data.get('password', 'admin123')
    result = init_first_admin(identifier, password)
    return jsonify(result)


@auth_bp.route('/api/apikeys', methods=['GET'])
def api_get_my_keys():
    user = _get_user()
    if not user:
        return jsonify({"success": False, "error": "未登录"}), 401
    keys = list_api_keys(user_id=user['user_id'], admin_view=False)
    return jsonify({"success": True, "keys": keys})


@auth_bp.route('/api/apikeys', methods=['POST'])
def api_create_key():
    user = _get_user()
    if not user:
        return jsonify({"success": False, "error": "未登录"}), 401
    data = request.json or {}
    name = data.get('name', '')
    limit = int(data.get('daily_limit', 100))
    if limit < 1:
        limit = 1
    if limit > 10000:
        limit = 10000
    result = create_api_key(user['user_id'], name, limit)
    return jsonify(result)


@auth_bp.route('/api/apikeys/<int:key_id>', methods=['DELETE'])
def api_delete_key(key_id):
    user = _get_user()
    if not user:
        return jsonify({"success": False, "error": "未登录"}), 401
    result = delete_api_key(user['user_id'], key_id, admin_user_id=None)
    return jsonify(result)


@auth_bp.route('/api/admin/apikeys', methods=['GET'])
def api_admin_all_keys():
    user = _get_user()
    if not user or not user.get('is_admin'):
        return jsonify({"success": False, "error": "仅管理员可访问"}), 403
    keys = list_api_keys(admin_view=True)
    return jsonify({"success": True, "keys": keys})


@auth_bp.route('/api/admin/apikeys/<int:key_id>/toggle', methods=['POST'])
def api_admin_toggle_key(key_id):
    user = _get_user()
    if not user or not user.get('is_admin'):
        return jsonify({"success": False, "error": "仅管理员可访问"}), 403
    data = request.json or {}
    status = data.get('status', 'suspended')
    result = toggle_api_key(user['user_id'], key_id, status)
    return jsonify(result)


@auth_bp.route('/api/admin/apikeys/<int:key_id>/limit', methods=['POST'])
def api_admin_set_limit(key_id):
    user = _get_user()
    if not user or not user.get('is_admin'):
        return jsonify({"success": False, "error": "仅管理员可访问"}), 403
    data = request.json or {}
    limit = int(data.get('daily_limit', 100))
    result = set_api_key_limit(user['user_id'], key_id, limit)
    return jsonify(result)


@auth_bp.route('/api/admin/apikeys/<int:key_id>', methods=['DELETE'])
def api_admin_delete_key(key_id):
    user = _get_user()
    if not user or not user.get('is_admin'):
        return jsonify({"success": False, "error": "仅管理员可访问"}), 403
    result = delete_api_key(user['user_id'], key_id, admin_user_id=user['user_id'])
    return jsonify(result)


ADMIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>云镜 - 管理后台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f7fa;color:#333}
.header{background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}
.header h1{font-size:20px;font-weight:600}
.header .user-info{font-size:14px}
.container{max-width:1100px;margin:24px auto;padding:0 24px}
.card{background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);padding:24px;margin-bottom:24px}
.card h2{font-size:17px;margin-bottom:16px;color:#111}
.btn{padding:8px 16px;border:none;border-radius:6px;cursor:pointer;font-size:14px;font-weight:500;transition:all 0.2s}
.btn-primary{background:#2563eb;color:#fff}
.btn-primary:hover{background:#1d4ed8}
.btn-danger{background:#dc2626;color:#fff}
.btn-danger:hover{background:#b91c1c}
.btn-secondary{background:#e5e7eb;color:#374151}
.btn-secondary:hover{background:#d1d5db}
.btn-sm{padding:4px 10px;font-size:12px}
table{width:100%;border-collapse:collapse}
th,td{padding:12px;text-align:left;border-bottom:1px solid #f0f0f0}
th{font-weight:600;color:#6b7280;font-size:13px;background:#fafafa}
tr:hover{background:#f9fafb}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px}
.badge-admin{background:#fef3c7;color:#92400e}
.badge-user{background:#dbeafe;color:#1e40af}
.badge-phone{background:#dcfce7;color:#166534}
.badge-email{background:#fce7f3;color:#9d174d}
.badge-username{background:#e0e7ff;color:#3730a3}
.empty{text-align:center;padding:40px;color:#9ca3af}
.mask{font-family:monospace}
input[type="text"],input[type="password"]{width:100%;padding:10px;border:1px solid #e5e7eb;border-radius:6px;font-size:14px;margin-bottom:10px}
.form-row{display:flex;gap:12px;align-items:flex-end}
.form-row > div{flex:1}
.alert{padding:12px;border-radius:8px;margin-bottom:12px;font-size:14px}
.alert-error{background:#fef2f2;color:#dc2626;border:1px solid #fecaca}
.alert-success{background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0}
</style>
</head>
<body>

<div class="header">
    <h1>🛡️ 云镜管理后台</h1>
    <div class="user-info" id="headerUser">加载中...</div>
</div>

<div class="container">

    <div id="loginCard" class="card">
        <h2>管理员登录</h2>
        <div id="loginAlert"></div>
        <input type="text" id="loginIdentifier" placeholder="管理员账号">
        <input type="password" id="loginPassword" placeholder="密码">
        <button class="btn btn-primary" onclick="adminLogin()">登录</button>
        <button class="btn btn-secondary" onclick="initAdmin()" style="margin-left:10px;">初始化默认管理员</button>
        <p style="margin-top:12px;color:#9ca3af;font-size:12px;">
            💡 默认管理员：admin / admin123（点"初始化"创建）
        </p>
    </div>

    <div id="adminPanel" style="display:none">

        <div class="card">
            <h2>用户列表 <span id="userCount" style="color:#9ca3af;font-weight:400;font-size:14px"></span></h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>账号</th>
                        <th>类型</th>
                        <th>昵称</th>
                        <th>角色</th>
                        <th>注册时间</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="userTableBody"></tbody>
            </table>
        </div>

        <div class="card">
            <h2>修改我的密码</h2>
            <div id="pwdAlert"></div>
            <input type="password" id="oldPwd" placeholder="当前密码">
            <input type="password" id="newPwd" placeholder="新密码（至少6位）">
            <button class="btn btn-primary" onclick="changeMyPwd()">修改密码</button>
        </div>

        <div class="card">
            <h2>🔑 API Key 管理 <span id="apiKeyCount" style="color:#9ca3af;font-weight:400;font-size:14px"></span></h2>
            <p style="color:#6b7280;font-size:13px;margin-bottom:16px;">
                用户可登录后在"我的密钥"里申请专属 Key，用 <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;">X-API-Key</code> header 调用 <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;">/api/chat</code> 接口
            </p>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>用户ID</th>
                        <th>密钥（脱敏）</th>
                        <th>名称</th>
                        <th>状态</th>
                        <th>今日额度</th>
                        <th>总调用</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="apiKeyTableBody"></tbody>
            </table>
        </div>

    </div>
</div>

<script>
const API_BASE = window.location.origin;
let authToken = localStorage.getItem('authToken') || '';

async function api(url, options = {}) {
    options.headers = options.headers || {};
    options.headers['Content-Type'] = 'application/json';
    if (authToken) options.headers['Authorization'] = 'Bearer ' + authToken;
    const resp = await fetch(API_BASE + url, options);
    return resp.json();
}

async function adminLogin() {
    const identifier = document.getElementById('loginIdentifier').value;
    const password = document.getElementById('loginPassword').value;
    const alert = document.getElementById('loginAlert');
    alert.innerHTML = '';
    const data = await api('/api/login', {method:'POST', body: JSON.stringify({identifier, password})});
    if (data.success && data.is_admin) {
        authToken = data.token;
        localStorage.setItem('authToken', authToken);
        localStorage.setItem('authUser', JSON.stringify({user_id:data.user_id, nickname:data.nickname, is_admin:true}));
        showPanel();
    } else {
        alert.className = 'alert alert-error';
        alert.textContent = data.is_admin ? (data.error || '登录失败') : '该账号不是管理员';
    }
}

async function initAdmin() {
    const data = await api('/api/admin/init', {method:'POST'});
    const alert = document.getElementById('loginAlert');
    alert.className = data.success ? 'alert alert-success' : 'alert alert-error';
    alert.textContent = data.success
        ? ('管理员已创建！账号：' + (data.identifier || 'admin') + ' 密码：' + (data.password || 'admin123'))
        : data.error;
}

async function showPanel() {
    const user = JSON.parse(localStorage.getItem('authUser') || 'null');
    const me = await api('/api/me');
    if (!me.success || !me.user.is_admin) {
        document.getElementById('loginCard').style.display = 'block';
        document.getElementById('adminPanel').style.display = 'none';
        return;
    }
    document.getElementById('loginCard').style.display = 'none';
    document.getElementById('adminPanel').style.display = 'block';
    document.getElementById('headerUser').innerHTML = me.user.nickname + '（管理员） <button class="btn btn-secondary btn-sm" onclick="logout()" style="margin-left:10px">退出</button>';
    await loadUsers();
    await loadApiKeys();
}

function logout() {
    localStorage.removeItem('authToken');
    localStorage.removeItem('authUser');
    authToken = '';
    document.getElementById('loginCard').style.display = 'block';
    document.getElementById('adminPanel').style.display = 'none';
}

async function loadUsers() {
    const data = await api('/api/admin/users');
    const tbody = document.getElementById('userTableBody');
    if (!data.success) { tbody.innerHTML = '<tr><td colspan="7" class="empty">' + data.error + '</td></tr>'; return; }
    document.getElementById('userCount').textContent = '共 ' + data.total + ' 人';
    const typeBadge = {phone:'badge-phone', email:'badge-email', username:'badge-username'};
    const typeText = {phone:'📱 手机', email:'📧 邮箱', username:'👤 用户名'};
    tbody.innerHTML = data.users.map(u => `
        <tr>
            <td>${u.id}</td>
            <td class="mask">${u.identifier}</td>
            <td><span class="badge ${typeBadge[u.auth_type]}">${typeText[u.auth_type] || u.auth_type}</span></td>
            <td>${u.nickname || '-'}</td>
            <td>${u.is_admin ? '<span class="badge badge-admin">🛡️ 管理员</span>' : '<span class="badge badge-user">👤 用户</span>'}</td>
            <td>${u.created_at}</td>
            <td>
                ${u.is_admin ? '' : `<button class="btn btn-secondary btn-sm" onclick="toggleAdmin(${u.id})">设为管理员</button>`}
                ${!u.is_admin ? `<button class="btn btn-danger btn-sm" onclick="delUser(${u.id})" style="margin-left:6px">删除</button>` : ''}
            </td>
        </tr>
    `).join('');
}

async function toggleAdmin(id) {
    if (!confirm('确定将该用户设为管理员？')) return;
    const data = await api('/api/admin/users/' + id + '/set_admin', {method:'POST', body: JSON.stringify({is_admin:true})});
    if (data.success) await loadUsers();
    else alert(data.error);
}

async function delUser(id) {
    if (!confirm('确定删除该用户？此操作不可恢复！')) return;
    const data = await api('/api/admin/users/' + id, {method:'DELETE'});
    if (data.success) await loadUsers();
    else alert(data.error);
}

async function changeMyPwd() {
    const oldPwd = document.getElementById('oldPwd').value;
    const newPwd = document.getElementById('newPwd').value;
    const alert = document.getElementById('pwdAlert');
    alert.innerHTML = '';
    const data = await api('/api/change_password', {method:'POST', body: JSON.stringify({old_password:oldPwd, new_password:newPwd})});
    alert.className = data.success ? 'alert alert-success' : 'alert alert-error';
    alert.textContent = data.success ? '密码修改成功！' : data.error;
    if (data.success) { document.getElementById('oldPwd').value = ''; document.getElementById('newPwd').value = ''; }
}

async function loadApiKeys() {
    const data = await api('/api/admin/apikeys');
    const tbody = document.getElementById('apiKeyTableBody');
    if (!data.success) { tbody.innerHTML = '<tr><td colspan="8" class="empty">' + data.error + '</td></tr>'; return; }
    document.getElementById('apiKeyCount').textContent = '共 ' + data.keys.length + ' 个';
    tbody.innerHTML = data.keys.map(k => {
        const used = k.daily_used;
        const limit = k.daily_limit;
        const pct = Math.min(100, Math.round(used / limit * 100));
        const statusBadge = k.status === 'active'
            ? '<span class="badge badge-admin">✅ 活跃</span>'
            : '<span style="background:#fef2f2;color:#dc2626;padding:3px 8px;border-radius:4px;font-size:12px">🚫 已停用</span>';
        const statusToggle = k.status === 'active'
            ? `<button class="btn btn-secondary btn-sm" onclick="toggleKey(${k.id}, 'suspended')">停用</button>`
            : `<button class="btn btn-secondary btn-sm" onclick="toggleKey(${k.id}, 'active')">启用</button>`;
        return `<tr>
            <td>${k.id}</td>
            <td>${k.user_id}</td>
            <td class="mask" style="font-family:monospace;font-size:12px">${k.key_display}</td>
            <td>${k.name || '-'}</td>
            <td>${statusBadge}</td>
            <td>
                <div style="background:#e5e7eb;border-radius:4px;height:8px;width:100%;margin-bottom:4px">
                    <div style="background:${pct > 80 ? '#ef4444' : pct > 50 ? '#f59e0b' : '#10b981'};height:100%;border-radius:4px;width:${pct}%"></div>
                </div>
                ${used}/${limit}
            </td>
            <td>${k.total_calls}</td>
            <td>
                ${statusToggle}
                <button class="btn btn-secondary btn-sm" onclick="setLimit(${k.id}, ${k.daily_limit})" style="margin-left:4px">调额度</button>
                <button class="btn btn-danger btn-sm" onclick="delKey(${k.id})" style="margin-left:4px">删除</button>
            </td>
        </tr>`;
    }).join('') || '<tr><td colspan="8" class="empty">暂无 API Key</td></tr>';
}

async function toggleKey(id, status) {
    const data = await api('/api/admin/apikeys/' + id + '/toggle', {method:'POST', body: JSON.stringify({status})});
    if (data.success) await loadApiKeys();
    else alert(data.error);
}

async function setLimit(id, current) {
    const val = prompt('设置每日额度上限（1-10000）：', current);
    if (!val) return;
    const n = parseInt(val);
    if (isNaN(n) || n < 1) { alert('请输入有效数字'); return; }
    const data = await api('/api/admin/apikeys/' + id + '/limit', {method:'POST', body: JSON.stringify({daily_limit: n})});
    if (data.success) await loadApiKeys();
    else alert(data.error);
}

async function delKey(id) {
    if (!confirm('确定删除该 API Key？删除后无法恢复！')) return;
    const data = await api('/api/admin/apikeys/' + id, {method:'DELETE'});
    if (data.success) await loadApiKeys();
    else alert(data.error);
}

showPanel();
</script>
</body>
</html>
"""


@auth_bp.route('/admin')
def admin_page():
    return render_template_string(ADMIN_HTML)