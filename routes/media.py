import os
import base64
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify

from config import BASE_DIR
from core.users import verify_token
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
_user_conv_cache = {}


def set_bot(bot):
    global _media_bot_ref, _files_bot_ref
    _media_bot_ref = bot
    _files_bot_ref = bot


def _get_user_id():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = verify_token(token)
    return user['user_id'] if user else None


def _ensure_conversation(user_id):
    cache_key = user_id or "anon"
    if cache_key not in _user_conv_cache:
        conv_id = str(uuid.uuid4())
        _user_conv_cache[cache_key] = {
            'id': conv_id,
            'history': []
        }
        conversations = load_conversations_from_file(user_id)
        new_conv = {
            'id': conv_id,
            'title': '新对话',
            'timestamp': datetime.now().isoformat(),
            'messages': []
        }
        conversations.insert(0, new_conv)
        save_conversations_to_file(conversations, user_id)
    return _user_conv_cache[cache_key]


@media_bp.route('/api/recognize_image', methods=['POST'])
def recognize_image():
    if not _media_bot_ref:
        return jsonify({'success': False, 'error': 'Bot not initialized'}), 400

    user_id = _get_user_id()
    conv = _ensure_conversation(user_id)

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
            image_tag = f'\n<img src="data:image/jpeg;base64,{image_base64}" style="max-width:200px;border-radius:8px;margin-top:6px;border:1px solid #eee;">'
            user_msg = f"🖼️ {file.filename or '粘贴的图片'}\n{prompt}{image_tag}"
            conv['history'].append({"role": "user", "content": user_msg})
            conv['history'].append({"role": "assistant", "content": result})
            conv['history'] = trim_history(conv['history'])

            title = prompt[:20] + '...' if len(prompt) > 20 else prompt
            update_current_conversation(conv['id'], conv['history'], title, user_id)

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
    reference_image = (data.get('reference_image') or '').strip() or None

    if not prompt:
        return jsonify({'success': False, 'error': '提示词不能为空'}), 400

    user_id = _get_user_id()
    conv = _ensure_conversation(user_id)

    try:
        result = _media_bot_ref.generate_image(prompt, size,
            reference_image=reference_image)
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

            conv['history'].append({"role": "user", "content": user_message})
            conv['history'].append({"role": "assistant", "content": assistant_message})
            conv['history'] = trim_history(conv['history'])

            title = prompt[:20] + '...' if len(prompt) > 20 else prompt
            update_current_conversation(conv['id'], conv['history'], title, user_id)
        else:
            conv['history'].append({"role": "user", "content": f"🎨 生成图片: {prompt}"})
            err_msg = result.get('error', '图片生成失败')
            conv['history'].append({"role": "assistant", "content": f"抱歉，图片生成失败：{err_msg}"})
            title = prompt[:20] + '...' if len(prompt) > 20 else prompt
            update_current_conversation(conv['id'], conv['history'], title, user_id)
        return jsonify(result)
    except Exception as e:
        conv['history'].append({"role": "user", "content": f"🎨 生成图片: {prompt}"})
        conv['history'].append({"role": "assistant", "content": f"图片生成出错：{e}"})
        title = prompt[:20] + '...' if len(prompt) > 20 else prompt
        update_current_conversation(conv['id'], conv['history'], title, user_id)
        return jsonify({'success': False, 'error': str(e)}), 500


@files_bp.route('/api/analyze_file', methods=['POST'])
def analyze_file():
    if not _files_bot_ref:
        return jsonify({'success': False, 'error': 'Bot not initialized'}), 400

    user_id = _get_user_id()
    conv = _ensure_conversation(user_id)

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
        conv['history'].append({"role": "user", "content": user_msg})
        conv['history'].append({"role": "assistant", "content": result})
        conv['history'] = trim_history(conv['history'])

        title = filename[:20] + '...' if len(filename) > 20 else filename
        update_current_conversation(conv['id'], conv['history'], title, user_id)

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
    if not _media_bot_ref:
        return jsonify({'success': False, 'error': 'Bot not initialized'}), 400

    if 'image' not in request.files:
        return jsonify({'success': False, 'error': '未上传图片'}), 400

    user_id = _get_user_id()
    conv = _ensure_conversation(user_id)

    file = request.files['image']
    raw = file.read()
    if not raw:
        return jsonify({'success': False, 'error': '图片内容为空'}), 400

    result = recognize_image_bytes(raw)

    try:
        image_base64 = request.form.get('image_base64', '')
        if image_base64:
            user_msg = f"<div style=\"margin:4px 0;\">🤖 人脸识别: {file.filename or '上传的图片'}</div><img src=\"{image_base64}\" style=\"max-width:200px;border-radius:8px;margin-top:6px;border:1px solid #eee;\">"
        else:
            user_msg = f"[人脸识别] {file.filename or '上传的图片'}"
        conv['history'].append({"role": "user", "content": user_msg})

        if result.get('success') and result.get('faces_found', 0) > 0:
            names = [r.get('name', 'Unknown') for r in result.get('results', [])]
            confs = [r.get('confidence', 0) for r in result.get('results', [])]
            summary_parts = []
            for r in result.get('results', []):
                label = r.get('name', 'Unknown')
                conf = r.get('confidence', 0) * 100
                summary_parts.append(f"{label} ({conf:.1f}%)")
            assistant_msg = f"人脸识别完成：检测到 {result['faces_found']} 张人脸 → {', '.join(summary_parts)}"
            if result.get('annotated_image'):
                assistant_msg += f"\n\n<img src=\"{result['annotated_image']}\" style=\"max-width:300px;border-radius:8px;border:1px solid #eee;\">"
        elif result.get('faces_found', 0) == 0:
            assistant_msg = "人脸识别完成：未检测到人脸"
            if image_base64:
                assistant_msg += f"\n\n<img src=\"{image_base64}\" style=\"max-width:300px;border-radius:8px;border:1px solid #eee;\">"
        else:
            assistant_msg = f"人脸识别失败：{result.get('error', '未知错误')}"

        conv['history'].append({"role": "assistant", "content": assistant_msg})
        conv['history'] = trim_history(conv['history'])

        update_current_conversation(conv['id'], conv['history'], '人脸识别', user_id)
    except Exception as e:
        print(f"[face_recognize] save error: {e}")

    return jsonify(result)