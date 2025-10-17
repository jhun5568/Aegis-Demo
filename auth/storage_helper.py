# /auth/storage_helper.py
"""파일 기반 자동 로그인 토큰 저장소"""

import os
import json
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timedelta

# 토큰 저장 디렉토리 (사용자 홈 디렉토리의 숨김 폴더)
TOKEN_DIR = Path.home() / ".aegis_auth"
TOKEN_FILE = TOKEN_DIR / "auto_login.json"

def ensure_token_dir():
    """토큰 디렉토리 생성"""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)

def save_auth_token(token: str, email: str, days: int = 30):
    """
    자동 로그인 토큰을 파일에 저장

    Args:
        token: Supabase 인증 토큰
        email: 사용자 이메일
        days: 토큰 유효 기간 (일)
    """
    ensure_token_dir()

    expires_at = (datetime.now() + timedelta(days=days)).isoformat()

    data = {
        "token": token,
        "email": email,
        "expires_at": expires_at
    }

    try:
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[INFO] Auto-login token saved for {email} (expires: {expires_at})")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save token: {e}")
        return False

def load_auth_token() -> Optional[Tuple[str, str]]:
    """
    저장된 토큰 로드

    Returns:
        (token, email) 또는 None (토큰이 없거나 만료된 경우)
    """
    if not TOKEN_FILE.exists():
        return None

    try:
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 만료 확인
        expires_at = datetime.fromisoformat(data['expires_at'])
        if datetime.now() > expires_at:
            print(f"[INFO] Auto-login token expired")
            clear_auth_token()
            return None

        print(f"[INFO] Auto-login token loaded for {data['email']}")
        return data['token'], data['email']

    except Exception as e:
        print(f"[ERROR] Failed to load token: {e}")
        return None

def clear_auth_token():
    """저장된 토큰 삭제"""
    try:
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
            print("[INFO] Auto-login token cleared")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to clear token: {e}")
        return False
