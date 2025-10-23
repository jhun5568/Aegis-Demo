"""
Google Sheets와 Streamlit 통합 모듈

기능:
- Google Sheets 읽기/쓰기
- DataFrame ↔ Google Sheets 변환
- 멀티테넌트 지원 (dooho, kukje)
- 캐싱 지원 (Streamlit @st.cache_resource)
"""

from __future__ import annotations

import gspread
from oauth2client.serviceaccount import ServiceAccountCredentials
import streamlit as st
import pandas as pd
from typing import List, Dict, Optional, Tuple
import json
from pathlib import Path


class GoogleSheetsManager:
    """Google Sheets 읽기/쓰기 관리 클래스"""

    def __init__(self, sheet_id: str):
        """
        Google Sheets 관리자 초기화

        Args:
            sheet_id: Google Sheet ID (URL에서 /d/ 와 /edit 사이의 긴 문자열)
        """
        self.sheet_id = sheet_id
        self.client = self._get_gspread_client()
        try:
            self.sheet = self.client.open_by_key(sheet_id)
        except gspread.exceptions.SpreadsheetNotFound:
            raise ValueError(f"Sheet ID '{sheet_id}'를 찾을 수 없습니다. 공유 설정을 확인하세요.")

    @staticmethod
    def _get_gspread_client() -> gspread.Client:
        """Streamlit secrets에서 gspread 클라이언트 생성"""
        try:
            creds_dict = st.secrets.get("google_sheets")
        except Exception:
            creds_dict = None

        if not creds_dict:
            raise ValueError(
                "google_sheets 설정이 .streamlit/secrets.toml에 없습니다. "
                "GOOGLE_SHEETS_SETUP.md를 참고하여 설정하세요."
            )

        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        try:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes=scope)
            return gspread.authorize(creds)
        except Exception as e:
            raise ValueError(f"Google 서비스 계정 인증 실패: {e}")

    def get_worksheet(self, tab_name: str) -> gspread.Worksheet:
        """탭 이름으로 워크시트 가져오기"""
        try:
            return self.sheet.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            raise ValueError(f"탭 '{tab_name}'을 찾을 수 없습니다. 탭 이름을 확인하세요.")

    def list_worksheets(self) -> List[str]:
        """모든 워크시트 이름 조회"""
        return [ws.title for ws in self.sheet.worksheets()]

    def read_as_dataframe(self, tab_name: str, skip_header: int = 1) -> pd.DataFrame:
        """
        Google Sheet 탭을 DataFrame으로 읽기

        Args:
            tab_name: 탭 이름 (예: "견적", "발주", "자재내역", "실행내역")
            skip_header: 헤더 행 수 (기본값: 1 = 첫 행을 헤더로 사용)

        Returns:
            pd.DataFrame: 읽은 데이터 (빈 행 제거됨)
        """
        ws = self.get_worksheet(tab_name)
        data = ws.get_all_values()

        if not data or len(data) < skip_header:
            # 헤더만 있고 데이터가 없는 경우
            return pd.DataFrame()

        headers = data[skip_header - 1]
        rows = data[skip_header:]

        # 모든 행이 비어있으면 빈 DataFrame 반환
        if not rows:
            df = pd.DataFrame(columns=headers)
            return df

        df = pd.DataFrame(rows, columns=headers)

        # 모든 셀이 비어있는 행 제거
        df = df.loc[df.astype(str).ne('').any(axis=1)].reset_index(drop=True)

        return df

    def write_dataframe(self, tab_name: str, df: pd.DataFrame, start_row: int = 2):
        """
        DataFrame을 Google Sheet 탭에 쓰기 (헤더 제외)

        Args:
            tab_name: 탭 이름
            df: 쓸 DataFrame (헤더 포함)
            start_row: 데이터 시작 행 (헤더는 start_row-1에 위치)

        주의: 이 함수는 헤더를 유지하고 데이터만 업데이트합니다
        """
        ws = self.get_worksheet(tab_name)

        # 기존 데이터 행 삭제 (헤더 제외)
        if ws.row_count > 1:
            ws.delete_rows(start_row, ws.row_count)

        # DataFrame을 2D 리스트로 변환
        if df.empty:
            return  # 빈 DataFrame이면 아무것도 하지 않음

        data = df.values.tolist()

        # Google Sheet에 쓰기
        ws.update(f"A{start_row}", data)

    def append_rows(self, tab_name: str, rows: List[List]):
        """
        행 추가하기

        Args:
            tab_name: 탭 이름
            rows: 추가할 행들 (각 행은 리스트)
        """
        if not rows:
            return

        ws = self.get_worksheet(tab_name)
        ws.append_rows(rows)

    def clear_tab(self, tab_name: str, start_row: int = 2):
        """
        탭의 데이터 삭제 (헤더 제외)

        Args:
            tab_name: 탭 이름
            start_row: 삭제 시작 행 (기본값: 2 = 헤더 다음부터)
        """
        ws = self.get_worksheet(tab_name)
        # A2부터 모든 데이터 삭제
        if ws.row_count > 1:
            ws.delete_rows(start_row, ws.row_count)

    def get_cell_value(self, tab_name: str, row: int, col: int) -> str:
        """특정 셀 값 읽기"""
        ws = self.get_worksheet(tab_name)
        return ws.cell(row, col).value or ""

    def set_cell_value(self, tab_name: str, row: int, col: int, value: str):
        """특정 셀 값 쓰기"""
        ws = self.get_worksheet(tab_name)
        ws.update_cell(row, col, value)

    def batch_update(self, tab_name: str, updates: List[Tuple[int, int, str]]):
        """
        여러 셀 한 번에 업데이트

        Args:
            tab_name: 탭 이름
            updates: [(row, col, value), ...] 리스트
        """
        ws = self.get_worksheet(tab_name)
        for row, col, value in updates:
            ws.update_cell(row, col, value)


