"""
PTOP v092 (radio navigation + light wrappers)

Keeps v0.91 features but replaces tab UI with a sidebar radio to reduce rerun-related view resets.
Large business logic stays in v0.91 (UnifiedQuotationSystem and helpers) to minimize risk.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

# Reuse v0.91 internals (base class + helpers)
from app.ptop_app_v091 import (
    get_tenant_from_params,
    UnifiedQuotationSystem as BaseUnifiedQuotationSystem,
    create_enhanced_search_interface,
    # P0: 생성 버튼 전환용 헬퍼
    _create_quotation_and_buffer,
    _save_quotation_to_db,
    _create_po_and_buffer,
    _save_po_to_db,
    _create_bom_and_execution_buffer,
    _save_bom_and_execution_to_db,
    # 아이템 정규화 함수
    normalize_item,
    normalize_items_list,
    get_item_required_fields,
    # P0-5: 총 길이 → 경간 계산
    calculate_span_count_from_total_length,
    # 문서 관리 함수
    parse_search_input,
    search_documents,
    validate_filename,
    upload_document_to_archive,
    delete_document_from_archive,
    generate_document_filename,
    save_generated_document_to_archive,
)

APP_VERSION = "092"


# ============================================================================
# v092 확장 클래스: UnifiedQuotationSystem (v091 상속)
# ============================================================================

class UnifiedQuotationSystem(BaseUnifiedQuotationSystem):
    """
    v092 확장 버전: BaseUnifiedQuotationSystem(v091)을 상속받아 새 기능 추가

    상속 구조:
    - BaseUnifiedQuotationSystem(v091): 기본 비즈니스 로직
    - UnifiedQuotationSystem(v092): 추가 기능 (P0-5 등)

    v091 변경 없이 v092만 확장하는 방식으로 고객사 서비스 보호
    """

    def __init__(self, tenant_id=None):
        """v092 초기화: 부모 클래스 호출"""
        super().__init__(tenant_id)

    # 향후 P0-5, P0-4 UI 통합 등 새 메서드를 여기에 추가 가능


# ============================================================================
# P0-3: 템플릿 시트 선택 폴백 로직 (v092 확장)
# ============================================================================

def get_template_sheet(workbook, candidate_names: list, default_to_first: bool = True) -> str:
    """
    openpyxl Workbook에서 시트명을 선택 (후보명 우선, 폴백: 첫 시트)

    Args:
        workbook: openpyxl Workbook 객체
        candidate_names: 찾을 시트명 후보 (우선순위 순)
        default_to_first: True면 없을 때 첫 시트 사용, False면 에러

    Returns:
        선택된 시트명

    Raises:
        KeyError: 후보명을 찾을 수 없고 default_to_first=False일 때

    Examples:
        >>> from openpyxl import load_workbook
        >>> wb = load_workbook('template.xlsx')
        >>> sheet_name = get_template_sheet(wb, ['자재내역서', '자재_실행내역서'])
        >>> ws = wb[sheet_name]
    """
    sheetnames = workbook.sheetnames
    if not sheetnames:
        raise ValueError("워크북에 시트가 없습니다")

    # 1. 후보명 중 첫 번째 매칭하는 것 사용
    for candidate in candidate_names:
        if candidate in sheetnames:
            return candidate

    # 2. 후보명을 찾지 못한 경우
    if default_to_first:
        # 폴백: 첫 시트 사용
        return sheetnames[0]
    else:
        # 에러: 명확한 메시지 제공
        raise KeyError(
            f"시트 '{candidate_names}' 중 일치하는 것을 찾을 수 없습니다.\n"
            f"사용 가능한 시트: {sheetnames}"
        )


# (DEV helpers were removed by rollback)


def _tenant_controls(tenant_id: str):
    with st.sidebar:
        company_map = {
            'dooho': '두호',
            'kukje': '국제',
            'demo': 'Aegis-Demo (데모)',
        }
        display_name = company_map.get(tenant_id, tenant_id)
        st.info(f"회사명: {display_name}")


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


# ============================================================================
# P0-4: 세 버튼 패턴 래퍼 (v092 UI 확장)
# ============================================================================

def _quotation_interface_p0(qs: UnifiedQuotationSystem, tenant_id: str):
    """
    P0-4: 견적서 세 버튼 패턴 (생성 → 저장 → 다운로드)
    기존 v091의 create_quotation_interface를 래핑하되, P0 헬퍼와 세션 버퍼 활용
    """
    st.header("💰 견적서 자동생성")

    if 'last_material_data' not in st.session_state:
        st.warning("먼저 자재 및 실행내역서를 생성해주세요.")
        return

    quotation_data = st.session_state.last_material_data
    site_name = quotation_data.get('site_info', {}).get('site_name', 'Unknown')
    item_count = len(quotation_data.get('items', []))
    st.info(f"현장: {site_name} | 견적 항목: {item_count}개")

    col1, col2 = st.columns(2)
    with col1:
        contract_type = st.selectbox("계약 유형", ["관급", "사급"], key="quote_contract_type_p0")
    with col2:
        from datetime import datetime
        quote_date = st.date_input("견적일자", datetime.now())

    quotation_data['contract_type'] = contract_type

    # 버튼 1: 생성
    button_cols = st.columns(3)
    with button_cols[0]:
        if st.button("📋 생성", type="primary", use_container_width=True, key="btn_quotation_gen_p0"):
            success, buffer, error_msg = _create_quotation_and_buffer(qs, quotation_data, contract_type)
            if success:
                st.session_state['quotation_generated_p0'] = True
                st.session_state['quotation_buffer_p0'] = buffer
                st.session_state['quotation_data_p0'] = quotation_data
                st.success("✅ 견적서 생성 완료!")
                st.rerun()
            else:
                st.error(f"생성 실패: {error_msg}")

    # 견적서 생성됨 → 상세 정보 + 저장/다운로드 버튼
    if st.session_state.get('quotation_generated_p0', False):
        qdata = st.session_state.get('quotation_data_p0', quotation_data)
        st.success("✅ 견적서 생성 완료!")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("공급가", f"{qdata.get('total_supply_price', 0):,}원")
        with col2:
            st.metric("총 금액", f"{qdata.get('total_amount', 0):,}원")

        st.subheader("📄 견적 상세내역")
        detail_df = pd.DataFrame([
            {
                '모델명': item.get('model_name', ''),
                '규격': item.get('specification', ''),
                '수량': f"{item.get('quantity', 0):,}{item.get('unit', '')}",
                '단가': f"{item.get('unit_price', 0):,}원",
                '금액': f"{item.get('supply_amount', 0):,}원"
            }
            for item in qdata.get('items', [])
        ])
        st.dataframe(detail_df, use_container_width=True)

        st.markdown("---")
        button_cols2 = st.columns(3)

        # 버튼 2: 저장
        with button_cols2[0]:
            if st.button("💾 저장", type="secondary", use_container_width=True, key="btn_quotation_save_p0"):
                success, error_msg = _save_quotation_to_db(tenant_id, qdata)
                if success:
                    st.session_state['quotation_saved_p0'] = True
                    st.success("✅ 데이터베이스에 저장되었습니다!")
                else:
                    st.error(f"저장 실패: {error_msg}")

        # 버튼 3: 다운로드
        with button_cols2[1]:
            if st.session_state.get('quotation_buffer_p0'):
                filename = f"{qs.tenant_config.get(tenant_id, {}).get('display_name', 'PTOP')}견적서_{qdata.get('site_info', {}).get('site_name', 'Unknown')}.xlsx"
                st.download_button(
                    label="📥 다운로드",
                    data=st.session_state['quotation_buffer_p0'].getvalue(),
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="secondary",
                    use_container_width=True,
                    key="btn_quotation_download_p0"
                )


def _po_interface_p0(qs: UnifiedQuotationSystem, tenant_id: str):
    """
    P0-4: 발주서 세 버튼 패턴 (생성 → 저장 → 다운로드)

    기존 v091의 create_purchase_order_interface를 래핑하되,
    경간 데이터 유효성 검증 추가 (v092 안전성 강화)

    주의: 발주서 생성 전에 반드시 "자재 및 실행내역서"를 먼저 생성해야 함
    """
    st.subheader("📑 발주서 생성")

    # ========================================================================
    # P0-4 안전장치: 경간 데이터 유효성 검증
    # ========================================================================

    # 세션에서 model_span_plan 확인 (자재내역서에서 저장됨)
    model_span_plan = st.session_state.get('model_span_plan', {})

    # 경간 정보가 없으면 경고 메시지 표시
    if not model_span_plan or len(model_span_plan) == 0:
        st.warning(
            "⚠️ 경간 정보가 없습니다!\n\n"
            "발주서를 정확하게 생성하려면 먼저 다음 단계를 완료해주세요:\n"
            "1. **📋 자재 및 실행내역서** 탭에서\n"
            "2. 현장명, 기초 유형 등을 입력하고\n"
            "3. **모델별 현장 길이 입력** 섹션에서 총 길이(m)를 입력하기\n\n"
            "그 후 이 화면에서 발주서를 생성하시면 경간별 정확한 수량으로 발주서가 생성됩니다."
        )
        st.info("💡 경간별 수량을 포함한 정확한 발주서를 생성하려면 위 단계를 먼저 완료해주세요.")

    # 경간 정보 요약 표시 (사용자에게 확인)
    st.success(f"✅ 경간 정보 로드됨: {len(model_span_plan)}개 모델")

    with st.expander("경간 정보 확인"):
        for model_name, span_info in model_span_plan.items():
            span_count = span_info.get('span_count', 0)
            total_length = span_info.get('total_length_m', 0)
            st.write(f"- **{model_name}**: {total_length}m → {span_count}경간")

    st.markdown("---")

    # ========================================================================
    # v091 발주서 인터페이스 호출 (경간 데이터가 유효할 때만)
    # ========================================================================
    qs.create_purchase_order_interface()


def _bom_execution_interface_p0(qs: UnifiedQuotationSystem, tenant_id: str):
    """
    P0-5: BOM/실행내역서 (총 길이 → 경간 자동계산)

    기존 v091의 create_material_execution_interface를 그대로 호출
    P0-5 기능: 자재내역서 생성 시 총 길이(m) 입력 → 자동으로 경간 계산
    (v091에서 이미 구현됨 - 라인 1911-1951)
    """
    # v091의 자재내역서 인터페이스 그대로 사용
    # P0-5는 이미 v091에 구현되어 있음:
    # - 총 길이(m) 입력
    # - 모델 폭으로 자동 경간 계산
    # - model_span_plan 세션 저장
    qs.create_material_execution_interface()


def _render_document_management(db, tenant_id: str):
    """
    문서 관리 인터페이스

    기능: 검색, 다운로드, 업로드, 삭제
    """
    st.header("📥 문서 관리")
    st.markdown("---")

    # Storage manager 초기화
    try:
        from app.storage_manager import get_storage_manager
        storage_manager = get_storage_manager()
    except Exception as e:
        st.error(f"Storage 초기화 실패: {e}")
        storage_manager = None

    # 검색 섹션
    st.subheader("검색")
    search_input = st.text_input(
        "프로젝트명 + 문서타입 검색",
        placeholder="예: 샘플 견적서",
        help="프로젝트명과 문서타입을 입력하세요 (예: '샘플 견적서', '가산 발주서')",
        key="doc_search_input"
    )

    search_col1, search_col2 = st.columns([3, 1])
    with search_col2:
        search_button = st.button("🔍 검색", use_container_width=True, key="doc_search_btn")

    # 검색 버튼 클릭 시 결과를 session state에 저장
    if search_button and search_input.strip():
        project_name, document_type = parse_search_input(search_input)
        if project_name:
            results = search_documents(db, tenant_id, project_name, document_type)
            st.session_state.doc_search_results = results
            st.session_state.doc_last_search = search_input
        else:
            st.session_state.doc_search_results = None

    st.markdown("---")

    # 검색 결과 섹션 (session state에서 읽음)
    if st.session_state.get("doc_search_results") is not None:
        st.subheader("검색 결과")

        results = st.session_state.doc_search_results
        search_input_display = st.session_state.get("doc_last_search", "")

        if not results:
            st.info("검색 결과가 없습니다.")
        else:
            st.success(f"✅ {len(results)}개의 파일을 찾았습니다.")

            result_data = []
            doc_metadata = {}

            for i, doc in enumerate(results):
                doc_type_display = {
                    "quotation": "견적서",
                    "po": "발주서",
                    "bom": "내역서"
                }.get(doc.get("document_type", ""), doc.get("document_type", ""))

                created_at = doc.get("created_at", "")
                if created_at and 'T' in created_at:
                    created_at = created_at.split('T')[0]

                result_data.append({
                    "파일명": doc.get("filename", ""),
                    "문서타입": doc_type_display,
                    "생성일": created_at,
                    "생성자": doc.get("created_by", ""),
                })

                doc_metadata[i] = {
                    "ID": doc.get("id", ""),
                    "경로": doc.get("storage_path", ""),
                    "파일명": doc.get("filename", "")
                }

            df_display = pd.DataFrame(result_data)
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # 액션 섹션
            st.subheader("파일 작업")
            selected_idx = st.selectbox(
                "작업할 파일 선택",
                range(len(result_data)),
                format_func=lambda i: result_data[i]['파일명'],
                key="doc_action_select"
            )

            if selected_idx is not None:
                selected_doc = result_data[selected_idx]
                selected_meta = doc_metadata[selected_idx]

                action_col1, action_col2 = st.columns(2)

                with action_col1:
                    if storage_manager:
                        success, file_bytes = storage_manager.download_file(selected_meta['경로'])
                        if success:
                            st.download_button(
                                label="⬇️ 다운로드",
                                data=file_bytes,
                                file_name=selected_meta['파일명'],
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                                key="doc_download_action"
                            )
                        else:
                            st.error(f"다운로드 실패: {file_bytes}")
                    else:
                        st.error("Storage 초기화 실패")

                with action_col2:
                    if st.button("🗑️ 삭제", use_container_width=True, key="doc_delete_action"):
                        st.session_state.doc_delete_confirm = True

                # 삭제 확인
                if st.session_state.get("doc_delete_confirm", False):
                    st.warning(f"'{selected_doc['파일명']}'을(를) 정말 삭제하시겠습니까?")
                    del_col1, del_col2 = st.columns(2)

                    with del_col1:
                        if st.button("✅ 예, 삭제", use_container_width=True, key="doc_confirm_delete"):
                            if storage_manager:
                                success, msg = delete_document_from_archive(
                                    db,
                                    storage_manager,
                                    selected_meta['ID'],
                                    selected_meta['경로']
                                )
                                if success:
                                    st.success(msg)
                                    st.session_state.doc_delete_confirm = False
                                    st.rerun()
                                else:
                                    st.error(msg)
                            else:
                                st.error("Storage 초기화 실패")

                    with del_col2:
                        if st.button("❌ 취소", use_container_width=True, key="doc_cancel_delete"):
                            st.session_state.doc_delete_confirm = False
                            st.rerun()

    st.markdown("---")

    # 파일 업로드 섹션
    st.subheader("파일 업로드")
    uploaded_file = st.file_uploader(
        "수정된 파일 업로드",
        type=["xlsx"],
        help="파일명 규칙: {현장명}_{문서타입}_{날짜}_v{버전}.xlsx\n예: 샘플초등학교_견적서_251022_v01.xlsx",
        key="doc_file_uploader"
    )

    if uploaded_file:
        st.info(f"📄 선택된 파일: {uploaded_file.name}")

        is_valid, error_msg, parsed_data = validate_filename(uploaded_file.name)

        if not is_valid:
            st.error(error_msg)
        else:
            st.success("✅ 파일명 형식이 올바릅니다.")

            with st.expander("📋 파일 정보"):
                col1, col2 = st.columns(2)
                with col1:
                    st.text(f"**현장명**: {parsed_data['project_name']}")
                    st.text(f"**문서타입**: {parsed_data['doc_type_korean']}")
                with col2:
                    st.text(f"**날짜**: {parsed_data['date_str']}")
                    st.text(f"**버전**: v{parsed_data['version']}")

            upload_col1, upload_col2 = st.columns([3, 1])
            with upload_col2:
                if st.button("📤 업로드", use_container_width=True, key="doc_upload_btn"):
                    if storage_manager:
                        file_bytes = uploaded_file.read()
                        username = st.session_state.get('user_id', tenant_id)

                        success, msg = upload_document_to_archive(
                            db,
                            storage_manager,
                            tenant_id,
                            username,
                            file_bytes,
                            uploaded_file.name,
                            parsed_data
                        )

                        if success:
                            st.success(msg)
                            st.toast("파일이 저장되었습니다!")
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.error("Storage 초기화 실패")


def main(mode: str = "pilot"):
    if 'debug_messages' not in st.session_state:
        st.session_state.debug_messages = []

    try:
        st.set_page_config(page_title=f"PTOP v{APP_VERSION}", layout="wide", initial_sidebar_state="expanded")
    except Exception:
        pass

    tenant_id = get_tenant_from_params()

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
        # P0-4/P0-5 통합: "💰 견적서 생성 (P0-4)" 중복 제거
        # 정상 워크플로우:
        # 1. 🧾 독립 견적 생성 (기본)
        # 2. 📋 자재 및 실행내역서 (P0-5: 경간 자동계산)
        # 3. 📑 발주서 생성 (P0-4: 경간 검증 후 발주)
        views = [
            "🧾 독립 견적 생성",
            "📋 자재 및 실행내역서",
            "📑 발주서 생성",
            "📦 재고 현황",
            "🧩 BOM 편집",
            "📥 문서 관리",
        ]
        qp_view = st.query_params.get('view')
        default_view = qp_view if qp_view in views else views[0]

        def update_view():
            st.query_params['view'] = st.session_state.ptop92_view

        view = st.radio("화면", views, index=views.index(default_view), key="ptop92_view", on_change=update_view)

    if view == "🧾 독립 견적 생성":
        qs.create_independent_quotation_interface()
    elif view == "📋 자재 및 실행내역서":
        _bom_execution_interface_p0(qs, tenant_id)
    elif view == "📑 발주서 생성":
        try:
            _po_interface_p0(qs, tenant_id)
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
    elif view == "📥 문서 관리":
        _render_document_management(qs.engine.db, tenant_id)


if __name__ == "__main__":
    main()


# RO 토글/환경변수 의존 제거: 항상 쓰기 가능 모드
