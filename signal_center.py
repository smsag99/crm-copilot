"""مرکز سیگنال — سه منبع، یک واحد شمارش، و یک عدد پول که ادعای علّی نمی‌کند.

سه منبع سیگنال در این داده وجود دارد و هر سه با کلید مشتری قابل نگاشت‌اند:

    شکایت           ۴۶۶ رکورد   ۱۴۲ مشتری   شیت «شکایات» + پل «اتصال_شکایت»
    درخواست توسعه   ۷۸۹ رکورد   ۲۰۴ مشتری   شیت «درخواست_توسعه»
    تعامل CRM     ۳٬۸۳۵ رکورد   ۶۲۴ مشتری   شیت «تعاملات_CRM»

# چرا این ماژول عدد «افزایش سود» نمی‌سازد

پرسش طبیعی این است: «رسیدگی به این شکایت چقدر فروش را بالا می‌برد؟» پیش از
ساختن هر فرمولی، آن را **آزمودیم** — و پاسخ داده منفی بود:

    تفاضل‌در‌تفاضل حجم ۹۰ روز، شکایتِ رسیدگی‌شده در برابر باز
        میانه ‎−۲۲٫۸ در برابر ‎−۱۴٫۰ واحد درصد،  Mann-Whitney p=۰٫۴۰
    همبستگی سرعت رسیدگی با تغییر حجم
        Spearman ρ=۰٫۰۴۴،  p=۰٫۴۵
    بازگشت خرید در ۱۸۰ روز، رسیدگی‌شده در برابر باز
        ۹۰٫۱٪ در برابر ۹۱٫۰٪ — بدون تفاوت
    خرید همان گروه کالا پس از تأیید نمونهٔ درخواست توسعه
        تأییدشده ‎−۲۶٫۸ در برابر ردشدهٔ فنی ‎−۳۰٫۱ واحد درصد،  p=۰٫۵۵

یعنی در این داده **هیچ شاهدی نیست که رسیدگی، خرید را بالا ببرد**. پس هر عددی که
به‌عنوان «افزایش فروش» بنویسیم ساختگی است. به‌جای آن، چیزی را می‌سنجیم که
واقعاً اندازه‌گیری‌پذیر است: **آنچه با نرسیدگی از دست می‌رود**، در
محافظه‌کارانه‌ترین حالت.

# ارزش کمینه — سه لایه، و ما کف را گزارش می‌کنیم

    ۱. کف اندازه‌گیری‌شده   پولی که واقعاً حرکت کرده است
       شکایت: احتمال بازگشتی × میانگین ارزش بازگشتی، برای همان نوع شکایت،
       از ۵۳۰ خط فاکتور پیوندخورده. توسعه و تعامل: صفر — چیزی حرکت نکرده.

    ۲. درآمد در معرض        درآمد سالانهٔ خود مشتری در همان گروه کالا
       سقف است، نه انتظار. روی صفحه هم با همین برچسب نوشته می‌شود.

    ۳. ارزش در خطر          درآمد در معرض × حاشیهٔ واقعی × احتمال ریزش
       حاشیهٔ واقعی یعنی پس از هزینهٔ پول؛ احتمال ریزش از مدل کالیبرهٔ
       ماندگاری (AUC ۰٫۸۳۱ روی پنجرهٔ خارج‌از‌زمان).

        ارزش کمینه = کف اندازه‌گیری‌شده + ارزش در خطر

**یک‌بار، نه سه‌بار.** کف اندازه‌گیری‌شده جمع‌پذیر است چون رویدادهای مجزاست، ولی
«ارزش در خطر» در سطح **مشتری** حساب می‌شود روی اجتماع گروه‌های کالای درگیر: یک
مشتری یک‌بار می‌رود، نه یک‌بار به‌ازای هر منبع. تعامل باز هم «مشکل محصول» نیست و
گروه کالای درگیری ندارد، پس هیچ ارزش در خطری به آن نسبت نمی‌دهیم — نقشش نشان
دادن شکاف عملیاتی است، نه پول.

چهار انتخاب که این عدد را عمداً کوچک نگه می‌دارد: فقط گروه کالای درگیر (نه کل
حساب)، حاشیهٔ **واقعی** پس از هزینهٔ پول (نه فروش)، احتمال ریزش **کالیبره‌شده**
(نه ۱۰۰٪)، و **هیچ** فرضی دربارهٔ خرید بیشتر پس از رسیدگی.

نتیجهٔ جانبی که خودش یک یافته است: برای مشتری با حاشیهٔ واقعی منفی، ارزش در خطر
صفر می‌شود — نگه‌داشتنش سود نمی‌سازد. برای همین‌ها عدد دوم می‌دهیم: ارزش رسیدگی
**اگر شرایط پرداخت اصلاح شود** و حاشیه به سطح دست‌یافتنی سبد برسد.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline import fa

TREND_DAYS = 182                 # دو نیم‌سال متوالی
GROWTH_HOT = 15.0                # ٪ رشد که «رو به رشد» می‌شود
GROWTH_COLD = -15.0

# در دو منبع «باز» معنا دارد؛ در CRM فیلد بستن اصلاً وجود ندارد.
OPEN_LABEL = {"complaint": "پروندهٔ باز", "dev": "بی‌پاسخ",
              "crm": "اقدام بعدی ثبت‌شده"}

# ── آزمون‌هایی که اجرا شد و اثر معناداری پیدا نکرد
EFFECT_TESTS = [
    {"claim": "رسیدگی به شکایت، حجم خرید ۹۰ روز بعد را بالا می‌برد",
     "test": "تفاضل‌در‌تفاضل در برابر روند سبد",
     "result": "میانهٔ ‎−۲۲٫۸ در برابر ‎−۱۴٫۰ واحد درصد", "p": 0.40,
     "n": "۲۹۰ رسیدگی‌شده در برابر ۱۳۲ باز", "verdict": "اثبات نشد"},
    {"claim": "هرچه رسیدگی سریع‌تر، اثرش بر خرید بیشتر",
     "test": "همبستگی رتبه‌ای سرعت رسیدگی با تغییر حجم",
     "result": "Spearman ρ=۰٫۰۴۴", "p": 0.45,
     "n": "۲۹۰ شکایت رسیدگی‌شده", "verdict": "اثبات نشد"},
    {"claim": "شکایت باز، مشتری را از دست می‌دهد",
     "test": "بازگشت خرید در ۱۸۰ روز پس از ثبت شکایت",
     "result": "۹۰٫۱٪ در برابر ۹۱٫۰٪", "p": None,
     "n": "۲۷۲ در برابر ۱۲۲", "verdict": "اثبات نشد"},
    {"claim": "تأیید نمونهٔ درخواست توسعه، خرید همان گروه کالا را بالا می‌برد",
     "test": "تفاضل‌در‌تفاضل روی همان گروه کالا",
     "result": "‎−۲۶٫۸ در برابر ‎−۳۰٫۱ واحد درصد", "p": 0.55,
     "n": "۱۶۹ تأییدشده در برابر ۱۶۵ ردشدهٔ فنی", "verdict": "اثبات نشد"},
]

SOURCE_META = {
    "complaint": {"label": "شکایت", "color": "critical", "sheet": "شکایات",
                  "sheet_key": "complaints",
                  "unit": "شکایت ثبت‌شده",
                  "question": "کدام مشکل کیفی تکرار می‌شود و پشتش چقدر پول است؟"},
    "dev": {"label": "درخواست توسعه", "color": "neu", "sheet": "درخواست_توسعه",
            "sheet_key": "dev_requests",
            "unit": "درخواست ثبت‌شده",
            "question": "کدام تغییر مشخصات را بیشترین درآمد پشتیبانی می‌کند؟"},
    "crm": {"label": "تعامل CRM", "color": "warning", "sheet": "تعاملات_CRM",
            "sheet_key": "crm",
            "unit": "تعامل ثبت‌شده",
            "question": "گفت‌وگو با مشتری حول چه چیزی می‌چرخد و چه چیزی معلق مانده؟"},
}

CRM_GAP_NOTE = (
    "شیت تعاملات برای هر رکورد «اقدام بعدی» ثبت می‌کند اما **هیچ فیلدی برای "
    "بستن آن ندارد** — تنها وضعیت موجود «ثبت اولیه» و «اصلاح‌شده» است. پس "
    "نمی‌توان گفت این اقدام‌ها انجام شده‌اند یا نه؛ فقط می‌دانیم ثبت شده‌اند. "
    "همین شکاف بود که لایهٔ ارجاع و گزارش کارشناس را لازم کرد: آنجا وضعیت و "
    "گزارش، هر دو ثبت می‌شوند.")


def _fa_num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _trend(dates: pd.Series, end: pd.Timestamp) -> dict:
    """شمارش دو نیم‌سال متوالی و جهت حرکت."""
    cut = end - pd.Timedelta(days=TREND_DAYS)
    prev_cut = cut - pd.Timedelta(days=TREND_DAYS)
    now = int(((dates >= cut) & (dates <= end)).sum())
    prev = int(((dates >= prev_cut) & (dates < cut)).sum())
    pct = ((now - prev) / prev * 100) if prev else None
    return {"prev": prev, "now": now,
            "change_pct": round(pct, 1) if pct is not None else None,
            "direction": ("رو به رشد" if pct is not None and pct >= GROWTH_HOT
                          else "رو به کاهش" if pct is not None and pct <= GROWTH_COLD
                          else "بی‌تغییر" if pct is not None else "تازه"),
            "window_days": TREND_DAYS,
            "range": [str(cut.date()), str(end.date())],
            "prev_range": [str(prev_cut.date()), str(cut.date())]}


def _monthly(dates: pd.Series, end: pd.Timestamp, months: int = 12) -> list[dict]:
    start = (end - pd.DateOffset(months=months)).to_period("M").to_timestamp()
    d = dates[(dates >= start) & (dates <= end)]
    if d.empty:
        return []
    g = d.dt.to_period("M").value_counts().sort_index()
    idx = pd.period_range(start.to_period("M"), end.to_period("M"), freq="M")
    return [{"month": str(m), "n": int(g.get(m, 0))} for m in idx]


# ═══════════════════════════════ جدول اکچوئری بازگشتی
def return_actuarial(C: pd.DataFrame, L: pd.DataFrame, S: pd.DataFrame) -> dict:
    """احتمال و ارزش بازگشتی برای هر نوع شکایت — از خطوط فاکتور پیوندخورده."""
    if C.empty or L.empty:
        return {"by_title": {}, "overall": {"p": 0.0, "mean_value": 0.0, "n": 0}}
    price = S.groupby("Customer_ID").apply(
        lambda g: g.line_amount.sum() / max(g.qty.sum(), 1e-9), include_groups=False)
    med = float(price.median()) if len(price) else 0.0
    lk = L.merge(C[["Complaint_ID", "Complaint_Title"]], on="Complaint_ID", how="inner")
    if lk.empty:
        return {"by_title": {}, "overall": {"p": 0.0, "mean_value": 0.0, "n": 0}}
    lk["value"] = lk.returned_qty * lk.Customer_ID.map(price).fillna(med)
    per = lk.groupby(["Complaint_Title", "Complaint_ID"]).agg(
        qty=("returned_qty", "sum"), value=("value", "sum")).reset_index()
    out = {}
    for title, g in per.groupby("Complaint_Title"):
        n = len(g)
        out[title] = {"n": int(n),
                      "p_return": round(float((g.qty > 0).mean()), 3),
                      "total_value": round(float(g.value.sum())),
                      "expected_cost": round(float(g.value.sum() / n))}
    ov = {"p": round(float((per.qty > 0).mean()), 3),
          "mean_value": round(float(per.value.sum() / len(per))),
          "total_value": round(float(per.value.sum())), "n": int(len(per))}
    return {"by_title": out, "overall": ov,
            "note": (f"از {len(per)} شکایتِ پیوندخورده به خط فاکتور. "
                     f"{ov['p'] * 100:.1f}٪ آن‌ها بازگشتی داشته‌اند و مجموع ارزش "
                     f"بازگشتی {ov['total_value']:,.0f} است.")}


# ═══════════════════════════════ تقاضای انباشته برای هر نوع درخواست
def dev_demand(R: pd.DataFrame, S: pd.DataFrame, F: pd.DataFrame) -> list[dict]:
    """درآمدی که پشت هر نوع درخواست توسعه ایستاده — اولویت تحقیق‌وتوسعه."""
    if R.empty:
        return []
    rev = S.groupby("Customer_ID").line_amount.sum()
    rgp = F.real_gp if "real_gp" in F.columns else pd.Series(dtype=float)
    rows = []
    for rt, g in R.groupby("Request_Type"):
        u = g.drop_duplicates("Customer_ID")
        cust = u.Customer_ID.tolist()
        rows.append({
            "request_type": fa(rt), "raw": rt,
            "requests": int(len(g)),
            "customers": int(len(u)),
            "revenue": round(float(rev.reindex(cust).fillna(0).sum())),
            "real_gp": round(float(rgp.reindex(cust).fillna(0).sum())),
            "open": int(g.Status.isin(["under_review", "in_development"]).sum()),
            "approved": int((g.Status == "sample_approved").sum()),
            "rejected": int((g.Status == "technically_rejected").sum()),
            "reject_rate": round(float((g.Status == "technically_rejected").mean() * 100), 1),
        })
    rows.sort(key=lambda r: -r["revenue"])
    return rows


# ═══════════════════════════════ ارزش کمینه برای یک مشتری در یک منبع
def _family_share(mix: dict, families: set) -> float:
    if not mix:
        return 0.0
    if not families:
        return 1.0
    return min(sum(v for k, v in mix.items() if k in families) / 100.0, 1.0)


def _value(p: dict, families: set, measured_floor: float,
           achievable_margin: float) -> dict:
    """ارزش کمینهٔ رسیدگی = کف اندازه‌گیری‌شده + ارزش در خطر."""
    c, f = p["commercial"], (p.get("features") or {})
    months = max(_fa_num(c.get("active_months")) or 1, 1)
    rev_year = _fa_num(c.get("revenue_nominal")) * min(12 / months, 1.0)
    share = _family_share(c.get("product_family_mix") or {}, families)
    exposure = rev_year * share
    rm = _fa_num(f.get("real_margin"))
    churn = max(0.0, min(1.0, 1 - _fa_num(f.get("retention"))))
    at_risk = exposure * max(rm, 0.0) / 100 * churn
    if_fixed = exposure * max(achievable_margin, 0.0) / 100 * churn
    blocked = bool(rm <= 0 and exposure > 0)
    return {
        "measured_floor": round(measured_floor),
        "exposure": round(exposure),
        "family_share_pct": round(share * 100, 1),
        "real_margin": round(rm, 2),
        "churn": round(churn, 3),
        "at_risk": round(at_risk),
        "min_value": round(measured_floor + at_risk),
        "value_if_terms_fixed": round(measured_floor + if_fixed),
        "margin_blocked": blocked,
        "basis": ("کف اندازه‌گیری‌شده + درآمد گروه کالای درگیر × حاشیهٔ واقعی × احتمال ریزش"
                  if not blocked else
                  "حاشیهٔ واقعی این مشتری منفی است؛ نگه‌داشتنش سود واقعی نمی‌سازد — "
                  f"عدد دوم، ارزش رسیدگی در صورت اصلاح شرایط پرداخت تا {achievable_margin:.2f}٪ است"),
    }


# ═══════════════════════════════ ساخت
def build(V: dict[str, pd.DataFrame], profiles: dict[str, dict],
          frame: pd.DataFrame, as_of: pd.Timestamp,
          achievable_margin: float = 6.83, limit: int = 200) -> dict:
    S, C, L, R, X = (V["sales"], V["complaints"], V["complaint_links"],
                     V["dev_requests"], V["crm"])
    end = min(as_of, S.date.max())
    act = return_actuarial(C, L, S)
    demand = dev_demand(R, S, frame)
    fam_of = S.groupby("Product_ID").product_family.first()

    # ── بخش‌ها: هر منبع، دسته‌بندی درونی، روند، و نگاشت به مشتری
    def section(key, df, tcol, cat_col, open_mask=None) -> dict:
        meta = SOURCE_META[key]
        cats = []
        for cat, g in df.groupby(cat_col):
            tr = _trend(g[tcol], end)
            cats.append({"category": fa(cat), "raw": cat, "n": int(len(g)),
                         "customers": int(g.Customer_ID.nunique()),
                         "open": int(open_mask(g)) if open_mask else 0,
                         **tr})
        cats.sort(key=lambda r: -r["n"])
        return {"key": key, **meta, "open_label": OPEN_LABEL[key],
                "total": int(len(df)), "customers": int(df.Customer_ID.nunique()),
                "open": int(open_mask(df)) if open_mask else 0,
                "trend": _trend(df[tcol], end),
                "monthly": _monthly(df[tcol], end),
                "categories": cats}

    sections = [
        section("complaint", C, "Created_At", "Complaint_Title",
                lambda g: (g.Complaint_Status != "closed").sum()),
        section("dev", R, "Created_At", "Request_Type",
                lambda g: g.Status.isin(["under_review", "in_development"]).sum()),
        section("crm", X, "Event_Time", "Interaction_Type",
                lambda g: (g.Next_Action != "no_action").sum()),
    ]

    # ── نگاشت به مشتری: هر مشتری، در هر منبع، چند اکتیویتی و چقدر پول
    rows: list[dict] = []
    prio = {}
    for cid, p in profiles.items():
        cc = C[C.Customer_ID == cid]
        rr = R[R.Customer_ID == cid]
        xx = X[X.Customer_ID == cid]
        if cc.empty and rr.empty and xx.empty:
            continue
        f = p.get("features") or {}
        entry = {"customer_id": cid,
                 "segment": p["identity"]["segment"],
                 "rfm_segment": f.get("rfm_segment"),
                 "revenue_rank": p["commercial"]["revenue_rank"],
                 "real_margin": round(_fa_num(f.get("real_margin")), 2),
                 "retention": round(_fa_num(f.get("retention")), 3),
                 "sources": {}, "min_value": 0, "exposure": 0,
                 "value_if_terms_fixed": 0}

        # ── کف اندازه‌گیری‌شده جمع‌پذیر است (رویدادهای مجزا)، ولی «ارزش در خطر»
        # یک‌بار در سطح مشتری حساب می‌شود: یک مشتری یک‌بار می‌رود، نه سه‌بار.
        fams: set[str] = set()
        floor = 0.0
        if not cc.empty:
            floor += sum(act["by_title"].get(t, {}).get("expected_cost", 0)
                         for t in cc[cc.Complaint_Status != "closed"].Complaint_Title)
            cfam = set(cc.product_family.dropna())
            fams |= cfam
            entry["sources"]["complaint"] = {
                "n": int(len(cc)),
                "open": int((cc.Complaint_Status != "closed").sum()),
                "critical": int(cc.Severity.isin(["critical", "high"]).sum()),
                "top": cc.Complaint_Title.value_counts().head(3).to_dict(),
                "families": sorted(cfam),
                "last": str(cc.Created_At.max().date()),
                "measured_floor": round(floor),
                "exposure": round(_value(p, cfam, 0.0, achievable_margin)["exposure"]),
                "risk_basis": bool(cfam)}
        if not rr.empty:
            dfam = set(rr.Product_ID.map(fam_of).dropna())
            fams |= dfam
            entry["sources"]["dev"] = {
                "n": int(len(rr)),
                "open": int(rr.Status.isin(["under_review", "in_development"]).sum()),
                "approved": int((rr.Status == "sample_approved").sum()),
                "rejected": int((rr.Status == "technically_rejected").sum()),
                "top": {fa(k): int(v) for k, v in rr.Request_Type.value_counts().head(3).items()},
                "families": sorted(dfam),
                "last": str(rr.Created_At.max().date()),
                "measured_floor": 0,
                "exposure": round(_value(p, dfam, 0.0, achievable_margin)["exposure"]),
                "risk_basis": bool(dfam)}
        if not xx.empty:
            pend = xx[xx.Next_Action != "no_action"]
            entry["sources"]["crm"] = {
                "n": int(len(xx)), "open": int(len(pend)),
                "top": {fa(k): int(v) for k, v in xx.Interaction_Type.value_counts().head(3).items()},
                "next_actions": {fa(k): int(v) for k, v in
                                 pend.Next_Action.value_counts().head(3).items()},
                "oldest_days": (int((end - pend.Event_Time.min()).days)
                                if len(pend) else None),
                "last_days": (int((end - pend.Event_Time.max()).days)
                              if len(pend) else None),
                "last": str(xx.Event_Time.max().date()),
                "measured_floor": 0, "exposure": 0,
                # تعامل باز، «مشکل محصول» نیست: گروه کالای درگیری ندارد، پس
                # هیچ ارزش در خطری به آن نسبت نمی‌دهیم. نقشش شکاف عملیاتی است.
                "risk_basis": False}

        v = _value(p, fams, floor, achievable_margin)
        entry["value"] = v
        entry["activities"] = sum(s["n"] for s in entry["sources"].values())
        entry["open_total"] = sum(s.get("open", 0) for s in entry["sources"].values())
        entry["min_value"] = v["min_value"]
        entry["exposure"] = v["exposure"]
        entry["value_if_terms_fixed"] = v["value_if_terms_fixed"]
        entry["margin_blocked"] = v["margin_blocked"]
        rows.append(entry)

    rows.sort(key=lambda r: (-r["min_value"], -r["value_if_terms_fixed"],
                             -r["activities"]))
    blocked = [r for r in rows if r["margin_blocked"]]

    crm_pend = X[X.Next_Action != "no_action"]
    crm_gap = {
        "with_next_action": int(len(crm_pend)),
        "total": int(len(X)),
        "customers": int(crm_pend.Customer_ID.nunique()),
        "older_than_90": int(((end - crm_pend.Event_Time).dt.days > 90).sum()),
        "median_age": int((end - crm_pend.Event_Time).dt.days.median()),
        "note": CRM_GAP_NOTE,
    }
    return {
        "sections": sections,
        "rows": rows[:limit],
        "total_rows": len(rows),
        "min_value_total": round(sum(r["min_value"] for r in rows)),
        "exposure_total": round(sum(r["exposure"] for r in rows)),
        "if_fixed_total": round(sum(r["value_if_terms_fixed"] for r in rows)),
        "blocked_customers": len(blocked),
        "blocked_value": round(sum(r["value_if_terms_fixed"] for r in blocked)),
        "return_actuarial": act,
        "dev_demand": demand,
        "crm_gap": crm_gap,
        "effect_tests": EFFECT_TESTS,
        "achievable_margin": achievable_margin,
        "as_of": str(end.date()),
        "headline": ("سه منبع سیگنال، ۹۰ روز روند، و یک عدد پول که ادعای علّی "
                     "نمی‌کند: ارزش کمینهٔ رسیدگی، نه افزایش فروش."),
        "value_note": (
            "چهار آزمون نشان داد رسیدگی، خرید بعدی را بالا نمی‌برد (p بین ۰٫۴۰ و "
            "۰٫۵۵). پس این عدد **ارزش از‌دست‌رفتنی** است، نه افزایش فروش: کف "
            "اندازه‌گیری‌شدهٔ بازگشتی، به‌علاوهٔ درآمد گروه کالای درگیر ضربدر "
            "حاشیهٔ واقعی ضربدر احتمال ریزش کالیبره‌شده."),
    }
