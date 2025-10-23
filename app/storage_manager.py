# storage_manager.py
# Supabase Storage를 관리하는 전용 모듈
# ptop 앱의 파일 업로드/다운로드 기능 담당
# 기존 db_supabase_adapter와 완전 분리 (db_adapter 수정 없음)

from __future__ import annotations
import os
import unicodedata
from typing import Optional, List, Tuple

try:
    from config_supabase import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY
except Exception:
    SUPABASE_URL = os.getenv("SUPABASE_URL") or ""
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""


def sanitize_storage_key(key: str) -> str:
    """
    Storage key에 사용 가능하도록 한글을 언더스코어로 변환

    한글 → 언더스코어 (_)
    공백 → 언더스코어 (_)
    기타 ASCII 문자 → 유지
    """
    result = ""
    for char in key:
        if ord(char) < 128 and char not in " ":  # ASCII 범위 (공백 제외)
            result += char
        elif char == "_" or char == "/" or char == "-" or char == ".":  # 허용되는 특수문자
            result += char
        else:  # 한글, 공백, 기타 비ASCII → 언더스코어
            result += "_"
    return result.replace("__", "_")


class StorageManager:
    """Supabase Storage를 통해 PTOP 문서 파일 관리"""

    BUCKET_NAME = 'ptop-files'

    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("Supabase 접속정보가 없습니다. SUPABASE_URL / SUPABASE_KEY 설정 확인")

        from supabase import create_client

        # Storage 작업에는 Service Role 키 사용 (RLS 우회)
        # Service Role 키가 없으면 일반 키 사용
        if SUPABASE_SERVICE_ROLE_KEY:
            self.supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        else:
            self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    def upload_file(self, tenant_id: str, document_type: str, document_id: str, file_bytes: bytes, filename: str):
        """
        문서 파일을 Supabase Storage에 업로드

        Args:
            tenant_id: 테넌트 ID
            document_type: 문서 타입 ('quotation', 'bom', 'po')
            document_id: 문서 ID (프로젝트명, 한글 가능)
            file_bytes: 파일 바이트
            filename: 파일명 (DB에 저장할 원본 한글 파일명)

        Returns:
            (성공여부, 저장경로 또는 에러메시지)
        """
        try:
            # Storage 경로: 한글 제거하여 ASCII만 사용
            sanitized_doc_id = sanitize_storage_key(document_id)
            sanitized_filename = sanitize_storage_key(filename)
            storage_path = f"{tenant_id}/{document_type}/{sanitized_doc_id}/{sanitized_filename}"

            bucket = self.supabase.storage.from_(self.BUCKET_NAME)

            # 파일 업로드
            # 파일명에 버전이 포함되므로 항상 고유한 파일이 저장됨
            bucket.upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
            )

            return True, storage_path
        except Exception as e:
            return False, str(e)

    def get_public_url(self, storage_path: str) -> str:
        """
        Storage에 저장된 파일의 공개 다운로드 URL 생성

        Args:
            storage_path: Storage 내 경로

        Returns:
            공개 다운로드 URL
        """
        try:
            bucket = self.supabase.storage.from_(self.BUCKET_NAME)
            url = bucket.get_public_url(storage_path)
            return url
        except Exception:
            return ""

    def download_file(self, storage_path: str):
        """
        Storage에서 파일 다운로드

        Args:
            storage_path: Storage 내 경로

        Returns:
            (성공여부, 파일 바이트)
        """
        try:
            bucket = self.supabase.storage.from_(self.BUCKET_NAME)
            file_bytes = bucket.download(storage_path)
            return True, file_bytes
        except Exception as e:
            return False, str(e).encode()

    def delete_file(self, storage_path: str) -> bool:
        """
        Storage에서 파일 삭제

        Args:
            storage_path: Storage 내 경로

        Returns:
            성공여부
        """
        try:
            bucket = self.supabase.storage.from_(self.BUCKET_NAME)
            bucket.remove([storage_path])
            return True
        except Exception:
            return False

    def list_files(self, tenant_id: str, document_type: str, document_id: str):
        """
        특정 문서의 모든 파일 목록 조회

        Args:
            tenant_id: 테넌트 ID
            document_type: 문서 타입
            document_id: 문서 ID (프로젝트명, 한글 가능)

        Returns:
            파일 목록 (딕셔너리 리스트)
        """
        try:
            sanitized_doc_id = sanitize_storage_key(document_id)
            path = f"{tenant_id}/{document_type}/{sanitized_doc_id}"
            bucket = self.supabase.storage.from_(self.BUCKET_NAME)
            files = bucket.list(path)
            return files or []
        except Exception:
            return []


# Singleton 패턴 - 앱 전체에서 하나의 인스턴스 사용
_storage_manager_instance = None

def get_storage_manager() -> StorageManager:
    """StorageManager 싱글톤 인스턴스 반환"""
    global _storage_manager_instance
    if _storage_manager_instance is None:
        _storage_manager_instance = StorageManager()
    return _storage_manager_instance
