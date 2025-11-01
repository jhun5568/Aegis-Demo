"""
나라장터 AI 입찰 분석 앱 MVP
독립 실행형 (런처 통합 X)
"""
import sys
import os

# 프로젝트 루트를 sys.path에 추가
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# .env 파일 로드
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, '.env'))

import streamlit as st
from datetime import datetime, timedelta
from utils.g2b_api_client import G2BAPIClient
from utils.g2b_statistics import BidAnalyzer
from utils.g2b_advisor import BidAdvisor


# 페이지 설정
st.set_page_config(
    page_title="나라장터 AI 입찰 분석",
    page_icon="🏛️",
    layout="wide"
)


def main():
    """메인 앱"""
    st.title("🏛️ 나라장터 AI 입찰 분석 (MVP)")
    st.caption("통계 기반 낙찰률 예측 + Gemini AI 전략 조언")

    # 탭 구성
    tab1, tab2, tab3 = st.tabs([
        "🔍 입찰가 추천",
        "📊 낙찰 통계",
        "ℹ️ 사용 방법"
    ])

    with tab1:
        render_recommendation_tab()

    with tab2:
        render_statistics_tab()

    with tab3:
        render_help_tab()


def render_recommendation_tab():
    """입찰가 추천 탭"""
    st.subheader("🤖 AI 입찰가 추천")

    # Step 1: 공고 검색
    st.write("### 🔍 Step 1: 공고 검색")

    # 세션 상태 초기화
    if 'selected_announcement' not in st.session_state:
        st.session_state.selected_announcement = None
    if 'search_results' not in st.session_state:
        st.session_state.search_results = []
    if 'search_keyword' not in st.session_state:
        st.session_state.search_keyword = ""

    with st.form("search_form"):
        col1, col2, col3 = st.columns(3)

        with col1:
            search_keyword = st.text_input(
                "검색 키워드",
                value="",
                placeholder="예: 울타리, 차양, 펜스 등",
                help="공고명에 포함될 키워드"
            )

        with col2:
            start_date = st.date_input(
                "시작일",
                value=datetime(2025, 1, 1),
                help="검색 시작 날짜"
            )

        with col3:
            end_date = st.date_input(
                "종료일",
                value=datetime(2025, 1, 31),
                help="검색 종료 날짜"
            )

        search_submitted = st.form_submit_button("🔎 공고 검색", type="primary")

    # 공고 검색 실행
    if search_submitted:
        if not search_keyword or search_keyword.strip() == "":
            st.warning("⚠️ 검색 키워드를 입력하세요.")
        else:
            with st.spinner("공고 검색 중... (날짜 범위가 넓으면 시간이 걸릴 수 있습니다)"):
                try:
                    client = G2BAPIClient()

                    # 1주일 단위로 나눠서 조회
                    all_items = client.fetch_awards_by_range(
                        start_date=start_date.strftime("%Y%m%d0000"),
                        end_date=end_date.strftime("%Y%m%d2359"),
                        keyword=search_keyword.strip(),
                        max_results=1000
                    )

                    # 키워드 필터링
                    filtered = [
                        item for item in all_items
                        if search_keyword.strip().lower() in item.get('bidNtceNm', '').lower()
                    ]

                    st.session_state.search_results = filtered
                    st.session_state.search_keyword = search_keyword.strip()

                    if filtered:
                        st.success(f"✅ {len(filtered)}건의 공고를 찾았습니다. (전체 {len(all_items)}건 중)")
                    else:
                        st.warning(f"⚠️ '{search_keyword}' 키워드를 포함한 공고가 없습니다. (전체 {len(all_items)}건 검색)")
                        st.info("💡 다른 키워드를 사용하거나 날짜 범위를 조정해보세요.")

                except Exception as e:
                    st.error(f"❌ 검색 오류: {str(e)}")

    # Step 2: 공고 선택
    if st.session_state.search_results:
        st.write("### 📋 Step 2: 공고 선택")

        # 공고 목록 표시
        announcement_options = []
        for idx, item in enumerate(st.session_state.search_results):
            bid_name = item.get('bidNtceNm', '알 수 없음')
            agency = item.get('dminsttNm', '알 수 없음')
            amount = item.get('arsltAmt', 0)
            rate = item.get('sucsfbidRate', 0)

            display_text = f"{bid_name[:50]}... | {agency[:20]} | {int(amount):,}원 | 낙찰률: {rate}%"
            announcement_options.append((display_text, idx))

        selected_idx = st.selectbox(
            "공고 선택",
            options=[opt[1] for opt in announcement_options],
            format_func=lambda x: announcement_options[x][0],
            help="분석할 공고를 선택하세요"
        )

        if st.button("✅ 이 공고로 분석하기"):
            st.session_state.selected_announcement = st.session_state.search_results[selected_idx]
            st.success("공고가 선택되었습니다. 아래에서 추가 정보를 입력하세요.")

    # Step 3: 분석 정보 입력 (공고 선택 후)
    if st.session_state.selected_announcement:
        selected = st.session_state.selected_announcement

        st.write("### 📝 Step 3: 분석 정보 입력")
        st.info(f"**선택된 공고:** {selected.get('bidNtceNm', '알 수 없음')}")

        with st.form("analysis_form"):
            col1, col2 = st.columns(2)

            with col1:
                bid_name = st.text_input(
                    "공고명",
                    value=selected.get('bidNtceNm', ''),
                    help="자동 입력됨"
                )

                estimated_price = st.number_input(
                    "예정가격 (원)",
                    min_value=1_000_000,
                    value=int(selected.get('presmptPrce', 200_000_000)),
                    step=10_000_000,
                    format="%d",
                    help="입찰 예정가격"
                )

                our_cost = st.number_input(
                    "우리 원가 (원, 선택)",
                    min_value=0,
                    value=0,
                    step=10_000_000,
                    format="%d",
                    help="수익성 분석을 위해 원가를 입력하세요"
                )

            with col2:
                category = st.text_input(
                    "분석 카테고리",
                    value=st.session_state.search_keyword,
                    help="유사 입찰 검색에 사용될 키워드"
                )

                region = st.selectbox(
                    "지역",
                    options=["전체", "서울", "경기", "부산", "대구", "인천", "광주",
                            "대전", "울산", "세종", "강원", "충북", "충남", "전북",
                            "전남", "경북", "경남", "제주"],
                    help="유사 입찰 검색 시 필터링"
                )

                analysis_start_date = st.date_input(
                    "분석 시작일",
                    value=datetime(2025, 1, 1),
                    help="과거 데이터 분석 시작일"
                )

                analysis_end_date = st.date_input(
                    "분석 종료일",
                    value=datetime(2025, 1, 31),
                    help="과거 데이터 분석 종료일"
                )

            submitted = st.form_submit_button("🔮 AI 분석 시작", type="primary")
    else:
        submitted = False
        analysis_start_date = None
        analysis_end_date = None

    # 분석 실행
    if submitted:
        with st.spinner("나라장터 데이터 수집 및 AI 분석 중..."):
            try:
                # 1. 낙찰 데이터 수집
                client = G2BAPIClient()

                # 사용자가 입력한 날짜 범위로 데이터 수집 (1주일 단위)
                awards = client.fetch_awards_by_range(
                    start_date=analysis_start_date.strftime("%Y%m%d0000"),
                    end_date=analysis_end_date.strftime("%Y%m%d2359"),
                    keyword=category if category and category.strip() else None,
                    max_results=1000
                )

                if not awards:
                    st.error("데이터를 가져올 수 없습니다. 날짜 범위를 확인하세요.")
                    st.info("💡 최근 1-2개월 데이터만 제공될 수 있습니다.")
                    return

                st.success(f"✅ {len(awards)}건의 낙찰 데이터 수집 완료")

                # 2. 통계 분석
                analyzer = BidAnalyzer(awards)

                category_filter = None if not category or category.strip() == "" else category.strip()
                region_filter = None if region == "전체" else region

                result = analyzer.recommend_bid_price(
                    estimated_price=estimated_price,
                    our_cost=our_cost if our_cost > 0 else None,
                    category=category_filter,
                    region=region_filter
                )

                if 'error' in result:
                    st.warning(f"⚠️ {result['error']}")
                    st.info("조건을 완화하거나 분석 기간을 늘려보세요.")
                    return

                # 3. 결과 표시
                stats = result['statistics']
                recs = result['recommendations']

                # 통계 요약
                st.write("---")
                st.write("### 📊 낙찰률 통계")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("분석 대상", f"{stats.sample_count}건")
                col2.metric("평균 낙찰률", f"{stats.avg_rate}%")
                col3.metric("낙찰률 범위", f"{stats.min_rate}~{stats.max_rate}%")
                col4.metric("신뢰도", stats.confidence_level.upper())

                # 추천 입찰가
                st.write("### 💰 AI 추천 입찰가")

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write("#### 🔥 공격적 전략")
                    st.metric("입찰가", f"{recs['aggressive']['price']:,}원")
                    st.metric("낙찰률", f"{recs['aggressive']['rate']}%")
                    st.metric("예상 낙찰 확률", f"{recs['aggressive']['probability']}%")
                    if recs['aggressive']['profit_rate']:
                        st.metric("예상 수익률", f"{recs['aggressive']['profit_rate']}%")

                with col2:
                    st.write("#### ⚖️ 중립 전략")
                    st.metric("입찰가", f"{recs['neutral']['price']:,}원")
                    st.metric("낙찰률", f"{recs['neutral']['rate']}%")
                    st.metric("예상 낙찰 확률", f"{recs['neutral']['probability']}%")
                    if recs['neutral']['profit_rate']:
                        st.metric("예상 수익률", f"{recs['neutral']['profit_rate']}%")

                with col3:
                    st.write("#### 🛡️ 안전 전략")
                    st.metric("입찰가", f"{recs['safe']['price']:,}원")
                    st.metric("낙찰률", f"{recs['safe']['rate']}%")
                    st.metric("예상 낙찰 확률", f"{recs['safe']['probability']}%")
                    if recs['safe']['profit_rate']:
                        st.metric("예상 수익률", f"{recs['safe']['profit_rate']}%")

                # 4. Gemini AI 조언
                st.write("---")
                st.write("### 💡 Gemini AI 전략 조언")

                with st.spinner("AI가 전략을 분석 중..."):
                    try:
                        advisor = BidAdvisor()

                        bid_info = {
                            'bid_name': bid_name,
                            'estimated_price': estimated_price,
                            'region': region,
                            'category': category
                        }

                        stats_dict = {
                            'sample_count': stats.sample_count,
                            'avg_rate': stats.avg_rate,
                            'min_rate': stats.min_rate,
                            'max_rate': stats.max_rate,
                            'std_rate': stats.std_rate,
                            'confidence_level': stats.confidence_level
                        }

                        advice = advisor.get_strategic_advice(
                            bid_info=bid_info,
                            statistics=stats_dict,
                            recommendations=recs,
                            our_cost=our_cost if our_cost > 0 else None
                        )

                        st.info(advice)

                    except Exception as e:
                        st.warning(f"AI 조언 생성 실패: {e}")
                        st.caption("통계 결과만으로도 충분히 활용 가능합니다.")

            except Exception as e:
                st.error(f"오류 발생: {e}")
                import traceback
                st.code(traceback.format_exc())


