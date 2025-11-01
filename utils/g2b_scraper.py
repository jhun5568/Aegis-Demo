"""
나라장터 웹스크래핑
JavaScript 렌더링을 포함한 동적 페이지 크롤링
"""
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from typing import List, Dict
import json


class G2BScraper:
    """나라장터 웹사이트 스크래퍼"""

    def __init__(self):
        self.base_url = "https://www.g2b.go.kr/ep/tbid/tbidFnsh.do"

    async def search_bids(
        self,
        keyword: str,
        start_date: str,  # YYYYMMDD
        end_date: str,    # YYYYMMDD
        category: str = "9000000"  # 9000000=물품
    ) -> List[Dict]:
        """
        나라장터에서 입찰공고 검색

        Args:
            keyword: 검색 키워드 (예: '울타리')
            start_date: 시작 날짜 (YYYYMMDD)
            end_date: 종료 날짜 (YYYYMMDD)
            category: 카테고리 (9000000=물품)

        Returns:
            입찰공고 목록
        """
        results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                # URL 구성
                url = f"{self.base_url}?taskClCode={category}&searchKey={keyword}&fromBidDt={start_date}&toBidDt={end_date}"

                print(f"페이지 로딩: {url}")
                await page.goto(url, wait_until="load", timeout=60000)

                # 페이지 로드 대기 (JavaScript 실행 완료 대기)
                await page.wait_for_timeout(5000)

                # 테이블이 로드될 때까지 대기
                try:
                    await page.wait_for_selector("table", timeout=10000)
                    print("테이블 발견")
                except:
                    print("테이블 대기 실패 - 계속 진행")

                # HTML 추출
                html = await page.content()

                # BeautifulSoup으로 파싱
                soup = BeautifulSoup(html, "html.parser")

                # 테이블 찾기
                tables = soup.find_all("table")
                print(f"테이블 개수: {len(tables)}")

                if not tables:
                    print("테이블을 찾을 수 없습니다.")
                    return results

                # 데이터 테이블 (보통 3번째 테이블)
                for table_idx, table in enumerate(tables):
                    rows = table.find_all("tr")
                    print(f"테이블 {table_idx}: {len(rows)}행")

                    if len(rows) > 10:  # 데이터가 있는 테이블
                        print(f"  → 데이터 테이블로 선택")

                        # 헤더 추출
                        header_row = rows[0]
                        headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
                        print(f"  헤더: {headers}")

                        # 데이터 행 추출
                        for row in rows[1:]:
                            cells = row.find_all("td")
                            if not cells:
                                continue

                            # 각 셀 텍스트 추출
                            cell_texts = [cell.get_text(strip=True) for cell in cells]

                            # 최소한의 데이터 검증
                            if len(cell_texts) >= 5:
                                bid_data = {
                                    "no": cell_texts[0],
                                    "category": cell_texts[1],
                                    "bid_no": cell_texts[2],
                                    "bid_name": cell_texts[3],
                                    "bid_type": cell_texts[4],
                                    "agency": cell_texts[5] if len(cell_texts) > 5 else "",
                                    "agency_class": cell_texts[6] if len(cell_texts) > 6 else "",
                                    "open_date": cell_texts[7] if len(cell_texts) > 7 else "",
                                    "announcement_date": cell_texts[8] if len(cell_texts) > 8 else "",
                                }
                                results.append(bid_data)
                                print(f"  추가: {bid_data['bid_name'][:50]}")

                        break  # 첫 데이터 테이블만 처리

            except Exception as e:
                print(f"오류: {type(e).__name__} - {str(e)}")

            finally:
                await browser.close()

        return results


async def main():
    """테스트"""
    scraper = G2BScraper()

    results = await scraper.search_bids(
        keyword="울타리",
        start_date="20251001",
        end_date="20251031",
        category="9000000"
    )

    print(f"\n=== 검색 결과: {len(results)}건 ===")
    for i, item in enumerate(results, 1):
        print(f"{i}. {item['bid_no']} - {item['bid_name'][:60]}")

    # JSON으로 저장
    with open("scraper_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nscraper_results.json 저장 완료")


if __name__ == "__main__":
    asyncio.run(main())
