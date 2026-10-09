import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify

from config import IMAGE_KEYWORDS
from core.users import verify_token, verify_api_key, check_quota, consume_quota
from core.storage import (
    load_conversations_from_file,
    save_conversations_to_file,
    update_current_conversation,
    trim_history,
)

chat_bp = Blueprint('chat', __name__)

_bot_ref = None
_user_conv_cache = {}


def set_bot(bot):
    global _bot_ref
    _bot_ref = bot


def _get_identity():
    api_key = request.headers.get('X-API-Key', '')
    if api_key and api_key.startswith('sk-yunjing-'):
        result = verify_api_key(api_key)
        if result.get('success'):
            return result['user_id'], 'api_' + str(result['key_id'])
        print(f"  [API Key] 验证失败: {result.get('error')}")
        return None, None

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = verify_token(token)
    user_id = user['user_id'] if user else None
    guest_id = None
    if not user_id:
        guest_id = request.headers.get('X-Device-ID', '').strip() or None
    return user_id, guest_id


def _ensure_conversation(user_id, guest_id):
    cache_key = str(user_id) if user_id else ("guest_" + guest_id if guest_id else "anon")
    if cache_key not in _user_conv_cache:
        conv_id = str(uuid.uuid4())
        _user_conv_cache[cache_key] = {
            'id': conv_id,
            'history': []
        }
        conversations = load_conversations_from_file(user_id, guest_id)
        new_conv = {
            'id': conv_id,
            'title': '新对话',
            'timestamp': datetime.now().isoformat(),
            'messages': []
        }
        conversations.insert(0, new_conv)
        save_conversations_to_file(conversations, user_id, guest_id)
    return _user_conv_cache[cache_key]


def _is_image_request(text: str) -> bool:
    t = text.lower().strip()
    return any(kw in t for kw in IMAGE_KEYWORDS)


@chat_bp.route('/api/chat', methods=['POST'])
def chat():
    if not _bot_ref:
        return jsonify({'success': False, 'error': 'Bot not initialized'}), 400

    data = request.json
    question = data.get('question', '')
    force_search = data.get('force_search', False)
    user_api_key = (data.get('user_api_key') or '').strip() or None
    user_provider = (data.get('user_provider') or '').strip() or None
    user_model = (data.get('user_model') or '').strip() or None
    reference_image = (data.get('reference_image') or '').strip() or None

    if not question:
        return jsonify({'success': False, 'error': '问题不能为空'}), 400

    user_id, guest_id = _get_identity()

    is_api_key_call = (guest_id and str(guest_id).startswith('api_'))
    if not is_api_key_call:
        if user_id:
            if not user_api_key:
                quota = consume_quota(user_id=user_id)
                if not quota.get('ok'):
                    return jsonify({
                        'success': False,
                        'error': quota.get('error', '免费额度已用完'),
                        'quota_exhausted': True,
                        'limit': quota.get('limit')
                    }), 429
        else:
            if not guest_id:
                guest_id = request.headers.get('X-Device-ID', '').strip() or None
            if guest_id:
                quota = consume_quota(guest_id=guest_id)
                if not quota.get('ok'):
                    return jsonify({
                        'success': False,
                        'error': quota.get('error', '免费额度已用完，请注册登录'),
                        'quota_exhausted': True,
                        'limit': quota.get('limit')
                    }), 429
            else:
                return jsonify({
                    'success': False,
                    'error': '请启用浏览器 Cookie 或登录后使用'
                }), 429
    conv = _ensure_conversation(user_id, guest_id)

    if _is_image_request(question):
        try:
            size = "1024x1024"
            result = _bot_ref.generate_image(question, size,
                user_api_key=user_api_key, user_provider=user_provider,
                reference_image=reference_image)
            if result.get("success") and result.get("image_data"):
                b64 = result["image_data"]
                mime = "image/png"
                if b64[:3] == "/9j":
                    mime = "image/jpeg"
                elif b64[:3] == "iVB":
                    mime = "image/png"
                img_tag = f'<img src="data:{mime};base64,{b64}" style="max-width:100%;border-radius:8px;margin:8px 0;">'
                caption = result.get("revised_prompt", "") or question
                answer = f"已为你生成图片：\n\n{img_tag}\n\n**提示词**: {caption}"

                conv['history'].append({"role": "user", "content": f"🎨 生成图片: {question}"})
                conv['history'].append({"role": "assistant", "content": answer})
                title = question[:20] + '...' if len(question) > 20 else question
                update_current_conversation(conv['id'], conv['history'], title, user_id, guest_id)

                return jsonify({'success': True, 'answer': answer})
            else:
                err = result.get('error', '图片生成失败')
                answer = f'抱歉，图片生成失败了：{err}\n\n我可以继续帮你解答其他问题。'
                conv['history'].append({"role": "user", "content": f"🎨 生成图片: {question}"})
                conv['history'].append({"role": "assistant", "content": answer})
                title = question[:20] + '...' if len(question) > 20 else question
                update_current_conversation(conv['id'], conv['history'], title, user_id, guest_id)
                return jsonify({'success': True, 'answer': answer})
        except Exception as e:
            answer = f'图片生成出错：{e}'
            conv['history'].append({"role": "user", "content": f"🎨 生成图片: {question}"})
            conv['history'].append({"role": "assistant", "content": answer})
            title = question[:20] + '...' if len(question) > 20 else question
            update_current_conversation(conv['id'], conv['history'], title, user_id, guest_id)
            return jsonify({'success': True, 'answer': answer})

    try:
        _bot_ref.conversation_history = list(conv['history'])
        response = _bot_ref.ask(question, force_search=force_search,
            user_api_key=user_api_key, user_provider=user_provider, user_model=user_model)
        conv['history'] = list(_bot_ref.conversation_history)
        conv['history'] = trim_history(conv['history'])

        title = None
        if len(conv['history']) <= 2:
            title = question[:20] + '...' if len(question) > 20 else question

        update_current_conversation(conv['id'], conv['history'], title, user_id, guest_id)

        return jsonify({'success': True, 'answer': response})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@chat_bp.route('/api/quota', methods=['GET'])
