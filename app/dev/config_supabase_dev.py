"""
DEV configuration for Supabase/SQLite switching.

Environment bridge (preferred in DEV):
- DEV_USE_SUPABASE: "1" to use Supabase; otherwise SQLite
- DEV_SUPABASE_URL: Supabase project URL
- DEV_SUPABASE_KEY: Supabase anon key (service key NOT allowed)
- DEV_READONLY: "1" to guard write ops at app level

Falls back to app.config_supabase when DEV_* are not provided.
All labels kept ASCII to avoid encoding issues in some terminals.
"""

import os

# Defaults from app config (if present)
DEFAULT_URL = None
DEFAULT_KEY = None
DEFAULT_USE = None
DEFAULT_PROCESS_STAGES = {
    'CUT': 'Cut/Bend',
    'LASER_PIPE': 'Laser(Pipe)',
    'LASER_SHEET': 'Laser(Sheet)',
    'BAND': 'Bending',
    'PAINT': 'Paint',
    'STICKER': 'Sticker',
    'RECEIVING': 'Receiving'
}

try:
    from app.config_supabase import SUPABASE_URL as _URL, SUPABASE_KEY as _KEY, USE_SUPABASE as _USE, PROCESS_STAGES as _STAGES
    DEFAULT_URL = _URL
    DEFAULT_KEY = _KEY
    DEFAULT_USE = _USE
    # Only override stages if it looks sane (dict-like)
    if isinstance(_STAGES, dict):
        DEFAULT_PROCESS_STAGES = _STAGES
except Exception:
    pass


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip() in ("1", "true", "True", "YES", "yes")


# DEV env first
USE_SUPABASE = _env_bool("DEV_USE_SUPABASE", DEFAULT_USE if DEFAULT_USE is not None else False)
SUPABASE_URL = os.getenv("DEV_SUPABASE_URL") or DEFAULT_URL or ""
SUPABASE_KEY = os.getenv("DEV_SUPABASE_KEY") or os.getenv("DEV_SUPABASE_ANON_KEY") or DEFAULT_KEY or ""

# Read-only guard (app-level)
DEV_READONLY = _env_bool("DEV_READONLY", True)

# Expose stages
PROCESS_STAGES = DEFAULT_PROCESS_STAGES


def dev_log_banner():
    use = 1 if USE_SUPABASE else 0
    url_set = bool(SUPABASE_URL)
    print(f"[DEV] Supabase USE={use} (URL set={url_set}) RO={1 if DEV_READONLY else 0}")

