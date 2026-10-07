import os
import base64
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify

from config import BASE_DIR
from core.storage import (
    load_conversations_from_file,
    save_conversations_to_file,
    update_current_conversation,
    trim_history,
)
from core.file_parser import extract_text
from core.image_utils import compress_image
from core.face_recognizer import recognize_image_bytes, is_available, get_class_names

media_bp = Blueprint('media', __name__)
files_bp = Blueprint('files', __name__)

_media_bot_ref = None
_files_bot_ref = None


def set_bot(bot):
    global _media_bot_ref, _files_bot_ref
    _media_bot_ref = bot
    _files_bot_ref = bot


def _ensure_conversation_for(bot_ref):
    if not bot_ref.current_conversation_id:
        conv_id = str(uuid.uuid4())
        bot_ref.current_conversation_id = conv_id
        bot_ref.conversation_history = []

        conversations = load_conversations_from_file()
        new_conv = {
            'id': conv_id,
            'title': '新对话',
            'timestamp': datetime.now().isoformat(),
            'messages': []
        }
        conversations.insert(0, new_conv)
        save_conversations_to_file(conversations)


@media_bp.route('/api/recognize_image', methods=['POST'])
def recognize_image():
    if not _media_bot_ref:
        return jsonify({'success': False, 'error': 'Bot not initialized'}), 400

    _ensure_conversation_for(_media_bot_ref)

    if 'image' not in request.files:
        return jsonify({'success': False, 'error': '未上传图片'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': '未选择图片'}), 400

    prompt = request.form.get('prompt', '请描述这张图片的内容')

    try:
        raw = file.read()
        if len(raw) == 0:
            return jsonify({'success': False, 'error': '图片内容为空'}), 400

        MAX_IMAGE = 12 * 1024 * 1024
        if len(raw) > MAX_IMAGE:
            return jsonify({
                'success': False,
                'error': f'图片过大（{len(raw)//1024//1024}MB），请上传 12MB 以内的图片'
            }), 413

        image_base64, mime = compress_image(raw, max_side=1568, quality=85)

        result = _media_bot_ref.recognize_image(image_base64, prompt)

        if result and not result.startswith("错误") and not result.startswith("所有"):
            user_msg = f"🖼️ {file.filename or '粘贴的图片'}\n{prompt}"
            _media_bot_ref.conversation_history.append({"role": "user", "content": user_msg})
            _media_bot_ref.conversation_history.append({"role": "assistant", "content": result})
            _media_bot_ref.conversation_history = trim_history(_media_bot_ref.conversation_history)

            title = prompt[:20] + '...' if len(prompt) > 20 else prompt
            update_current_conversation(
                _media_bot_ref.current_conversation_id,
                _media_bot_ref.conversation_history,
                title
            )

        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@media_bp.route('/api/generate_image', methods=['POST'])
def generate_image():
    if not _media_bot_ref:
        return jsonify({'success': False, 'error': 'Bot not initialized'}), 400

    data = request.json
    prompt = data.get('prompt', '')
    size = data.get('size', '1024x1024')

    if not prompt:
        return jsonify({'success': False, 'error': '提示词不能为空'}), 400

    _ensure_conversation_for(_media_bot_ref)

    try:
        result = _media_bot_ref.generate_image(prompt, size)
        if result.get("success") and result.get("image_data"):
            images_dir = os.path.join(BASE_DIR, "static", "images")
            os.makedirs(images_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            filename = f"img_{timestamp}_{unique_id}.png"
            filepath = os.path.join(images_dir, filename)

            image_data = result["image_data"]
            image_bytes = base64.b64decode(image_data)

            with open(filepath, 'wb') as f:
                f.write(image_bytes)

            result["image_path"] = f"/static/images/{filename}"

            user_message = f"🎨 生成图片: {prompt}"
            revised = result.get("revised_prompt", "")
            assistant_message = f"已为你生成图片：\n\n<img src=\"/static/images/{filename}\" style=\"max-width:100%;border-radius:8px;margin:8px 0;\">"
            if revised:
                assistant_message += f"\n\n**提示词**: {revised}"

            _media_bot_ref.conversation_history.append({"role": "user", "content": user_message})
            _media_bot_ref.conversation_history.append({"role": "assistant", "content": assistant_message})
            _media_bot_ref.conversation_history = trim_history(_media_bot_ref.conversation_history)

            title = prompt[:20] + '...' if len(prompt) > 20 else prompt
            update_current_conversation(
                _media_bot_ref.current_conversation_id,
                _media_bot_ref.conversation_history,
                title
            )
        else:
            _media_bot_ref.conversation_history.append({"role": "user", "content": f"🎨 生成图片: {prompt}"})
            err_msg = result.get('error', '图片生成失败')
            _media_bot_ref.conversation_history.append({"role": "assistant", "content": f"抱歉，图片生成失败：{err_msg}"})
            title = prompt[:20] + '...' if len(prompt) > 20 else prompt
            update_current_conversation(
                _media_bot_ref.current_conversation_id,
                _media_bot_ref.conversation_history,
                title
            )
        return jsonify(result)
    except Exception as e:
        _media_bot_ref.conversation_history.append({"role": "user", "content": f"🎨 生成图片: {prompt}"})
        _media_bot_ref.conversation_history.append({"role": "assistant", "content": f"图片生成出错：{e}"})
        title = prompt[:20] + '...' if len(prompt) > 20 else prompt
        update_current_conversation(
            _media_bot_ref.current_conversation_id,
            _media_bot_ref.conversation_history,
            title
        )
        return jsonify({'success': False, 'error': str(e)}), 500


@files_bp.route('/api/analyze_file', methods=['POST'])
def analyze_file():
    if not _files_bot_ref:
        return jsonify({'success': False, 'error': 'Bot not initialized'}), 400

    _ensure_conversation_for(_files_bot_ref)

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未上传文件'}), 400

    file = request.files['file']
    filename = file.filename.strip() if file.filename else ''
    if not filename:
        return jsonify({'success': False, 'error': '未选择文件'}), 400

    try:
        raw = file.read()
    except Exception as e:
        return jsonify({'success': False, 'error': f'读取文件失败: {str(e)}'}), 500

    MAX_SIZE = 15 * 1024 * 1024
    if len(raw) > MAX_SIZE:
        return jsonify({
            'success': False,
            'error': f'文件过大（{len(raw) // 1024 // 1024}MB），请上传 15MB 以内的文件'
        }), 413

    try:
        content = extract_text(filename, raw)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    MAX_TEXT = 300_000
    if len(content) > MAX_TEXT:
        content = content[:MAX_TEXT] + f"\n\n... (文件过长，已截断，原始大小 {len(content)} 字符)"

    try:
        result = _files_bot_ref.analyze_file(filename, content)

        user_msg = f"📄 {filename}"
        _files_bot_ref.conversation_history.append({"role": "user", "content": user_msg})
        _files_bot_ref.conversation_history.append({"role": "assistant", "content": result})
        _files_bot_ref.conversation_history = trim_history(_files_bot_ref.conversation_history)

        title = filename[:20] + '...' if len(filename) > 20 else filename
        update_current_conversation(
            _files_bot_ref.current_conversation_id,
            _files_bot_ref.conversation_history,
            title
        )

        return jsonify({'success': True, 'result': result, 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@media_bp.route('/api/face_info', methods=['GET'])
def face_info():
    available = is_available()
    return jsonify({
        'success': True,
        'available': available,
        'class_names': get_class_names() if available else [],
    })


@media_bp.route('/api/face_recognize', methods=['POST'])
def face_recognize():
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': '未上传图片'}), 400

    file = request.files['image']
    raw = file.read()
    if not raw:
        return jsonify({'success': False, 'error': '图片内容为空'}), 400

    result = recognize_image_bytes(raw)
    return jsonify(result)