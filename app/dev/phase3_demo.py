# -*- coding: utf-8 -*-
"""
DEV - Phase 3 Demo (Quotations / POs / BOM / Execution)

Run: streamlit run app/dev/launcher_dev.py
"""

from __future__ import annotations

from pathlib import Path
from datetime import date as _date
import time as _time
import random as _rand
from typing import List, Dict
import sys

import pandas as pd
import streamlit as st

# Path setup so absolute imports under app/* work
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_APP = _ROOT / 'app'
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from app.dev.config_supabase_dev import (
    DEV_READONLY,
    dev_log_banner,
)
from app.db_supabase_adapter import DatabaseManager


@st.cache_resource(show_spinner=False)
def get_adapter() -> DatabaseManager:
    return DatabaseManager()


# ---------- Column normalization ----------
_SYNONYMS: Dict[str, set] = {
    '품목': {'품목', '품명', '자재명', '모델', '모델명', 'material_name'},
    '규격': {'규격', '완전규격', 'standard'},
    '단위': {'단위', 'unit'},
    '수량': {'수량', '경간당수량', '경간당 수량', 'quantity'},
    '단가': {'단가', '단가(원)', 'unit_price'},
    '금액': {'금액', '공급가액', 'amount'},
    '공급가': {'공급가', '공급가액', 'supply_price'},
    '부가세': {'부가세', 'vat'},
    '합계(VAT포함)': {'합계(VAT포함)', 'total', '합계'},
    '비고': {'비고', 'notes', 'remarks'},
    '모델참조': {'모델참조', '모델명', 'model_reference'},
    '하차지': {'하차지', 'delivery_location'},
    '차량번호': {'차량번호', 'vehicle_number'},
    '납품처': {'납품처', 'delivery_destination'},
    '분류': {'분류', 'category', 'classification'},
    '비율(%)': {'비율(%)', 'rate_percent', '비율_percent', 'ratio'},
}


def _canonize_columns(df: pd.DataFrame) -> pd.DataFrame:
    try:
        mapping = {}
        for col in list(df.columns):
            s = str(col).strip()
            for canon, syns in _SYNONYMS.items():
                if s in syns or s == canon:
                    mapping[col] = canon
                    break
        return df.rename(columns=mapping) if mapping else df
    except Exception:
        return df


def _latest_snapshot(dm: DatabaseManager, tenant_id: str, linked_type: str, linked_id: str):
    try:
        df = dm.get_bom_snapshots(tenant_id, linked_type=linked_type, linked_id=linked_id)
        if df is None or df.empty:
            return {}
        df['__created_at'] = pd.to_datetime(df.get('created_at'), errors='coerce')
        row = df.sort_values(['__created_at']).dropna(subset=['__created_at']).iloc[-1]
        return row.get('payload_json') or {}
    except Exception:
        return {}


def _dedupe_latest(df: pd.DataFrame, id_col: str) -> pd.DataFrame:
    try:
        if df is None or df.empty or id_col not in df.columns:
            return df
        tmp = df.copy()
        if 'created_at' in tmp.columns:
            tmp['__created_at'] = pd.to_datetime(tmp['created_at'], errors='coerce')
            tmp = tmp.sort_values(['__created_at'])
        return tmp.drop_duplicates(subset=[id_col], keep='last').drop(columns=['__created_at'], errors='ignore')
    except Exception:
        return df


def _tenant_selector() -> str:
    st.subheader('회사')
    return st.selectbox('회사', ['dooho', 'kukje'], index=0, key='phase3_tenant')


