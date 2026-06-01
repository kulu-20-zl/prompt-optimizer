"""SQLite 数据库自动备份。"""

import os
import shutil
from datetime import datetime

from backend.config import Config


def backup_database(max_keep: int = 5) -> str | None:
    src = Config.DB_FILE
    if not os.path.isfile(src):
        return None

    backup_dir = os.path.join(os.path.dirname(src), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(backup_dir, f"grammar_assistant_{stamp}.db")
    shutil.copy2(src, dest)

    backups = sorted(
        [
            os.path.join(backup_dir, name)
            for name in os.listdir(backup_dir)
            if name.endswith(".db")
        ],
        key=os.path.getmtime,
        reverse=True,
    )
    for old in backups[max_keep:]:
        try:
            os.remove(old)
        except OSError:
            pass

    return dest
