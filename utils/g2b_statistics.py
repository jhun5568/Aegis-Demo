"""
나라장터 낙찰정보 통계 분석
"""
import statistics
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class BidStatistics:
    """낙찰률 통계 결과"""
    sample_count: int           # 분석 대상 건수
    avg_rate: float             # 평균 낙찰률
    min_rate: float             # 최소 낙찰률
    max_rate: float             # 최대 낙찰률
    std_rate: float             # 표준편차
    median_rate: float          # 중앙값

    # 추천 입찰률
    recommended_aggressive: float  # 공격적 (평균 - 1σ)
    recommended_neutral: float     # 중립 (평균)
    recommended_safe: float        # 안전 (평균 + 0.5σ)

    # 신뢰도
    confidence_level: str       # 'high', 'medium', 'low'


class BidAnalyzer:
    """낙찰 데이터 분석기"""

    def __init__(self, awards_data: List[Dict]):
        """
        Args:
            awards_data: g2b_api_client에서 가져온 낙찰정보 리스트
        """
        self.awards_data = awards_data

    def calculate_statistics(
        self,
        category: str = None,
        region: str = None,
        price_min: int = None,
        price_max: int = None
    ) -> Optional[BidStatistics]:
        """
        조건에 맞는 낙찰 데이터의 통계 계산

        Args:
            category: 카테고리 필터 ('울타리', '차양', None=전체)
            region: 지역 필터 ('서울', '경기', None=전체)
            price_min: 최소 낙찰금액
            price_max: 최대 낙찰금액

        Returns:
            BidStatistics 객체 또는 None (데이터 부족 시)
        """
        # 필터링
        filtered = self._filter_data(category, region, price_min, price_max)

        if len(filtered) < 3:
            return None  # 최소 3건 이상 필요

        # 낙찰률 추출
        rates = []
        for item in filtered:
            rate = item.get('sucsfbidRate')
            if rate:
                try:
                    rates.append(float(rate))
                except (ValueError, TypeError):
                    continue

        if len(rates) < 3:
            return None

        # 통계 계산
        avg_rate = statistics.mean(rates)
        min_rate = min(rates)
        max_rate = max(rates)
        std_rate = statistics.stdev(rates) if len(rates) > 1 else 0
        median_rate = statistics.median(rates)

        # 추천 입찰률 계산
        aggressive = max(avg_rate - std_rate, min_rate)  # 너무 낮지 않게
        neutral = avg_rate
        safe = avg_rate + (std_rate * 0.5)  # 약간 여유있게

        # 신뢰도 평가
        confidence = self._evaluate_confidence(len(rates), std_rate)

        return BidStatistics(
            sample_count=len(rates),
            avg_rate=round(avg_rate, 2),
            min_rate=round(min_rate, 2),
            max_rate=round(max_rate, 2),
            std_rate=round(std_rate, 2),
            median_rate=round(median_rate, 2),
            recommended_aggressive=round(aggressive, 2),
            recommended_neutral=round(neutral, 2),
            recommended_safe=round(safe, 2),
            confidence_level=confidence
        )

    def _filter_data(
        self,
        category: str = None,
        region: str = None,
        price_min: int = None,
        price_max: int = None
    ) -> List[Dict]:
        """조건에 맞는 데이터 필터링"""
        from utils.g2b_api_client import G2BAPIClient

        filtered = []
        for item in self.awards_data:
            # 카테고리 필터
            if category:
                bid_name = item.get('bidNtceNm', '')
                item_category = G2BAPIClient.categorize_bid(bid_name)
                if item_category != category:
                    continue

            # 지역 필터
            if region:
                dminstt_nm = item.get('dminsttNm', '')
                item_region = G2BAPIClient.extract_region(dminstt_nm)
                if item_region != region:
                    continue

            # 금액 필터
            if price_min or price_max:
                sucsf_amt = item.get('sucsfbidAmt')
                if sucsf_amt:
                    try:
                        amt = int(sucsf_amt)
                        if price_min and amt < price_min:
                            continue
                        if price_max and amt > price_max:
                            continue
                    except (ValueError, TypeError):
                        continue

            filtered.append(item)

        return filtered

    def _evaluate_confidence(self, sample_count: int, std_rate: float) -> str:
        """
        신뢰도 평가

        Args:
            sample_count: 샘플 수
            std_rate: 표준편차

        Returns:
            'high', 'medium', 'low'
        """
        # 샘플 수와 편차 기반 신뢰도
        if sample_count >= 30 and std_rate < 3.0:
            return 'high'
        elif sample_count >= 10 and std_rate < 5.0:
            return 'medium'
        else:
            return 'low'

    def get_win_probability(
        self,
        our_bid_rate: float,
        statistics: BidStatistics
    ) -> float:
        """
        우리 입찰률에 대한 낙찰 확률 추정 (간단한 모델)

        Args:
            our_bid_rate: 우리 입찰률
            statistics: 낙찰 통계

        Returns:
            낙찰 확률 (0~100%)
        """
        avg = statistics.avg_rate
        std = statistics.std_rate

        if std == 0:
            std = 1.0  # 0으로 나누기 방지

        # Z-score 계산
        z_score = (our_bid_rate - avg) / std

        # 간단한 확률 모델 (정규분포 근사)
        if z_score <= -2:  # 평균보다 2σ 이하
            probability = 95
        elif z_score <= -1:  # 평균보다 1σ 이하
            probability = 70
        elif z_score <= 0:  # 평균 이하
            probability = 50
        elif z_score <= 0.5:  # 평균보다 0.5σ 위
            probability = 30
        elif z_score <= 1:  # 평균보다 1σ 위
            probability = 15
        else:  # 평균보다 1σ 초과
            probability = 5

        return probability

    def recommend_bid_price(
        self,
        estimated_price: int,
        our_cost: int = None,
        category: str = None,
        region: str = None
    ) -> Dict:
        """
        입찰가 추천

        Args:
            estimated_price: 예정가격
            our_cost: 우리 원가 (선택)
            category: 카테고리
            region: 지역

        Returns:
            {
                'statistics': BidStatistics,
                'recommendations': {
                    'aggressive': {'price': int, 'rate': float, 'probability': float},
                    'neutral': {...},
                    'safe': {...}
                },
                'is_profitable': bool (원가 대비)
            }
        """
        # 통계 계산
        stats = self.calculate_statistics(
            category=category,
            region=region,
            price_min=int(estimated_price * 0.5),
            price_max=int(estimated_price * 1.5)
        )

        if not stats:
            return {
                'error': '유사한 입찰 데이터가 부족합니다. (최소 3건 필요)',
                'statistics': None,
                'recommendations': None
            }

        # 3가지 입찰가 계산
        recommendations = {}

        for strategy in ['aggressive', 'neutral', 'safe']:
            if strategy == 'aggressive':
                rate = stats.recommended_aggressive
            elif strategy == 'neutral':
                rate = stats.recommended_neutral
            else:
                rate = stats.recommended_safe

            price = int(estimated_price * (rate / 100))
            probability = self.get_win_probability(rate, stats)

            # 원가 대비 수익성
            is_profitable = True
            profit_rate = None
            if our_cost:
                is_profitable = price > our_cost
                if is_profitable and our_cost > 0:
                    profit_rate = round(((price - our_cost) / our_cost) * 100, 2)

            recommendations[strategy] = {
                'price': price,
                'rate': rate,
                'probability': probability,
                'is_profitable': is_profitable,
                'profit_rate': profit_rate
            }

        return {
            'statistics': stats,
            'recommendations': recommendations
        }