def _project_selector(dm: DatabaseManager, tenant_id: str) -> str:
    """Show only site name in dropdown, return project_id.
    Only list projects that have PTOP-generated data (Phase 3 traces).
    Sources: quotations.project_id, purchase_orders.project_id,
    bom_snapshots.linked_id for linked_type in ['project','execution'].
    Sorted by latest activity (created_at desc).
    """
    latest_map: dict[str, pd.Timestamp] = {}

    def _upd(pid: str, ts: pd.Timestamp):
        if not pid:
            return
        cur = latest_map.get(pid)
        if cur is None or (pd.notna(ts) and (pd.isna(cur) or ts > cur)):
            latest_map[pid] = ts

    # Quotations
    try:
        qdf = dm.get_quotations(tenant_id)
        if isinstance(qdf, pd.DataFrame) and not qdf.empty and 'project_id' in qdf.columns:
            qdf['__created_at'] = pd.to_datetime(qdf.get('created_at'), errors='coerce')
            for _, r in qdf[['project_id', '__created_at']].dropna(subset=['project_id']).iterrows():
                _upd(str(r['project_id']), r['__created_at'])
    except Exception:
        pass

    # POs
    try:
        pdf = dm.get_purchase_orders(tenant_id)
        if isinstance(pdf, pd.DataFrame) and not pdf.empty and 'project_id' in pdf.columns:
            pdf['__created_at'] = pd.to_datetime(pdf.get('created_at'), errors='coerce')
            for _, r in pdf[['project_id', '__created_at']].dropna(subset=['project_id']).iterrows():
                _upd(str(r['project_id']), r['__created_at'])
    except Exception:
        pass

    # BOM/Execution
    try:
        sdf = dm.get_bom_snapshots(tenant_id, linked_type=None, linked_id=None)
        if isinstance(sdf, pd.DataFrame) and not sdf.empty and 'linked_id' in sdf.columns:
            s = sdf.copy()
            if 'linked_type' in s.columns:
                s = s[s['linked_type'].isin(['project', 'execution'])]
            s['__created_at'] = pd.to_datetime(s.get('created_at'), errors='coerce')
            for _, r in s[['linked_id', '__created_at']].dropna(subset=['linked_id']).iterrows():
                _upd(str(r['linked_id']), r['__created_at'])
    except Exception:
        pass

    if not latest_map:
        return ''

    name_map: dict[str, str] = {}
    try:
        proj_df = dm.get_projects()
        if isinstance(proj_df, pd.DataFrame) and not proj_df.empty and 'project_id' in proj_df.columns:
            for _, r in proj_df.iterrows():
                pid = str(r.get('project_id'))
                name = str(r.get('site_name') or r.get('project_name') or '')
                if pid:
                    name_map[pid] = name or pid
    except Exception:
        pass

    entries = [
        {
            'pid': pid,
            'name': name_map.get(pid, pid),
            'latest': latest_map.get(pid)
        }
        for pid in latest_map.keys()
    ]
    try:
        entries.sort(key=lambda x: (pd.isna(x['latest']), x['latest']), reverse=True)
    except Exception:
        entries.sort(key=lambda x: x['name'])

    sel = st.selectbox('프로젝트 선택', entries, index=0, key='global_project',
                       format_func=lambda o: (o.get('name') if isinstance(o, dict) else str(o)))
    return sel.get('pid') if isinstance(sel, dict) else str(sel)


def _quotations_view(dm: DatabaseManager, tenant_id: str, project_id: str):
    st.header('견적')

    # 삭제 버튼
    col1, col2 = st.columns([5, 1])
    with col2:
        if st.button('❌ 삭제', key=f'q_delete_{project_id}', help='모든 견적 스냅샷 삭제'):
            try:
                # 독립 견적은 project_id가 없으므로 linked_type만 사용해서 모두 삭제
                snapshots_df = dm.get_bom_snapshots(tenant_id, linked_type='independent_quotation')
                if isinstance(snapshots_df, pd.DataFrame) and not snapshots_df.empty:
                    deleted_count = 0
                    for _, row in snapshots_df.iterrows():
                        snapshot_id = row.get('id')
                        if snapshot_id:
                            dm.supabase.table('bom_snapshots').delete().eq('id', snapshot_id).execute()
                            deleted_count += 1
                    st.success(f'✅ {deleted_count}개 삭제됨')
                    st.rerun()
                else:
                    st.info('삭제할 데이터 없음')
            except Exception as e:
                st.error(f'삭제 실패: {e}')

    df = _dedupe_latest(dm.get_quotations(tenant_id), 'quotation_id')
    f = df.copy()
    if 'project_id' in f.columns and project_id:
        f = f[f['project_id'].astype(str) == str(project_id)]
    show_cols = [c for c in ['quotation_id', 'tenant_id', 'customer_id', 'project_id', 'status', 'total_amount', 'created_at'] if c in f.columns]
    edit_df = st.data_editor(f[show_cols] if not f.empty and show_cols else f,
                             use_container_width=True, hide_index=True, num_rows='dynamic',
                             key=f'q_editor_{project_id}')
    if st.button('저장(견적)', key=f'q_save_{project_id}'):
        try:
            orig = f.set_index('quotation_id') if 'quotation_id' in f.columns else f
            new = edit_df.set_index('quotation_id') if 'quotation_id' in edit_df.columns else edit_df
            ids = set(orig.index).intersection(set(new.index)) if not orig.empty and not new.empty else set()
            for qid in ids:
                ro = orig.loc[qid]
                rn = new.loc[qid]
                changes = {}
                for col in ['customer_id', 'project_id', 'status', 'total_amount']:
                    if col in rn.index and str(ro.get(col)) != str(rn.get(col)):
                        changes[col] = rn.get(col)
                if changes:
                    dm.update_quotation(qid, **changes)
            st.success('저장 완료')
            st.rerun()
        except Exception as e:
            st.error(f'저장 실패: {e}')


