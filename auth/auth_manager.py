# /auth/auth_manager.py
from typing import Optional, Tuple
import streamlit as st
from supabase import create_client
from auth.storage_helper import save_auth_token, clear_auth_token

class AuthManager:
    def __init__(self, url: str, key: str):
        self.client = create_client(url, key)

    # 로그인
    def sign_in(self, email: str, password: str, remember_me: bool = False) -> Tuple[bool, str]:
        try:
            res = self.client.auth.sign_in_with_password({"email": email, "password": password})
            user = res.user
            st.session_state["auth_user"] = {"id": user.id, "email": user.email}
            st.session_state["auth_token"] = res.session.access_token if res.session else None

            # Remember Me: 토큰을 파일에 저장 (30일간 유효)
            if remember_me and res.session:
                save_auth_token(res.session.access_token, user.email, days=30)

            return True, "로그인 되었습니다."
        except Exception as e:
            return False, f"로그인 실패: {e}"

    # 토큰으로 자동 로그인
    def sign_in_with_token(self, token: str) -> Tuple[bool, str]:
        try:
            # Supabase 토큰 검증
            user = self.client.auth.get_user(token)
            if user and user.user:
                st.session_state["auth_user"] = {"id": user.user.id, "email": user.user.email}
                st.session_state["auth_token"] = token
                return True, "자동 로그인 되었습니다."
            return False, "토큰이 만료되었습니다."
        except Exception as e:
            return False, f"자동 로그인 실패: {e}"

    # 회원가입
    def sign_up(self, email: str, password: str, name: str) -> Tuple[bool, str]:
        try:
            res = self.client.auth.sign_up({"email": email, "password": password,
                                            "options": {"data": {"name": name}}})
            return True, "인증 메일을 발송했습니다. 메일함을 확인해 주세요."
        except Exception as e:
            return False, f"회원가입 실패: {e}"

    # 비밀번호 재설정
    def reset_password(self, email: str) -> Tuple[bool, str]:
        try:
            self.client.auth.reset_password_email(email)
            return True, "재설정 링크를 이메일로 보냈습니다."
        except Exception as e:
            return False, f"재설정 실패: {e}"

    # 로그아웃
    def sign_out(self):
        try:
            self.client.auth.sign_out()
        except Exception:
            pass
        for k in ["auth_user", "auth_token", "user_profile"]:
            st.session_state.pop(k, None)

        # 자동 로그인 토큰도 삭제
        clear_auth_token()

    # 사용자가 접근할 수 있는 테넌트 목록 가져오기
    def get_allowed_tenants(self, user_email: str) -> list:
        """
        사용자 이메일을 기반으로 접근 가능한 모든 테넌트 ID 목록을 반환합니다.
        """
        if not user_email:
            return []
        
        try:
            # 1. user_tenant_permissions 테이블에서 권한 조회
            permissions_res = self.client.table("user_tenant_permissions").select("tenant_id").eq("user_email", user_email).execute()
            
            if permissions_res and permissions_res.data:
                allowed_tenants = [item['tenant_id'] for item in permissions_res.data]
            else:
                allowed_tenants = []

            # 2. users 테이블의 기본 tenant_id도 추가 (중복 제거)
            user_res = self.client.table("users").select("tenant_id").eq("email", user_email).maybe_single().execute()
            if user_res and user_res.data and user_res.data.get('tenant_id'):
                base_tenant = user_res.data['tenant_id']
                if base_tenant not in allowed_tenants:
                    allowed_tenants.append(base_tenant)
            
            return allowed_tenants if allowed_tenants else []

        except Exception as e:
            st.error(f"테넌트 권한 조회 실패: {e}")
            return []
