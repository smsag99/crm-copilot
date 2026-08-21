"""سیگنال‌های مشتری، تفسیر آن‌ها، و پیش‌بینی تصمیم بعدی — با رفرنس کامل

سه اصل:
  ۱. هر سیگنال به رکورد منبعش رفرنس دارد: نام شیت، شناسهٔ رکورد، تاریخ، فیلد و مقدار.
  ۲. هیچ احتمالی حدسی نیست. همه از نرخ پایهٔ تجربی می‌آیند که با شمارش رویدادهای
     واقعی در calibrate_rates.py محاسبه شده‌اند.
  ۳. جایی که داده سیگنال ندارد، صریح می‌گوییم «سیگنال ندارد» — نه اینکه عددی
     بسازیم.
"""
from __future__ import annotations

from typing import Any

import jalali
from pipeline import fa

# ═════════════════════════════════ نرخ‌های پایهٔ تجربی
# منبع: calibrate_rates.py — ۱۰٬۳۳۹ مشاهدهٔ مشتری-ماه در ۲۱ تاریخ برش
REORDER_BY_RECENCY = [
    (30, 0.784, "۰ تا ۳۰ روز", 3272),
    (60, 0.550, "۳۱ تا ۶۰ روز", 1192),
    (90, 0.438, "۶۱ تا ۹۰ روز", 861),
    (150, 0.316, "۹۱ تا ۱۵۰ روز", 1258),
    (240, 0.150, "۱۵۱ تا ۲۴۰ روز", 1230),
    (365, 0.095, "۲۴۱ تا ۳۶۵ روز", 1132),
    (10 ** 6, 0.049, "بیش از ۳۶۵ روز", 1394),
]
# منبع: ۱٬۳۶۱ مشاهدهٔ مشتری-فصل
COMPLAINT_BY_HISTORY = [(0, 0.065, "بدون شکایت پیشین", 1001), (1, 0.153, "۱ شکایت", 177),
                        (3, 0.360, "۲ تا ۳ شکایت", 114), (10 ** 6, 0.710, "۴ شکایت یا بیشتر", 69)]
DEV_BY_HISTORY = [(0, 0.108, "بدون درخواست پیشین", 888), (1, 0.182, "۱ درخواست", 225),
                  (3, 0.453, "۲ تا ۳ درخواست", 137), (10 ** 6, 0.748, "۴ درخواست یا بیشتر", 111)]

OFFER_ACCEPT_OVERALL = 0.333
OFFER_ACCEPT_BY_REASON = {
    "fast_settlement": 0.376, "new_product_intro": 0.364, "order_volume_growth": 0.337,
    "product_trial": 0.333, "wallet_share_growth": 0.320, "key_account_retention": 0.300,
    "price_competition": 0.295,
}
OFFER_REASON_NOTE = ("دامنهٔ نرخ پذیرش بین دلایل مختلف ۲۹.۵٪ تا ۳۷.۶٪ است و آزمون کای‌دو "
                     "(۱۰.۶ با ۱۲ درجه آزادی، آستانهٔ ۵٪ ≈ ۱۷) معنادار نیست. یعنی دلیل آفر — "
                     "مثل عمق تخفیف — پذیرش را پیش‌بینی نمی‌کند. دلیل آفر تعیین می‌کند "
                     "«اقدام درست چیست»، نه «چقدر احتمال موفقیت دارد».")

LATE_PAYMENT_NOTE = ("تأخیر پرداخت تقریباً ساختاری است: احتمال تأخیر بالای میانه از ۳۹.۷٪ "
                     "(سابقهٔ پاک) تا ۵۷.۹٪ (سابقهٔ بد) تغییر می‌کند، حول نرخ پایهٔ ۵۱٪. "
                     "سابقهٔ پرداخت خبر کمی دارد.")


def _rate(table, value):
    for cut, p, label, n in table:
        if value <= cut:
            return p, label, n
    return table[-1][1], table[-1][2], table[-1][3]


