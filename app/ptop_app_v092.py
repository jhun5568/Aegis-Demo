"""
PTOP v092 (radio navigation + light wrappers)

Keeps v0.91 features but replaces tab UI with a sidebar radio to reduce rerun-related view resets.
Large business logic stays in v0.91 (UnifiedQuotationSystem and helpers) to minimize risk.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

# Reuse v0.91 internals
from app.ptop_app_v091 import (
    get_tenant_from_params,
    UnifiedQuotationSystem,
    create_enhanced_search_interface,
)

APP_VERSION = "092"


# (DEV helpers were removed by rollback)


def _tenant_controls(tenant_id: str):
    with st.sidebar:
        st.subheader("회사 전환")
        current = tenant_id
        st.info(f"현재 회사: {current}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("dooho", key="ptop92_tenant_dooho", use_container_width=True, disabled=(tenant_id == 'dooho')):
                st.query_params["tenant"] = 'dooho'
                st.rerun()
        with col2:
            if st.button("kukje", key="ptop92_tenant_kukje", use_container_width=True, disabled=(tenant_id == 'kukje')):
                st.query_params["tenant"] = 'kukje'
                st.rerun()


def _ensure_qs(tenant_id: str) -> UnifiedQuotationSystem:
    if 'qs_092' not in st.session_state or st.session_state.get('qs_092_tenant') != tenant_id:
        st.session_state.qs_092 = UnifiedQuotationSystem(tenant_id)
        st.session_state.qs_092_tenant = tenant_id
    return st.session_state.qs_092


def _render_inventory(data: dict):
    st.header("📦 재고 현황")
    inv = data.get('inventory')
    if inv is None or len(inv) == 0:
        st.info("재고 데이터가 없습니다.")
        return
    try:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("품목 수", f"{len(inv)}")
        with col2:
            col_name = None
            for c in ["보유재고", "가용재고", "available", "stock"]:
                if c in inv.columns:
                    col_name = c
                    break
            if col_name:
                st.metric("보유 재고 합계", f"{pd.to_numeric(inv[col_name], errors='coerce').fillna(0).sum():,}")
    except Exception:
        pass
    st.dataframe(inv, use_container_width=True)


def _render_bom_editor(qs: UnifiedQuotationSystem, data: dict, tenant_id: str):
    st.header("🧩 BOM 편집")
    # 검색 우선: 대량 로딩을 피하기 위해 최소 2자 검색어 요구
    col_search, col_select = st.columns([1, 1])
    with col_search:
        keyword = st.text_input("모델 검색(부분 단어, 2자 이상)", value="", key="bom_edit_keyword")
    if not keyword or len(str(keyword).strip()) < 2:
        st.info("모델명을 2자 이상 입력하면 검색합니다.")
        return
    try:
        with st.spinner("모델 검색 중..."):
            models = qs.engine.search_models(str(keyword).strip())
            if not isinstance(models, pd.DataFrame):
                models = pd.DataFrame()
    except Exception as e:
        st.error(f"모델 검색 오류: {e}")
        return
    with col_select:
        choices = models['model_name'].tolist() if 'model_name' in models.columns else []
        sel_name = st.selectbox("모델 선택", choices, key="bom_edit_model")
    if not sel_name:
        return
    row = models[models['model_name'] == sel_name]
    if row.empty:
        st.warning("선택한 모델 정보를 찾을 수 없습니다.")
        return
    model_id = row.iloc[0].get('model_id')

    # 서버측 축소 조회 + 페이징
    page_key = f"bom_page_{model_id}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0
    per_page = 100
    offset = st.session_state[page_key] * per_page

    try:
        with st.spinner("BOM 불러오는 중..."):
            q = qs.engine.db.schema('ptop').table('bom')\
                .select('material_name,standard,quantity,unit,category,created_at,updated_at')\
                .eq('tenant_id', tenant_id)\
                .eq('model_id', model_id)\
                .order('created_at', desc=False)\
                .range(offset, offset + per_page - 1)
            res = q.execute()
            bom = pd.DataFrame(res.data or [])
    except Exception:
        bom = pd.DataFrame()

    # 원본 컬럼 보관(업데이트/업서트 시 재사용, 분류/메모/단가/타입)
    aux_cols = ['unit_price', 'notes', 'material_type', 'category']
    aux_map = {}
    if not bom.empty:
        for _, r in bom.iterrows():
            key = (str(r.get('material_name','')).strip(), str(r.get('standard','')).strip())
            aux_map[key] = {c: r.get(c) for c in aux_cols}

    # 표시용 컬럼 8개 구성
    disp = pd.DataFrame()
    if not bom.empty:
        disp = pd.DataFrame({
            'model_name': [sel_name]*len(bom),
            '자재명': bom.get('material_name', pd.Series([None]*len(bom))),
            '규격': bom.get('standard', pd.Series([None]*len(bom))),
            '수량': pd.to_numeric(bom.get('quantity', pd.Series([0]*len(bom))), errors='coerce').fillna(0),
            '단위': bom.get('unit', pd.Series([None]*len(bom))),
            '분류': bom.get('category', pd.Series([None]*len(bom))),
            'created_at': pd.to_datetime(bom.get('created_at', pd.Series([None]*len(bom))), errors='coerce').dt.date.astype('string'),
            'updated_at': pd.to_datetime(bom.get('updated_at', pd.Series([None]*len(bom))), errors='coerce').dt.date.astype('string'),
        })

    st.subheader("현재 BOM")
    editor_cfg = {
        'model_name': st.column_config.TextColumn('model_name', disabled=True),
        '자재명': st.column_config.TextColumn('자재명'),
        '규격': st.column_config.TextColumn('규격'),
        '수량': st.column_config.NumberColumn('수량', min_value=0.0, step=0.1),
        '단위': st.column_config.TextColumn('단위'),
        '분류': st.column_config.TextColumn('분류'),
        'created_at': st.column_config.TextColumn('created_at', disabled=True),
        'updated_at': st.column_config.TextColumn('updated_at', disabled=True),
    }
    edited = st.data_editor(
        disp,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",  # 행 삭제/추가 가능(삭제는 저장 시 정책으로 필터)
        column_config=editor_cfg,
        key=f"bom_editor_{model_id}"
    )

    # 페이징 컨트롤
    colp1, colp2, colp3 = st.columns([1,1,6])
    with colp1:
        if st.button("⬅️ 이전") and st.session_state[page_key] > 0:
            st.session_state[page_key] -= 1
            st.rerun()
    with colp2:
        # 다음 페이지 유무를 간단히 판단: 현재 로우가 꽉 찼으면 다음 가능성
        if len(disp) >= per_page:
            if st.button("다음 ➡️"):
                st.session_state[page_key] += 1
                st.rerun()

    # 변경사항 저장 처리
    if st.button("변경사항 저장", type="primary"):
        try:
            # 키 계산(자재명+규격)
            def _key_df(df):
                if df is None or df.empty:
                    return set()
                return set((str(r['자재명']).strip(), str(r['규격']).strip()) for _, r in df.iterrows())

            orig_keys = _key_df(disp)
            new_keys = _key_df(edited)

            added = new_keys - orig_keys
            deleted = orig_keys - new_keys
            common = orig_keys & new_keys

            # 세션에 저장된 '이번 세션에서 추가한 키' 가져오기
            added_session_key = f"bom_added_keys_{model_id}"
            session_added = set(st.session_state.get(added_session_key, []))

            # 1) 삭제 처리: MANUAL 분류 전체 삭제 허용(안전 정책)
            refused_deletes = []
            for k in deleted:
                orig_cat = (aux_map.get(k, {}) or {}).get('category')
                if str(orig_cat).upper() == 'MANUAL':
                    qs.engine.delete_bom_item(model_id=model_id, material_name=k[0], standard=k[1])
                else:
                    refused_deletes.append(k)

            # 2) 추가 처리: 새로 추가된 행 insert
            upsert_rows = []
            for k in added:
                row = edited[(edited['자재명'].astype(str).str.strip() == k[0]) & (edited['규격'].astype(str).str.strip() == k[1])].iloc[0]
                upsert_rows.append({
                    'tenant_id': tenant_id,
                    'model_id': model_id,
                    'model_name': sel_name,
                    'material_name': k[0],
                    'standard': k[1],
                    'quantity': float(row.get('수량') or 0),
                    'unit': str(row.get('단위') or 'EA'),
                    'category': str(row.get('분류') or 'MANUAL'),
                    'material_type': 'SUB',
                    'notes': (aux_map.get(k, {}) or {}).get('notes', ''),
                    'unit_price': (aux_map.get(k, {}) or {}).get('unit_price', 0),
                })

            # 3) 변경 처리: 공통 키에서 값이 달라진 경우 delete+add
            for k in common:
                row_o = disp[(disp['자재명'].astype(str).str.strip() == k[0]) & (disp['규격'].astype(str).str.strip() == k[1])].iloc[0]
                row_n = edited[(edited['자재명'].astype(str).str.strip() == k[0]) & (edited['규격'].astype(str).str.strip() == k[1])].iloc[0]
                changed = False
                for col in ['수량','단위','분류','자재명','규격']:
                    if str(row_o.get(col)) != str(row_n.get(col)):
                        changed = True
                        break
                if changed:
                    new_key = (str(row_n.get('자재명')).strip(), str(row_n.get('규격')).strip())
                    upsert_rows.append({
                        'tenant_id': tenant_id,
                        'model_id': model_id,
                        'model_name': sel_name,
                        'material_name': new_key[0],
                        'standard': new_key[1],
                        'quantity': float(row_n.get('수량') or 0),
                        'unit': str(row_n.get('단위') or 'EA'),
                        'category': str(row_n.get('분류') or 'MANUAL'),
                        'material_type': (aux_map.get(k, {}) or {}).get('material_type', 'SUB'),
                        'notes': (aux_map.get(k, {}) or {}).get('notes', ''),
                        'unit_price': (aux_map.get(k, {}) or {}).get('unit_price', 0),
                    })
                    session_added.add(new_key)

            # 배치 업서트 실행
            if upsert_rows:
                try:
                    qs.engine.db.schema('ptop').table('bom').upsert(upsert_rows, on_conflict='tenant_id,model_id,material_name,standard').execute()
                except Exception:
                    # 폴백: 개별 추가
                    for r in upsert_rows:
                        qs.engine.add_bom_item(model_id=r['model_id'], material_data={
                            'material_name': r['material_name'],
                            'standard': r['standard'],
                            'quantity': r['quantity'],
                            'unit': r['unit'],
                            'category': r['category'],
                            'material_type': r.get('material_type','SUB'),
                            'notes': r.get('notes',''),
                            'unit_price': r.get('unit_price',0),
                        })

            # 세션 저장
            st.session_state[added_session_key] = list(session_added)

            if refused_deletes:
                st.warning(f"삭제 불가 항목이 복원됩니다(관리자만 삭제 가능): {len(refused_deletes)}건")
            st.success("변경사항을 반영했습니다.")
            st.rerun()
        except Exception as e:
            st.error(f"저장 중 오류: {e}")

    # 수동 항목 추가 폼
    st.subheader("부자재 직접 추가")
    with st.form("bom_add_manual", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            mat_name = st.text_input("품목명", value="")
            standard = st.text_input("규격", value="")
            unit = st.selectbox("단위", ["EA", "M", "M2", "KG"], index=0)
            qty = st.number_input("수량", min_value=0.0, value=1.0, step=1.0)
            qty_basis = st.radio("수량 산정", ["직접 입력", "경간당"], index=0, horizontal=True, key="bom_qty_basis")
            span_count = st.number_input("경간 수", min_value=1, value=1, step=1, disabled=(qty_basis != "경간당"))
        with col2:
            unit_price = st.number_input("단가(원)", min_value=0.0, value=0.0, step=100.0)
            supplier = st.text_input("업체명(선택)", value="")
            notes = st.text_input("비고(선택)", value="")
        submitted = st.form_submit_button("추가")

    if submitted:
        try:
            # 1) BOM 테이블에 추가 (엔진 재사용)
            eff_qty = qty * (span_count if qty_basis == "경간당" else 1)
            payload = {
                'material_name': mat_name,
                'standard': standard,
                'quantity': eff_qty,
                'unit': unit,
                'category': 'MANUAL',
                'material_type': 'SUB',
                'notes': notes,
                'unit_price': unit_price,
            }
            ok1 = qs.engine.add_bom_item(model_id=model_id, material_data=payload)

            # 2) sub_materials에도 저장(재사용 가능하도록)
            try:
                # Prefer UPSERT to avoid duplicates on (tenant_id, product_name, standard)
                qs.engine.db.schema('ptop').table('sub_materials').upsert({
                    'tenant_id': tenant_id,
                    'product_name': mat_name,
                    'standard': standard,
                    'unit': unit,
                    'unit_price': unit_price,
                    'notes': notes,
                    'supplier': supplier or None,
                }, on_conflict='tenant_id,product_name,standard').execute()
                ok2 = True
            except Exception as e:
                # Fallback to insert if upsert not supported
                try:
                    qs.engine.db.schema('ptop').table('sub_materials').insert({
                        'tenant_id': tenant_id,
                        'product_name': mat_name,
                        'standard': standard,
                        'unit': unit,
                        'unit_price': unit_price,
                        'notes': notes,
                        'supplier': supplier or None,
                    }).execute()
                    ok2 = True
                except Exception as e2:
                    ok2 = False
                    st.warning(f"sub_materials 저장 실패: {e2}")

            if ok1:
                st.success("BOM에 추가되었습니다.")
                # 이번 세션에 추가한 키 기록(삭제 허용 판단용)
                added_session_key = f"bom_added_keys_{model_id}"
                arr = st.session_state.get(added_session_key, [])
                k = (str(mat_name).strip(), str(standard).strip())
                if k not in arr:
                    arr.append(k)
                st.session_state[added_session_key] = arr
                st.rerun()
            else:
                st.error("BOM 추가에 실패했습니다.")
        except Exception as e:
            st.error(f"오류: {e}")


# (BOM 분석) 제거: 현재 탭은 효용이 낮고 오류 가능성 있어 제외


def main(mode: str = "pilot"):
    if 'debug_messages' not in st.session_state:
        st.session_state.debug_messages = []

    try:
        st.set_page_config(page_title=f"PTOP v{APP_VERSION}", layout="wide", initial_sidebar_state="expanded")
    except Exception:
        pass

    tenant_id = get_tenant_from_params()

    st.header(f"🖥️ 업무자동화 시스템 v{APP_VERSION}")
    st.markdown("---")

    if mode == "pilot":
        _tenant_controls(tenant_id)

    if st.session_state.get('debug_messages'):
        st.subheader("디버그 메시지")
        with st.expander("메시지 보기", expanded=True):
            for msg in st.session_state.debug_messages:
                st.warning(msg)
            if st.button("지우기"):
                st.session_state.debug_messages = []
                st.rerun()

    qs = _ensure_qs(tenant_id)
    data = qs.load_data()

    
    if not data:
        st.error("데이터 로딩에 실패했습니다. 파일/접속을 확인해 주세요.")
        return

    with st.sidebar:
        # Persist last-selected view via query param
        views = [
            "🧾 독립 견적 생성",
            "📋 자재 및 실행내역서",
            "📑 발주서 생성",
            "🔍 모델 조회",
            "📦 재고 현황",
            "🧩 BOM 편집",
        ]
        qp_view = st.query_params.get('view')
        if 'ptop92_view' not in st.session_state:
            st.session_state.ptop92_view = qp_view if qp_view in views else views[0]
        view = st.radio("화면", views, index=views.index(st.session_state.ptop92_view), key="ptop92_view")
        if qp_view != view:
            st.query_params['view'] = view

    if view == "🧾 독립 견적 생성":
        qs.create_independent_quotation_interface()
    elif view == "📋 자재 및 실행내역서":
        qs.create_material_execution_interface()
    elif view == "📑 발주서 생성":
        try:
            qs.create_purchase_order_interface()
        except KeyError as e:
            st.error(f"발주서 생성 오류: 누락된 필드 {e}. 입력 데이터(BOM/자재) 구성을 확인해 주세요.")
        except Exception as e:
            st.error(f"발주서 생성 오류: {e}")
    elif view == "🔍 모델 조회":
        st.header("🔍 모델 조회")
        create_enhanced_search_interface(data.get('models', pd.DataFrame()), qs, data.get('bom', pd.DataFrame()))
    elif view == "📦 재고 현황":
        _render_inventory(data)
    elif view == "🧩 BOM 편집":
        _render_bom_editor(qs, data, tenant_id)
    # BOM 분석 탭은 제거


if __name__ == "__main__":
    main()


# RO 토글/환경변수 의존 제거: 항상 쓰기 가능 모드
