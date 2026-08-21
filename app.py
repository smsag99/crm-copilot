"""سرور دستیار هوشمند مشتریان — FastAPI

اجرا:
    export GEMINI_API_KEY=...          # اختیاری؛ بدون آن حالت قطعی کار می‌کند
    python -m uvicorn app:app --reload --port 8000
سپس http://127.0.0.1:8000
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import assignments as AS
import insights as I
import jalali
from copilot import SUGGESTED_QUESTIONS, Copilot
from signals import (COMPLAINT_BY_HISTORY as SG_COMPLAINT, DEV_BY_HISTORY as SG_DEV,
                     OFFER_ACCEPT_BY_REASON as SG_OFFER_REASON,
                     OFFER_ACCEPT_OVERALL as SG_OFFER_OVERALL,
                     OFFER_REASON_NOTE as SG_OFFER_NOTE,
                     REORDER_BY_RECENCY as SG_REORDER)
from store import load_store, norm, render_profile_fa

BASE = Path(__file__).parent
STATIC = BASE / "static"

app = FastAPI(title="دستیار هوشمند مشتریان — نفیس نخ", docs_url="/api/docs")

print("بارگذاری پروفایل‌ها…")
STORE = load_store()
COPILOT = Copilot(STORE)
print(f"آماده: {len(STORE.P)} پروفایل | حالت دستیار: {COPILOT.mode}")


# ────────────────────────────────────────────────────────────────── مدل‌ها
class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []


# ────────────────────────────────────────────────────────────────── صفحات
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ────────────────────────────────────────────────────────────────── API
@app.get("/api/meta")
def meta():
    s = STORE.portfolio
    return {
        "as_of": s["as_of"],
        "as_of_fa": jalali.fmt(s["as_of"], "long"),
        "customers": s["customers"],
        "text_records": len(STORE.text_index),
        "copilot_mode": COPILOT.mode,
        "copilot_model": COPILOT.model if COPILOT.client else None,
        "copilot_error": COPILOT.last_error,
        "suggested_questions": SUGGESTED_QUESTIONS,
        "risk_codes": RISK_CODES,
        "opportunity_codes": OPP_CODES,
        "signal_codes": SIGNAL_CODES,
        "sort_options": SORT_OPTIONS,
        "rfm_segments": list(STORE.portfolio.get("rfm_meta", {}).keys()),
        "quadrants": list(STORE.portfolio.get("quadrant_meta", {}).keys()),
        "focus_options": list(STORE.portfolio.get("focus_meta", {}).keys()),
        "finance_rate_monthly": STORE.portfolio.get("finance_rate_monthly"),
        "reference_total": int(STORE.frame.reference_count.sum()),
        "data_caveats": _caveats(s),
        "periods": (STORE.periods or {}).get("periods", []),
        "period_recommended": (STORE.periods or {}).get("recommended"),
        "period_anchor_fa": (STORE.periods or {}).get("anchor_fa"),
    }


def _caveats(s: dict) -> list[str]:
    h = s.get("half_years") or []
    price = (f"قیمت میانگین واحد در مقایسهٔ هم‌ارز {h[0]['label']} تا {h[-1]['label']} "
             f"{h[-1]['price_index'] / 100:.1f} برابر شده") if len(h) >= 2 else "قیمت‌ها به‌شدت تغییر کرده‌اند"
    return [
        f"فروش اسمی است و واحد پول در فایل منبع مشخص نشده. {price}؛ پس برای هر تحلیل روند، "
        "حجم (کیلوگرم) یا فروش حقیقی مبناست، نه فروش اسمی.",
        f"حاشیه سود ترکیبی است: {s['realized_cost_share_pct']}٪ خطوط بر مبنای هزینهٔ تحقق‌یافته "
        "و بقیه بر مبنای هزینهٔ برآوردی محصول-ماه. مبنای برآوردی حاشیه را حدود ۵ واحد درصد "
        "خوش‌بینانه‌تر نشان می‌دهد، پس همیشه سهم مبنا را کنار عدد حاشیه بخوانید.",
        "«معوق» سررسیدگذشته و ریسک اعتباری است؛ «سررسیدنشده» سرمایه در گردش است و ریسک نیست. "
        "مشارکت خالص فقط بخش معوق را از سود ناخالص کسر می‌کند.",
        "فیلد وضعیت مشتری در فایل منبع (Customer_Status) تقریباً همان رکود ۱۸۰ روزه است: "
        "از ۲۴۳ مشتری خریدار، هیچ‌کدام «غیرفعال» علامت نخورده‌اند و از ۴۰۱ مشتری راکد، ۳۷۱ "
        "مورد «غیرفعال»اند (هم‌خطی ۹۵٪). یعنی این فیلد اطلاعات تازه‌ای بر رکود نمی‌افزاید و "
        "به‌کارگیری‌اش در مدل‌سازی ریزش، استدلال دایره‌وار است. قرنطینه شده و در هیچ تحلیلی به‌کار نرفته.",
        "۵۲ ردیف با شناسهٔ SL-CMP در شیت فروش، رکورد ردیابی شکایت‌اند نه فروش (تاریخ ۱۴۰۴–۱۴۰۵ "
        "و تنها ردیف‌های دارای همبافت). این ردیف‌ها از تمام محاسبات فروش جدا شده‌اند.",
    ]


RISK_CODES = [
    {"code": "overdue_exceeds_gp", "label": "معوق بیش از سود ناخالص"},
    {"code": "overdue_aged", "label": "معوق کهنه (+۱ سال)"},
    {"code": "bounced_cheques", "label": "چک برگشتی"},
    {"code": "over_credit_limit", "label": "عبور از سقف اعتبار"},
    {"code": "low_collection_rate", "label": "نرخ وصول پایین"},
    {"code": "dormant", "label": "مشتری راکد"},
    {"code": "volume_collapse", "label": "ریزش حجم خرید"},
    {"code": "quality_linked_decline", "label": "کاهش خرید پس از شکایت"},
    {"code": "open_severe_complaint", "label": "شکایت باز با شدت زیاد"},
    {"code": "thin_margin", "label": "حاشیه سود نازک"},
    {"code": "many_negative_lines", "label": "خطوط زیان‌ده زیاد"},
    {"code": "uncontacted_active", "label": "فعال بدون تماس"},
    {"code": "no_crm_history", "label": "بدون سابقه در CRM"},
    {"code": "competitor_dominant", "label": "سهم غالب رقیب"},
    {"code": "single_family_dependency", "label": "وابستگی تک‌محصولی"},
]

OPP_CODES = [
    {"code": "wallet_share_gap", "label": "شکاف سهم از سبد"},
    {"code": "approved_sample_idle", "label": "نمونهٔ تأییدشده بلااستفاده"},
    {"code": "pending_dev_request", "label": "درخواست توسعهٔ بی‌پاسخ"},
    {"code": "pending_offers", "label": "آفر بی‌پاسخ"},
    {"code": "offer_responsive", "label": "پاسخ‌ده به آفر"},
    {"code": "cross_sell", "label": "فروش مکمل"},
    {"code": "growing", "label": "رشد حجم خرید"},
    {"code": "repricing_upside", "label": "ظرفیت اصلاح قیمت"},
    {"code": "win_back", "label": "بازیابی مشتری بزرگ"},
    {"code": "recovered_trust", "label": "شکایت رسیدگی‌شده و خرید پایدار"},
]

SORT_OPTIONS = [
    {"key": "value_at_play", "label": "پول در حرکت (فهرست تمرکز)", "asc": False},
    {"key": "real_gp", "label": "سود واقعی پس از هزینهٔ پول", "asc": True},
    {"key": "real_margin", "label": "حاشیهٔ واقعی", "asc": True},
    {"key": "cost_of_money", "label": "هزینهٔ پول (مبلغ)", "asc": False},
    {"key": "cost_of_money_pct", "label": "هزینهٔ پول (٪)", "asc": False},
    {"key": "days_cash", "label": "روزهای پول قفل‌شده", "asc": False},
    {"key": "rfm_move", "label": "حرکت RFM", "asc": True},
    {"key": "ltv_total", "label": "ارزش طول عمر (LTV)", "asc": False},
    {"key": "rescue_value", "label": "ارزش نجات", "asc": False},
    {"key": "revenue", "label": "فروش", "asc": False},
    {"key": "gross_profit", "label": "سود ناخالص", "asc": False},
    {"key": "margin_pct", "label": "حاشیه سود", "asc": True},
    {"key": "retention", "label": "احتمال ماندگاری", "asc": True},
    {"key": "p_churn", "label": "احتمال قطع خرید", "asc": False},
    {"key": "p_reorder", "label": "احتمال سفارش مجدد", "asc": False},
    {"key": "net_contribution", "label": "مشارکت خالص", "asc": True},
    {"key": "overdue", "label": "مطالبات معوق", "asc": False},
    {"key": "oldest_overdue_days", "label": "عمر معوق", "asc": False},
    {"key": "days_since_purchase", "label": "روز از آخرین خرید", "asc": False},
    {"key": "silence_ratio", "label": "نسبت سکوت", "asc": False},
    {"key": "volume_trend", "label": "روند حجم", "asc": True},
    {"key": "rank_gap", "label": "اختلاف رتبهٔ فروش و LTV", "asc": True},
    {"key": "signal_score", "label": "شدت سیگنال منفی", "asc": False},
    {"key": "risk_score", "label": "امتیاز ریسک", "asc": False},
    {"key": "opportunity_score", "label": "امتیاز فرصت", "asc": False},
    {"key": "open_complaints", "label": "شکایت باز", "asc": False},
    {"key": "wallet_share", "label": "سهم از سبد", "asc": True},
]

SIGNAL_CODES = [
    {"code": "silence_gap", "label": "سکوت بیش از الگوی معمول"},
    {"code": "volume_trend", "label": "تغییر حجم خرید"},
    {"code": "purchase_plan", "label": "برنامهٔ خرید اعلام‌شده"},
    {"code": "price_talk", "label": "مذاکرهٔ قیمت و تخفیف"},
    {"code": "market_price_pressure", "label": "فشار قیمتی بازار"},
    {"code": "margin_gap", "label": "فاصله از میانهٔ حاشیه"},
    {"code": "margin_drift", "label": "جابه‌جایی حاشیه اخیر"},
    {"code": "complaint_history", "label": "سابقهٔ شکایت"},
    {"code": "quality_purchase_link", "label": "افت خرید پس از شکایت"},
    {"code": "lab_evenness", "label": "یکنواختی آزمایشگاه"},
    {"code": "quality_talk", "label": "گفت‌وگوی کیفیت"},
    {"code": "overdue", "label": "مطالبات سررسیدگذشته"},
    {"code": "chase", "label": "پیگیری مکرر وصول"},
    {"code": "bounced", "label": "چک برگشتی"},
    {"code": "dev_history", "label": "نیاز فنی اعلام‌شده"},
    {"code": "wallet_gap", "label": "شکاف سهم از سبد"},
    {"code": "wallet_falling", "label": "کاهش سهم از سبد"},
    {"code": "no_crm", "label": "بدون تعامل CRM"},
    {"code": "uncontacted_buyer", "label": "خریدار بدون تماس"},
    {"code": "open_actions", "label": "اقدام بازماندهٔ CRM"},
]


@app.get("/api/portfolio")
def portfolio():
    s = dict(STORE.portfolio)
    f = STORE.frame
    s["text_records"] = len(STORE.text_index)
    s["risk_counts"] = [
        {"code": r["code"], "label": r["label"],
         "customers": int(f["risk_codes"].str.contains(r["code"], na=False).sum()),
         "revenue": float(f.loc[f["risk_codes"].str.contains(r["code"], na=False), "revenue"].sum()),
         "overdue": float(f.loc[f["risk_codes"].str.contains(r["code"], na=False), "overdue"].sum())}
        for r in RISK_CODES]
    s["opportunity_counts"] = [
        {"code": o["code"], "label": o["label"],
         "customers": int(f["opp_codes"].str.contains(o["code"], na=False).sum()),
         "revenue": float(f.loc[f["opp_codes"].str.contains(o["code"], na=False), "revenue"].sum())}
        for o in OPP_CODES]
    s["risk_counts"].sort(key=lambda x: -x["customers"])
    s["opportunity_counts"].sort(key=lambda x: -x["customers"])
    return s


@app.get("/api/customers")
def customers(q: str = "", sort_by: str = "ltv_total", ascending: bool = False,
              segment: str = "", risk: str = "", opportunity: str = "", signal: str = "",
              rfm: str = "", quadrant: str = "", focus: str = "", limit: int = 200):
    f = STORE.frame.copy()
    if q:
        qq = norm(q)
        f = f[[qq in norm(i) for i in f.index]]
    if segment:
        f = f[f.segment == segment]
    if risk:
        f = f[f["risk_codes"].str.contains(risk, na=False)]
    if opportunity:
        f = f[f["opp_codes"].str.contains(opportunity, na=False)]
    if signal:
        f = f[f["signal_codes"].str.contains(signal, na=False)]
    if rfm:
        f = f[f["rfm_segment"] == rfm]
    if quadrant:
        f = f[f["quadrant"] == quadrant]
    if focus:
        f = f[f["focus"] == focus]
    if sort_by not in f.columns:
        raise HTTPException(400, f"ستون «{sort_by}» وجود ندارد")
    f = f.sort_values(sort_by, ascending=ascending, na_position="last").head(int(limit))
    cols = ["segment", "revenue", "revenue_rank", "gross_profit", "margin_pct", "overdue",
            "days_cash", "cost_of_money", "cost_of_money_pct", "real_margin", "real_gp",
            "net_margin", "net_gp", "margin_rank", "real_margin_rank", "margin_rank_gap",
            "focus", "focus_rank", "value_at_play", "value_at_play_basis",
            "growth_potential", "cost_to_serve_score", "rfm_prev", "rfm_move",
            "rfm_move_label", "rfm_alert",
            "net_contribution", "days_since_purchase", "volume_trend", "open_complaints",
            "risk_score", "opportunity_score", "signal_score", "top_risk", "top_opportunity",
            "top_signal", "next_action", "next_owner", "wallet_share", "collection_rate",
            "volume", "ltv_total", "ltv_historic", "ltv_future", "ltv_rank", "rank_gap",
            "retention", "rfm", "rfm_segment", "R", "F", "M", "quadrant", "rescue_value",
            "rescue_rank", "gp_monthly", "order_gap", "silence_ratio", "families",
            "reference_count", "p_reorder", "p_churn", "p_complaint", "p_discount"]
    out = f[cols].reset_index().rename(columns={"index": "customer_id"})
    return JSONResponse(content={"total": int(len(STORE.frame)), "shown": len(out),
                                 "rows": _clean(out.to_dict("records"))})


def _clean(obj: Any) -> Any:
    """NaN را به None تبدیل می‌کند تا JSON معتبر بماند."""
    import math
    if isinstance(obj, list):
        return [_clean(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


@app.get("/api/customer/{customer_id}")
def customer(customer_id: str):
    p = STORE.P.get(customer_id.strip().upper())
    if not p:
        raise HTTPException(404, "مشتری یافت نشد")
    return JSONResponse(content=_clean({
        **p,
        "profile_text": render_profile_fa(p),
        "dates_fa": {
            "relationship_start": jalali.fmt(p["identity"]["relationship_start"]),
            "first_purchase": jalali.fmt(p["commercial"]["first_purchase"]),
            "last_purchase": jalali.fmt(p["commercial"]["last_purchase"]),
            "last_interaction": jalali.fmt(p["engagement"]["last_interaction"]),
            "last_complaint": jalali.fmt(p["complaints"]["last_complaint"]),
        },
    }))


@app.get("/api/segments")
def segments():
    s = STORE.portfolio
    return JSONResponse(content=_clean({
        "median_margin": s.get("median_margin"),
        "quadrants": s.get("quadrants"), "quadrant_meta": s.get("quadrant_meta"),
        "quadrant_points": s.get("quadrant_points"),
        "rfm": s.get("rfm"), "rfm_meta": s.get("rfm_meta"), "rfm_matrix": s.get("rfm_matrix"),
        "ltv_total": s.get("ltv_total"), "ltv_historic": s.get("ltv_historic"),
        "ltv_future": s.get("ltv_future"),
        "negative_ltv_customers": s.get("negative_ltv_customers"),
        "retention_median": s.get("retention_median"),
    }))


@app.get("/api/worklist")
def worklist(limit: int = 120):
    """کارتابل: کارت‌های مشکل، و سطر هر مشتری با هدف، هویت و بهترین کانال."""
    w = STORE.portfolio.get("worklist") or {}
    if not w:
        raise HTTPException(503, "کارتابل در کش موجود نیست؛ ابتدا کش را بسازید")
    return JSONResponse(content=_clean({**w, "rows": w["rows"][:int(limit)]}))


@app.get("/api/signals_center")
def signals_center(limit: int = 200):
    """مرکز سیگنال: سه منبع، روند هر دسته، نگاشت به مشتری، و ارزش کمینهٔ رسیدگی."""
    sc = STORE.portfolio.get("signals_center") or {}
    if not sc:
        raise HTTPException(503, "مرکز سیگنال در کش موجود نیست؛ ابتدا کش را بسازید")
    return JSONResponse(content=_clean({**sc, "rows": sc["rows"][:int(limit)]}))


@app.get("/api/offers")
def offers(limit: int = 120):
    """موتور آفر: بازی‌ها، سطرها با دلیل، آفرهای مسدود و آزمون‌های عامل‌ها."""
    o = STORE.portfolio.get("offers_engine") or {}
    if not o:
        raise HTTPException(503, "موتور آفر در کش موجود نیست؛ ابتدا کش را بسازید")
    return JSONResponse(content=_clean({**o, "rows": o["rows"][:int(limit)]}))


# ─────────────────────────────────────────────────── لایهٔ ارجاع به کارشناس
class ReferralRequest(BaseModel):
    customer_id: str
    expert_id: str = ""
    note: str = ""


class ReportRequest(BaseModel):
    report: dict


class DecisionRequest(BaseModel):
    key: str
    note: str = ""
    date: str = ""


def _wl_row(cid: str) -> dict:
    rows = (STORE.portfolio.get("worklist") or {}).get("rows") or []
    r = next((x for x in rows if x["customer_id"] == cid.strip().upper()), None)
    if not r:
        raise HTTPException(404, f"مشتری {cid} در کارتابل نیست")
    return r


@app.get("/api/experts")
def experts():
    """روستر کارشناسان با بار کاری اندازه‌گیری‌شده، و پیگیری ارجاع‌ها."""
    return JSONResponse(content=_clean({
        "experts": STORE.portfolio.get("experts") or [],
        "specialisation_note": STORE.portfolio.get("specialisation_note"),
        "report_fields": AS.REPORT_FIELDS, "report_note": AS.REPORT_NOTE,
        "decision_options": AS.DECISION_OPTIONS,
        "status_color": AS.STATUS_COLOR,
        "referrals": AS.all_referrals(), "summary": AS.summary(),
    }))


@app.get("/api/experts/{expert_id}")
def expert_inbox(expert_id: str):
    """کارتابل یک کارشناس: فقط ارجاعات او، مرتب بر اساس اهمیت."""
    eid = expert_id.strip().upper()
    e = next((x for x in (STORE.portfolio.get("experts") or [])
              if x["expert_id"] == eid), None)
    if not e:
        raise HTTPException(404, f"کارشناس {expert_id} در سامانه نیست")
    return JSONResponse(content=_clean({
        "expert": e, "referrals": AS.for_expert(eid),
        "report_fields": AS.REPORT_FIELDS, "report_note": AS.REPORT_NOTE,
        "status_color": AS.STATUS_COLOR,
    }))


@app.get("/api/referral_suggest/{customer_id}")
def referral_suggest(customer_id: str):
    """پیشنهاد کارشناس با دلیل داده‌محور — پیش از ارسال ارجاع."""
    r = _wl_row(customer_id)
    if not AS.referrable(r):
        raise HTTPException(400, "این کار از نوع جلسه است و در کارتابل مدیر می‌ماند")
    owner = (STORE.P.get(r["customer_id"]) or {}).get("identity", {}).get("sales_rep_id")
    E = STORE.portfolio.get("experts") or []
    return JSONResponse(content=_clean({
        "customer_id": r["customer_id"], "owner": owner,
        "suggestion": AS.suggest_expert(r, owner, E), "experts": E,
        "specialisation_note": STORE.portfolio.get("specialisation_note"),
        "channel": r.get("channel"), "channel_why": r.get("channel_why"),
        "goal": r.get("goal"), "priority_fa": r.get("priority_fa"),
    }))


@app.post("/api/referrals")
def create_referral(req: ReferralRequest):
    r = _wl_row(req.customer_id)
    if not AS.referrable(r):
        raise HTTPException(400, "این کار از نوع جلسه است و ارجاع‌پذیر نیست")
    owner = (STORE.P.get(r["customer_id"]) or {}).get("identity", {}).get("sales_rep_id")
    s = AS.suggest_expert(r, owner, STORE.portfolio.get("experts") or [])
    eid = (req.expert_id or s["expert_id"] or "").strip().upper()
    if not any(x["expert_id"] == eid for x in (STORE.portfolio.get("experts") or [])):
        raise HTTPException(400, f"کارشناس {eid} در سامانه نیست")
    return JSONResponse(content=_clean(AS.create(r, eid, s, req.note)))


@app.post("/api/referrals/{rid}/report")
def referral_report(rid: str, req: ReportRequest):
    out = AS.submit_report(rid, dict(req.report))
    if out is None:
        raise HTTPException(404, f"ارجاع {rid} یافت نشد")
    if out.get("error"):
        raise HTTPException(400, out["error"])
    return JSONResponse(content=_clean(out))


@app.post("/api/referrals/{rid}/decision")
def referral_decision(rid: str, req: DecisionRequest):
    out = AS.decide(rid, req.key, req.note, req.date)
    if out is None:
        raise HTTPException(404, f"ارجاع {rid} یا تصمیم {req.key} یافت نشد")
    return JSONResponse(content=_clean(out))


@app.get("/api/referrals/{rid}/report.md")
def referral_report_file(rid: str):
    """فایل گزارش کارشناس — همان فیلدهای الزامی، قابل دانلود و پیوست."""
    ref = AS.get(rid)
    if not ref:
        raise HTTPException(404, f"ارجاع {rid} یافت نشد")
    if not ref.get("report"):
        raise HTTPException(404, "کارشناس هنوز گزارشی ثبت نکرده است")
    from fastapi.responses import Response
    return Response(AS.report_file(ref), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition":
                             f'attachment; filename="{rid}-report.md"'})


@app.post("/api/referrals/{rid}/status")
def referral_status(rid: str, status: str):
    out = AS.set_status(rid, status)
    if out is None:
        raise HTTPException(404, f"ارجاع {rid} یا وضعیت {status} یافت نشد")
    return JSONResponse(content=_clean(out))


@app.get("/api/focus")
def focus():
    """اسکناریوی F: فهرست تمرکز، چهار خانه، هزینهٔ پول و شواهد اعتبارسنجی."""
    s = STORE.portfolio
    return JSONResponse(content=_clean({
        "focus_list": s.get("focus_list"), "focus": s.get("focus"),
        "focus_meta": s.get("focus_meta"),
        "margin_points": s.get("margin_points"),
        "finance_rate_monthly": s.get("finance_rate_monthly"),
        "finance_rate_source": s.get("finance_rate_source"),
        "cost_of_money": s.get("cost_of_money"),
        "cost_of_money_pct": s.get("cost_of_money_pct"),
        "gross_profit": s.get("gross_profit"),
        "gross_margin_pct": s.get("gross_margin_pct"),
        "real_gross_profit": s.get("real_gross_profit"),
        "real_margin_pct": s.get("real_margin_pct"),
        "expected_writeoff": s.get("expected_writeoff"),
        "net_gross_profit": s.get("net_gross_profit"),
        "net_margin_pct": s.get("net_margin_pct"),
        "negative_real_margin_customers": s.get("negative_real_margin_customers"),
        "negative_gross_margin_customers": s.get("negative_gross_margin_customers"),
        "days_cash_median": s.get("days_cash_median"),
        "days_cash_benchmark": s.get("days_cash_benchmark"),
        "achievable_real_margin": s.get("achievable_real_margin"),
        "margin_spread_gross": s.get("margin_spread_gross"),
        "margin_spread_real": s.get("margin_spread_real"),
        "credit_pricing": s.get("credit_pricing"),
        "payment_profile": s.get("payment_profile"),
        "recovery_curve": s.get("recovery_curve"), "recovery_note": s.get("recovery_note"),
        "validation": s.get("validation"),
        "rfm_movement": s.get("rfm_movement"), "rfm_alerts": s.get("rfm_alerts"),
        "rfm_m_basis": s.get("rfm_m_basis"),
        "customers": s.get("customers"), "revenue": s.get("revenue_nominal"),
    }))


@app.get("/api/period")
def period(key: str = ""):
    """تحلیل یک طول دوره. اگر کلید ندهند، دورهٔ پیشنهادی برگردانده می‌شود."""
    PP = STORE.periods or {}
    if not PP:
        raise HTTPException(503, "تحلیل دوره‌ای در کش موجود نیست؛ ابتدا کش را بسازید")
    k = key or PP["recommended"]
    if k not in PP["data"]:
        raise HTTPException(400, f"دورهٔ «{k}» تعریف نشده است")
    return JSONResponse(content=_clean({
        "anchor": PP["anchor"], "anchor_fa": PP["anchor_fa"],
        "anchor_note": PP["anchor_note"],
        "periods": PP["periods"], "recommended": PP["recommended"],
        "recommendation_why": PP["recommendation_why"],
        "recommendation_table": PP["recommendation_table"],
        **PP["data"][k],
    }))


@app.get("/api/patterns")
def patterns():
    return JSONResponse(content=_clean({
        "patterns": STORE.portfolio.get("patterns"),
        "model_card": STORE.portfolio.get("model_card"),
        "base_rates": {
            "reorder_by_recency": [
                {"band": b, "p": pv, "n": n} for _, pv, b, n in SG_REORDER],
            "complaint_by_history": [
                {"band": b, "p": pv, "n": n} for _, pv, b, n in SG_COMPLAINT],
            "dev_by_history": [
                {"band": b, "p": pv, "n": n} for _, pv, b, n in SG_DEV],
            "offer_accept_by_reason": SG_OFFER_REASON,
            "offer_accept_overall": SG_OFFER_OVERALL,
            "offer_reason_note": SG_OFFER_NOTE,
        },
    }))


@app.get("/api/search_text")
def search_text(q: str, limit: int = 25, kind: str = ""):
    terms = [t for t in norm(q).split() if len(t) > 2]
    if not terms:
        return {"hits": [], "note": "عبارت جست‌وجو خیلی کوتاه است."}
    hits = []
    for d in STORE.text_index:
        if kind and d["kind"] != kind:
            continue
        score = sum(1 for t in terms if t in d["_n"])
        if score:
            hits.append({"score": score, "customer_id": d["customer_id"], "kind": d["kind"],
                         "date": d["date"], "date_fa": jalali.fmt(d["date"]),
                         "title": d["title"], "meta": d["meta"], "text": str(d["text"])[:500]})
    hits.sort(key=lambda x: (-x["score"], x["date"] or ""))
    by_cust: dict[str, int] = {}
    for h in hits:
        by_cust[h["customer_id"]] = by_cust.get(h["customer_id"], 0) + 1
    return {"total": len(hits), "customers": len(by_cust),
            "top_customers": sorted(by_cust.items(), key=lambda x: -x[1])[:8],
            "hits": hits[:int(limit)]}


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(400, "پرسش خالی است")
    r = COPILOT.ask(req.question, req.history)
    return r


@app.get("/api/health")
def health():
    return {"ok": True, "profiles": len(STORE.P), "mode": COPILOT.mode}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
