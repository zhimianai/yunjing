import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
    print('[wsgi] .env loaded')
except Exception as e:
    print(f'[wsgi] dotenv error: {e}')

from config import API_KEYS, PROVIDER, MODEL, ENABLE_SEARCH
from core.bot import AIChatBot

api_key = API_KEYS.get(PROVIDER, "")
print(f'[wsgi] PROVIDER={PROVIDER}, api_key={"SET" if api_key else "MISSING"}')

bot = AIChatBot(api_key=api_key, model=MODEL, provider=PROVIDER, enable_search=ENABLE_SEARCH)

from app_factory import create_app
app = create_app()

from routes.chat import set_bot as set_chat_bot
from routes.config_routes import set_bot as set_config_bot
from routes.media import set_bot as set_media_bot
from routes.conversations import set_bot as set_conv_bot

set_chat_bot(bot)
set_config_bot(bot)
set_media_bot(bot)
set_conv_bot(bot)
print('[wsgi] All bot refs set')