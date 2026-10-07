import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify

from core.storage import (
    load_conversations_from_file,
    save_conversations_to_file,
)

conversations_bp = Blueprint('conversations', __name__)

_bot_ref = None


def set_bot(bot):
    global _bot_ref
    _bot_ref = bot


@conversations_bp.route('/api/conversations', methods=['GET'])
def get_conversations():
    try:
        conversations = load_conversations_from_file()
        cleaned = [c for c in conversations if not (
            c.get('title') == '新对话' and not c.get('messages')
        )]
        if len(cleaned) != len(conversations):
            save_conversations_to_file(cleaned)
            if _bot_ref and _bot_ref.current_conversation_id:
                still_exists = any(c['id'] == _bot_ref.current_conversation_id for c in cleaned)
                if not still_exists:
                    _bot_ref.current_conversation_id = None
                    _bot_ref.conversation_history = []
        return jsonify({'success': True, 'conversations': cleaned})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@conversations_bp.route('/api/conversations', methods=['POST'])
def create_conversation():
    try:
        conversations = load_conversations_from_file()

        conv_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        new_conversation = {
            'id': conv_id,
            'title': '新对话',
            'timestamp': timestamp,
            'messages': []
        }

        conversations.insert(0, new_conversation)
        save_conversations_to_file(conversations)

        if _bot_ref:
            _bot_ref.conversation_history = []
            _bot_ref.current_conversation_id = conv_id

        return jsonify({'success': True, 'conversation': new_conversation})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@conversations_bp.route('/api/conversations/<conv_id>', methods=['GET'])
def load_conversation(conv_id):
    try:
        conversations = load_conversations_from_file()
        conversation = next((c for c in conversations if c['id'] == conv_id), None)

        if not conversation:
            return jsonify({'success': False, 'error': '对话不存在'}), 404

        if _bot_ref:
            _bot_ref.conversation_history = conversation.get('messages', [])
            _bot_ref.current_conversation_id = conv_id

        return jsonify({'success': True, 'conversation': conversation})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@conversations_bp.route('/api/conversations/<conv_id>', methods=['DELETE'])
def delete_conversation(conv_id):
    try:
        conversations = load_conversations_from_file()
        conversations = [c for c in conversations if c['id'] != conv_id]

        save_conversations_to_file(conversations)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@conversations_bp.route('/api/conversations/clear', methods=['POST'])
def clear_conversations():
    try:
        save_conversations_to_file([])

        if _bot_ref:
            _bot_ref.conversation_history = []
            _bot_ref.current_conversation_id = None

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@conversations_bp.route('/api/conversations/<conv_id>/title', methods=['PUT'])
def update_conversation_title(conv_id):
    try:
        data = request.json
        title = data.get('title', '新对话')

        conversations = load_conversations_from_file()
        for conv in conversations:
            if conv['id'] == conv_id:
                conv['title'] = title
                break

        save_conversations_to_file(conversations)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500