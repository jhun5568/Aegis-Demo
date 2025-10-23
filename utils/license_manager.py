# utils/license_manager.py
"""라이선스 관리 시스템"""

from typing import Optional, Tuple
from datetime import datetime
import streamlit as st


class LicenseManager:
    """회사별 라이선스 체크 관리자"""

    def __init__(self, supabase_client, tenant_id: str):
        """
        Args:
            supabase_client: Supabase 클라이언트
            tenant_id: 회사 식별자 (예: 'dooho', 'kukje')
        """
        self.db = supabase_client
        self.tenant_id = tenant_id

    def check_license(self) -> Tuple[bool, str, dict]:
        """
        라이선스 유효성 체크

        Returns:
            (유효여부, 메시지, 라이선스정보)
        """
        try:
            # tenants 테이블에서 라이선스 정보 조회
            result = self.db.schema('ptop').table('tenants')\
                .select('*')\
                .eq('tenant_id', self.tenant_id)\
                .execute()

            if not result.data:
                return False, f"❌ 등록되지 않은 회사입니다. (tenant_id: {self.tenant_id})", {}

            tenant = result.data[0]

            # 1. 활성화 상태 체크
            if not tenant.get('is_active', False):
                return False, f"❌ 서비스가 중지되었습니다.\n\n관리자에게 문의하세요.\n담당자: {tenant.get('contact_email', 'N/A')}", tenant

            # 2. 만료일 체크
            expires_at = tenant.get('license_expires_at')
            if expires_at:
                # ISO 형식 날짜 파싱
                try:
                    expire_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    now = datetime.now(expire_date.tzinfo)

                    if now > expire_date:
                        return False, f"❌ 라이선스가 만료되었습니다.\n\n만료일: {expire_date.strftime('%Y년 %m월 %d일')}\n담당자: {tenant.get('contact_email', 'N/A')}", tenant

                    # 만료 7일 전 경고
                    days_left = (expire_date - now).days
                    if days_left <= 7:
                        warning_msg = f"⚠️ 라이선스가 {days_left}일 후 만료됩니다.\n만료일: {expire_date.strftime('%Y년 %m월 %d일')}"
                        st.warning(warning_msg)

                except Exception as e:
                    print(f"[WARNING] 만료일 파싱 실패: {e}")

            # 3. 라이선스 유효
            return True, f"✅ 라이선스 유효 ({tenant['company_name']})", tenant

        except Exception as e:
            print(f"[ERROR] 라이선스 체크 실패: {e}")
            return False, f"❌ 라이선스 확인 중 오류 발생: {e}", {}

    def get_license_info(self) -> Optional[dict]:
        """
        라이선스 정보 조회

        Returns:
            라이선스 정보 dict 또는 None
        """
        try:
            result = self.db.schema('ptop').table('tenants')\
                .select('*')\
                .eq('tenant_id', self.tenant_id)\
                .execute()

            if result.data:
                return result.data[0]
            return None

        except Exception as e:
            print(f"[ERROR] 라이선스 정보 조회 실패: {e}")
            return None

    def display_license_info(self):
        """사이드바에 라이선스 정보 표시 (선택사항)"""
        license_info = self.get_license_info()

        if license_info:
            with st.sidebar:
                st.markdown("---")
                st.caption("📋 라이선스 정보")

                expires_at = license_info.get('license_expires_at')
                if expires_at:
                    try:
                        expire_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        st.caption(f"만료일: {expire_date.strftime('%Y-%m-%d')}")
                    except:
                        pass

                st.caption(f"회사: {license_info.get('company_name', 'N/A')}")


def check_and_enforce_license(supabase_client, tenant_id: str) -> bool:
    """
    라이선스 체크 및 강제 적용 (앱 시작 시 호출)

    Args:
        supabase_client: Supabase 클라이언트
        tenant_id: 회사 식별자

    Returns:
        라이선스 유효 여부
    """
    lm = LicenseManager(supabase_client, tenant_id)
    is_valid, message, info = lm.check_license()

    if not is_valid:
        # 라이선스 무효 시 앱 중지
        st.error(message)
        st.markdown("---")
        st.markdown("### 📞 문의")
        st.info(f"""
        **담당자 이메일**: {info.get('contact_email', 'admin@example.com')}
        **연락처**: {info.get('contact_phone', 'N/A')}
        """)
        st.stop()

    return True
