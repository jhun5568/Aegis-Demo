# db_supabase_adapter.py
# Supabase 전용 DatabaseManager (wip_app_v0.7와 호환 최소 구현)
from __future__ import annotations
import os
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import pandas as pd

# (선택) config_supabase.py에서 URL/KEY를 가져오도록 시도
try:
    from config_supabase import SUPABASE_URL, SUPABASE_KEY
except Exception:
    SUPABASE_URL = os.getenv("SUPABASE_URL") or ""
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""

from supabase import create_client, Client
try:
    import streamlit as st
except Exception:
    class _Dummy:
        def cache_resource(self, *a, **k):
            def deco(fn):
                return fn
            return deco
    st = _Dummy()  # type: ignore

@st.cache_resource(show_spinner=False)
def get_supabase_client(url: str, key: str) -> Client:
    return create_client(url, key)

def _to_dateframe(data: List[Dict[str, Any]]):
    df = pd.DataFrame(data or [])
    for col in ("order_date","due_date","planned_date","done_date","created_at","final_due_date","installation_completed_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return df

class DatabaseManager:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("Supabase 접속정보가 없습니다. SUPABASE_URL / SUPABASE_KEY 설정 확인")
        self.supabase: Client = get_supabase_client(SUPABASE_URL, SUPABASE_KEY)
        try:
            # Lightweight schema check for process_events
            self.supabase.table("process_events").select("event_id, created_at").limit(1).execute()
        except Exception as e:
            print("[WARN] process_events schema check failed. Expect columns: event_id (PK), created_at (TIMESTAMPTZ).")
            print(f"[WARN] Details: {e}")

    # ---------- READ ----------
    def get_projects(self, customer_id: Optional[str]=None) -> pd.DataFrame:
        q = self.supabase.table("projects").select("*")
        if customer_id: q = q.eq("customer_id", customer_id)
        res = q.order("created_at", desc=True).execute()
        return _to_dateframe(res.data)

    def get_orders(self, customer_id: Optional[str]=None) -> pd.DataFrame:
        q = self.supabase.table("orders").select("*")
        if customer_id: q = q.eq("customer_id", customer_id)
        res = q.order("created_at", desc=True).execute()
        return _to_dateframe(res.data)

    def get_vendors(self, process_type: Optional[str]=None) -> pd.DataFrame:
        q = self.supabase.table("vendors").select("*")
        if process_type:
            # 부분일치 검색
            q = q.like("process_types", f"%{process_type}%")
        res = q.execute()
        return _to_dateframe(res.data)

    def get_process_events(self, order_id: Optional[str]=None, order_ids: Optional[List[str]]=None) -> pd.DataFrame:
        q = self.supabase.table("process_events").select("*")
        if order_ids:
            q = q.in_("order_id", order_ids)
        elif order_id:
            q = q.eq("order_id", order_id)
        res = q.order("created_at", desc=True).execute()
        return _to_dateframe(res.data)

    # ---------- WRITE ----------
    def add_process_event(self, order_id: str, stage: str, progress: int=0,
                          planned_date: Optional[date]=None, done_date: Optional[date]=None,
                          vendor: Optional[str]=None, note: str="") -> bool:
        payload = {
            "order_id": order_id, "stage": stage, "progress": int(progress),
            "planned_date": (str(planned_date) if planned_date else None),
            "done_date": (str(done_date) if done_date else None),
            "vendor": vendor, "note": note
        }
        ins = self.supabase.table("process_events").insert(payload).execute()
        # 진행단계 표시 갱신
        self.supabase.table("orders").update({
            "current_stage": stage,
            "status": ("완료" if (done_date or progress>=100) else "진행중")
        }).eq("order_id", order_id).execute()
        return True

    def update_project_installation(self, project_id: str,
                                    completed_date: Optional[date]=None,
                                    staff_count: Optional[int]=None,
                                    days: Optional[int]=None,
                                    tax_invoice: Optional[bool]=None,
                                    trade_statement: Optional[bool]=None) -> bool:
        update_data: Dict[str, Any] = {}
        if completed_date is not None:
            update_data["installation_completed_date"] = str(completed_date) if completed_date else None
        if staff_count is not None:
            update_data["installation_staff_count"] = int(staff_count)
        if days is not None:
            update_data["installation_days"] = int(days)
        if tax_invoice is not None:
            update_data["tax_invoice_issued"] = bool(tax_invoice)
        if trade_statement is not None:
            update_data["trade_statement_issued"] = bool(trade_statement)
        if not update_data:
            return True
        self.supabase.table("projects").update(update_data).eq("project_id", project_id).execute()
        return True

    # ------------------ PHASE 3: Quotations/PO/Inventory (minimal CRUD) ------------------
    def get_quotations(self, tenant_id: str):
        res = self.supabase.table("quotations").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True).execute()
        return _to_dateframe(res.data)

    def add_quotation(self, quotation_id: str, tenant_id: str, customer_id: Optional[str]=None,
                      project_id: Optional[str]=None, total_amount: Optional[float]=0, status: str='draft') -> bool:
        payload = {
            "quotation_id": quotation_id,
            "tenant_id": tenant_id,
            "customer_id": customer_id,
            "project_id": project_id,
            "total_amount": total_amount or 0,
            "status": status,
        }
        self.supabase.table("quotations").insert(payload).execute()
        return True

    def update_quotation(self, quotation_id: str, **kwargs) -> bool:
        allowed = {k: v for k, v in kwargs.items() if k in ("customer_id","project_id","total_amount","status")}
        if not allowed:
            return True
        self.supabase.table("quotations").update(allowed).eq("quotation_id", quotation_id).execute()
        return True

    def delete_quotation(self, quotation_id: str) -> bool:
        self.supabase.table("quotations").delete().eq("quotation_id", quotation_id).execute()
        return True

    def get_purchase_orders(self, tenant_id: str):
        res = self.supabase.table("purchase_orders").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True).execute()
        return _to_dateframe(res.data)

    def add_purchase_order(self, po_id: str, tenant_id: str, vendor_id: Optional[str]=None,
                            project_id: Optional[str]=None, due_date: Optional[date]=None,
                            quotation_ref: Optional[str]=None, status: str='draft') -> bool:
        payload = {
            "po_id": po_id,
            "tenant_id": tenant_id,
            "vendor_id": vendor_id,
            "project_id": project_id,
            "due_date": (str(due_date) if due_date else None),
            "quotation_ref": quotation_ref,
            "status": status,
        }
        self.supabase.table("purchase_orders").insert(payload).execute()
        return True

    def update_purchase_order(self, po_id: str, **kwargs) -> bool:
        allowed = {k: v for k, v in kwargs.items() if k in ("vendor_id","project_id","due_date","quotation_ref","status")}
        if "due_date" in allowed and allowed["due_date"] is not None:
            allowed["due_date"] = str(allowed["due_date"])  # ensure ISO date
        if not allowed:
            return True
        self.supabase.table("purchase_orders").update(allowed).eq("po_id", po_id).execute()
        return True

    def delete_purchase_order(self, po_id: str) -> bool:
        self.supabase.table("purchase_orders").delete().eq("po_id", po_id).execute()
        return True

    def get_inventory(self, tenant_id: str):
        res = self.supabase.table("inventory").select("*").eq("tenant_id", tenant_id).order("updated_at", desc=True).execute()
        return _to_dateframe(res.data)

    def add_inventory_txn(self, tenant_id: str, material_id: str, delta: float, reason: Optional[str]=None, related_po_id: Optional[str]=None) -> bool:
        payload = {
            "tenant_id": tenant_id,
            "material_id": material_id,
            "delta": float(delta),
            "reason": reason,
            "related_po_id": related_po_id,
        }
        self.supabase.table("inventory_txns").insert(payload).execute()
        # Optional: Adjust on_hand/reserved here or via DB trigger (recommended)
        return True

    # Items (quotations)
    def get_quotation_items(self, quotation_id: str):
        res = self.supabase.table("quotation_items").select("*").eq("quotation_id", quotation_id).execute()
        return _to_dateframe(res.data)

    def add_quotation_item(self, quotation_id: str, item_name: str, spec: str = "", quantity: float = 0, unit_price: float = 0) -> bool:
        payload = {
            "quotation_id": quotation_id,
            "item_name": item_name,
            "spec": spec,
            "quantity": float(quantity),
            "unit_price": float(unit_price),
        }
        self.supabase.table("quotation_items").insert(payload).execute()
        return True

    def update_quotation_item(self, item_id: int, **kwargs) -> bool:
        allowed = {k: v for k, v in kwargs.items() if k in ("item_name", "spec", "quantity", "unit_price")}
        if not allowed:
            return True
        self.supabase.table("quotation_items").update(allowed).eq("id", item_id).execute()
        return True

    def delete_quotation_item(self, item_id: int) -> bool:
        self.supabase.table("quotation_items").delete().eq("id", item_id).execute()
        return True

    # Items (purchase orders)
    def get_po_items(self, po_id: str):
        res = self.supabase.table("po_items").select("*").eq("po_id", po_id).execute()
        return _to_dateframe(res.data)

    def add_po_item(self, po_id: str, item_name: str, material_id: Optional[str] = None, quantity: float = 0, unit_price: float = 0) -> bool:
        payload = {
            "po_id": po_id,
            "item_name": item_name,
            "material_id": material_id,
            "quantity": float(quantity),
            "unit_price": float(unit_price),
        }
        self.supabase.table("po_items").insert(payload).execute()
        return True

    def update_po_item(self, item_id: int, **kwargs) -> bool:
        allowed = {k: v for k, v in kwargs.items() if k in ("item_name", "material_id", "quantity", "unit_price")}
        if not allowed:
            return True
        self.supabase.table("po_items").update(allowed).eq("id", item_id).execute()
        return True

    def delete_po_item(self, item_id: int) -> bool:
        self.supabase.table("po_items").delete().eq("id", item_id).execute()
        return True

    # BOM snapshots
    def get_bom_snapshots(self, tenant_id: str, linked_type: Optional[str] = None, linked_id: Optional[str] = None):
        q = self.supabase.table("bom_snapshots").select("*").eq("tenant_id", tenant_id)
        if linked_type:
            q = q.eq("linked_type", linked_type)
        if linked_id:
            q = q.eq("linked_id", linked_id)
        res = q.order("created_at", desc=True).execute()
        return _to_dateframe(res.data)

    def add_bom_snapshot(self, tenant_id: str, linked_type: str, linked_id: str, revision: int, payload_json: dict) -> bool:
        payload = {
            "tenant_id": tenant_id,
            "linked_type": linked_type,
            "linked_id": linked_id,
            "revision": int(revision),
            "payload_json": payload_json,
        }
        self.supabase.table("bom_snapshots").insert(payload).execute()
        return True
