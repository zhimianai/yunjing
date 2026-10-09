from flask import Blueprint, request, jsonify

from config import API_KEYS, PROVIDER_DEFAULT_MODELS, PROVIDER, MODEL, ENABLE_SEARCH, save_env
from core.bot import AIChatBot

config_bp = Blueprint('config', __name__)

_bot_ref = None


def set_bot(bot):
    global _bot_ref
    _bot_ref = bot


@config_bp.route('/api/config', methods=['GET', 'POST'])
def config():
    global PROVIDER, MODEL, API_KEYS, _bot_ref

    if request.method == 'GET':
        config_data = {
            'provider': PROVIDER,
            'model': MODEL,
            'enable_search': _bot_ref.enable_search if _bot_ref else ENABLE_SEARCH,
            'has_server_key': {p: bool(API_KEYS.get(p)) for p in API_KEYS}
        }
        return jsonify({'success': True, 'config': config_data})

    if request.method == 'POST':
        data = request.json
        provider = data.get('provider', PROVIDER)
        model = data.get('model', MODEL)
        api_key = data.get('api_key', '')
        enable_search = data.get('enable_search', False)

        PROVIDER = provider

        default_model = PROVIDER_DEFAULT_MODELS.get(provider, "deepseek-chat")
        if not model or not AIChatBot._is_model_for_provider(model, provider):
            model = default_model
        MODEL = model

        if api_key:
            API_KEYS[provider] = api_key

        current_api_key = API_KEYS.get(provider, "")

        _bot_ref = AIChatBot(
            api_key=current_api_key,
            model=MODEL,
            provider=PROVIDER,
            enable_search=enable_search
        )

        save_env({
            "AI_PROVIDER": PROVIDER,
            "AI_MODEL": MODEL,
            "ENABLE_SEARCH": str(enable_search).lower(),
        })

        from routes.chat import set_bot as set_chat_bot
        from routes.media import set_bot as set_media_bot
        from routes.conversations import set_bot as set_conv_bot
        set_chat_bot(_bot_ref)
        set_media_bot(_bot_ref)
        set_conv_bot(_bot_ref)

        return jsonify({'success': True, 'message': f'配置已更新并保存（模型已自动调整为 {MODEL}）'})