import json
import os
from datetime import datetime

from config import (
    HISTORY_FILE,
    CONVERSATIONS_FILE,
    MAX_HISTORY_TURNS,
    MAX_HISTORY_CHARS,
    DATA_DIR,
)


def _user_conv_file(user_id: int = None, guest_id: str = None) -> str:
    if user_id:
        return os.path.join(DATA_DIR, f".conversations_{user_id}.json")
    if guest_id:
        return os.path.join(DATA_DIR, f".conversations_guest_{guest_id}.json")
    return os.path.join(DATA_DIR, ".conversations_orphan.json")


def save_history_to_file(history: list, user_id: int = None, guest_id: str = None):
    path = _user_conv_file(user_id, guest_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_history_from_file(user_id: int = None, guest_id: str = None) -> list:
    path = _user_conv_file(user_id, guest_id)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def save_conversations_to_file(conversations: list, user_id: int = None, guest_id: str = None):
    path = _user_conv_file(user_id, guest_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(conversations, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_conversations_from_file(user_id: int = None, guest_id: str = None) -> list:
    path = _user_conv_file(user_id, guest_id)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def update_current_conversation(conv_id: str, messages: list, title: str = None, user_id: int = None, guest_id: str = None):
    try:
        conversations = load_conversations_from_file(user_id, guest_id)

        found = False
        for conv in conversations:
            if conv['id'] == conv_id:
                conv['messages'] = messages
                if title and (not conv.get('title') or conv.get('title') == '新对话'):
                    conv['title'] = title
                conversations.remove(conv)
                conversations.insert(0, conv)
                found = True
                break

        if not found:
            new_conv = {
                'id': conv_id,
                'title': title or '新对话',
                'timestamp': datetime.now().isoformat(),
                'messages': messages
            }
            conversations.insert(0, new_conv)

        save_conversations_to_file(conversations, user_id, guest_id)
    except Exception:
        pass


def trim_history(history: list) -> list:
    if len(history) <= MAX_HISTORY_TURNS * 2:
        return history
    total_chars = sum(len(str(m.get("content", ""))) for m in history)
    if total_chars <= MAX_HISTORY_CHARS:
        return history
    keep_from = 0
    for i in range(len(history)):
        if history[i].get("role") == "assistant":
            keep_from = i
            break
    if keep_from >= len(history) - 2:
        keep_from = 0
    return history[keep_from:]