def _po_view(dm: DatabaseManager, tenant_id: str, project_id: str):
    st.header('발주')

    # 삭제 버튼
    col1, col2 = st.columns([5, 1])
    with col2:
        if st.button('❌ 삭제', key=f'po_delete_{project_id}', help='이 프로젝트의 발주 스냅샷 전부 삭제'):
            try:
                # 발주서는 linked_id가 "project_id_category" 형식이므로 모든 PO 삭제
                # (같은 project_id의 모든 카테고리 발주서 삭제)
                snapshots_df = dm.get_bom_snapshots(tenant_id, linked_type='purchase_order')
                if isinstance(snapshots_df, pd.DataFrame) and not snapshots_df.empty:
                    deleted_count = 0
                    for _, row in snapshots_df.iterrows():
                        linked_id = row.get('linked_id', '')
                        snapshot_id = row.get('id')
                        # project_id로 시작하는 항목만 삭제
                        if snapshot_id and str(linked_id).startswith(f"{project_id}_"):
                            dm.supabase.table('bom_snapshots').delete().eq('id', snapshot_id).execute()
                            deleted_count += 1
                    if deleted_count > 0:
                        st.success(f'✅ {deleted_count}개 삭제됨')
                        st.rerun()
                    else:
                        st.info('삭제할 데이터 없음')
                else:
                    st.info('삭제할 데이터 없음')
            except Exception as e:
                st.error(f'삭제 실패: {e}')

    df = _dedupe_latest(dm.get_purchase_orders(tenant_id), 'po_id')
    f = df.copy()
    if 'project_id' in f.columns and project_id:
        f = f[f['project_id'].astype(str) == str(project_id)]
    show_cols = [c for c in ['po_id', 'tenant_id', 'vendor_id', 'project_id', 'due_date', 'status', 'created_at'] if c in f.columns]
    edit_df = st.data_editor(f[show_cols] if not f.empty and show_cols else f,
                             use_container_width=True, hide_index=True, num_rows='dynamic',
                             key=f'po_editor_{project_id}')
    if st.button('저장(발주)', key=f'po_save_{project_id}'):
        try:
            orig = f.set_index('po_id') if 'po_id' in f.columns else f
            new = edit_df.set_index('po_id') if 'po_id' in edit_df.columns else edit_df
            ids = set(orig.index).intersection(set(new.index)) if not orig.empty and not new.empty else set()
            for pid in ids:
                ro = orig.loc[pid]
                rn = new.loc[pid]
                changes = {}
                for col in ['vendor_id', 'project_id', 'due_date', 'quotation_ref', 'status']:
                    if col in rn.index and str(ro.get(col)) != str(rn.get(col)):
                        changes[col] = rn.get(col)
                if changes:
                    dm.update_purchase_order(pid, **changes)
            st.success('저장 완료')
            st.rerun()
        except Exception as e:
            st.error(f'저장 실패: {e}')


def _bom_view(dm: DatabaseManager, tenant_id: str, project_id: str):
    st.header('자재내역서')

    # 삭제 버튼
    col1, col2 = st.columns([5, 1])
    with col2:
        if st.button('❌ 삭제', key=f'bom_delete_{project_id}', help='이 프로젝트의 자재내역서 스냅샷 전부 삭제'):
            try:
                snapshots_df = dm.get_bom_snapshots(tenant_id, linked_type='project', linked_id=str(project_id))
                if isinstance(snapshots_df, pd.DataFrame) and not snapshots_df.empty:
                    deleted_count = 0
                    for _, row in snapshots_df.iterrows():
                        snapshot_id = row.get('id')
                        if snapshot_id:
                            dm.supabase.table('bom_snapshots').delete().eq('id', snapshot_id).execute()
                            deleted_count += 1
                    st.success(f'✅ {deleted_count}개 삭제됨')
                    st.rerun()
                else:
                    st.info('삭제할 데이터 없음')
            except Exception as e:
                st.error(f'삭제 실패: {e}')

    payload = _latest_snapshot(dm, tenant_id, 'project', str(project_id))
    items_df = pd.DataFrame()
    try:
        if isinstance(payload, dict) and isinstance(payload.get('items'), list):
            items_df = pd.DataFrame(payload['items'])
        elif isinstance(payload, list):
            items_df = pd.DataFrame(payload)
        elif isinstance(payload, dict):
            items_df = pd.json_normalize(payload)
    except Exception:
        items_df = pd.DataFrame()
    items_df = _canonize_columns(items_df)
    # Phase 3 템플릿 헤더 순서 (자재내역서 Row 8)
    excel_order = ['No.', '품목', '규격', '단위', '수량', '단가', '공급가', '비고', '하차지', '차량번호', '납품처']
    if not items_df.empty:
        present = [c for c in excel_order if c in items_df.columns]
        rest = [c for c in items_df.columns if c not in present]
        items_df = items_df[present + rest]
    edited = st.data_editor(items_df, use_container_width=True, hide_index=True, num_rows='dynamic',
                            key=f'bom_editor_{project_id}')
    if st.button('저장(자재내역서)', disabled=DEV_READONLY, key=f'bom_save_{project_id}'):
        try:
            new_payload = payload if isinstance(payload, dict) else {}
            new_payload = dict(new_payload)
            canon = _canonize_columns(edited)
            try:
                edited_out = canon.reindex(columns=excel_order + [c for c in canon.columns if c not in excel_order])
            except Exception:
                edited_out = canon
            new_payload['items'] = edited_out.to_dict(orient='records')
            dm.add_bom_snapshot(tenant_id, 'project', str(project_id), int(_time.time()), new_payload)
            st.success('저장 완료')
            st.rerun()
        except Exception as e:
            st.error(f'저장 실패: {e}')


