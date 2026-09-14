"""live_engine.py (APScheduler motoru) ile Streamlit arayuzu arasinda dosya tabanli
basit bir IPC (Inter-Process Communication) katmani. Motor bagimsiz bir surec olarak
calisir; arayuz onun yazdigi JSON durumunu okuyarak canli gosterir.
"""

import json
import os
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent.parent / ".state"
STATE_FILE = STATE_DIR / "live_state.json"
PID_FILE = STATE_DIR / "live_engine.pid"

STATE_DIR.mkdir(exist_ok=True)


def write_state(state: dict) -> None:
    tmp_path = STATE_FILE.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(state, f)
    os.replace(tmp_path, STATE_FILE)


def read_state() -> dict | None:
    if not STATE_FILE.exists():
        return None
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_pid(pid: int) -> None:
    PID_FILE.write_text(str(pid))


def read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None


def is_running() -> bool:
    pid = read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def clear_pid() -> None:
    PID_FILE.unlink(missing_ok=True)