def get_quota():
    user_id, guest_id = _get_identity()
    if user_id:
        result = check_quota(user_id=user_id)
        return jsonify({'success': True, 'quota': result, 'need_own_key': True})
    if not guest_id:
        guest_id = request.headers.get('X-Device-ID', '').strip() or None
    if guest_id:
        result = check_quota(guest_id=guest_id)
        return jsonify({'success': True, 'quota': result, 'is_guest': True})
    return jsonify({'success': True, 'quota': None, 'is_guest': True})


@chat_bp.route('/api/clear', methods=['POST'])
def clear_history():
    user_id, guest_id = _get_identity()
    cache_key = str(user_id) if user_id else ("guest_" + guest_id if guest_id else "anon")
    if cache_key in _user_conv_cache:
        del _user_conv_cache[cache_key]
    save_conversations_to_file([], user_id, guest_id)
    return jsonify({'success': True})


@chat_bp.route('/api/toggle_search', methods=['POST'])
def toggle_search():
    if not _bot_ref:
        return jsonify({
            'success': False,
            'error': '请先配置API Key'
        }), 400
    from core.search import WebSearcher
    _bot_ref.enable_search = not _bot_ref.enable_search
    if _bot_ref.enable_search and not _bot_ref.searcher:
        _bot_ref.searcher = WebSearcher()
    return jsonify({
        'success': True,
        'enabled': _bot_ref.enable_search,
        'message': f'网络搜索已{"启用" if _bot_ref.enable_search else "关闭"}'
    })


@chat_bp.route('/api/history', methods=['GET'])
def get_history():
    user_id = _get_user_id()
    cache_key = user_id or "anon"
    if cache_key in _user_conv_cache:
        return jsonify({'history': _user_conv_cache[cache_key]['history']})
    return jsonify({'history': []})


@chat_bp.route('/api/generate_file', methods=['POST'])
def generate_file():
    if not _bot_ref:
        return jsonify({'success': False, 'error': 'Bot not initialized'}), 400

    data = request.json
    prompt = data.get('prompt', '')
    file_type = data.get('file_type', 'txt')

    if not prompt:
        return jsonify({'success': False, 'error': '提示词不能为空'}), 400

    try:
        result = _bot_ref.generate_file(prompt, file_type)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500