def _execution_view(dm: DatabaseManager, tenant_id: str, project_id: str):
    st.header('실행내역서')

    # 삭제 버튼
    col1, col2 = st.columns([5, 1])
    with col2:
        if st.button('❌ 삭제', key=f'exec_delete_{project_id}', help='이 프로젝트의 실행내역서 스냅샷 전부 삭제'):
            try:
                snapshots_df = dm.get_bom_snapshots(tenant_id, linked_type='execution', linked_id=str(project_id))
                if isinstance(snapshots_df, pd.DataFrame) and not snapshots_df.empty:
                    deleted_count = 0
                    for _, row in snapshots_df.iterrows():
                        snapshot_id = row.get('id')
                        if snapshot_id:
                            dm.supabase.table('bom_snapshots').delete().eq('id', snapshot_id).execute()
                            deleted_count += 1
                    st.success(f'✅ {deleted_count}개 삭제됨')
                    st.rerun()
                else:
                    st.info('삭제할 데이터 없음')
            except Exception as e:
                st.error(f'삭제 실패: {e}')

    payload = _latest_snapshot(dm, tenant_id, 'execution', str(project_id))
    items = payload.get('items', []) if isinstance(payload, dict) else []
    df_items = pd.DataFrame(items)
    df_items = _canonize_columns(df_items)

    # Phase 3 템플릿 헤더 순서 (실행내역서 Row 9)
    excel_order = ['분류', '품목', '금액', '비율(%)', '부가세', '합계(VAT포함)', '비고']
    if not df_items.empty:
        present = [c for c in excel_order if c in df_items.columns]
        rest = [c for c in df_items.columns if c not in present]
        df_items = df_items[present + rest]

    edited = st.data_editor(df_items, use_container_width=True, hide_index=True, num_rows='dynamic',
                            key=f'exec_editor_{project_id}')
    if st.button('저장(실행내역서)', key=f'exec_save_{project_id}'):
        try:
            header = payload.get('header', {}) if isinstance(payload, dict) else {}
            new_payload = {
                'header': header,
                'items': _canonize_columns(edited).to_dict(orient='records'),
                'type': 'execution'
            }
            dm.add_bom_snapshot(tenant_id, 'execution', str(project_id), int(_time.time()), new_payload)
            st.success('저장 완료')
            st.rerun()
        except Exception as e:
            st.error(f'저장 실패: {e}')


def render():
    dev_log_banner()
    st.title('DEV - Phase 3 (간소화)')
    if DEV_READONLY:
        st.info('읽기 전용 모드: 쓰기 작업이 비활성화됩니다.')
    tenant_id = _tenant_selector()
    dm = get_adapter()

    st.markdown('---')
    project_id = _project_selector(dm, tenant_id)
    if not project_id:
        st.warning('프로젝트를 선택하세요.')
        return

    view = st.sidebar.radio('화면', ['견적', '발주', '자재내역서', '실행내역서'], key='phase3_view')
    if view == '견적':
        _quotations_view(dm, tenant_id, project_id)
    elif view == '발주':
        _po_view(dm, tenant_id, project_id)
    elif view == '자재내역서':
        _bom_view(dm, tenant_id, project_id)
    else:
        _execution_view(dm, tenant_id, project_id)


if __name__ == '__main__':
    render()

