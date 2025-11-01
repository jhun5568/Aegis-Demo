"""
나라장터 낙찰정보 API 테스트 스크립트
1시간 후 실행: python utils/g2b_api_test.py
"""
import os
import sys
import requests
import json
from dotenv import load_dotenv

# 윈도우 콘솔 인코딩 설정
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# .env 로드
load_dotenv()

def test_g2b_award_api():
    """낙찰정보 API 테스트"""

    api_key = os.getenv('G2B_API_KEY')
    if not api_key:
        print("❌ G2B_API_KEY가 .env에 없습니다.")
        return

    print(f"✅ API Key 로드 완료: {api_key[:20]}...")

    # 낙찰정보 API 엔드포인트
    url = "https://apis.data.go.kr/1230000/as/ScsbidInfoService/getScsbidListSttusCnstwk"

    params = {
        'serviceKey': api_key,
        'pageNo': '1',
        'numOfRows': '3',
        'type': 'json',
        'inqryDiv': '1',  # 1=등록일시, 2=공고일시, 3=개찰일시
        'inqryBgnDt': '202501010000',
        'inqryEndDt': '202501312359'
    }

    print("\n📡 API 호출 중...")
    print(f"URL: {url}")
    print(f"기간: 2025-01-01 ~ 2025-01-31")

    try:
        response = requests.get(url, params=params, timeout=30)

        print(f"\n🔍 응답 상태: {response.status_code}")

        if response.status_code == 200:
            print("✅ API 호출 성공!")

            data = response.json()
            print("\n📋 응답 구조:")
            print(json.dumps(data, indent=2, ensure_ascii=False))

            # 중요 필드 확인
            if 'response' in data and 'body' in data['response']:
                body = data['response']['body']
                items = body.get('items', [])

                print(f"\n✅ 총 {len(items)}건 조회")

                if items:
                    print("\n🔍 첫 번째 데이터 상세:")
                    first_item = items[0] if isinstance(items, list) else items

                    # 핵심 필드 확인
                    print(f"- 입찰공고번호: {first_item.get('bidNtceNo', 'N/A')}")
                    print(f"- 공고명: {first_item.get('bidNtceNm', 'N/A')}")
                    print(f"- 낙찰업체: {first_item.get('bidwinnrNm', 'N/A')}")
                    print(f"- 낙찰금액: {first_item.get('sucsfbidAmt', 'N/A')}")
                    print(f"- 낙찰률: {first_item.get('sucsfbidRate', 'N/A')}")

                    # ⭐ 중요: 기술점수 관련 필드 확인
                    print("\n⭐ 2단계 경쟁입찰 관련 필드:")
                    tech_fields = ['tchscrEvlMth', 'evlScore', 'prcEvlScore', 'tchscrScore']
                    for field in tech_fields:
                        if field in first_item:
                            print(f"  ✅ {field}: {first_item[field]}")

                    print("\n📄 전체 필드 목록:")
                    for key in first_item.keys():
                        print(f"  - {key}")

        elif response.status_code == 401:
            print("❌ 인증 실패 (401)")
            print("💡 아직 트래픽 활성화가 안된 것 같습니다.")
            print("💡 10~20분 후 다시 시도하세요.")

        else:
            print(f"❌ 오류 발생: {response.status_code}")
            print(response.text[:500])

    except Exception as e:
        print(f"❌ 예외 발생: {e}")

if __name__ == "__main__":
    test_g2b_award_api()
