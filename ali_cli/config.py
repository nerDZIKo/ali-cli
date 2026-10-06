"""Project-local configuration and saved Playwright sessions."""

import json
import os
from pathlib import Path
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def local_credentials():
    """Read credentials without interpolation, logging, or changing the environment."""
    values = dotenv_values(PROJECT_ROOT / ".env", interpolate=False)
    return (
        os.environ.get("LOGIN") or values.get("LOGIN") or "",
        os.environ.get("PASSWORD") or values.get("PASSWORD") or "",
    )


def get_home() -> Path:
    """Return the Ali CLI config root. Respects ALI_CLI_HOME env var."""
    return Path(os.environ.get("ALI_CLI_HOME", PROJECT_ROOT / ".ali-cli"))


CONFIG_DIR = get_home()
CONFIG_FILE = CONFIG_DIR / "config.json"
# SESSION_FILE and STATE_FILE (in session_manager.py) point at the same file —
# Playwright storage_state serialized to JSON. Historically the code used
# two different names; unified here so every path reads/writes the same file.
SESSION_FILE = CONFIG_DIR / "state.json"
COOKIES_FILE = CONFIG_DIR / "cookies.json"

DEFAULT_CONFIG = {
    "email": "",
    "headless": True,
    "timeout": 30000,
}


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)


def load_config():
    ensure_config_dir()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            stored = json.load(f)
        return {**DEFAULT_CONFIG, **stored}
    return dict(DEFAULT_CONFIG)


def save_config(config):
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)


def get_email(cli_override: str | None = None) -> str:
    """Resolve the Alibaba login email.

    Priority: CLI --email > ALI_EMAIL > LOGIN from environment/.env > config.json.
    Raises RuntimeError if no email is configured.
    """
    if cli_override:
        return cli_override
    config = load_config()
    email = os.environ.get("ALI_EMAIL") or local_credentials()[0] or config.get("email")
    if not email:
        raise RuntimeError(
            "No Alibaba login email configured. "
            "Run `ali config set-email you@example.com` or pass `--email`."
        )
    return email


def save_session(storage_state):
    """Save Playwright browser storage state."""
    ensure_config_dir()
    with open(SESSION_FILE, "w") as f:
        json.dump(storage_state, f, indent=2)
    os.chmod(SESSION_FILE, 0o600)


def load_session():
    if SESSION_FILE.exists():
        with open(SESSION_FILE) as f:
            return json.load(f)
    return None


def clear_session():
    for f in [SESSION_FILE, COOKIES_FILE]:
        if f.exists():
            f.unlink()


def save_cookies(cookies):
    """Save raw cookie list from browser context."""
    ensure_config_dir()
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f, indent=2)
    os.chmod(COOKIES_FILE, 0o600)


def load_cookies():
    if COOKIES_FILE.exists():
        with open(COOKIES_FILE) as f:
            return json.load(f)
    return None


def session_exists():
    return SESSION_FILE.exists()
