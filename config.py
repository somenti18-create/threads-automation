import os
import shutil

DATA_DIR = os.environ.get("DATA_DIR", ".")
os.makedirs(DATA_DIR, exist_ok=True)

_APP_DIR = os.path.dirname(os.path.abspath(__file__))

def data_path(filename):
    return os.path.join(DATA_DIR, filename)

def ensure_data_file(filename):
    """初回起動時にappディレクトリからDATA_DIRにコピー"""
    dest = data_path(filename)
    if not os.path.exists(dest):
        src = os.path.join(_APP_DIR, filename)
        if os.path.exists(src):
            shutil.copy2(src, dest)
    return dest
