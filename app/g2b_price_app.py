"""
G2B 조달청 가격정보 수집 앱
- 독립 실행 가능한 Streamlit 앱
"""

import os
import sys
import streamlit as st
import pandas as pd
from datetime import datetime

# 프로젝트 루트 경로 추가
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from utils.g2b_price_collector import G2BPriceCollector
from app.config_supabase import get_supabase_client

st.set_page_config(
    page_title="G2B 가격정보 수집",
    page_icon="💰",
    layout="wide"
)

st.title("💰 G2B 조달청 가격정보 수집")

# 환경변수에서 API 키 읽기
g2b_api_key = os.getenv('G2B_API_KEY', '')

if not g2b_api_key:
    st.error("❌ G2B_API_KEY 환경변수가 설정되지 않았습니다.")
    st.info("`.env` 파일에 `G2B_API_KEY=YOUR_KEY` 추가 후 재시작하세요.")
    st.stop()

# Supabase 클라이언트
try:
    supabase = get_supabase_client()
    collector = G2BPriceCollector(service_key=g2b_api_key, supabase_client=supabase)
except Exception as e:
    st.error(f"❌ 초기화 실패: {e}")
    st.stop()

# 사이드바: 테넌트 선택
with st.sidebar:
    st.header("⚙️ 설정")
    tenant_id = st.selectbox("회사 선택", ["dooho", "kukje", "demo"])

    st.markdown("---")
    st.markdown("### 📊 작업 모드")

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["🔍 품명 검색", "📦 BOM 기반 수집", "🔄 BOM 단가 업데이트", "📋 수집 이력"])

# 탭 1: 품명 검색
with tab1:
    st.subheader("🔍 품명으로 가격정보 검색")

    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("품명 입력", placeholder="예: 앵글, 소화용기구, H형강")
    with col2:
        num_rows = st.number_input("결과 수", min_value=1, max_value=100, value=10)

    if st.button("🔍 검색", type="primary"):
        if not search_query:
            st.warning("품명을 입력하세요.")
        else:
            with st.spinner(f"'{search_query}' 검색 중..."):
                results = collector.search_price_by_product_name(search_query, num_of_rows=num_rows)

            if results:
                st.success(f"✅ {len(results)}건 발견")

                # 데이터프레임 변환
                df = pd.DataFrame(results)
                display_cols = ['prdct_clsfc_no_nm', 'krn_prdct_nm', 'prce', 'unit', 'ntice_dt', 'bsns_div_nm']
                df_display = df[display_cols].copy()
                df_display.columns = ['품명', '규격명', '가격(원)', '단위', '게시일', '업무구분']

                st.dataframe(df_display, use_container_width=True)

                # DB 저장 버튼
                if st.button("💾 Supabase에 저장"):
                    saved = collector.save_to_supabase(results, tenant_id=tenant_id)
                    st.success(f"✅ {saved}건 저장 완료")
            else:
                st.warning("⚠️ 검색 결과가 없습니다.")

# 탭 2: BOM 기반 수집
with tab2:
    st.subheader("📦 BOM 자재 기반 전체 수집")

    st.info("""
    **동작 방식:**
    1. BOM 테이블에서 고유 자재명 추출
    2. 각 자재에 대해 G2B API 검색
    3. 결과를 Supabase에 자동 저장
    """)

    col1, col2 = st.columns(2)
    with col1:
        delay = st.slider("API 호출 간격(초)", min_value=0.1, max_value=2.0, value=0.5, step=0.1)
    with col2:
        max_per_item = st.number_input("자재당 최대 수집 건수", min_value=1, max_value=20, value=5)

    if st.button("🚀 전체 수집 시작", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        # BOM 자재 조회
        bom_items = supabase.table('bom').select('material_name').eq('tenant_id', tenant_id).execute()
        unique_materials = list(set([item['material_name'] for item in bom_items.data]))

        total = len(unique_materials)
        collected = 0
        saved = 0

        for i, material in enumerate(unique_materials):
            status_text.text(f"[{i+1}/{total}] {material} 검색 중...")

            results = collector.search_price_by_product_name(material, num_of_rows=max_per_item)
            if results:
                collected += len(results)
                saved += collector.save_to_supabase(results, tenant_id=tenant_id)

            progress_bar.progress((i + 1) / total)

        status_text.empty()
        progress_bar.empty()

        st.success(f"""
        ✅ 수집 완료
        - 총 자재: {total}개
        - 수집: {collected}건
        - 저장: {saved}건
        """)

# 탭 3: BOM 단가 업데이트
with tab3:
    st.subheader("🔄 BOM 단가 자동 업데이트")

    st.info("""
    **동작 방식:**
    1. 단가가 없는 BOM 자재 조회
    2. G2B 가격정보와 유사도 매칭 (AI)
    3. 임계값 이상이면 자동 업데이트
    """)

    similarity = st.slider("유사도 임계값 (%)", min_value=50, max_value=100, value=70, step=5)

    if st.button("🔄 단가 업데이트 시작", type="primary"):
        with st.spinner("BOM 단가 업데이트 중..."):
            updated = collector.match_with_bom(tenant_id=tenant_id, similarity_threshold=similarity/100)

        if updated > 0:
            st.success(f"✅ {updated}건 업데이트 완료")
        else:
            st.info("ℹ️ 업데이트할 항목이 없습니다.")

# 탭 4: 수집 이력
with tab4:
    st.subheader("📋 수집된 가격정보 이력")

    try:
        # 최근 수집 데이터 조회
        price_data = supabase.table('g2b_price_info').select('*').eq(
            'tenant_id', tenant_id
        ).eq('is_active', True).order('created_at', desc=True).limit(100).execute()

        if price_data.data:
            df = pd.DataFrame(price_data.data)
            display_cols = ['prdct_clsfc_no_nm', 'krn_prdct_nm', 'prce', 'unit', 'ntice_dt', 'matched_material_name', 'match_score']
            df_display = df[display_cols].copy()
            df_display.columns = ['품명', '규격명', '가격(원)', '단위', '게시일', '매칭 자재명', '유사도(%)']

            st.dataframe(df_display, use_container_width=True)

            # 통계
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("총 수집 건수", len(df))
            with col2:
                matched = df[df['matched_material_name'].notna()]
                st.metric("매칭 완료", len(matched))
            with col3:
                avg_price = df['prce'].mean()
                st.metric("평균 가격", f"{avg_price:,.0f}원")
        else:
            st.info("ℹ️ 수집된 가격정보가 없습니다.")

    except Exception as e:
        st.error(f"❌ 조회 실패: {e}")
