import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import webbrowser
import threading

from flask import Flask, render_template

from config import API_KEYS, PROVIDER, MODEL, ENABLE_SEARCH
from core.bot import AIChatBot

try:
    from routes.chat import chat_bp, set_bot as set_chat_bot
except Exception as e:
    print(f"[app_factory] chat import failed: {e}")
    chat_bp = None
    set_chat_bot = None

try:
    from routes.config_routes import config_bp, set_bot as set_config_bot
except Exception as e:
    print(f"[app_factory] config import failed: {e}")
    config_bp = None
    set_config_bot = None

try:
    from routes.media import media_bp, files_bp, set_bot as set_media_bot
except Exception as e:
    print(f"[app_factory] media import failed: {e}")
    media_bp = None
    files_bp = None
    set_media_bot = None

try:
    from routes.conversations import conversations_bp, set_bot as set_conv_bot
except Exception as e:
    print(f"[app_factory] conversations import failed: {e}")
    conversations_bp = None
    set_conv_bot = None

try:
    from routes.auth import auth_bp
except Exception as e:
    print(f"[app_factory] auth import failed: {e}")
    auth_bp = None


def create_app() -> Flask:
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    @app.route('/')
    def home():
        return render_template('index.html')

    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    @app.route('/<path:filename>')
    def root_static(filename):
        root_dir = os.path.dirname(os.path.abspath(__file__))
        fp = os.path.join(root_dir, filename)
        if os.path.isfile(fp):
            from flask import send_file
            return send_file(fp)
        return '', 404

    if chat_bp:
        app.register_blueprint(chat_bp)
    if config_bp:
        app.register_blueprint(config_bp)
    if media_bp:
        app.register_blueprint(media_bp)
    if files_bp:
        app.register_blueprint(files_bp)
    if conversations_bp:
        app.register_blueprint(conversations_bp)
    if auth_bp:
        app.register_blueprint(auth_bp)
        print("[app_factory] auth_bp registered OK")
    else:
        print("[app_factory] auth_bp NOT available - did you upload routes/auth.py?")

    return app


def run_web_mode(bot, port=5000):
    app = create_app()

    if set_chat_bot:
        set_chat_bot(bot)
    if set_config_bot:
        set_config_bot(bot)
    if set_media_bot:
        set_media_bot(bot)
    if set_conv_bot:
        set_conv_bot(bot)

    def open_browser():
        time.sleep(1.5)
        webbrowser.open(f'http://127.0.0.1:{port}')

    threading.Thread(target=open_browser, daemon=True).start()
    print(f"\nWeb服务器已启动，浏览器将自动打开 http://127.0.0.1:{port}")
    print("按 Ctrl+C 停止服务器\n")

    app.run(host='127.0.0.1', port=port, debug=False, threaded=True, processes=1)


def main():
    print("=" * 50)
    print("智面 AI - Web模式 (AI问答 + 人脸识别)")
    print("=" * 50)

    provider = PROVIDER
    model = MODEL
    enable_search = ENABLE_SEARCH
    api_key = API_KEYS.get(provider, "")

    if not api_key:
        print(f"\n错误: 未找到 {provider} 的API密钥")
        print("请在项目根目录创建 .env 文件，内容参考 .env.example")
        print("或通过系统环境变量设置对应的 API Key")
        input("\n按回车键退出...")
        return

    bot = AIChatBot(api_key=api_key, model=model, provider=provider, enable_search=enable_search)
    run_web_mode(bot)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("\n程序异常退出:")
        traceback.print_exc()
        input("\n按回车键关闭窗口...")