if __name__ == "__main__":
    # 테스트 코드
    from utils.g2b_api_client import G2BAPIClient

    client = G2BAPIClient()
    awards = client.fetch_awards(num_rows=100)

    analyzer = BidAnalyzer(awards['items'])

    # 전체 통계
    stats = analyzer.calculate_statistics()
    if stats:
        print("=== 전체 낙찰률 통계 ===")
        print(f"샘플 수: {stats.sample_count}건")
        print(f"평균: {stats.avg_rate}%")
        print(f"범위: {stats.min_rate}% ~ {stats.max_rate}%")
        print(f"표준편차: {stats.std_rate}%")
        print(f"중앙값: {stats.median_rate}%")
        print(f"\n추천 입찰률:")
        print(f"  공격적: {stats.recommended_aggressive}%")
        print(f"  중립: {stats.recommended_neutral}%")
        print(f"  안전: {stats.recommended_safe}%")
        print(f"\n신뢰도: {stats.confidence_level}")

    # 입찰가 추천 테스트
    print("\n=== 입찰가 추천 예시 ===")
    print("예정가격: 2억원, 원가: 1.6억원")
    result = analyzer.recommend_bid_price(
        estimated_price=200_000_000,
        our_cost=160_000_000
    )

    if 'error' not in result:
        recs = result['recommendations']
        for strategy, data in recs.items():
            print(f"\n{strategy.upper()}:")
            print(f"  입찰가: {data['price']:,}원 ({data['rate']}%)")
            print(f"  낙찰 확률: {data['probability']}%")
            if data['profit_rate']:
                print(f"  예상 수익률: {data['profit_rate']}%")
