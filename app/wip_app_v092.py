"""
DEV - WIP v092 Wrapper

Purpose
- Render the original WIP v09 screen (app/wip_app_v0.9.py) in DEV, so the UI matches production.
- Keep DEV convenience (optional read-only banner) without touching production files.

Run: streamlit run app/dev/launcher_dev.py
"""

from __future__ import annotations

import sys
from pathlib import Path
import os
from datetime import date as _date

import streamlit as st
import pandas as pd
import importlib.util

# Ensure absolute imports for app/* work when loaded by importlib
_APP = Path(__file__).resolve().parent  # app/ 폴더
_ROOT = _APP.parent  # 프로젝트 루트
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from app.dev.config_supabase_dev import (
    SUPABASE_URL,
    SUPABASE_KEY,
    USE_SUPABASE,
    DEV_READONLY,
    dev_log_banner,
)
def render(allowed_tenants=None):
    dev_log_banner()
    # Bridge DEV config to env for downstream modules if they read from env
    os.environ.setdefault('SUPABASE_URL', SUPABASE_URL or '')
    os.environ.setdefault('SUPABASE_KEY', SUPABASE_KEY or '')

    # Load original WIP app by path and call its main()
    wip_path = (_ROOT / 'app' / 'wip_app_v0.9.py').resolve()
    if not wip_path.exists():
        st.error(f"Original WIP app not found: {wip_path}")
        return

    try:
        spec = importlib.util.spec_from_file_location('wip_app_v0_9', str(wip_path))
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)  # type: ignore
    except Exception as e:
        st.error(f"Failed to import original WIP: {e}")
        return

    # Call main with allowed_tenants if supported; fallback to bare main()
    # launcher.py에서 전달받은 allowed_tenants 사용, 없으면 기본값
    tenants = allowed_tenants or ['dooho', 'kukje']
    try:
        if hasattr(mod, 'main'):
            try:
                mod.main(allowed_tenants=tenants)  # type: ignore
            except TypeError:
                mod.main()  # type: ignore
        else:
            st.error('main() not found in original WIP module')
    except Exception as e:
        st.error(f'Failed to render original WIP: {e}')

    # Demo 테넌트 메시지
    if allowed_tenants and 'demo' not in allowed_tenants:
        try:
            tenant_id = os.getenv('TENANT_ID', 'dooho')
            if tenant_id == 'demo':
                st.info("📌 데모 모드에서 WIP 앱을 사용할 수 없습니다.")
        except Exception:
            pass


def main(allowed_tenants=None):
    """
    Main entry point for WIP app v092

    Args:
        allowed_tenants: List of allowed tenant IDs (optional, for launcher compatibility)
    """
    render(allowed_tenants=allowed_tenants)


if __name__ == "__main__":
    render()