# ============================================================================
# 멀티테넌트별 Sheet ID 설정
# ============================================================================

# Google Sheet ID 설정
# Google Sheet URL에서 /d/XXXXX/edit 의 XXXXX 부분
SHEET_IDS = {
    "dooho": "1YEV3m1G9rdk-3EjpcmMjkZ5LGL2Qite56ldld",   # ptop 실행 관리 - dooho
    "kukje": "",   # TODO: kukje용 Sheet ID 추가 필요
}


def set_sheet_id(tenant_id: str, sheet_id: str):
    """테넌트별 Sheet ID 설정"""
    SHEET_IDS[tenant_id] = sheet_id
    st.success(f"✅ {tenant_id} Sheet ID 설정됨")


def get_sheets_manager(tenant_id: str) -> GoogleSheetsManager:
    """
    테넌트별 Google Sheets 관리자 획득

    Args:
        tenant_id: 테넌트 ID (dooho, kukje 등)

    Returns:
        GoogleSheetsManager: 관리자 객체

    Raises:
        ValueError: Sheet ID가 설정되지 않았거나 잘못된 경우
    """
    sheet_id = SHEET_IDS.get(tenant_id, "").strip()
    if not sheet_id:
        raise ValueError(
            f"테넌트 '{tenant_id}'에 대한 Sheet ID가 설정되지 않았습니다. "
            f"GOOGLE_SHEETS_SETUP.md를 참고하여 set_sheet_id()를 호출하세요."
        )
    return GoogleSheetsManager(sheet_id)


# ============================================================================
# 문서별 헤더 정의
# ============================================================================

DOCUMENT_HEADERS = {
    "견적": ["No.", "품목", "규격", "단위", "수량", "단가", "공급가", "부가세", "비고"],
    "발주": ["No.", "품목", "규격", "단위", "수량", "단가", "금액", "비고"],
    "자재내역": ["No.", "품목", "규격", "단위", "수량", "단가", "공급가", "비고", "하차지", "차량번호", "납품처"],
    "실행내역": ["분류", "품목", "금액", "비율(%)", "부가세", "합계(VAT포함)", "비고"],
}


def create_tabs_if_not_exist(manager: GoogleSheetsManager):
    """
    필요한 탭이 없으면 생성하기

    Args:
        manager: GoogleSheetsManager 객체
    """
    existing_tabs = manager.list_worksheets()

    for tab_name, headers in DOCUMENT_HEADERS.items():
        if tab_name not in existing_tabs:
            # 새 탭 생성
            worksheet = manager.sheet.add_worksheet(title=tab_name, rows=100, cols=len(headers))
            # 헤더 추가
            worksheet.append_rows([headers])
            st.info(f"✅ 탭 '{tab_name}' 생성되었습니다")


# ============================================================================
# 테스트 및 진단 함수
# ============================================================================

def test_connection(tenant_id: str = "dooho"):
    """
    Google Sheets 연결 테스트

    Args:
        tenant_id: 테넌트 ID (기본값: dooho)
    """
    try:
        manager = get_sheets_manager(tenant_id)
        st.success("✅ Google Sheets 연결 성공!")
        st.info(f"시트 제목: {manager.sheet.title}")
        st.write("**탭 목록:**")
        for tab in manager.list_worksheets():
            st.write(f"  - {tab}")
    except Exception as e:
        st.error(f"❌ Google Sheets 연결 실패: {e}")


def show_diagnostics(tenant_id: str = "dooho"):
    """
    진단 정보 표시

    Args:
        tenant_id: 테넌트 ID
    """
    st.subheader("📊 Google Sheets 진단")

    # Sheet ID 확인
    sheet_id = SHEET_IDS.get(tenant_id, "").strip()
    if sheet_id:
        st.success(f"✅ {tenant_id} Sheet ID: {sheet_id[:30]}...")
    else:
        st.warning(f"⚠️ {tenant_id} Sheet ID 설정 안 됨")

    # secrets.toml 확인
    try:
        creds = st.secrets.get("google_sheets")
        if creds:
            st.success("✅ Google Sheets 자격증명 설정됨")
            st.json({
                "type": creds.get("type"),
                "project_id": creds.get("project_id"),
                "client_email": creds.get("client_email"),
            })
        else:
            st.error("❌ secrets.toml에 google_sheets 설정이 없습니다")
    except Exception as e:
        st.error(f"❌ Secrets 접근 오류: {e}")

    # 연결 테스트
    if st.button("🔗 연결 테스트"):
        test_connection(tenant_id)


