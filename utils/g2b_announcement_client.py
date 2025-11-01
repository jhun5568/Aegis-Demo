"""
나라장터 입찰공고 API 클라이언트
"""
import os
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


class G2BAnnouncementClient:
    """나라장터 입찰공고 API 클라이언트"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('G2B_API_KEY')
        self.base_url = "https://apis.data.go.kr/1230000/BidPublicInfoService"

        if not self.api_key:
            raise ValueError("G2B_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    def fetch_announcements(
        self,
        start_date: str = None,
        end_date: str = None,
        page_no: int = 1,
        num_rows: int = 100,
        inqry_div: str = '1'  # 1=등록일시, 2=공고일시, 3=개찰일시
    ) -> Dict:
        """
        입찰공고 목록 조회 (공사)

        Args:
            start_date: 조회시작일시 (YYYYMMDDHHMM) - 기본값: 30일 전
            end_date: 조회종료일시 (YYYYMMDDHHMM) - 기본값: 오늘
            page_no: 페이지 번호
            num_rows: 한 페이지 결과 수 (최대 999)
            inqry_div: 조회구분

        Returns:
            {
                'totalCount': 총 건수,
                'items': [입찰공고 리스트],
                'pageNo': 현재 페이지,
                'numOfRows': 페이지당 건수
            }
        """
        # 기본 날짜 설정
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d0000")
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d2359")

        endpoint = f"{self.base_url}/getBidPblancListInfoCnstwk"

        params = {
            'serviceKey': self.api_key,
            'pageNo': str(page_no),
            'numOfRows': str(num_rows),
            'type': 'json',
            'inqryDiv': inqry_div,
            'inqryBgnDt': start_date,
            'inqryEndDt': end_date
        }

        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # 응답 구조 파싱
            if 'response' not in data:
                return {'totalCount': 0, 'items': [], 'pageNo': page_no, 'numOfRows': num_rows}

            header = data['response'].get('header', {})
            if header.get('resultCode') != '00':
                raise Exception(f"API 오류: {header.get('resultMsg', 'Unknown error')}")

            body = data['response'].get('body', {})
            items = body.get('items', [])

            # items가 dict인 경우 리스트로 변환
            if isinstance(items, dict):
                items = [items]

            return {
                'totalCount': body.get('totalCount', 0),
                'items': items,
                'pageNo': body.get('pageNo', page_no),
                'numOfRows': body.get('numOfRows', num_rows)
            }

        except requests.exceptions.RequestException as e:
            raise Exception(f"API 호출 실패: {e}")

    def fetch_announcements_by_range(
        self,
        start_date: str,
        end_date: str,
        max_results: int = 1000
    ) -> List[Dict]:
        """
        긴 기간의 입찰공고를 1주일씩 나눠서 조회

        Args:
            start_date: 조회시작일시 (YYYYMMDDHHMM)
            end_date: 조회종료일시 (YYYYMMDDHHMM)
            max_results: 최대 결과 수

        Returns:
            전체 입찰공고 리스트
        """
        from datetime import datetime, timedelta

        all_items = []

        # 문자열을 datetime으로 변환
        start_dt = datetime.strptime(start_date[:8], "%Y%m%d")
        end_dt = datetime.strptime(end_date[:8], "%Y%m%d")

        current_start = start_dt

        while current_start <= end_dt:
            # 1주일 단위로 끝 날짜 설정
            current_end = min(current_start + timedelta(days=6), end_dt)

            # API 호출
            week_start = current_start.strftime("%Y%m%d0000")
            week_end = current_end.strftime("%Y%m%d2359")

            try:
                result = self.fetch_announcements(
                    start_date=week_start,
                    end_date=week_end,
                    num_rows=100,
                    page_no=1,
                    inqry_div='1'
                )

                items = result.get('items', [])
                all_items.extend(items)

                # 최대 결과 수 체크
                if len(all_items) >= max_results:
                    all_items = all_items[:max_results]
                    break

            except Exception as e:
                print(f"Warning: {week_start}~{week_end} 조회 실패: {e}")

            # 다음 주로 이동
            current_start = current_end + timedelta(days=1)

        return all_items

    def search_by_keyword(
        self,
        keyword: str,
        start_date: str = None,
        end_date: str = None,
        max_results: int = 100
    ) -> List[Dict]:
        """
        키워드로 입찰공고 검색

        Args:
            keyword: 검색 키워드 (예: '울타리', '차양', '펜스')
            start_date: 조회시작일시
            end_date: 조회종료일시
            max_results: 최대 결과 수

        Returns:
            필터링된 입찰공고 리스트
        """
        if not start_date or not end_date:
            end_date = datetime.now().strftime("%Y%m%d2359")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d0000")

        all_items = self.fetch_announcements_by_range(start_date, end_date, max_results * 10)

        # 키워드 필터링
        filtered = [
            item for item in all_items
            if keyword.lower() in item.get('bidNtceNm', '').lower()
        ]

        return filtered[:max_results]