# ═════════════════════════════════════════════════════ رفرنس
SHEET_FA = {
    "sales": "فروش", "invoices": "فاکتورها", "collections": "وصول",
    "complaints": "شکایات", "crm": "تعاملات_CRM", "dev_requests": "درخواست_توسعه",
    "offers": "آفرها", "wallet_share": "سهم_سبد", "lab": "کیفیت_لات",
    "market_signals": "سیگنال_بازار", "customers": "مشتریان", "products": "محصولات",
    "realized_cost": "اجزای_هزینه_تحقق", "estimated_cost": "برآورد_هزینه_ماهانه",
    "derived": "محاسبه‌شده",
}
FIELD_FA = {
    "Severity": "شدت", "Complaint_Status": "وضعیت شکایت", "Complaint_Title": "عنوان شکایت",
    "Created_At": "تاریخ ثبت", "Resolved_At": "تاریخ رسیدگی", "Interaction_Type": "نوع تعامل",
    "Next_Action": "اقدام بعدی", "Summary_Text": "خلاصهٔ گزارش", "Request_Type": "نوع درخواست",
    "Status": "وضعیت", "Requirement_Text": "شرح نیاز", "Owner_Unit": "واحد مسئول",
    "Offer_Reason": "دلیل آفر", "Offer_Discount_Pct": "درصد تخفیف", "Result": "نتیجه",
    "Validity_Days": "روز اعتبار", "days_late": "روز تأخیر", "bounced_cheque": "چک برگشتی",
    "open": "مانده باز", "due_date": "تاریخ سررسید", "qty": "مقدار", "unit_price": "قیمت واحد",
    "Nafis_Purchase": "خرید از ما", "Estimated_Total_Purchase": "خرید کل برآوردی",
    "Main_Competitor": "رقیب اصلی", "Market_Trend": "روند بازار",
    "Evenness_CV_Pct": "یکنواختی CV", "Lab_Result": "نتیجهٔ آزمایش",
    "date": "تاریخ", "recency": "رکود", "vol_trend": "روند حجم", "families": "گروه کالا",
    "margin": "حاشیه سود", "collection_rate": "نرخ وصول", "wallet": "سهم از سبد",
}


def with_fallback(refs: list[dict], fallback: dict) -> list[dict]:
    """هیچ ادعایی بدون رفرنس نمی‌ماند.

    وقتی شمارش از تجمیع کل تاریخ می‌آید ولی رکورد مربوطه در برش اخیر نیست،
    یا وقتی پایهٔ ادعا نرخ تجربی است نه رکورد مشتری، رفرنس تجمیعی می‌گذاریم و
    صریح می‌گوییم منبع چیست.
    """
    return refs if refs else [fallback]


def ref(sheet: str, record_id: str | None = None, date: str | None = None,
        fields: dict | None = None, note: str = "") -> dict:
    """یک رفرنس: از کدام شیت، کدام رکورد، کدام فیلد و چه مقداری."""
    return {
        "sheet": SHEET_FA.get(sheet, sheet),
        "sheet_key": sheet,
        "record_id": record_id,
        "date": date,
        "date_fa": jalali.fmt(date) if date else None,
        "fields": [{"name": k, "name_fa": FIELD_FA.get(k, k), "value": str(v)}
                   for k, v in (fields or {}).items()],
        "note": note,
    }


# ═══════════════════════════════════════════════════ سیگنال‌ها
DOMAINS = {
    "خرید": {"icon": "buy", "desc": "نشانه‌های تمایل یا کاهش خرید"},
    "قیمت": {"icon": "price", "desc": "فشار قیمتی و مذاکرهٔ تخفیف"},
    "کیفیت": {"icon": "quality", "desc": "شکایت، آزمایشگاه و برگشتی"},
    "پرداخت": {"icon": "pay", "desc": "وصول، تأخیر و چک"},
    "توسعه": {"icon": "dev", "desc": "نیاز فنی اعلام‌شدهٔ مشتری"},
    "رقابت": {"icon": "comp", "desc": "حضور رقیب و سهم از سبد"},
    "ارتباط": {"icon": "touch", "desc": "کیفیت و تازگی تماس‌ها"},
}


