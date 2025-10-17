"""
Supabase 설정 파일 (멀티테넌트 지원)
WIP v0.6 - SQLite → Supabase 전환
"""

import os
import streamlit as st

# ============================================================================
# Supabase 설정 (Streamlit Secrets에서 로드)
# ============================================================================
# .streamlit/secrets.toml 파일의 [supabase] 섹션을 사용합니다.
try:
    SUPABASE_URL = st.secrets["supabase"]["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["supabase"]["SUPABASE_KEY"]
except Exception:
    # Fallback: 환경 변수에서 직접 읽기 (로컬 개발용)
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")

# DB 모드 선택
USE_SUPABASE = True  # True: Supabase 사용, False: SQLite 사용 (롤백용)

# 연결 타임아웃 설정
SUPABASE_TIMEOUT = 10  # 10초 타임아웃

# SQLite 백업 경로 (만약을 대비)
SQLITE_DB_PATH = "../database/wip_database.db"
SQLITE_BACKUP_PATH = "../database/wip_database_backup.db"

# 공정 단계 정의
PROCESS_STAGES = {
    'CUT': '절단/절곡',
    'LASER_PIPE': 'P레이저(파이프)',
    'LASER_SHEET': '레이저(판재)',
    'BAND': '벤딩',
    'PAINT': '페인트',
    'STICKER': '스티커',
    'RECEIVING': '입고'
}

# Supabase 클라이언트를 생성하는 함수 (중앙 관리)
def get_supabase_client():
    """환경 변수에 따라 올바른 Supabase 클라이언트를 생성하여 반환합니다."""
    from supabase import create_client
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("❌ Supabase 접속 정보가 설정되지 않았습니다. .streamlit/secrets.toml 파일을 확인해주세요.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# AuthManager 인스턴스를 생성하는 함수 (레거시 호환성, 추후 제거 권장)
def get_auth_manager():
    """AuthManager 인스턴스를 반환합니다. (레거시)"""
    from auth.auth_manager import AuthManager
    return AuthManager(SUPABASE_URL, SUPABASE_KEY)
