import os

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_env_path, override=False)
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

API_KEYS = {
    "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
    "qwen": os.getenv("QWEN_API_KEY", ""),
    "wenxin": os.getenv("WENXIN_API_KEY", ""),
    "openai": os.getenv("OPENAI_API_KEY", ""),
}

PROVIDER_DEFAULT_MODELS = {
    "deepseek": "deepseek-chat",
    "qwen": "qwen-plus",
    "wenxin": "ernie-4.5-turbo-128k",
    "openai": "gpt-4o-mini",
}

PROVIDER = os.getenv("AI_PROVIDER", "deepseek")
MODEL = os.getenv("AI_MODEL", PROVIDER_DEFAULT_MODELS.get(PROVIDER, "deepseek-chat"))
ENABLE_SEARCH = os.getenv("ENABLE_SEARCH", "false").lower() in ("true", "1", "yes")

DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")
QIANFAN_BASE_URL = os.getenv("QIANFAN_BASE_URL", "https://qianfan.baidubce.com/v2")

HISTORY_FILE = os.path.join(DATA_DIR, ".chat_history.json")
CONVERSATIONS_FILE = os.path.join(DATA_DIR, ".conversations.json")
MAX_HISTORY_TURNS = 30
MAX_HISTORY_CHARS = 12000

IMAGE_KEYWORDS = [
    '画一张', '画一幅', '画个', '画一', '绘制', '绘一张', '绘一幅',
    '生成图片', '生成图像', '生成照片', '生图', '生成一张', '生成一幅',
    '做一张图', '做个图', '出一张图', '出图',
    '帮我画', '给我画', '帮我生成', '给我生成', '帮我做', '给我做',
    '图片生成', '图像生成',
    '画头像', '做头像', '画logo', '做logo',
    'draw', 'generate image', 'create image', 'make image', 'picture of',
]

TEXT_EXTS = {
    '.txt', '.md', '.markdown', '.rst', '.log',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.properties', '.env',
    '.csv', '.tsv', '.xml', '.html', '.htm', '.css', '.scss', '.less',
    '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.c', '.cpp', '.cc', '.h', '.hpp',
    '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.sql',
    '.vue', '.sh', '.bash', '.bat', '.cmd', '.ps1', '.r', '.pl', '.lua', '.asm',
}

DOC_EXTS = {'.pdf', '.docx', '.xlsx', '.xlsm', '.pptx'}

DOC_EXTS_DESC = {
    '.pdf': 'PDF', '.docx': 'Word (.docx)',
    '.xlsx': 'Excel (.xlsx)', '.xlsm': 'Excel (.xlsm)',
    '.pptx': 'PowerPoint (.pptx)',
}

UNSUPPORTED_EXTS = {'.doc', '.xls', '.ppt', '.zip', '.rar', '.7z', '.gz', '.tar', '.bz2', '.xz'}


def save_env(updates: dict):
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    existing = {}
    order = []

    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if "=" in line and not line.lstrip().startswith("#"):
                    k, _, v = line.partition("=")
                    existing[k.strip()] = v.strip()
                    order.append(k.strip())

    for k, v in updates.items():
        existing[k] = v
        if k not in order:
            order.append(k)

    with open(env_path, "w", encoding="utf-8") as f:
        for k in order:
            f.write(f"{k}={existing[k]}\n")