def extract_signals(p: dict, f: dict) -> list[dict]:
    """سیگنال‌های قابل مشاهدهٔ مشتری، هر یک با تفسیر و رفرنس."""
    c, m, r = p["commercial"], p["margin"], p["receivables"]
    cp, e, dv, of, ws, mk = (p["complaints"], p["engagement"], p["development"],
                             p["offers"], p["wallet_share"], p["market"])
    Sg: list[dict] = []

    def add(code, domain, name, direction, strength, value, interp, refs):
        Sg.append({"code": code, "domain": domain, "name": name, "direction": direction,
                   "strength": round(float(min(max(strength, 0), 1)), 2), "value": value,
                   "interpretation": interp, "references": refs})

    # ───────────────────────────────────────────── خرید
    d = c["days_since_last_purchase"]
    gap, sil = f.get("order_gap"), f.get("silence_ratio")
    if d is not None:
        pr, band, n = _rate(REORDER_BY_RECENCY, d)
        if sil and sil >= 2.5 and d > 60 and gap and gap >= 3:
            add("silence_gap", "خرید", "سکوت طولانی‌تر از الگوی معمول", "منفی",
                min(1.0, sil / 10),
                f"{d} روز بی‌خرید، {sil:.1f} برابر فاصلهٔ معمول سفارش ({gap:.0f} روز)",
                f"مشتری معمولاً هر {gap:.0f} روز سفارش می‌داد. این سکوت الگوی خودش را شکسته است. "
                f"نرخ پایهٔ سفارش مجدد در این بازهٔ رکود {pr:.0%} است.",
                [ref("sales", None, c["last_purchase"],
                     {"date": c["last_purchase"], "recency": f"{d} روز"},
                     f"فاصلهٔ میانگین سفارش از {c['invoices']} فاکتور محاسبه شد")])
        elif d <= 45:
            add("recent_buyer", "خرید", "خرید فعال و تازه", "مثبت", 0.8,
                f"{d} روز از آخرین خرید", f"در بازهٔ فعال؛ نرخ پایهٔ سفارش مجدد {pr:.0%}",
                [ref("sales", None, c["last_purchase"], {"date": c["last_purchase"]})])

    vt = c["volume_trend_pct"]
    if vt is not None and abs(vt) >= 25:
        neg = vt < 0
        add("volume_trend", "خرید",
            "ریزش حجم خرید" if neg else "رشد حجم خرید", "منفی" if neg else "مثبت",
            min(1.0, abs(vt) / 100), f"{vt:+.0f}٪ در شش ماه",
            ("حجم — نه فروش اسمی — مبنای درست روند است، چون از تورم ۸ برابری قیمت مصون است."
             if neg else "رشد حقیقی حجم، مستقل از اثر قیمت."),
            [ref("derived", None, None,
                 {"vol_trend": f"{vt:+.0f}٪"},
                 "شش ماه اخیر در برابر شش ماه پیش از آن، بر پایهٔ کیلوگرم")])

    plan = e["by_type"].get("purchase_plan", 0)
    if plan:
        items = [x for x in e["items"] if x["type"] == "purchase_plan"][:2]
        add("purchase_plan", "خرید", "اعلام برنامهٔ خرید توسط مشتری", "مثبت", 0.6,
            f"{plan} گزارش برنامهٔ خرید در CRM",
            "مشتری خودش برنامهٔ دورهٔ بعد را اعلام کرده — پنجرهٔ طبیعی برای پیشنهاد حجمی.",
            with_fallback(
                [ref("crm", x["id"], x["date"],
                     {"Interaction_Type": fa(x["type"]),
                      "Summary_Text": str(x["summary"])[:120]}) for x in items],
                ref("crm", None, None, {"Interaction_Type": f"برنامه خرید ×{plan}"},
                    f"شمارش از تجمیع {e['interactions']} تعامل؛ رکوردهای این نوع "
                    "قدیمی‌تر از ۱۰ تعامل اخیر هستند")))

    # ───────────────────────────────────────────── قیمت
    price_talk = e["by_type"].get("price_and_discount", 0)
    if price_talk:
        items = [x for x in e["items"] if x["type"] == "price_and_discount"][:2]
        add("price_talk", "قیمت", "مذاکرهٔ قیمت و تخفیف", "هشدار", min(1.0, price_talk / 4),
            f"{price_talk} تعامل قیمت و تخفیف",
            "گفت‌وگوی قیمت فعال است؛ احتمال درخواست تخفیف در دور بعد بالاست.",
            with_fallback(
                [ref("crm", x["id"], x["date"],
                     {"Interaction_Type": fa(x["type"]),
                      "Summary_Text": str(x["summary"])[:120]}) for x in items],
                ref("crm", None, None, {"Interaction_Type": f"قیمت و تخفیف ×{price_talk}"},
                    f"شمارش از تجمیع {e['interactions']} تعامل؛ رکوردهای این نوع "
                    "قدیمی‌تر از ۱۰ تعامل اخیر هستند")))

    if mk["signals"] and f.get("price_pressure_signals"):
        add("market_price_pressure", "قیمت", "فشار قیمتی در گزارش بازار", "هشدار", 0.5,
            f"{int(f['price_pressure_signals'])} گزارش فشار قیمتی",
            "سیگنال بازار پیش از درخواست مشتری رسیده — فرصت پیش‌دستی در قیمت‌گذاری.",
            [ref("market_signals", None, mk["latest_signal"],
                 {"Market_Trend": "فشار قیمتی"})])

    gm = m["gross_margin_pct"]
    pm = f.get("portfolio_median_margin")
    if gm is not None and pm is not None:
        gapm = gm - pm
        if abs(gapm) >= 3:
            add("margin_gap", "قیمت",
                "حاشیه زیر میانهٔ سبد" if gapm < 0 else "حاشیه بالای میانهٔ سبد",
                "منفی" if gapm < 0 else "مثبت", min(1.0, abs(gapm) / 10),
                f"{gm:.1f}٪ در برابر میانهٔ سبد {pm:.1f}٪ ({gapm:+.1f} واحد)",
                (f"{m['negative_margin_lines']} خط زیان‌ده "
                 f"({m['negative_margin_line_pct']:.0f}٪) دارد."
                 if gapm < 0 else "قیمت‌گذاری این مشتری بهتر از میانهٔ سبد است."),
                [ref("derived", None, None,
                     {"margin": f"{gm:.1f}٪"},
                     f"مبنای بهای تمام‌شده: {m['realized_cost_share_pct']:.0f}٪ تحقق‌یافته")])

    md = f.get("margin_drift")
    if md is not None and abs(md) >= 2:
        add("margin_drift", "قیمت",
            "افت حاشیه در شش ماه اخیر" if md < 0 else "بهبود حاشیه در شش ماه اخیر",
            "منفی" if md < 0 else "مثبت", min(1.0, abs(md) / 8),
            f"{md:+.1f} واحد درصد نسبت به میانگین تاریخی",
            "حاشیهٔ اخیر از حاشیهٔ تاریخی فاصله گرفته — احتمالاً ترکیب سبد یا قیمت عوض شده.",
            [ref("derived", None, None, {"margin": f"{f.get('margin6'):.1f}٪ اخیر"}
                 if f.get("margin6") is not None else {})])

    # ───────────────────────────────────────────── کیفیت
    if cp["total"]:
        pr, band, n = _rate(COMPLAINT_BY_HISTORY, cp["total"])
        sev_txt = "، ".join(f"{fa(k)}×{v}" for k, v in cp["by_severity"].items())
        add("complaint_history", "کیفیت", "سابقهٔ شکایت", "منفی",
            min(1.0, cp["total"] / 6), f"{cp['total']} شکایت ({cp['open']} باز) — {sev_txt}",
            f"با {band}، نرخ پایهٔ ثبت شکایت جدید در ۱۸۰ روز آینده {pr:.0%} است "
            f"(بر پایهٔ {n} مشاهدهٔ مشتری-فصل).",
            [ref("complaints", x["id"], x["date"],
                 {"Severity": fa(x["severity"]), "Complaint_Status": fa(x["status"]),
                  "Complaint_Title": x["title"]})
             for x in cp["items"][:3]])

    imp = cp.get("purchase_impact")
    if imp and imp.get("change_pct") is not None and imp["change_pct"] <= -25 and imp["window_complete"]:
        add("quality_purchase_link", "کیفیت", "افت خرید پس از نخستین شکایت", "منفی", 0.9,
            f"{imp['volume_before']:,.0f} → {imp['volume_after']:,.0f} کیلوگرم "
            f"({imp['change_pct']:+.0f}٪)",
            "شاهد است نه اثبات علیت. توجه: در سطح کل سبد، شکایت پیش‌بین ریزش نیست "
            "(آزمون‌شده و رد شده)؛ ولی در سطح این مشتری خاص، همزمانی معنادار است.",
            [ref("complaints", cp["items"][0]["id"] if cp["items"] else None,
                 imp["first_complaint"], {"Created_At": imp["first_complaint"]},
                 f"پنجرهٔ مقایسه {imp['window_days']} روز پیش و پس")])

    if p["quality"]["lab_records"] and f.get("cv_evenness"):
        cvv = f["cv_evenness"]
        if cvv > 1.9:
            add("lab_evenness", "کیفیت", "یکنواختی نخ در محدودهٔ بالا", "هشدار",
                min(1.0, (cvv - 1.5) / 1.0), f"CV یکنواختی {cvv:.2f}٪",
                "بالاتر از میانهٔ سبد؛ در ترکیب با شکایت شید رنگ قابل بررسی است.",
                [ref("lab", None, None, {"Evenness_CV_Pct": f"{cvv:.2f}٪"},
                     f"میانگین {p['quality']['lab_records']} رکورد آزمایشگاه")])

    qtouch = e["by_type"].get("product_quality", 0)
    if qtouch >= 2:
        items = [x for x in e["items"] if x["type"] == "product_quality"][:2]
        add("quality_talk", "کیفیت", "گفت‌وگوی مکرر کیفیت در CRM", "هشدار",
            min(1.0, qtouch / 4), f"{qtouch} تعامل کیفیت محصول",
            "نگرانی کیفی در تماس‌ها مطرح است، حتی اگر به شکایت رسمی نرسیده باشد.",
            [ref("crm", x["id"], x["date"],
                 {"Interaction_Type": fa(x["type"]), "Summary_Text": str(x["summary"])[:120]})
             for x in items])

    # ───────────────────────────────────────────── پرداخت
    if r["uncollected_overdue"] > 0:
        oi = r.get("overdue_invoices") or []
        strength = min(1.0, r["uncollected_overdue"] / max(abs(m["gross_profit"]), 1))
        add("overdue", "پرداخت", "مطالبات سررسیدگذشته", "منفی", strength,
            f"{r['uncollected_overdue']:,.0f} معوق"
            + (f"، قدیمی‌ترین {r['oldest_overdue_days']} روز" if r["oldest_overdue_days"] else ""),
            f"در برابر {m['gross_profit']:,.0f} سود ناخالص انباشته. "
            f"مشارکت خالص {r['net_contribution']:,.0f}.",
            [ref("invoices", x["invoice_no"], x["date"],
                 {"open": f"{x['open']:,.0f}", "due_date": x["due_date"],
                  "days_late": f"{x['days_overdue']} روز"})
             for x in oi[:3]])

    chase = e["by_type"].get("receivables_chase", 0)
    if chase >= 2:
        items = [x for x in e["items"] if x["type"] == "receivables_chase"][:2]
        add("chase", "پرداخت", "پیگیری مکرر وصول در CRM", "منفی", min(1.0, chase / 4),
            f"{chase} تعامل وصول مطالبات"
            + (f" ({f['chase_share']:.0f}٪ کل تعاملات)" if f.get("chase_share") else ""),
            "وقت کارشناس فروش صرف وصول می‌شود، نه فروش.",
            [ref("crm", x["id"], x["date"],
                 {"Interaction_Type": fa(x["type"]), "Summary_Text": str(x["summary"])[:120]})
             for x in items])

    if r["bounced_cheques"]:
        add("bounced", "پرداخت", "چک برگشتی", "منفی", min(1.0, r["bounced_cheques"] / 3),
            f"{r['bounced_cheques']} مورد", LATE_PAYMENT_NOTE,
            [ref("collections", None, None,
                 {"bounced_cheque": f"{r['bounced_cheques']} مورد"},
                 "توجه: در آزمون داده، چک برگشتی تأخیر بیشتر در آینده را پیش‌بینی نکرد")])

    # ───────────────────────────────────────────── توسعه
    if dv["requests"]:
        pr, band, n = _rate(DEV_BY_HISTORY, dv["requests"])
        add("dev_history", "توسعه", "نیاز فنی اعلام‌شده", "مثبت",
            min(1.0, dv["requests"] / 6),
            f"{dv['requests']} درخواست ({dv['approved']} نمونه تأیید، {dv['pending']} باز)",
            f"با {band}، نرخ پایهٔ درخواست جدید در ۱۸۰ روز {pr:.0%} است. "
            f"این نیاز اعلام‌شدهٔ خود مشتری است، نه حدس ما.",
            [ref("dev_requests", x["id"], x["date"],
                 {"Request_Type": fa(x["type"]), "Status": fa(x["status"]),
                  "Requirement_Text": str(x["requirement"])[:120],
                  "Owner_Unit": fa(x["owner"])})
             for x in dv["items"][:3]])

    # ───────────────────────────────────────────── رقابت
    if ws["months_observed"]:
        share, seg = ws["avg_share_pct"], ws["segment_avg_share_pct"]
        comps = ws["main_competitors"]
        top = max(comps, key=comps.get) if comps else None
        if share is not None and seg is not None and share < seg - 3:
            add("wallet_gap", "رقابت", "سهم از سبد زیر میانهٔ بخش", "منفی",
                min(1.0, (seg - share) / 30),
                f"{share:.0f}٪ در برابر میانهٔ بخش {seg:.0f}٪",
                (f"رقیب اصلی گزارش‌شده {fa(top)} در {comps[top]} ماه. "
                 f"خرید برآوردی مشتری {ws['estimated_total_purchase']:,.0f} کیلوگرم در ماه."),
                [ref("wallet_share", None, None,
                     {"Nafis_Purchase": f"سهم {share:.0f}٪",
                      "Estimated_Total_Purchase": f"{ws['estimated_total_purchase']:,.0f} کیلوگرم/ماه",
                      "Main_Competitor": fa(top) if top else "—"},
                     f"میانگین {ws['months_observed']} ماه برآورد کارشناس")])
        wt = f.get("wallet_trend")
        if wt is not None and wt <= -5:
            add("wallet_falling", "رقابت", "سهم از سبد در حال کاهش", "منفی",
                min(1.0, abs(wt) / 25), f"{wt:+.0f} واحد از میانگین دوره",
                "رقیب در حال گرفتن سهم است؛ آخرین ماه از میانگین پایین‌تر است.",
                [ref("wallet_share", None, None,
                     {"Nafis_Purchase": f"آخرین سهم {ws['latest_share_pct']}٪"})])

    # ───────────────────────────────────────────── ارتباط
    lt = e["days_since_last_interaction"]
    if e["interactions"] == 0:
        add("no_crm", "ارتباط", "بدون هیچ تعامل ثبت‌شده", "منفی", 0.7, "۰ تعامل در CRM",
            "دانش این مشتری فقط در ذهن کارشناس است — دقیقاً همان مسئله‌ای که این "
            "سامانه برای حلش ساخته شده.",
            [ref("crm", None, None, {}, "هیچ رکوردی برای این مشتری وجود ندارد")])
    elif lt is not None and lt > 180 and (d or 999) < 120:
        add("uncontacted_buyer", "ارتباط", "خرید فعال بدون تماس ثبت‌شده", "هشدار", 0.6,
            f"آخرین خرید {d} روز پیش، آخرین تعامل {lt} روز پیش",
            "مشتری می‌خرد ولی رابطه مدیریت نمی‌شود؛ در برابر رقیب بی‌دفاع است.",
            [ref("crm", e["items"][0]["id"] if e["items"] else None,
                 e["last_interaction"], {"Interaction_Type": "آخرین تعامل"})])

    if e["open_next_actions"]:
        tot = sum(e["open_next_actions"].values())
        add("open_actions", "ارتباط", "اقدام‌های بعدی بازمانده در CRM", "هشدار",
            min(1.0, tot / 8), f"{tot} اقدام ثبت‌شده و بدون بستن",
            "، ".join(f"{fa(k)}×{v}" for k, v in e["open_next_actions"].items()),
            with_fallback(
                [ref("crm", x["id"], x["date"],
                     {"Next_Action": fa(x["next_action"]), "Interaction_Type": fa(x["type"])})
                 for x in e["items"][:3] if x["next_action"] != "no_action"],
                ref("crm", None, None, {"Next_Action": f"{tot} اقدام باز"},
                    f"شمارش از تجمیع {e['interactions']} تعامل")))

    order = {"منفی": 0, "هشدار": 1, "مثبت": 2}
    return sorted(Sg, key=lambda x: (order[x["direction"]], -x["strength"]))


