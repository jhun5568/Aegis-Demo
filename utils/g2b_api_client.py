"""
나라장터 낙찰정보 API 클라이언트
"""
import os
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from xml.etree import ElementTree as ET

load_dotenv()


class G2BAPIClient:
    """나라장터 낙찰정보 API 클라이언트"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('G2B_API_KEY')
        self.base_url = "https://apis.data.go.kr/1230000/as/ScsbidInfoService"

        if not self.api_key:
            raise ValueError("G2B_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    def fetch_awards(
        self,
        start_date: str = None,
        end_date: str = None,
        keyword: str = None,
        page_no: int = 1,
        num_rows: int = 100,
        inqry_div: str = '1'  # 1=등록일시, 2=공고일시, 3=개찰일시
    ) -> Dict:
        """
        낙찰정보 목록 조회 (물품)

        Args:
            start_date: 조회시작일시 (YYYYMMDDHHMM) - 기본값: 30일 전
            end_date: 조회종료일시 (YYYYMMDDHHMM) - 기본값: 오늘
            keyword: 검색 키워드 (공고명에 포함된 단어)
            page_no: 페이지 번호
            num_rows: 한 페이지 결과 수 (최대 999)
            inqry_div: 조회구분

        Returns:
            {
                'totalCount': 총 건수,
                'items': [낙찰정보 리스트],
                'pageNo': 현재 페이지,
                'numOfRows': 페이지당 건수
            }
        """
        # 기본 날짜 설정
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d%H%M")
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d%H%M")

        # 물품 낙찰정보 엔드포인트
        endpoint = f"{self.base_url}/getScsbidListSttusThngPPSSrch"

        params = {
            'serviceKey': self.api_key,
            'pageNo': str(page_no),
            'numOfRows': str(num_rows),
            'inqryDiv': inqry_div,
            'inqryBgnDt': start_date,
            'inqryEndDt': end_date
        }

        # 키워드 추가 (선택사항)
        if keyword:
            params['bidNtceNm'] = keyword

        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()

            # XML 응답 파싱
            root = ET.fromstring(response.text)

            header = root.find('header')
            if header is None:
                raise Exception("응답 구조 오류: header 없음")

            result_code = header.findtext('resultCode', '99')
            result_msg = header.findtext('resultMsg', 'Unknown error')

            if result_code != '00':
                raise Exception(f"API 오류: {result_msg}")

            body = root.find('body')
            if body is None:
                return {'totalCount': 0, 'items': [], 'pageNo': page_no, 'numOfRows': num_rows}

            # 총 건수
            total_count_elem = body.find('totalCount')
            total_count = int(total_count_elem.text) if total_count_elem is not None else 0

            # 항목 리스트
            items_elem = body.find('items')
            items = []

            if items_elem is not None:
                for item_elem in items_elem.findall('item'):
                    item_dict = {}
                    for child in item_elem:
                        item_dict[child.tag] = child.text
                    if item_dict:
                        items.append(item_dict)

            return {
                'totalCount': total_count,
                'items': items,
                'pageNo': page_no,
                'numOfRows': num_rows
            }

        except requests.exceptions.RequestException as e:
            raise Exception(f"API 호출 실패: {e}")
        except ET.ParseError as e:
            raise Exception(f"XML 파싱 실패: {e}")

    def fetch_awards_by_range(
        self,
        start_date: str,
        end_date: str,
        keyword: str = None,
        max_results: int = 500
    ) -> List[Dict]:
        """
        긴 기간의 낙찰정보를 1주일씩 나눠서 조회 (API 제약 1주일)

        Args:
            start_date: 조회시작일시 (YYYYMMDDHHMM)
            end_date: 조회종료일시 (YYYYMMDDHHMM)
            keyword: 검색 키워드
            max_results: 최대 결과 수

        Returns:
            전체 낙찰정보 리스트
        """
        all_items = []

        # 문자열을 datetime으로 변환
        start_dt = datetime.strptime(start_date[:8], "%Y%m%d")
        end_dt = datetime.strptime(end_date[:8], "%Y%m%d")

        current_start = start_dt

        while current_start <= end_dt:
            # 1주일 단위로 끝 날짜 설정
            current_end = min(current_start + timedelta(days=6), end_dt)

            # API 호출
            week_start = current_start.strftime("%Y%m%d%H%M").replace('%H%M', '0000')
            week_end = current_end.strftime("%Y%m%d%H%M").replace('%H%M', '2359')

            try:
                result = self.fetch_awards(
                    start_date=week_start,
                    end_date=week_end,
                    keyword=keyword,
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

    def fetch_all_awards(
        self,
        start_date: str = None,
        end_date: str = None,
        max_pages: int = 10
    ) -> List[Dict]:
        """
        전체 낙찰정보 수집 (페이징 자동 처리)

        Args:
            start_date: 조회시작일시
            end_date: 조회종료일시
            max_pages: 최대 페이지 수 (무한루프 방지)

        Returns:
            전체 낙찰정보 리스트
        """
        all_items = []
        page_no = 1

        while page_no <= max_pages:
            result = self.fetch_awards(
                start_date=start_date,
                end_date=end_date,
                page_no=page_no,
                num_rows=100
            )

            items = result.get('items', [])
            if not items:
                break

            all_items.extend(items)

            # 마지막 페이지 확인
            total_count = result.get('totalCount', 0)
            current_count = page_no * result.get('numOfRows', 100)

            if current_count >= total_count:
                break

            page_no += 1

        return all_items

    def search_by_keyword(
        self,
        keywords: List[str],
        start_date: str = None,
        end_date: str = None,
        max_results: int = 100
    ) -> List[Dict]:
        """
        키워드로 낙찰정보 검색

        Args:
            keywords: 검색 키워드 리스트 (예: ['울타리', '차양', '펜스'])
            start_date: 조회시작일시
            end_date: 조회종료일시
            max_results: 최대 결과 수

        Returns:
            필터링된 낙찰정보 리스트
        """
        all_items = self.fetch_all_awards(start_date, end_date, max_pages=5)

        # 키워드 필터링
        filtered = []
        for item in all_items:
            bid_name = item.get('bidNtceNm', '')
            if any(keyword in bid_name for keyword in keywords):
                filtered.append(item)

                if len(filtered) >= max_results:
                    break

        return filtered

    @staticmethod
    def categorize_bid(bid_name: str) -> str:
        """공고명에서 카테고리 자동 분류"""
        if any(kw in bid_name for kw in ['울타리', '펜스', '난간']):
            return '울타리'
        elif any(kw in bid_name for kw in ['차양', '캐노피', '텐트']):
            return '차양'
        else:
            return '기타'

    @staticmethod
    def extract_region(dminstt_nm: str) -> str:
        """발주기관명에서 지역 추출"""
        if not dminstt_nm:
            return '기타'

        # 예: "경기도 용인시" -> "경기"
        regions = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
                   '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주']

        for region in regions:
            if region in dminstt_nm:
                return region

        return '기타'

    @staticmethod
    def calculate_estimated_price(sucsf_bid_amt: int, sucsf_bid_rate: float) -> int:
        """낙찰금액과 낙찰률로 예정가격 역산"""
        if not sucsf_bid_amt or not sucsf_bid_rate or sucsf_bid_rate == 0:
            return 0

        return int(sucsf_bid_amt / (sucsf_bid_rate / 100))


if __name__ == "__main__":
    # 테스트 코드
    client = G2BAPIClient()

    print("=== 나라장터 낙찰정보 API 테스트 ===\n")

    # 최근 30일 데이터 조회
    result = client.fetch_awards(num_rows=5)
    print(f"총 {result['totalCount']}건 중 {len(result['items'])}건 조회\n")

    # 샘플 출력
    for item in result['items'][:3]:
        print(f"공고명: {item.get('bidNtceNm')}")
        print(f"낙찰업체: {item.get('bidwinnrNm')}")
        print(f"낙찰률: {item.get('sucsfbidRate')}%")
        print(f"참가업체: {item.get('prtcptCnum')}개")
        print(f"카테고리: {client.categorize_bid(item.get('bidNtceNm', ''))}")
        print(f"지역: {client.extract_region(item.get('dminsttNm', ''))}")
        print("-" * 50)

    # 키워드 검색
    print("\n=== 울타리/차양 검색 ===\n")
    filtered = client.search_by_keyword(['울타리', '차양'], max_results=3)
    print(f"{len(filtered)}건 발견")
    for item in filtered:
        print(f"- {item.get('bidNtceNm')}")