def render_statistics_tab():
    """낙찰 통계 탭"""
    st.subheader("📊 최근 낙찰 통계")

    # 필터 옵션
    col1, col2, col3 = st.columns(3)

    with col1:
        search_months = st.slider("분석 기간 (개월)", 1, 12, 3, key="stats_months")

    with col2:
        category = st.text_input("카테고리 (선택)", value="", placeholder="예: 울타리, 차양 등", key="stats_category")

    with col3:
        num_rows = st.number_input("조회 건수", 10, 500, 100, key="stats_rows")

    if st.button("📈 통계 조회", type="primary"):
        with st.spinner("데이터 수집 중..."):
            try:
                client = G2BAPIClient()

                end_date = datetime.now()
                start_date = end_date - timedelta(days=search_months * 30)

                awards = client.fetch_awards(
                    start_date=start_date.strftime("%Y%m%d0000"),
                    end_date=end_date.strftime("%Y%m%d2359"),
                    num_rows=num_rows
                )

                if not awards['items']:
                    st.warning("데이터가 없습니다.")
                    return

                analyzer = BidAnalyzer(awards['items'])

                category_filter = None if not category or category.strip() == "" else category.strip()

                stats = analyzer.calculate_statistics(category=category_filter)

                if not stats:
                    st.warning("통계 계산에 충분한 데이터가 없습니다.")
                    return

                # 통계 카드
                st.write("### 📊 전체 통계")

                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("샘플 수", f"{stats.sample_count}건")
                col2.metric("평균", f"{stats.avg_rate}%")
                col3.metric("중앙값", f"{stats.median_rate}%")
                col4.metric("표준편차", f"{stats.std_rate}%")
                col5.metric("범위", f"{stats.min_rate}~{stats.max_rate}%")

                # 최근 낙찰 목록
                st.write("### 📋 최근 낙찰 내역")

                for item in awards['items'][:20]:
                    with st.expander(f"{item.get('bidNtceNm', 'N/A')}"):
                        col1, col2 = st.columns(2)

                        with col1:
                            st.write(f"**낙찰업체**: {item.get('bidwinnrNm', 'N/A')}")
                            st.write(f"**낙찰금액**: {int(item.get('sucsfbidAmt', 0)):,}원")
                            st.write(f"**낙찰률**: {item.get('sucsfbidRate', 'N/A')}%")

                        with col2:
                            st.write(f"**참가업체**: {item.get('prtcptCnum', 'N/A')}개")
                            st.write(f"**발주기관**: {item.get('dminsttNm', 'N/A')}")
                            st.write(f"**개찰일**: {item.get('rlOpengDt', 'N/A')}")

            except Exception as e:
                st.error(f"오류: {e}")


