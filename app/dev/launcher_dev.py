"""
DEV launcher for testing PTOP/WIP v092 without affecting production app/*.

Run:
    streamlit run app/dev/launcher_dev.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import importlib.util
import types
import streamlit as st

# Ensure project root on sys.path so that absolute imports resolve
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# DEV config banner
from app.dev.config_supabase_dev import dev_log_banner


def _load_by_path(mod_name: str, path: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"Cannot load module from {path}")
    m = importlib.util.module_from_spec(spec)
    # Ensure module is visible to runtime (required for dataclasses and typing resolution)
    sys.modules[mod_name] = m
    spec.loader.exec_module(m)
    return m


def page_ptop_v092():
    st.header("DEV - PTOP v092")
    try:
        # v092 (includes P0 helper functions + normalization)
        from app import ptop_app_v092 as ptop
        if hasattr(ptop, 'main'):
            ptop.main(mode="pilot")
        else:
            st.error("main() not found in PTOP v092")
    except ImportError as e:
        st.error(f"Failed to load PTOP v092: {e}\n\nEnsure app/ptop_app_v092.py exists and P0 functions are available.")
    except Exception as e:
        st.error(f"Failed to run PTOP v092: {e}")


def page_wip_v092():
    here = os.path.dirname(__file__)
    mod_path = os.path.join(here, "wip_app_v092.py")
    try:
        mod = _load_by_path("dev_wip_v092", mod_path)
        if hasattr(mod, "render"):
            mod.render()  # type: ignore
        else:
            st.error("render() not found in wip_app_v092.py")
    except Exception as e:
        st.error(f"Failed to load WIP v092: {e}")


def main():
    st.set_page_config(page_title="DEV Launcher", layout="wide", initial_sidebar_state="expanded")
    dev_log_banner()

    st.sidebar.title("DEV")
    choice = st.sidebar.radio("Select App", ["DEV - PTOP v092", "DEV - WIP v092", "DEV - Phase 3 Demo"], index=1)

    if choice == "DEV - PTOP v092":
        page_ptop_v092()
    elif choice == "DEV - WIP v092":
        page_wip_v092()
    else:
        # Lazy-load Phase 3 demo
        here = os.path.dirname(__file__)
        mod_path = os.path.join(here, "phase3_demo.py")
        try:
            mod = _load_by_path("dev_phase3_demo", mod_path)
            if hasattr(mod, "render"):
                mod.render()  # type: ignore
            else:
                st.error("render() not found in phase3_demo.py")
        except Exception as e:
            st.error(f"Failed to load Phase 3 Demo: {e}")


if __name__ == "__main__":
    main()
