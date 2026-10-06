"""Local Playwright session lifecycle; no cloud or mailbox integration."""

import json
import os
import time

from ali_cli.config import get_home

ALI_DIR = get_home()
STATE_FILE = ALI_DIR / "state.json"
COOKIES_FILE = ALI_DIR / "cookies.json"
LOGIN_STATUS_FILE = ALI_DIR / "login-status.json"


def _private_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(data, stream, indent=2)


def save_state(storage_state, cookies=None):
    _private_json(STATE_FILE, storage_state)
    if cookies is not None:
        _private_json(COOKIES_FILE, cookies)


def load_state():
    if not STATE_FILE.exists():
        return None
    try:
        return {k: v for k, v in json.loads(STATE_FILE.read_text()).items()
                if not k.startswith("_")}
    except (ValueError, OSError, AttributeError):
        return None


def state_age_hours():
    return (time.time() - STATE_FILE.stat().st_mtime) / 3600 if STATE_FILE.exists() else None


def update_login_status(success, method="local_playwright"):
    _private_json(LOGIN_STATUS_FILE, {
        "success": success, "method": method, "timestamp": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })


def get_browser(target_url=None):
    from ali_cli.browser import BrowserManager
    return BrowserManager(headless=True, timeout=30000)


def check_logged_in(bm, target_url=None):
    from ali_cli.local_auth import MESSENGER_URL, authenticated
    bm.page.goto(MESSENGER_URL, wait_until="domcontentloaded", timeout=30000)
    confirmed = authenticated(bm.page)
    if confirmed and target_url:
        bm.page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
    return confirmed


def refresh_login(console=None, email=None, timeout=180, manual=False):
    from ali_cli.local_auth import local_login
    state, cookies = local_login(email=email, timeout=timeout, manual=manual, console=console)
    save_state(state, cookies)
    update_login_status(True)


def keepalive():
    if not load_state():
        print("No saved session. Run 'ali login'.")
        return False
    try:
        with get_browser() as bm:
            if check_logged_in(bm):
                save_state(bm._context.storage_state(), bm._context.cookies())
                return True
    except Exception:
        pass
    return False
