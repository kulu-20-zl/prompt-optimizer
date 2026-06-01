import os

from dotenv import load_dotenv

# 项目根目录（project/）
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

# 固定数据库文件路径，避免重启后因工作目录不同而用到另一个空库
DB_FILE = os.path.join(INSTANCE_DIR, "grammar_assistant.db")


def _sqlite_uri(db_path: str) -> str:
    return "sqlite:///" + db_path.replace("\\", "/")


load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI") or _sqlite_uri(DB_FILE)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "") or OPENAI_API_KEY
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "") or OPENAI_BASE_URL
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "") or os.getenv("OPENAI_MODEL", "deepseek-v4-pro")
    MOCK_AI = os.getenv("MOCK_AI", "0") == "1"
    MOCK_AI_DELAY = float(os.getenv("MOCK_AI_DELAY", "0"))
    MAX_TEXT_LENGTH = 2000
    MAX_PER_PAGE = 50
    DEFAULT_PER_PAGE = 10
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
    LOGIN_RATE_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "5"))
    LOGIN_RATE_WINDOW = int(os.getenv("LOGIN_RATE_WINDOW", "60"))
    ENABLE_DB_BACKUP = os.getenv("ENABLE_DB_BACKUP", "1") == "1"
    DB_BACKUP_KEEP = int(os.getenv("DB_BACKUP_KEEP", "5"))

    # 供启动日志使用
    DB_FILE = DB_FILE