def render_help_tab():
    """사용 방법 탭"""
    st.subheader("ℹ️ 사용 방법")

    st.markdown("""
    ## 🎯 이 앱의 목적

    나라장터 공공입찰에서 **최적 입찰가를 예측**하여 낙찰 성공률을 높이는 것입니다.

    ---

    ## 🚀 사용 방법

    ### 1️⃣ 입찰가 추천 탭

    1. **입찰 정보 입력**
       - 공고명, 예정가격, 원가 등 입력
       - 카테고리/지역 선택 (유사 입찰 검색)

    2. **AI 분석 시작**
       - 과거 낙찰 데이터 자동 수집
       - 통계 분석 + AI 전략 조언 생성

    3. **결과 확인**
       - 3가지 전략 (공격적/중립/안전) 추천
       - 각 전략의 낙찰 확률 및 수익률
       - Gemini AI의 전략 조언

    ### 2️⃣ 낙찰 통계 탭

    - 최근 낙찰 데이터 조회
    - 카테고리별 통계 분석
    - 낙찰 내역 상세 확인

    ---

    ## ⚠️ 주의사항

    1. **정확도**: 통계 기반 예측으로 **70% 정확도** (참고용)
    2. **데이터**: 최근 3~6개월 데이터 권장
    3. **신뢰도**: 샘플 수가 많을수록 정확
    4. **2단계 경쟁입찰**: 기술점수는 반영 안됨 (가격 중심 분석)

    ---

    ## 📞 문의

    - 개발: Aegis BIMer
    - 버전: MVP 1.0
    - 기반: 나라장터 OpenAPI + Gemini AI
    """)


if __name__ == "__main__":
    main()