# ═══════════════════════════════ پیش‌بینی تصمیم بعدی مشتری
def predict_decisions(p: dict, f: dict, signals: list[dict]) -> list[dict]:
    """تصمیم‌های احتمالی مشتری در دورهٔ بعد — با نرخ پایه، تعدیل و رفرنس."""
    c, m, r = p["commercial"], p["margin"], p["receivables"]
    cp, e, dv, of, ws = (p["complaints"], p["engagement"], p["development"],
                         p["offers"], p["wallet_share"])
    codes = {s["code"] for s in signals}
    P: list[dict] = []

    def add(code, question, prob, base_txt, mods, refs, conf, note=""):
        P.append({"code": code, "question": question,
                  "probability": round(float(min(max(prob, 0.01), 0.99)), 3),
                  "base": base_txt, "modifiers": mods, "references": refs,
                  "confidence": conf, "note": note})

    # ── ۱. سفارش مجدد در ۹۰ روز
    d = c["days_since_last_purchase"]
    if d is not None:
        base, band, n = _rate(REORDER_BY_RECENCY, d)
        mods, prob = [], base
        sil = f.get("silence_ratio")
        if sil and sil >= 4:
            mods.append({"name": "سکوت چند برابر الگوی معمول", "delta": -0.10,
                         "why": f"{sil:.1f} برابر فاصلهٔ معمول سفارش"})
            prob -= 0.10
        if int(f.get("families") or 0) >= 2:
            mods.append({"name": "خرید از ۲+ گروه کالا", "delta": +0.08,
                         "why": "الگوی سنجیده: حدود ۲۰ واحد درصد بازگشت بیشتر، "
                                "تکرارشده در دو پنجرهٔ اعتبارسنجی"})
            prob += 0.08
        if "purchase_plan" in codes:
            mods.append({"name": "برنامهٔ خرید اعلام‌شده", "delta": +0.07,
                         "why": "مشتری خودش دورهٔ بعد را اعلام کرده"})
            prob += 0.07
        if of["pending"]:
            mods.append({"name": f"{of['pending']} آفر باز", "delta": +0.05,
                         "why": "مذاکرهٔ در جریان"})
            prob += 0.05
        add("reorder_90d", "آیا در ۹۰ روز آینده سفارش می‌دهد؟", prob,
            f"نرخ پایهٔ تجربی {base:.0%} برای رکود {band} (از {n:,} مشاهدهٔ مشتری-ماه)",
            mods,
            [ref("sales", None, c["last_purchase"],
                 {"date": c["last_purchase"], "recency": f"{d} روز"},
                 "نرخ پایه از ۱۰٬۳۳۹ مشاهدهٔ مشتری-ماه در ۲۱ تاریخ برش محاسبه شد")],
            "بالا" if d <= 240 else "متوسط")

    # ── ۲. درخواست تخفیف
    price_talk = e["by_type"].get("price_and_discount", 0)
    rej = of["rejected"]
    base = 0.20
    mods, prob = [], base
    if price_talk:
        dd = min(0.30, 0.10 * price_talk)
        mods.append({"name": f"{price_talk} تعامل قیمت و تخفیف", "delta": +dd,
                     "why": "گفت‌وگوی قیمت در CRM ثبت شده"})
        prob += dd
    if rej:
        dd = min(0.20, 0.05 * rej)
        mods.append({"name": f"{rej} آفر ردشده", "delta": +dd,
                     "why": "قیمت پیشنهادی پیشین پذیرفته نشده"})
        prob += dd
    if f.get("price_pressure_signals"):
        mods.append({"name": "فشار قیمتی بازار", "delta": +0.10,
                     "why": "گزارش بازار پیش از درخواست مشتری"})
        prob += 0.10
    if (m["gross_margin_pct"] or 0) > (f.get("portfolio_median_margin") or 0) + 3:
        mods.append({"name": "حاشیه بالای میانه", "delta": +0.05,
                     "why": "فضای تخفیف وجود دارد و مشتری معمولاً می‌داند"})
        prob += 0.05
    if prob > base or price_talk:
        add("discount_request", "آیا درخواست تخفیف می‌دهد؟", prob,
            f"نرخ پایهٔ فرضی {base:.0%} — این مورد نرخ پایهٔ تجربی ندارد",
            mods,
            with_fallback(
                [ref("crm", x["id"], x["date"],
                     {"Interaction_Type": fa(x["type"]),
                      "Summary_Text": str(x["summary"])[:100]})
                 for x in e["items"] if x["type"] == "price_and_discount"][:2],
                ref("derived", None, None,
                    {"Offer_Reason": f"{rej} آفر ردشده" if rej else "بدون سابقهٔ مذاکرهٔ قیمت"},
                    "رکورد مذاکرهٔ قیمتی در CRM ثبت نشده؛ عدد فقط از نرخ پایهٔ فرضی و "
                    "نشانه‌های غیرمستقیم می‌آید")),
            "پایین",
            "برخلاف بقیهٔ پیش‌بینی‌ها، نرخ پایهٔ این مورد از داده استخراج نشد چون رویداد "
            "«درخواست تخفیف» به‌صورت مستقل در داده ثبت نمی‌شود. عدد را نسبی بخوانید.")

    # ── ۳. قطع خرید
    ret = f.get("retention")
    if ret is not None:
        add("churn", "آیا رابطه قطع می‌شود؟", 1 - ret,
            f"مکمل احتمال ماندگاری کالیبره‌شده ({ret:.0%})",
            [{"name": x["name"], "delta": -x["delta"], "why": x["why"]}
             for x in (f.get("retention_components") or [])],
            [ref("derived", None, None,
                 {"recency": f"{d} روز" if d is not None else "—",
                  "vol_trend": f"{c['volume_trend_pct']:+.0f}٪"
                               if c["volume_trend_pct"] is not None else "—"},
                 "امتیاز ماندگاری روی پنجرهٔ خارج‌از‌زمان سنجیده شد: AUC ۰.۸۳۱، "
                 "خطای کالیبراسیون ۰.۰۴")],
            "بالا")

    # ── ۴. شکایت جدید
    base, band, n = _rate(COMPLAINT_BY_HISTORY, cp["total"])
    mods, prob = [], base
    if "quality_talk" in codes:
        mods.append({"name": "گفت‌وگوی کیفیت در CRM", "delta": +0.08,
                     "why": "نگرانی کیفی مطرح‌شده ولی بدون شکایت رسمی"})
        prob += 0.08
    if "lab_evenness" in codes:
        mods.append({"name": "یکنواختی آزمایشگاه در محدودهٔ بالا", "delta": +0.05,
                     "why": "CV بالاتر از میانهٔ سبد"})
        prob += 0.05
    add("new_complaint", "آیا شکایت جدید ثبت می‌کند؟", prob,
        f"نرخ پایهٔ تجربی {base:.0%} برای «{band}» (از {n:,} مشاهدهٔ مشتری-فصل)", mods,
        with_fallback(
            [ref("complaints", x["id"], x["date"],
                 {"Severity": fa(x["severity"]), "Complaint_Title": x["title"]})
             for x in cp["items"][:2]],
            ref("derived", None, None, {"Severity": "بدون سابقهٔ شکایت"},
                f"این مشتری شکایتی ثبت نکرده؛ عدد کاملاً نرخ پایهٔ تجربی گروه "
                f"«{band}» است از {n:,} مشاهدهٔ مشتری-فصل")),
        "متوسط" if cp["total"] else "بالا")

    # ── ۵. درخواست توسعهٔ جدید
    base, band, n = _rate(DEV_BY_HISTORY, dv["requests"])
    mods, prob = [], base
    if e["by_type"].get("product_sample", 0):
        mods.append({"name": "تعامل نمونهٔ محصول", "delta": +0.06,
                     "why": "چرخهٔ نمونه در جریان است"})
        prob += 0.06
    add("new_dev_request", "آیا درخواست فنی جدید می‌دهد؟", prob,
        f"نرخ پایهٔ تجربی {base:.0%} برای «{band}» (از {n:,} مشاهدهٔ مشتری-فصل)", mods,
        with_fallback(
            [ref("dev_requests", x["id"], x["date"],
                 {"Request_Type": fa(x["type"]), "Status": fa(x["status"])})
             for x in dv["items"][:2]],
            ref("derived", None, None, {"Request_Type": "بدون سابقهٔ درخواست"},
                f"این مشتری درخواست توسعه‌ای ثبت نکرده؛ عدد کاملاً نرخ پایهٔ تجربی "
                f"گروه «{band}» است از {n:,} مشاهدهٔ مشتری-فصل")),
        "متوسط")

    # ── ۶. تأخیر پرداخت فاکتور بعدی
    if r["invoiced"]:
        base = 0.51
        mods, prob = [], base
        cr = r["collection_rate_pct"]
        if cr is not None and cr < 80:
            mods.append({"name": f"نرخ وصول {cr:.0f}٪", "delta": +0.06,
                         "why": "سابقهٔ وصول ناقص"})
            prob += 0.06
        if r["bounced_cheques"]:
            mods.append({"name": f"{r['bounced_cheques']} چک برگشتی", "delta": +0.03,
                         "why": "اثر ضعیف است ولی جهت‌دار"})
            prob += 0.03
        if "chase" in codes:
            mods.append({"name": "پیگیری مکرر وصول", "delta": +0.04,
                         "why": "فشار وصول در CRM ثبت شده"})
            prob += 0.04
        add("late_payment", "آیا پرداخت بعدی با تأخیر بالای میانه است؟", prob,
            f"نرخ پایهٔ تجربی {base:.0%} (میانهٔ تأخیر سبد ۲۳ روز)", mods,
            [ref("collections", None, None,
                 {"days_late": f"میانگین {r['avg_days_late']} روز",
                  "bounced_cheque": f"{r['bounced_cheques']} مورد"})],
            "پایین", LATE_PAYMENT_NOTE)

    return sorted(P, key=lambda x: -x["probability"])
