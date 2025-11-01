"""
Gemini 기반 입찰 전략 조언
"""
import os
import google.generativeai as genai
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()


class BidAdvisor:
    """Gemini Flash를 이용한 입찰 전략 조언"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

    def get_strategic_advice(
        self,
        bid_info: Dict,
        statistics: Dict,
        recommendations: Dict,
        our_cost: int = None
    ) -> str:
        """
        입찰 전략 조언 생성

        Args:
            bid_info: 입찰 정보 {'bid_name': str, 'estimated_price': int, ...}
            statistics: 낙찰률 통계 (BidStatistics 객체의 dict)
            recommendations: 추천 입찰가 정보
            our_cost: 우리 원가

        Returns:
            전략 조언 텍스트
        """
        prompt = self._build_prompt(bid_info, statistics, recommendations, our_cost)

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"AI 조언 생성 실패: {str(e)}"

    def _build_prompt(
        self,
        bid_info: Dict,
        statistics: Dict,
        recommendations: Dict,
        our_cost: Optional[int]
    ) -> str:
        """프롬프트 생성"""

        # 통계 정보
        stats_text = f"""
- 분석 대상: {statistics['sample_count']}건
- 평균 낙찰률: {statistics['avg_rate']}%
- 낙찰률 범위: {statistics['min_rate']}% ~ {statistics['max_rate']}%
- 표준편차: {statistics['std_rate']}%
- 신뢰도: {statistics['confidence_level']}
"""

        # 추천 입찰가 정보
        recs_text = ""
        for strategy, data in recommendations.items():
            strategy_kr = {'aggressive': '공격적', 'neutral': '중립', 'safe': '안전'}[strategy]
            recs_text += f"\n{strategy_kr}:\n"
            recs_text += f"  - 입찰가: {data['price']:,}원 ({data['rate']}%)\n"
            recs_text += f"  - 예상 낙찰 확률: {data['probability']}%\n"
            if data.get('profit_rate'):
                recs_text += f"  - 예상 수익률: {data['profit_rate']}%\n"

        # 원가 정보
        cost_text = ""
        if our_cost:
            cost_rate = round((our_cost / bid_info['estimated_price']) * 100, 2)
            cost_text = f"\n우리 원가: {our_cost:,}원 (원가율 {cost_rate}%)"

        prompt = f"""
당신은 공공입찰 전문 컨설턴트입니다. 다음 입찰에 대한 전략적 조언을 제공하세요.

## 입찰 정보
- 공고명: {bid_info.get('bid_name', 'N/A')}
- 예정가격: {bid_info['estimated_price']:,}원
- 지역: {bid_info.get('region', 'N/A')}
- 카테고리: {bid_info.get('category', 'N/A')}{cost_text}

## 과거 낙찰 통계
{stats_text}

## AI 추천 입찰가
{recs_text}

## 요청사항
다음 내용을 **200자 이내**로 간결하게 답변하세요:

1. 어떤 전략(공격적/중립/안전)을 선택해야 할까요? 그 이유는?
2. 이 입찰의 주요 위험 요소 1가지
3. 낙찰 성공을 위한 핵심 조언 1가지

답변은 친근하고 실용적으로 작성하세요.
"""
        return prompt


if __name__ == "__main__":
    # 테스트 코드
    from utils.g2b_api_client import G2BAPIClient
    from utils.g2b_statistics import BidAnalyzer

    print("=== Gemini 입찰 조언 테스트 ===\n")

    # 낙찰 데이터 수집
    client = G2BAPIClient()
    awards = client.fetch_awards(num_rows=100)

    # 통계 분석
    analyzer = BidAnalyzer(awards['items'])
    result = analyzer.recommend_bid_price(
        estimated_price=200_000_000,
        our_cost=160_000_000,
        category=None,
        region=None
    )

    if 'error' in result:
        print(result['error'])
    else:
        # AI 조언 생성
        advisor = BidAdvisor()

        bid_info = {
            'bid_name': '2025년 울타리 설치 공사',
            'estimated_price': 200_000_000,
            'region': '경기',
            'category': '울타리'
        }

        stats_dict = {
            'sample_count': result['statistics'].sample_count,
            'avg_rate': result['statistics'].avg_rate,
            'min_rate': result['statistics'].min_rate,
            'max_rate': result['statistics'].max_rate,
            'std_rate': result['statistics'].std_rate,
            'confidence_level': result['statistics'].confidence_level
        }

        advice = advisor.get_strategic_advice(
            bid_info=bid_info,
            statistics=stats_dict,
            recommendations=result['recommendations'],
            our_cost=160_000_000
        )

        print("📊 통계 분석 결과:")
        print(f"  평균 낙찰률: {stats_dict['avg_rate']}%")
        print(f"  샘플 수: {stats_dict['sample_count']}건")

        print("\n💡 AI 전략 조언:")
        print(advice)
