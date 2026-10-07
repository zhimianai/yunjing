import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify

from config import IMAGE_KEYWORDS
from core.storage import (
    load_conversations_from_file,
    save_conversations_to_file,
    update_current_conversation,
    trim_history,
)

chat_bp = Blueprint('chat', __name__)

_bot_ref = None


def set_bot(bot):
    global _bot_ref
    _bot_ref = bot


def _ensure_conversation():
    if not _bot_ref.current_conversation_id:
        conv_id = str(uuid.uuid4())
        _bot_ref.current_conversation_id = conv_id
        _bot_ref.conversation_history = []

        conversations = load_conversations_from_file()
        new_conv = {
            'id': conv_id,
            'title': '新对话',
            'timestamp': datetime.now().isoformat(),
            'messages': []
        }
        conversations.insert(0, new_conv)
        save_conversations_to_file(conversations)


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

    if not question:
        return jsonify({'success': False, 'error': '问题不能为空'}), 400

    _ensure_conversation()

    if _is_image_request(question):
        try:
            size = "1024x1024"
            result = _bot_ref.generate_image(question, size)
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

                _bot_ref.conversation_history.append({"role": "user", "content": f"🎨 生成图片: {question}"})
                _bot_ref.conversation_history.append({"role": "assistant", "content": answer})
                title = question[:20] + '...' if len(question) > 20 else question
                update_current_conversation(_bot_ref.current_conversation_id, _bot_ref.conversation_history, title)

                return jsonify({'success': True, 'answer': answer})
            else:
                err = result.get('error', '图片生成失败')
                answer = f'抱歉，图片生成失败了：{err}\n\n我可以继续帮你解答其他问题。'
                _bot_ref.conversation_history.append({"role": "user", "content": f"🎨 生成图片: {question}"})
                _bot_ref.conversation_history.append({"role": "assistant", "content": answer})
                title = question[:20] + '...' if len(question) > 20 else question
                update_current_conversation(_bot_ref.current_conversation_id, _bot_ref.conversation_history, title)
                return jsonify({'success': True, 'answer': answer})
        except Exception as e:
            answer = f'图片生成出错：{e}'
            _bot_ref.conversation_history.append({"role": "user", "content": f"🎨 生成图片: {question}"})
            _bot_ref.conversation_history.append({"role": "assistant", "content": answer})
            title = question[:20] + '...' if len(question) > 20 else question
            update_current_conversation(_bot_ref.current_conversation_id, _bot_ref.conversation_history, title)
            return jsonify({'success': True, 'answer': answer})

    try:
        response = _bot_ref.ask(question, force_search=force_search)
        _bot_ref.conversation_history = trim_history(_bot_ref.conversation_history)

        title = None
        if len(_bot_ref.conversation_history) <= 2:
            title = question[:20] + '...' if len(question) > 20 else question

        update_current_conversation(
            _bot_ref.current_conversation_id,
            _bot_ref.conversation_history,
            title
        )

        return jsonify({'success': True, 'answer': response})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@chat_bp.route('/api/clear', methods=['POST'])
def clear_history():
    if _bot_ref:
        _bot_ref.clear_history()
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
    if _bot_ref:
        return jsonify({'history': _bot_ref.get_history()})
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