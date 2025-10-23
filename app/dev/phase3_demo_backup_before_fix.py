"""
DEV - Phase 3 Demo (Quotations / POs / Inventory / BOM)

Purpose
- Mirror PTOP-generated data for quick verification and light edits.
- One-click import from PTOP session_state without affecting production.

Run: streamlit run app/dev/launcher_dev.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import date as _date
import time as _time
import random as _rand
import json

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


def _to_jsonable(obj):
    from datetime import datetime, date as __date
    try:
        import numpy as _np
    except Exception:
        class _NP:
            integer = ()
            floating = ()
        _np = _NP()
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, (datetime, __date)):
        return obj.isoformat()
    try:
        if isinstance(obj, pd.Timestamp):
            return obj.to_pydatetime().isoformat()
    except Exception:
        pass
    if hasattr(_np, 'integer') and isinstance(obj, _np.integer):
        return int(obj)
    if hasattr(_np, 'floating') and isinstance(obj, _np.floating):
        return float(obj)
    if hasattr(obj, 'item'):
        try:
            return obj.item()
        except Exception:
            return str(obj)
    return obj


def _sig_from_quotation(qdata: dict):
    try:
        items = qdata.get('items') or []
        site = qdata.get('site_info') or {}
        proj = site.get('project_id') or site.get('site_name') or ''
        key_items = []
        for it in items:
            name = (it.get('model_name') or it.get('material_name') or '').strip()
            spec = (it.get('specification') or it.get('standard') or '').strip()
            qty = float(it.get('quantity') or 0)
            price = float(it.get('unit_price') or 0)
            key_items.append((name, spec, qty, price))
        key_items.sort()
        return (str(proj), tuple(key_items))
    except Exception:
        return None


def _sig_from_categories(cats: dict):
    try:
        sig = []
        for cat, items in (cats.items() if isinstance(cats, dict) else []):
            key = []
            for it in (items or []):
                name = (it.get('material_name') or '').strip()
                spec = (it.get('standard') or '').strip()
                qty = float(it.get('quantity') or 0)
                key.append((name, spec, qty))
            key.sort()
            sig.append((str(cat), tuple(key)))
        sig.sort()
        return tuple(sig)
    except Exception:
        return None


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
    st.subheader('?뚯궗紐?)
    return st.selectbox('?뚯궗紐?, ['dooho', 'kukje'], index=0, key='phase3_tenant')


def _transfer_from_ptop_session(dm: DatabaseManager, tenant_id: str):
    qdata = st.session_state.get('last_material_data')
    cats = st.session_state.get('analyzed_categories')
    out = {'quotation_id': None, 'po_ids': [], 'bom_snapshot': False}

    q_sig = _sig_from_quotation(qdata) if isinstance(qdata, dict) else None
    po_sig = _sig_from_categories(cats) if isinstance(cats, dict) else None

    # Quotation
    if isinstance(qdata, dict) and qdata.get('items') and q_sig and q_sig != st.session_state.get('phase3_q_sig'):
        items = qdata.get('items') or []
        site = qdata.get('site_info') or {}
        project_id = site.get('project_id')
        total_amount = qdata.get('total_amount')
        if total_amount is None:
            try:
                total_amount = float(sum(float(i.get('supply_amount', 0) or 0) for i in items))
            except Exception:
                total_amount = 0.0
        qid = f"Q-{int(_time.time())}-{_rand.randint(100,999)}"
        dm.add_quotation(qid, tenant_id, customer_id=None, project_id=project_id, total_amount=total_amount)
        for it in items:
            name = (it.get('model_name') or it.get('material_name') or '').strip()
            spec = (it.get('specification') or it.get('standard') or '').strip()
            qty = float(it.get('quantity') or 0)
            unit_price = float(it.get('unit_price') or 0)
            dm.add_quotation_item(qid, name, spec=spec, quantity=qty, unit_price=unit_price)
        out['quotation_id'] = qid
        st.session_state['phase3_q_sig'] = q_sig

    # POs
    if isinstance(cats, dict) and cats and po_sig and po_sig != st.session_state.get('phase3_po_sig'):
        site = (qdata or {}).get('site_info') if isinstance(qdata, dict) else {}
        project_id = (site or {}).get('project_id')
        po_ids = []
        for category, items in cats.items():
            if not items:
                continue
            abbr = str(category)[:3].upper() if category else 'GEN'
            po_id = f"PO-{int(_time.time())}-{abbr}"
            dm.add_purchase_order(po_id, tenant_id, vendor_id=None, project_id=project_id, due_date=_date.today(), quotation_ref=None)
            for it in items:
                name = (it.get('material_name') or '').strip()
                spec = (it.get('standard') or '').strip()
                item_name = (f"{name} {spec}").strip()
                qty = float(it.get('quantity') or 0)
                dm.add_po_item(po_id, item_name, material_id=None, quantity=qty, unit_price=0.0)
            po_ids.append(po_id)
        if po_ids:
            out['po_ids'] = po_ids
            st.session_state['phase3_po_sig'] = po_sig

    # BOM Snapshot (from last_material_data)
    if isinstance(qdata, dict) and qdata and q_sig and q_sig != st.session_state.get('phase3_bom_sig'):
        site = qdata.get('site_info') or {}
        linked_type = 'project'
        linked_id = site.get('project_id') or site.get('site_name') or 'unknown'
        payload = _to_jsonable(qdata)
        dm.add_bom_snapshot(tenant_id, linked_type, str(linked_id), int(_time.time()), payload)
        out['bom_snapshot'] = True
        st.session_state['phase3_bom_sig'] = q_sig

    return out


def _quotations_view(dm: DatabaseManager, tenant_id: str):
    st.header('寃ъ쟻')
    df = _dedupe_latest(dm.get_quotations(tenant_id), 'quotation_id')
    ca, cb = st.columns([2,1])
    with ca:
        q_search = st.text_input('?꾨줈?앺듃 寃??, value='', key='q_search_proj')
    with cb:
        years = sorted(list(set(pd.to_datetime(df.get('created_at', pd.Series([])), errors='coerce').dt.year.dropna().astype(int)))) if not df.empty else []
        sel_year = st.selectbox('?꾨룄', ['?꾩껜'] + [str(y) for y in years], index=0, key='q_year')
        months = ['?꾩껜'] + [f"{m:02d}" for m in range(1,13)]
        sel_month = st.selectbox('??, months, index=0, key='q_month')
    try:
        f = df.copy()
        if q_search and 'project_id' in f.columns:
            f = f[f['project_id'].astype(str).str.contains(str(q_search), na=False)]
        if 'created_at' in f.columns:
            f['created_at'] = pd.to_datetime(f['created_at'], errors='coerce')
            if sel_year != '?꾩껜':
                f = f[f['created_at'].dt.year == int(sel_year)]
            if sel_month != '?꾩껜':
                f = f[f['created_at'].dt.month == int(sel_month)]
    except Exception:
        f = df

    st.subheader('?몄쭛')
    show_cols = [c for c in ['quotation_id','tenant_id','customer_id','project_id','status','total_amount','created_at'] if c in f.columns]
    edit_df = st.data_editor(
        f[show_cols] if not f.empty and show_cols else f,
        use_container_width=True,
        hide_index=True,
        num_rows='dynamic',
        key='q_editor'
    )
    c1, c2 = st.columns([1,1])
    with c1:
        if st.button('蹂寃쎌궗?????寃ъ쟻)'):
            try:
                orig = f.set_index('quotation_id') if 'quotation_id' in f.columns else f
                new = edit_df.set_index('quotation_id') if 'quotation_id' in edit_df.columns else edit_df
                ids = set(orig.index).intersection(set(new.index)) if not orig.empty and not new.empty else set()
                for qid in ids:
                    ro = orig.loc[qid]
                    rn = new.loc[qid]
                    changes = {}
                    for col in ['customer_id','project_id','status','total_amount']:
                        if col in rn.index and str(ro.get(col)) != str(rn.get(col)):
                            changes[col] = rn.get(col)
                    if changes:
                        dm.update_quotation(qid, **changes)
                st.success('????꾨즺')
                st.rerun()
            except Exception as e:
                st.error(f'?ㅽ뙣: {e}')
    with c2:
        del_ids = st.multiselect('??젣??寃ъ쟻 ?좏깮', edit_df['quotation_id'].tolist() if 'quotation_id' in edit_df.columns else [], key='q_del')
        if st.button('?좏깮 ??젣(寃ъ쟻)') and del_ids:
            try:
                for qid in del_ids:
                    dm.delete_quotation(qid)
                st.success(f'??젣 ?꾨즺: {len(del_ids)}嫄?)
                st.rerun()
            except Exception as e:
                st.error(f'??젣 ?ㅽ뙣: {e}')

    st.subheader('寃ъ쟻 ?꾩씠??)
    sel_q = st.selectbox('寃ъ쟻 ?좏깮', df['quotation_id'].tolist() if not df.empty else [], key='sel_q')
    if sel_q:
        items = dm.get_quotation_items(sel_q)
        st.dataframe(items, use_container_width=True)
        # Excel-like snapshot view for quotation
        try:
            sn = dm.get_bom_snapshots(tenant_id, linked_type='quotation', linked_id=sel_q)
            if sn is not None and not sn.empty and 'payload_json' in sn.columns:
                payload = sn.iloc[0]['payload_json'] or {}
                rows = payload.get('items', []) if isinstance(payload, dict) else []
                if rows:
                    qdf = pd.DataFrame(rows)
                    excel_order = ['?덈ぉ','洹쒓꺽','?섎웾','?④?','湲덉븸','鍮꾧퀬']
                    present = [c for c in excel_order if c in qdf.columns]
                    rest = [c for c in qdf.columns if c not in present]
                    qdf = qdf[present + rest]
                    st.subheader('寃ъ쟻???묒???')
                    st.dataframe(qdf, use_container_width=True)
        except Exception:
            pass
        if not items.empty:
            del_id = st.selectbox('??젣???꾩씠??id', items['id'].tolist(), key='del_q_item')
            if st.button('?꾩씠????젣(寃ъ쟻)', disabled=DEV_READONLY):
                try:
                    dm.delete_quotation_item(int(del_id))
                    st.success('??젣??)
                    st.rerun()
                except Exception as e:
                    st.error(f'?ㅽ뙣: {e}')


def _po_view(dm: DatabaseManager, tenant_id: str):
    st.header('諛쒖＜')
    df = _dedupe_latest(dm.get_purchase_orders(tenant_id), 'po_id')
    ca, cb = st.columns([2,1])
    with ca:
        f_proj = st.text_input('?꾨줈?앺듃 寃??, value='', key='po_project')
    with cb:
        years = sorted(list(set(pd.to_datetime(df.get('created_at', pd.Series([])), errors='coerce').dt.year.dropna().astype(int)))) if not df.empty else []
        sel_year = st.selectbox('?꾨룄', ['?꾩껜'] + [str(y) for y in years], index=0, key='po_year')
        months = ['?꾩껜'] + [f"{m:02d}" for m in range(1,13)]
        sel_month = st.selectbox('??, months, index=0, key='po_month')
    try:
        f = df.copy()
        if f_proj and 'project_id' in f.columns:
            f = f[f['project_id'].astype(str).str.contains(str(f_proj), na=False)]
        if 'created_at' in f.columns:
            f['created_at'] = pd.to_datetime(f['created_at'], errors='coerce')
            if sel_year != '?꾩껜':
                f = f[f['created_at'].dt.year == int(sel_year)]
            if sel_month != '?꾩껜':
                f = f[f['created_at'].dt.month == int(sel_month)]
    except Exception:
        f = df

    st.subheader('?몄쭛')
    show_cols = [c for c in ['po_id','tenant_id','vendor_id','project_id','due_date','status','created_at'] if c in f.columns]
    edit_df = st.data_editor(
        f[show_cols] if not f.empty and show_cols else f,
        use_container_width=True,
        hide_index=True,
        num_rows='dynamic',
        key='po_editor'
    )
    c1, c2 = st.columns([1,1])
    with c1:
        if st.button('蹂寃쎌궗?????諛쒖＜)'):
            try:
                orig = f.set_index('po_id') if 'po_id' in f.columns else f
                new = edit_df.set_index('po_id') if 'po_id' in edit_df.columns else edit_df
                ids = set(orig.index).intersection(set(new.index)) if not orig.empty and not new.empty else set()
                for pid in ids:
                    ro = orig.loc[pid]
                    rn = new.loc[pid]
                    changes = {}
                    for col in ['vendor_id','project_id','due_date','quotation_ref','status']:
                        if col in rn.index and str(ro.get(col)) != str(rn.get(col)):
                            changes[col] = rn.get(col)
                    if changes:
                        dm.update_purchase_order(pid, **changes)
                st.success('????꾨즺')
                st.rerun()
            except Exception as e:
                st.error(f'?ㅽ뙣: {e}')
    with c2:
        del_ids = st.multiselect('??젣??諛쒖＜ ?좏깮', edit_df['po_id'].tolist() if 'po_id' in edit_df.columns else [], key='po_del')
        if st.button('?좏깮 ??젣(諛쒖＜)') and del_ids:
            try:
                for pid in del_ids:
                    dm.delete_purchase_order(pid)
                st.success(f'??젣 ?꾨즺: {len(del_ids)}嫄?)
                st.rerun()
            except Exception as e:
                st.error(f'??젣 ?ㅽ뙣: {e}')

    st.subheader('諛쒖＜ ?꾩씠??)
    sel_po = st.selectbox('諛쒖＜ ?좏깮', df['po_id'].tolist() if not df.empty else [], key='sel_po')
    if sel_po:
        items = dm.get_po_items(sel_po)
        st.dataframe(items, use_container_width=True)
        # Excel-like snapshot view for PO
        try:
            sn = dm.get_bom_snapshots(tenant_id, linked_type='po', linked_id=sel_po)
            if sn is not None and not sn.empty and 'payload_json' in sn.columns:
                payload = sn.iloc[0]['payload_json'] or {}
                rows = payload.get('items', []) if isinstance(payload, dict) else []
                if rows:
                    pdf = pd.DataFrame(rows)
                    excel_order = ['?덈ぉ','洹쒓꺽','?⑥쐞','?섎웾','?④?','湲덉븸','鍮꾧퀬','紐⑤뜽李몄“']
                    present = [c for c in excel_order if c in pdf.columns]
                    rest = [c for c in pdf.columns if c not in present]
                    pdf = pdf[present + rest]
                    st.subheader('諛쒖＜???묒???')
                    st.dataframe(pdf, use_container_width=True)
        except Exception:
            pass
        if not items.empty:
            del_id = st.selectbox('??젣???꾩씠??id', items['id'].tolist(), key='del_po_item')
            if st.button('?꾩씠????젣(諛쒖＜)', disabled=DEV_READONLY):
                try:
                    dm.delete_po_item(int(del_id))
                    st.success('??젣??)
                    st.rerun()
                except Exception as e:
                    st.error(f'?ㅽ뙣: {e}')


def _inventory_view(dm: DatabaseManager, tenant_id: str):
    st.header('?ш퀬')
    df = dm.get_inventory(tenant_id)
    st.dataframe(df, use_container_width=True)


def _bom_view(dm: DatabaseManager, tenant_id: str):
    st.header('?먯옱?댁뿭???ㅻ깄??')
    raw = dm.get_bom_snapshots(tenant_id, linked_type=None, linked_id=None)
    df = raw.copy()
    if not df.empty and 'linked_type' in df.columns:
        df = df[df['linked_type'] == 'project']

    ca, cb = st.columns([2,1])
    with ca:
        q = st.text_input('?꾨줈?앺듃 寃??, value='', key='bom_proj_q')
    with cb:
        st.caption('?곌껐?좏삎? ?꾨줈?앺듃濡?怨좎젙')

    if q and 'linked_id' in df.columns:
        df = df[df['linked_id'].astype(str).str.contains(str(q), na=False)]

    st.subheader('?ㅻ깄??紐⑸줉')
    cols = [c for c in ['linked_id','revision','created_at'] if c in df.columns]
    st.dataframe(df[cols] if cols else df, use_container_width=True)

    latest = pd.DataFrame()
    if not df.empty and 'linked_id' in df.columns:
        df['__created_at'] = pd.to_datetime(df.get('created_at'), errors='coerce')
        latest = df.sort_values(['linked_id','__created_at']).drop_duplicates(subset=['linked_id'], keep='last')
        latest = latest.drop(columns=['__created_at'], errors='ignore')

    sel_pid = st.selectbox('?꾨줈?앺듃 ?좏깮', latest['linked_id'].tolist() if not latest.empty else [], key='bom_sel_proj')
    if sel_pid:
        row = latest[latest['linked_id'] == sel_pid].iloc[0]
        payload = row.get('payload_json') if 'payload_json' in latest.columns else None
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

        # Enforce Excel-like column order for BOM table
        try:
            excel_order = ['?덈ぉ', '洹쒓꺽', '?섎웾', '?⑥쐞', '?④?', '湲덉븸', '鍮꾧퀬', '紐⑤뜽李몄“']
            if not items_df.empty:
                present = [c for c in excel_order if c in items_df.columns]
                rest = [c for c in items_df.columns if c not in present]
                items_df = items_df[present + rest]
        except Exception:
            pass

        st.subheader('?먯옱?댁뿭???몄쭛')
        if items_df.empty:
            st.info('?쒖떆????ぉ???놁뒿?덈떎. PTOP?먯꽌 ?먯옱?댁뿭?쒕? ?앹꽦?섍퀬 ?닿??섏꽭??')
            return

        edited = st.data_editor(
            items_df,
            use_container_width=True,
            hide_index=True,
            num_rows='dynamic',
            key=f'bom_items_editor_{sel_pid}'
        )

        if st.button('???ㅻ깄?룹쑝濡????, disabled=DEV_READONLY, key=f'bom_save_{sel_pid}'):
            try:
                new_payload = payload if isinstance(payload, dict) else {}
                new_payload = dict(new_payload)
                # Save with Excel-like column order
                excel_order = ['?덈ぉ', '洹쒓꺽', '?섎웾', '?⑥쐞', '?④?', '湲덉븸', '鍮꾧퀬', '紐⑤뜽李몄“']
                try:
                    edited_out = edited.reindex(columns=excel_order + [c for c in edited.columns if c not in excel_order])
                except Exception:
                    edited_out = edited
                new_payload['items'] = edited_out.to_dict(orient='records')
                dm.add_bom_snapshot(tenant_id, 'project', str(sel_pid), int(_time.time()), _to_jsonable(new_payload))
                st.success('????꾨즺')
                st.rerun()
            except Exception as e:
                st.error(f'????ㅽ뙣: {e}')



def _execution_view(dm: DatabaseManager, tenant_id: str):
    st.header('실행내역서')
    raw = dm.get_bom_snapshots(tenant_id, linked_type='execution', linked_id=None)
    df = raw.copy()
    ca, cb = st.columns([2,1])
    with ca:
        q = st.text_input('프로젝트 검색', value='', key='exec_proj_q')
    with cb:
        st.caption('관/사 구분 없이 동일 서식 사용')
    if q and 'linked_id' in df.columns:
        df = df[df['linked_id'].astype(str).str.contains(str(q), na=False)]
    latest = pd.DataFrame()
    if not df.empty and 'linked_id' in df.columns:
        df['__created_at'] = pd.to_datetime(df.get('created_at'), errors='coerce')
        latest = df.sort_values(['linked_id','__created_at']).drop_duplicates(subset=['linked_id'], keep='last')
        latest = latest.drop(columns=['__created_at'], errors='ignore')
    sel_pid = st.selectbox('프로젝트 선택', latest['linked_id'].tolist() if not latest.empty else [], key='exec_sel_proj')
    if not sel_pid:
        return
    row = latest[latest['linked_id'] == sel_pid].iloc[0]
    payload = row.get('payload_json') if 'payload_json' in latest.columns else {}
    header = payload.get('header', {}) if isinstance(payload, dict) else {}
    total = header.get('계약금액(부가세포함)')
    total = st.number_input('계약금액(부가세포함)', value=float(total or 0.0), min_value=0.0, step=1000.0, key='exec_total')
    items = payload.get('items', []) if isinstance(payload, dict) else []
    df_items = pd.DataFrame(items)
    exec_order = ['구분','품목','금액','백분율(%)','부가세','합계(VAT포함)','백분율(%)','비고']
    if not df_items.empty:
        present = [c for c in exec_order if c in df_items.columns]
        rest = [c for c in df_items.columns if c not in present]
        df_items = df_items[present + rest]
    st.subheader('실행내역서 편집')
    edited = st.data_editor(df_items, use_container_width=True, hide_index=True, num_rows='dynamic', key=f'exec_editor_{sel_pid}')
    if st.button('새 스냅샷으로 저장(실행내역서)', key=f'exec_save_{sel_pid}'):
        try:
            try:
                edited_out = edited.reindex(columns=exec_order + [c for c in edited.columns if c not in exec_order])
            except Exception:
                edited_out = edited
            new_payload = {
                'header': {'계약금액(부가세포함)': total},
                'items': edited_out.to_dict(orient='records'),
                'type': 'execution'
            }
            dm.add_bom_snapshot(tenant_id, 'execution', str(sel_pid), int(_time.time()), new_payload)
            st.success('저장 완료')
            st.rerun()
        except Exception as e:
            st.error(f'저장 실패: {e}')def render():
    dev_log_banner()
    st.title('DEV - Phase 3')
    if DEV_READONLY:
        st.info('?쎄린 ?꾩슜 紐⑤뱶: ?곌린 ?묒뾽??鍮꾪솢?깊솕?⑸땲??)
    tenant_id = _tenant_selector()
    dm = get_adapter()

    st.markdown('---')
    c1, c2 = st.columns([2,5])
    with c1:
        do_transfer = st.button('PTOP ?몄뀡?먯꽌 媛?몄삤湲?, disabled=DEV_READONLY, key='ptop_transfer_btn')
    with c2:
        st.caption('PTOP ??뿉???앹꽦??寃ъ쟻/諛쒖＜/BOM????踰덉뿉 ?닿??⑸땲??')
    if do_transfer:
        try:
            res = _transfer_from_ptop_session(dm, tenant_id)
            msgs = []
            if res.get('quotation_id'):
                msgs.append(f"Q {res['quotation_id']}")
            if res.get('po_ids'):
                msgs.append(f"PO {len(res['po_ids'])}")
            if res.get('bom_snapshot'):
                msgs.append('BOM 1')
            if msgs:
                st.success('?닿? ?꾨즺: ' + ', '.join(msgs))
            else:
                st.warning('?닿???PTOP ?몄뀡 ?곗씠?곌? ?놁뒿?덈떎.')
        except Exception as e:
            st.error(f'?닿? ?ㅽ뙣: {e}')

    view = st.sidebar.radio('?붾㈃', ['寃ъ쟻','諛쒖＜','?ш퀬','?먯옱?댁뿭??], key='phase3_view')
    if view == '寃ъ쟻':
        _quotations_view(dm, tenant_id)
    elif view == '諛쒖＜':
        _po_view(dm, tenant_id)
    elif view == '?ш퀬':
        _inventory_view(dm, tenant_id)
    else:
        _bom_view(dm, tenant_id)


if __name__ == '__main__':
    render()

