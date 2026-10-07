import json
from datetime import datetime

from config import (
    HISTORY_FILE,
    CONVERSATIONS_FILE,
    MAX_HISTORY_TURNS,
    MAX_HISTORY_CHARS,
)


def save_history_to_file(history: list):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_history_from_file() -> list:
    try:
        import os
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def save_conversations_to_file(conversations: list):
    try:
        with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(conversations, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_conversations_from_file() -> list:
    try:
        import os
        if os.path.exists(CONVERSATIONS_FILE):
            with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def update_current_conversation(conv_id: str, messages: list, title: str = None):
    try:
        conversations = load_conversations_from_file()

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

        save_conversations_to_file(conversations)
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