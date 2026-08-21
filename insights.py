"""ریسک، فرصت و اقدام بعدی — همه با رفرنس به رکورد منبع  (MVP ۰۳ و ۰۴)

فلسفه: تمام محاسبه اینجا و قطعی انجام می‌شود؛ مدل زبانی فقط روایت می‌کند.
هر ریسک، فرصت و اقدام سه چیز همراه دارد:
  ۱. «شاهد» — عدد یا واقعیتی که آن را ایجاب می‌کند
  ۲. «رفرنس» — نام شیت، شناسهٔ رکورد، تاریخ، فیلد و مقدار
  ۳. «استدلال» — چرا از این شاهد به این اقدام رسیدیم
"""
from __future__ import annotations

from typing import Any

from pipeline import fa
from signals import (OFFER_ACCEPT_BY_REASON, OFFER_ACCEPT_OVERALL, OFFER_REASON_NOTE,
                     ref, with_fallback)

URGENCY = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.2}
SEVERITY_FA = {"critical": "بحرانی", "high": "زیاد", "medium": "متوسط", "low": "کم"}
OWNER_FA = {
    "collections": "واحد وصول مطالبات", "sales": "واحد فروش",
    "pricing": "کمیته قیمت‌گذاری", "quality": "کنترل کیفیت",
    "rnd": "تحقیق‌وتوسعه", "planning": "برنامه‌ریزی تولید", "credit": "کمیته اعتباری",
}


def money(x: float | None) -> str:
    if x is None:
        return "—"
    s = "-" if x < 0 else ""
    x = abs(float(x))
    if x >= 1e9:
        return f"{s}{x / 1e9:,.2f} میلیارد"
    if x >= 1e6:
        return f"{s}{x / 1e6:,.1f} میلیون"
    if x >= 1e3:
        return f"{s}{x / 1e3:,.0f} هزار"
    return f"{s}{x:,.0f}"


def qty(x: float | None) -> str:
    return "—" if x is None else f"{x:,.0f} کیلوگرم"


def pct(x: float | None, digits: int = 1) -> str:
    return "—" if x is None else f"{x:,.{digits}f}٪"


# ══════════════════════════ اقدام بر پایهٔ دلیل آفر  (الزام ۱)
# دلیل آفر «چه کاری» را تعیین می‌کند، نه «چقدر احتمال موفقیت». آزمون کای‌دو
# نشان داد نرخ پذیرش بین دلایل تفاوت معنادار ندارد — پس نقش دلیل، مسیریابی
# اقدام به واحد و گام درست است.
OFFER_REASON_PLAY = {
    "fast_settlement": {
        "label": "تسویه سریع",
        "action": "پیگیری وصول همراه با یادآوری شرط تخفیف: تخفیف تنها با تسویه در مهلت اعتبار",
        "owner": "collections",
        "logic": "آفر برای تسریع تسویه صادر شده؛ پس پیگیری آن کار وصول است نه فروش. "
                 "اگر آفر منقضی شود، اهرم تسویه از دست می‌رود.",
        "next_step": "تماس وصول در ۴۸ ساعت و ثبت تعهد پرداخت مکتوب",
    },
    "order_volume_growth": {
        "label": "افزایش حجم سفارش",
        "action": "ارائهٔ پلهٔ حجمی مشخص: قیمت در برابر تعهد تناژ، با سقف زمانی",
        "owner": "sales",
        "logic": "هدف آفر رشد حجم است؛ بدون پلهٔ عددی و تعهد متقابل، تخفیف بدون بازگشت است.",
        "next_step": "تعیین پله‌های تناژ و ارسال پیشنهاد کتبی",
    },
    "wallet_share_growth": {
        "label": "افزایش سهم از سبد",
        "action": "مقایسهٔ فنی و قیمتی با رقیب اصلی همان مشتری و پیشنهاد جایگزینی تدریجی",
        "owner": "sales",
        "logic": "برای گرفتن سهم، باید بدانیم سهم فعلی دست کدام رقیب است و چرا. "
                 "داده سهم از سبد و نام رقیب اصلی را دارد.",
        "next_step": "استخراج شکاف سهم از داشبورد و تدوین پیشنهاد جایگزینی",
    },
    "key_account_retention": {
        "label": "حفظ مشتری کلیدی",
        "action": "بازدید حضوری مدیر فروش پیش از انقضای آفر، با محور ریشهٔ نارضایتی",
        "owner": "sales",
        "logic": "آفر حفظ مشتری یعنی سازمان خطر رفتن را حس کرده. تخفیف تنها، علت "
                 "رفتن را حل نمی‌کند؛ باید ریشه پیدا شود.",
        "next_step": "تعیین وقت بازدید و آماده کردن سابقهٔ شکایت و کیفیت پیش از جلسه",
    },
    "price_competition": {
        "label": "رقابت قیمتی",
        "action": "تحلیل بهای تمام‌شده پیش از پاسخ قیمتی؛ تعیین کف قیمت قابل قبول",
        "owner": "pricing",
        "logic": "پاسخ به رقابت قیمتی بدون دانستن کف بهای تمام‌شده، ریسک فروش زیر "
                 "قیمت تمام‌شده دارد. این مشتری داده بهای تمام‌شده دارد.",
        "next_step": "محاسبهٔ حاشیه در سطح کد کالا و تعیین کف قیمت",
    },
    "new_product_intro": {
        "label": "معرفی محصول جدید",
        "action": "ارسال نمونه با معرفی فنی و تعیین بازهٔ آزمون در خط مشتری",
        "owner": "rnd",
        "logic": "معرفی محصول جدید بدون آزمون در خط مشتری به سفارش نمی‌رسد؛ "
                 "چرخهٔ نمونه باید مهلت‌دار باشد.",
        "next_step": "ارسال نمونه و تعیین تاریخ بازخورد فنی",
    },
    "product_trial": {
        "label": "آزمون محصول",
        "action": "پیگیری نتیجهٔ آزمون و ثبت بازخورد فنی مکتوب مشتری",
        "owner": "rnd",
        "logic": "آزمون بدون ثبت نتیجه، هم فرصت فروش و هم دانش فنی را از بین می‌برد.",
        "next_step": "تماس فنی برای گرفتن نتیجهٔ آزمون و ثبت آن در CRM",
    },
}

# اقدام بر پایهٔ نوع درخواست توسعه
DEV_TYPE_PLAY = {
    "strength_improvement": ("بهبود استحکام", "quality",
                             "تعیین هدف عددی استحکام و آزمون در سه بچ متوالی"),
    "colour_shade_improvement": ("بهبود شید رنگ", "quality",
                                 "بررسی پایداری شید بین بوبین‌ها و ارائهٔ گزارش کنترل کیفیت"),
    "hairiness_reduction": ("کاهش پرز", "quality",
                            "بازبینی پارامتر روغن‌زنی و آزمون پرز در نمونهٔ جدید"),
    "denier_change": ("تغییر دنیر", "planning",
                      "سنجش امکان تولید در برنامهٔ خط و اعلام حداقل تناژ اقتصادی"),
    "filament_count_change": ("تغییر تعداد فیلامنت", "planning",
                              "سنجش امکان فنی خط و اعلام زمان‌بندی نمونه"),
    "custom_packaging": ("بسته‌بندی اختصاصی", "planning",
                         "برآورد هزینهٔ بسته‌بندی و تعیین حداقل سفارش"),
}

# اقدام بر پایهٔ شدت شکایت
COMPLAINT_SEVERITY_PLAY = {
    "critical": ("رسیدگی فوری با مالک مشخص و مهلت ۴۸ ساعت؛ اطلاع نتیجه به مشتری", "quality"),
    "high": ("تعیین مسئول رسیدگی و مهلت یک‌هفته‌ای؛ ارسال گزارش اقدام اصلاحی", "quality"),
    "medium": ("بررسی در جلسهٔ هفتگی کیفیت و ثبت نتیجه در CRM", "quality"),
    "low": ("ثبت و پاسخ کتبی؛ رصد تکرار در همان کد کالا", "quality"),
}


# ═══════════════════════════════════════════════════════════ ریسک‌ها
def find_risks(p: dict, f: dict) -> list[dict]:
    c, m, r = p["commercial"], p["margin"], p["receivables"]
    cp, e, ws, mk = p["complaints"], p["engagement"], p["wallet_share"], p["market"]
    R: list[dict] = []

    def add(code, title, severity, evidence, logic, action, owner, at_stake=0.0, refs=None):
        R.append({"code": code, "title": title, "severity": severity,
                  "severity_fa": SEVERITY_FA[severity], "evidence": evidence,
                  "logic": logic, "action": action, "owner": OWNER_FA[owner],
                  "value_at_stake": round(at_stake), "references": refs or []})

    oi = r.get("overdue_invoices") or []
    inv_refs = [ref("invoices", x["invoice_no"], x["date"],
                    {"open": f"{x['open']:,.0f}", "due_date": x["due_date"],
                     "days_late": f"{x['days_overdue']} روز"}) for x in oi[:4]]

    # ── اعتبار و وصول
    if r["uncollected_overdue"] > 0 and m["gross_profit"] > 0 and \
            r["uncollected_overdue"] > m["gross_profit"]:
        add("overdue_exceeds_gp", "مطالبات معوق از کل سود ناخالص بیشتر است", "critical",
            f"{money(r['uncollected_overdue'])} معوق در برابر {money(m['gross_profit'])} "
            f"سود ناخالص انباشته؛ مشارکت خالص {money(r['net_contribution'])}",
            "هر ریال فروش بیشتر به این مشتری، ریسک را بزرگ‌تر می‌کند نه سود را. "
            "تا وقتی معوق از سود بیشتر است، رابطه از منظر نقدی زیان‌ده است.",
            "توقف فروش اعتباری تا تسویه بخشی از معوق؛ تعیین برنامه پرداخت مکتوب",
            "collections", r["uncollected_overdue"], inv_refs)

    if (r["oldest_overdue_days"] or 0) > 365:
        add("overdue_aged", "معوق کهنه (بیش از یک سال)", "high",
            f"قدیمی‌ترین بدهی سررسیدشده {r['oldest_overdue_days']} روز عمر دارد و "
            f"{r['invoices_uncollected']} فاکتور هیچ وصولی نداشته است",
            "بدهی بالای یک سال عملاً وارد محدودهٔ مطالبات مشکوک‌الوصول می‌شود؛ "
            "تصمیم حسابداری لازم است، نه فقط پیگیری فروش.",
            "ارجاع به کمیته اعتباری برای تعیین تکلیف: تسویه، تقسیط یا ذخیره‌گیری",
            "credit", r["uncollected_overdue"], inv_refs)

    if r["bounced_cheques"] > 0:
        add("bounced_cheques", f"{r['bounced_cheques']} چک برگشتی", "high",
            f"{r['bounced_cheques']} مورد ثبت شده و نرخ وصول {pct(r['collection_rate_pct'])} است",
            "چک برگشتی نشانهٔ تنش نقدی است. توجه: در آزمون دادهٔ همین سبد، چک برگشتی "
            "تأخیر بیشتر در آینده را پیش‌بینی نکرد — پس آن را نشانهٔ وضعیت بدانید، نه پیش‌بین.",
            "بازنگری شرایط پرداخت به نقدی یا پیش‌پرداخت؛ درخواست تضمین جدید",
            "credit", r["uncollected_overdue"],
            [ref("collections", None, None,
                 {"bounced_cheque": f"{r['bounced_cheques']} مورد",
                  "days_late": f"میانگین {r['avg_days_late']} روز"})])

    if (r["credit_limit_utilisation_pct"] or 0) > 100:
        add("over_credit_limit", "عبور از سقف اعتبار", "high",
            f"معوق {money(r['uncollected_overdue'])} معادل "
            f"{pct(r['credit_limit_utilisation_pct'], 0)} سقف اعتبار "
            f"({money(p['identity']['credit_limit'])})",
            "سقف اعتبار برای همین لحظه تعریف شده بود. عبور از آن یعنی کنترل اعتباری "
            "در عمل اجرا نشده است.",
            "بازتعریف سقف اعتبار یا مسدودسازی سفارش جدید تا کاهش مانده",
            "credit", r["uncollected_overdue"] - p["identity"]["credit_limit"],
            [ref("customers", p["customer_id"], None,
                 {"Credit_Limit": f"{p['identity']['credit_limit']:,.0f}"}, "مستر مشتری")] + inv_refs)

    if (r["collection_rate_pct"] or 100) < 80:
        add("low_collection_rate", "نرخ وصول پایین", "medium",
            f"تنها {pct(r['collection_rate_pct'])} از {money(r['invoiced'])} فاکتورشده "
            f"وصول شده؛ میانگین تأخیر {r['avg_days_late']} روز",
            "نرخ وصول زیر ۸۰٪ یعنی یک‌پنجم فروش هرگز به نقد تبدیل نشده. "
            "این را باید در قیمت لحاظ کرد، نه در امید.",
            "تشدید پیگیری وصول و پیوند تخفیف آتی به تسویه",
            "collections", r["uncollected_overdue"], inv_refs)

    # ── ریزش
    d = c["days_since_last_purchase"]
    sil = f.get("silence_ratio")
    if d is not None and d > 180:
        sev = "high" if (c["revenue_rank"] or 999) <= 150 else "medium"
        extra = f" و {sil:.1f} برابر فاصلهٔ معمول سفارش ({f.get('order_gap'):.0f} روز)" \
            if sil and sil >= 2 and f.get("order_gap") else ""
        add("dormant", f"مشتری راکد ({d} روز بی‌خرید)", sev,
            f"آخرین خرید {d} روز پیش{extra}؛ رتبه درآمدی {c['revenue_rank']} از ۶۴۴ با "
            f"{money(c['revenue_nominal'])} فروش تاریخی",
            f"نرخ پایهٔ تجربی سفارش مجدد در این بازهٔ رکود کمتر از "
            f"{'۱۰٪' if d > 240 else '۲۰٪'} است. هر ماه تأخیر، شانس بازگشت را کم می‌کند.",
            "تماس بازگشت با آفر هدفمند؛ ریشه‌یابی علت قطع خرید در گفت‌وگوی حضوری",
            "sales", f.get("rescue_value") or 0,
            [ref("sales", None, c["last_purchase"],
                 {"date": c["last_purchase"], "recency": f"{d} روز"},
                 "نرخ پایه از ۱۰٬۳۳۹ مشاهدهٔ مشتری-ماه")])

    vt = c["volume_trend_pct"]
    if vt is not None and vt < -50:
        add("volume_collapse", f"ریزش حجم خرید ({pct(vt, 0)} در ۶ ماه)", "high",
            f"حجم شش ماه اخیر {pct(abs(vt), 0)} کمتر از شش ماه پیش از آن "
            f"(کل حجم تاریخی {qty(c['volume'])})",
            "حجم مبنای درست روند است چون از تورم ۸ برابری قیمت مصون است. "
            "فروش اسمی این مشتری می‌تواند رشد نشان دهد در حالی که تناژ نصف شده.",
            "بازدید حضوری کارشناس فروش و بررسی جایگزینی توسط رقیب",
            "sales", f.get("rescue_value") or 0,
            [ref("derived", None, None, {"vol_trend": f"{vt:+.0f}٪"},
                 "شش ماه اخیر در برابر شش ماه پیش، بر پایهٔ کیلوگرم")])

    # ── کیفیت
    imp = cp.get("purchase_impact")
    if imp and imp.get("change_pct") is not None and imp["change_pct"] < -25 and imp["window_complete"]:
        add("quality_linked_decline", "کاهش خرید پس از ثبت شکایت", "critical",
            f"در {imp['window_days']} روز پیش از نخستین شکایت ({imp['first_complaint']}) "
            f"حجم {qty(imp['volume_before'])} بود و پس از آن {qty(imp['volume_after'])} "
            f"({pct(imp['change_pct'], 0)})",
            "همزمانی است نه علیت اثبات‌شده. در سطح کل سبد آزمودیم و شکایت پیش‌بین ریزش "
            "نبود؛ ولی در سطح این مشتری، فاصلهٔ زمانی به‌قدری نزدیک است که بررسی "
            "فنی مشترک را توجیه می‌کند.",
            "بازبینی فنی مشترک با مشتری روی همان کد کالا و ارائهٔ گزارش اقدام اصلاحی",
            "quality", f.get("rescue_value") or 0,
            [ref("complaints", x["id"], x["date"],
                 {"Severity": fa(x["severity"]), "Complaint_Title": x["title"],
                  "Complaint_Status": fa(x["status"])})
             for x in cp["items"][:3]])

    if cp["open"] > 0 and cp["critical_or_high"] > 0:
        worst = next((x for x in cp["items"]
                      if x["severity"] in ("critical", "high") and x["status"] != "closed"),
                     cp["items"][0] if cp["items"] else None)
        play, owner = COMPLAINT_SEVERITY_PLAY.get(
            worst["severity"] if worst else "medium", COMPLAINT_SEVERITY_PLAY["medium"])
        add("open_severe_complaint", f"{cp['open']} شکایت باز با شدت زیاد یا بحرانی", "high",
            f"{cp['total']} شکایت ثبت‌شده، {cp['open']} باز، {cp['critical_or_high']} با شدت "
            f"زیاد یا بحرانی؛ {cp['linked_order_lines']} خط فروش درگیر"
            + (f"؛ آخرین: «{worst['title']}»" if worst else ""),
            "شکایت باز، پروندهٔ رسیدگی‌نشده است. مسیر اقدام از شدت شکایت می‌آید: "
            f"برای شدت «{fa(worst['severity']) if worst else 'متوسط'}» گام درست همین است.",
            play, owner, 0.0,
            [ref("complaints", x["id"], x["date"],
                 {"Severity": fa(x["severity"]), "Complaint_Status": fa(x["status"]),
                  "Complaint_Title": x["title"]})
             for x in cp["items"] if x["status"] != "closed"][:3])

    # ── هزینهٔ پول و حاشیهٔ واقعی (نکتهٔ مرکزی راهنمای داوران)
    com = f.get("cost_of_money_pct")
    rm = f.get("real_margin")
    gmm = m["gross_margin_pct"]
    if com is not None and rm is not None and gmm is not None:
        dc = f.get("days_cash") or 0
        rate = (f.get("finance_rate_monthly") or 0.04) * 100
        if rm < 0 and gmm >= 0:
            add("negative_real_margin",
                f"سود واقعی منفی است ({pct(rm)}) — هزینهٔ پول حاشیه را خورده",
                "critical" if rm < -5 else "high",
                f"حاشیهٔ ناخالص {pct(gmm)} است، ولی پول این مشتری به‌طور میانگین "
                f"{dc:.0f} روز قفل می‌ماند؛ با نرخ {rate:.0f}٪ ماهانه یعنی "
                f"{pct(com)} هزینهٔ پول و {pct(rm)} سود واقعی",
                "قیمت این مشتری برای فروش نقدی بسته شده ولی پولش دیرتر برمی‌گردد. "
                "در آزمون قیمت‌های همین داده، مارک‌آپ اعتبار در قیمت ثبت نشده است — "
                "پس این هزینه جایی جبران نمی‌شود.",
                "بردن شرایط پرداخت به نقدی یا پیش‌پرداخت، یا افزودن مارک‌آپ اعتبار "
                f"معادل {pct(com)} به قیمت؛ اگر هیچ‌کدام ممکن نیست، کاهش تماس فروش",
                "pricing", abs(float(f.get("cost_of_money") or 0)),
                [ref("derived", None, None,
                     {"days_cash": f"{dc:.0f} روز", "cost_of_money": pct(com),
                      "real_margin": pct(rm)},
                     f"نرخ {rate:.0f}٪ ماهانه فرض بیرونی از راهنمای داوران است، "
                     "نه استخراج از داده؛ در داشبورد قابل تغییر است")])
        elif com > gmm * 0.5 and com > 5:
            add("high_cost_of_money",
                f"هزینهٔ پول نیمی از حاشیه را می‌خورد ({pct(com)})", "high",
                f"{dc:.0f} روز پول قفل‌شده در برابر مبنای نقدی سبد؛ "
                f"حاشیهٔ ناخالص {pct(gmm)} → سود واقعی {pct(rm)}",
                "این مشتری سودآور به‌نظر می‌رسد ولی نیمی از سودش هزینهٔ تأمین مالی است. "
                "کوتاه کردن چرخهٔ نقد، ارزان‌ترین راه افزایش سود این حساب است.",
                "کوتاه کردن دورهٔ وصول: تخفیف تسویهٔ زودهنگام یا پیش‌پرداخت جزئی",
                "credit", abs(float(f.get("cost_of_money") or 0)) * 0.5,
                [ref("derived", None, None,
                     {"days_cash": f"{dc:.0f} روز", "cost_of_money": pct(com)})])

    if f.get("rfm_alert"):
        add("rfm_drop", "افت امتیاز RFM در مشتری پرارزش", "high",
            f"از {f.get('RFM_prev')} به {f.get('RFM')} در {int(f.get('rfm_move_days') or 91)} روز "
            f"({f.get('rfm_move'):+.0f} پله)",
            "امتیاز هر دوره مستقل محاسبه می‌شود، پس این افت یعنی نسبت به هم‌گروه‌ها "
            "عقب افتاده — نه فقط نوسان فصلی. افت امتیاز مشتری پرارزش، زودترین "
            "هشدار قابل اتکای این سامانه است.",
            "تماس مدیر فروش در همین هفته و پیدا کردن دلیل افت پیش از آنکه به رکود برسد",
            "sales", float(f.get("rescue_value") or 0),
            [ref("derived", None, None,
                 {"RFM": f"{f.get('RFM_prev')} → {f.get('RFM')}",
                  "recency": f"{c['days_since_last_purchase']} روز"},
                 f"مقایسهٔ امتیاز با {int(f.get('rfm_move_days') or 91)} روز پیش")])

    # ── سودآوری
    gm = m["gross_margin_pct"]
    pmed = f.get("portfolio_median_margin")
    if gm is not None and gm < 3:
        worst_p = [x for x in c["top_products"] if (x.get("margin_pct") or 0) < 0][:3]
        add("thin_margin", f"حاشیه سود بسیار نازک ({pct(gm)})", "high",
            f"حاشیه {pct(gm)} در برابر میانهٔ سبد {pct(pmed)}؛ "
            f"{m['negative_margin_lines']} خط زیان‌ده ({pct(m['negative_margin_line_pct'], 0)}) "
            f"با {money(abs(m['gross_profit_destroyed']))} زیان انباشته",
            f"مبنای بهای تمام‌شده {pct(m['realized_cost_share_pct'], 0)} تحقق‌یافته است؛ "
            "بقیه برآوردی که حاشیه را حدود ۵ واحد خوش‌بینانه‌تر نشان می‌دهد. "
            "یعنی حاشیهٔ واقعی احتمالاً از این هم کمتر است.",
            "بازنگری قیمت یا حذف کدهای زیان‌ده از سبد این مشتری",
            "pricing", abs(m["gross_profit_destroyed"]),
            [ref("sales", x["product_id"], None,
                 {"unit_price": f"حاشیه {pct(x.get('margin_pct'))}",
                  "qty": f"{x['qty']:,.0f} کیلوگرم"}, x["desc"][:60])
             for x in worst_p] or
            [ref("derived", None, None, {"margin": pct(gm)})])
    elif m["negative_margin_line_pct"] > 30:
        add("many_negative_lines", "سهم بالای خطوط زیان‌ده", "medium",
            f"{pct(m['negative_margin_line_pct'], 0)} خطوط زیان‌ده "
            f"({m['negative_margin_lines']} خط، {money(abs(m['gross_profit_destroyed']))} زیان)",
            "حاشیهٔ کل مثبت است ولی از میانگین‌گیری می‌آید؛ یک‌سوم خطوط پول از دست می‌دهد.",
            "شناسایی کدهای کالای زیان‌ده و اصلاح قیمت پایه",
            "pricing", abs(m["gross_profit_destroyed"]),
            [ref("derived", None, None,
                 {"margin": f"{m['negative_margin_lines']} خط زیان‌ده از {c['order_lines']}"})])

    # ── ارتباط و رقابت
    di = e["days_since_last_interaction"]
    if e["interactions"] == 0 and c["revenue_nominal"] > 0:
        add("no_crm_history", "هیچ تعاملی در CRM ثبت نشده", "medium",
            f"با {money(c['revenue_nominal'])} فروش و {c['invoices']} فاکتور، "
            "هیچ گزارش تعاملی ثبت نشده است",
            "دانش این مشتری فقط در ذهن کارشناس است — همان مسئله‌ای که این سامانه "
            "برای حلش ساخته شده. با رفتن کارشناس، دانش هم می‌رود.",
            "ثبت تاریخچهٔ شناخته‌شدهٔ مشتری در CRM توسط کارشناس مسئول", "sales", 0.0,
            [ref("crm", None, None, {}, "هیچ رکوردی برای این مشتری وجود ندارد")])
    elif di is not None and di > 180 and d is not None and d < 120:
        add("uncontacted_active", "مشتری فعال بدون تماس ثبت‌شده", "medium",
            f"آخرین خرید {d} روز پیش اما آخرین تعامل ثبت‌شده {di} روز پیش",
            "مشتری می‌خرد ولی رابطه مدیریت نمی‌شود. در برابر تماس رقیب بی‌دفاع است.",
            "برنامه تماس دوره‌ای و ثبت گزارش تعامل در CRM", "sales", 0.0,
            [ref("crm", e["items"][0]["id"] if e["items"] else None, e["last_interaction"],
                 {"Interaction_Type": fa(e["items"][0]["type"]) if e["items"] else "—"})])

    if ws["main_competitors"] and (ws["avg_share_pct"] or 100) < 25:
        top = max(ws["main_competitors"], key=ws["main_competitors"].get)
        add("competitor_dominant", "سهم غالب رقیب در سبد خرید مشتری", "medium",
            f"میانگین سهم ما {pct(ws['avg_share_pct'])} از خرید برآوردی "
            f"{qty(ws['estimated_total_purchase'])} ماهانه؛ رقیب اصلی {fa(top)} "
            f"در {ws['main_competitors'][top]} ماه",
            "سهم از سبد تنها جایی است که «بازار ازدست‌رفته» دیده می‌شود؛ فروش ما "
            "چیزی از آن نمی‌گوید.",
            "تحلیل شکاف قیمت و تحویل در برابر رقیب اصلی", "sales", 0.0,
            [ref("wallet_share", None, None,
                 {"Main_Competitor": fa(top),
                  "Nafis_Purchase": f"سهم {pct(ws['avg_share_pct'])}",
                  "Estimated_Total_Purchase": qty(ws["estimated_total_purchase"])},
                 f"برآورد کارشناس در {ws['months_observed']} ماه")])

    fam = c["product_family_mix"]
    if fam and max(fam.values()) > 90 and c["revenue_nominal"] > 0:
        top_fam = max(fam, key=fam.get)
        add("single_family_dependency", "وابستگی به یک گروه کالا", "low",
            f"{pct(fam[top_fam], 0)} فروش این مشتری تنها از {top_fam} است",
            "الگوی سنجیده: مشتریان تک‌گروه حدود ۲۰ واحد درصد کمتر برمی‌گردند — "
            "در هر دو پنجرهٔ اعتبارسنجی و با کنترل عمق رابطه.",
            "معرفی گروه کالای مکمل؛ بالاترین اهرم ماندگاری در این سبد", "sales", 0.0,
            [ref("derived", None, None, {"families": f"{int(f.get('families') or 1)} گروه"},
                 "الگوی تأییدشدهٔ تنوع گروه کالا")])

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(R, key=lambda x: (order[x["severity"]], -x["value_at_stake"]))


# ═══════════════════════════════════════════════════════════ فرصت‌ها
def find_opportunities(p: dict, f: dict) -> list[dict]:
    c, m, r = p["commercial"], p["margin"], p["receivables"]
    cp, e, dv, of, ws = (p["complaints"], p["engagement"], p["development"],
                         p["offers"], p["wallet_share"])
    O: list[dict] = []

    def add(code, title, potential, evidence, logic, action, owner, value=0.0, refs=None):
        O.append({"code": code, "title": title, "potential": potential,
                  "potential_fa": SEVERITY_FA[potential], "evidence": evidence,
                  "logic": logic, "action": action, "owner": OWNER_FA[owner],
                  "value": round(value), "references": refs or []})

    # ── شکاف سهم از سبد
    share, seg = ws["avg_share_pct"], ws["segment_avg_share_pct"]
    if share is not None and seg is not None and share < seg and ws["estimated_total_purchase"]:
        gap = seg - share
        monthly_kg = ws["estimated_total_purchase"] * gap / 100
        price = (c["revenue_nominal"] / c["volume"]) if c["volume"] else 0
        marg = (m["gross_margin_pct"] or 0) / 100
        add("wallet_share_gap", "شکاف سهم از سبد خرید مشتری", "high",
            f"سهم ما {pct(share)} در برابر میانهٔ بخش {p['identity']['segment']} "
            f"({pct(seg)})؛ خرید برآوردی {qty(ws['estimated_total_purchase'])} در ماه. "
            f"رسیدن به میانهٔ بخش معادل {qty(monthly_kg)} در ماه است",
            f"با حاشیهٔ فعلی {pct(m['gross_margin_pct'])}، این حجم سالانه حدود "
            f"{money(monthly_kg * price * marg * 12)} سود ناخالص است. "
            "سهم از سبد برآورد کارشناس است، نه اندازه‌گیری — پس عدد را سقف بدانید.",
            "تدوین پیشنهاد حجمی پله‌ای برای جذب سهم بیشتر", "sales",
            monthly_kg * price * marg * 12,
            [ref("wallet_share", None, None,
                 {"Nafis_Purchase": f"سهم {pct(share)}",
                  "Estimated_Total_Purchase": qty(ws["estimated_total_purchase"])},
                 f"میانگین {ws['months_observed']} ماه؛ منبع برآورد: "
                 + "، ".join(fa(k) for k in ws["estimate_sources"]))])

    # ── آفرهای باز، با اقدام بر پایهٔ دلیل  (الزام ۱)
    for item in (of.get("open_items") or [])[:3]:
        play = OFFER_REASON_PLAY.get(item["reason"])
        if not play:
            continue
        base = OFFER_ACCEPT_BY_REASON.get(item["reason"], OFFER_ACCEPT_OVERALL)
        expired = item["days_since"] > item["validity_days"]
        add(f"offer_{item['reason']}",
            f"آفر باز با دلیل «{play['label']}»" + ("، مهلت گذشته" if expired else ""),
            "high" if expired else "medium",
            f"آفر {item['id']} در {item['date']} با تخفیف {pct(item['discount_pct'], 1)} "
            f"({item['base_price']:,.0f} → {item['offered_price']:,.0f}) صادر شد؛ "
            f"{item['days_since']} روز گذشته و اعتبار {item['validity_days']} روز بود",
            play["logic"] + f" نرخ پذیرش تاریخی این دلیل {base:.0%} است. " + OFFER_REASON_NOTE,
            play["action"] + f" — گام فوری: {play['next_step']}", play["owner"], 0.0,
            [ref("offers", item["id"], item["date"],
                 {"Offer_Reason": play["label"], "Offer_Discount_Pct": pct(item["discount_pct"], 1),
                  "Validity_Days": f"{item['validity_days']} روز", "Result": fa(item["result"])})])

    # ── نمونهٔ تأییدشده
    if dv["approved"] > 0:
        items = [x for x in dv["items"] if x["status"] == "sample_approved"][:3]
        detail = items[0]["requirement"][:110] if items else ""
        add("approved_sample_idle", f"{dv['approved']} نمونهٔ تأییدشده، آمادهٔ تبدیل به سفارش",
            "high",
            f"{dv['approved']} درخواست توسعه به مرحلهٔ تأیید نمونه رسیده"
            + (f". نمونهٔ اخیر: «{detail}»" if detail else ""),
            "نمونهٔ تأییدشده هزینهٔ فنی‌اش را داده و به مرحلهٔ قیمت‌گذاری رسیده. "
            "اگر به سفارش نرسد، هم هزینهٔ تحقیق‌وتوسعه سوخته و هم انتظار مشتری بی‌پاسخ مانده.",
            "پیگیری تبدیل نمونهٔ تأییدشده به سفارش انبوه و قیمت‌گذاری آن", "rnd",
            (f.get("gp_monthly") or 0) * 3,
            with_fallback(
                [ref("dev_requests", x["id"], x["date"],
                     {"Request_Type": fa(x["type"]), "Status": fa(x["status"]),
                      "Requirement_Text": str(x["requirement"])[:120],
                      "Owner_Unit": fa(x["owner"])}) for x in items],
                ref("dev_requests", None, None,
                    {"Status": f"نمونه تأیید ×{dv['approved']}"},
                    f"شمارش از تجمیع {dv['requests']} درخواست؛ رکوردهای تأییدشده "
                    "قدیمی‌تر از ۸ درخواست اخیر هستند")))

    # ── درخواست توسعهٔ باز، با اقدام بر پایهٔ نوع
    pending = [x for x in dv["items"] if x["status"] in ("under_review", "in_development")]
    if pending:
        by_type: dict[str, list] = {}
        for x in pending:
            by_type.setdefault(x["type"], []).append(x)
        biggest = max(by_type.items(), key=lambda kv: len(kv[1]))
        label, owner, step = DEV_TYPE_PLAY.get(
            biggest[0], (fa(biggest[0]), "rnd", "تعیین مهلت پاسخ فنی و اطلاع نتیجه به مشتری"))
        add("pending_dev_request", f"{len(pending)} درخواست توسعه بی‌پاسخ", "medium",
            f"{dv['requests']} درخواست ثبت شده، {len(pending)} بی‌پاسخ؛ پرتکرارترین نوع "
            f"«{label}» با {len(biggest[1])} مورد",
            "این نیاز اعلام‌شدهٔ خود مشتری است، نه حدس ما. توجه: در آزمون داده، درخواست "
            "توسعه پیش‌بین مستقل ماندگاری نبود — پس آن را فرصت فروش بدانید، نه شاخص ریسک.",
            f"{step} (مسئول اعلام‌شده در داده: {fa(biggest[1][0]['owner'])})", owner, 0.0,
            [ref("dev_requests", x["id"], x["date"],
                 {"Request_Type": fa(x["type"]), "Status": fa(x["status"]),
                  "Requirement_Text": str(x["requirement"])[:120], "Owner_Unit": fa(x["owner"])})
             for x in biggest[1][:3]])

    # ── فروش مکمل  (الگوی تأییدشده)
    if c["cross_sell_families"]:
        fams = "، ".join(c["cross_sell_families"][:3])
        cur = int(f.get("families") or 1)
        add("cross_sell", "گروه کالای فروخته‌نشده در این مشتری",
            "high" if cur == 1 else "medium",
            f"این مشتری از {cur} گروه کالا خرید می‌کند؛ هم‌بخشی‌هایش از {fams} هم می‌خرند",
            "الگوی سنجیده و تکرارشده: خرید از ۲+ گروه کالا حدود ۲۰ واحد درصد بازگشت "
            "دوازده‌ماهه بیشتر می‌دهد — با کنترل عمق رابطه، در هر دو پنجرهٔ اعتبارسنجی. "
            "این بالاترین اهرم ماندگاری شناسایی‌شده در این سبد است.",
            "ارسال نمونه و معرفی فنی گروه‌های کالای پیشنهادی", "sales",
            (f.get("gp_monthly") or 0) * 6,
            [ref("derived", None, None,
                 {"families": f"{cur} گروه فعلی", "date": "الگوی سنجیده"},
                 "پنجرهٔ آزمون: ۵۱٪ در برابر ۷۱٪ بازگشت برای ۳-۶ ماه فعال؛ "
                 "۶۱٪ در برابر ۸۳٪ برای ۷-۱۲ ماه فعال")])

    # ── اصلاح شرایط پرداخت — بزرگ‌ترین اهرم این سبد
    vap = f.get("value_at_play")
    if (f.get("value_at_play_basis") == "اصلاح شرایط پرداخت") and vap and vap > 0:
        dc = f.get("days_cash") or 0
        add("terms_renegotiation", "آزادسازی سود با کوتاه کردن چرخهٔ نقد", "high",
            f"پول این مشتری {dc:.0f} روز قفل می‌ماند در برابر مبنای نقدی سبد "
            f"{(f.get('days_cash_benchmark') or 15.6):.0f} روز؛ هزینهٔ پول {pct(f.get('cost_of_money_pct'))}",
            "رساندن این مشتری به مبنای نقدی سبد، بدون یک ریال فروش بیشتر، "
            f"سالانه حدود {money(vap)} سود آزاد می‌کند. در این سبد این اهرم از "
            "رشد حجم بزرگ‌تر است.",
            "مذاکرهٔ شرایط پرداخت: تخفیف تسویهٔ زودهنگام، پیش‌پرداخت جزئی، یا "
            "افزودن مارک‌آپ اعتبار به قیمت",
            "credit", float(vap),
            [ref("derived", None, None,
                 {"days_cash": f"{dc:.0f} روز",
                  "cost_of_money": pct(f.get("cost_of_money_pct"))},
                 "آزمون قیمت نشان داد مارک‌آپ اعتبار در قیمت ثبت نشده است")])

    # ── رشد و اصلاح قیمت
    vt = c["volume_trend_pct"]
    if vt is not None and vt > 25:
        add("growing", f"رشد حجم خرید ({pct(vt, 0)} در ۶ ماه)", "high",
            f"حجم شش ماه اخیر {pct(vt, 0)} بیشتر از دورهٔ پیش، با حاشیهٔ "
            f"{pct(m['gross_margin_pct'])}",
            "رشد حقیقی حجم است نه اثر قیمت. پنجرهٔ طبیعی برای بستن قرارداد حجمی "
            "پیش از آنکه رقیب متوجه شود.",
            "تثبیت رشد با قرارداد حجمی؛ بررسی ظرفیت تولید", "planning",
            (f.get("gp_monthly") or 0) * 6,
            [ref("derived", None, None, {"vol_trend": f"{vt:+.0f}٪"})])

    gm = m["gross_margin_pct"]
    if gm is not None and 0 < gm < 8 and c["revenue_nominal"] > 5e7:
        upside = c["revenue_nominal"] * (8 - gm) / 100
        add("repricing_upside", "ظرفیت اصلاح قیمت در مشتری بزرگ", "high",
            f"با {money(c['revenue_nominal'])} فروش، حاشیه {pct(gm)} است؛ رسیدن به ۸٪ "
            f"معادل {money(upside)} سود بیشتر روی همین حجم",
            f"امتیاز ماندگاری این مشتری {(f.get('retention') or 0):.0%} است، پس رابطه "
            "تحمل مذاکرهٔ قیمت را دارد. اصلاح یک واحد حاشیه از رشد ۱۰٪ حجم راحت‌تر است.",
            "مذاکره اصلاح قیمت با تکیه بر تحلیل بهای تمام‌شده", "pricing", upside,
            [ref("derived", None, None,
                 {"margin": pct(gm)},
                 f"مبنای بهای تمام‌شده: {pct(m['realized_cost_share_pct'], 0)} تحقق‌یافته")])

    if (of["acceptance_rate_pct"] or 0) >= 50 and of["total"] >= 5:
        add("offer_responsive", "مشتری به آفر پاسخ‌ده است", "medium",
            f"{of['accepted']} پذیرش از {of['total']} آفر (نرخ "
            f"{pct(of['acceptance_rate_pct'])}) با میانگین تخفیف "
            f"{pct(of['avg_discount_pct'], 2)}",
            f"نرخ پذیرش کل سبد {OFFER_ACCEPT_OVERALL:.0%} است؛ این مشتری بالاتر از "
            "میانگین پاسخ می‌دهد. آفر ابزار مؤثری برای اوست.",
            "استفاده از آفر هدفمند برای رشد حجم", "sales", 0.0,
            [ref("offers", x["id"], x["date"],
                 {"Offer_Reason": fa(x["reason"]), "Result": fa(x["result"]),
                  "Offer_Discount_Pct": pct(x["discount_pct"], 1)})
             for x in (of.get("recent_items") or [])[:3]])

    d = c["days_since_last_purchase"]
    if d is not None and d > 180 and (c["revenue_rank"] or 999) <= 100:
        add("win_back", "بازیابی مشتری بزرگ راکد", "high",
            f"رتبه درآمدی {c['revenue_rank']} از ۶۴۴ با {money(c['revenue_nominal'])} "
            f"فروش تاریخی در {c['active_months']} ماه فعال، اما {d} روز بی‌خرید",
            f"ارزش نجات برآوردی {money(f.get('rescue_value'))} در سال است "
            "(سود ماهانه × احتمال از دست دادن × ۱۲). "
            "این عدد رتبهٔ اولویت بازیابی را می‌سازد.",
            "کمپین بازگشت با آفر و بازدید مدیر فروش", "sales",
            f.get("rescue_value") or 0,
            [ref("sales", None, c["last_purchase"],
                 {"date": c["last_purchase"], "recency": f"{d} روز"})])

    if cp["total"] > 0 and cp["open"] == 0 and (vt or 0) > -10:
        add("recovered_trust", "شکایت‌های رسیدگی‌شده و خرید پایدار", "low",
            f"{cp['total']} شکایت ثبت و همه بسته؛ میانگین رسیدگی "
            f"{cp['avg_resolution_days']} روز و حجم افت معناداری نداشته",
            "سابقهٔ رسیدگی موفق، در مذاکرات کیفی آتی سرمایه است.",
            "استفاده از این سابقه به‌عنوان مرجع کیفیت در مذاکرات", "sales", 0.0,
            [ref("complaints", x["id"], x["date"],
                 {"Complaint_Status": fa(x["status"]), "Resolved_At": x.get("resolved_at")})
             for x in cp["items"][:2]])

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(O, key=lambda x: (order[x["potential"]], -x["value"]))


# ═══════════════════════════════════════════ اقدام بعدی پیشنهادی
def next_best_actions(p: dict, f: dict, risks: list[dict], opps: list[dict],
                      top: int = 4) -> list[dict]:
    """رتبه‌بندی بر «مبلغ در معرض × فوریت»، با استدلال و رفرنس کامل."""
    pool = []
    for x in risks:
        pool.append({"kind": "risk", "kind_fa": "کاهش ریسک", "code": x["code"],
                     "title": x["title"], "action": x["action"], "owner": x["owner"],
                     "evidence": x["evidence"], "logic": x["logic"],
                     "references": x["references"], "weight": URGENCY[x["severity"]],
                     "value": x["value_at_stake"]})
    for x in opps:
        pool.append({"kind": "opportunity", "kind_fa": "بهره‌گیری از فرصت", "code": x["code"],
                     "title": x["title"], "action": x["action"], "owner": x["owner"],
                     "evidence": x["evidence"], "logic": x["logic"],
                     "references": x["references"], "weight": URGENCY[x["potential"]] * 0.85,
                     "value": x["value"]})
    if not pool:
        return []
    mx = max((x["value"] for x in pool), default=0) or 1
    for x in pool:
        share = x["value"] / mx if mx else 0
        x["score"] = round(x["weight"] * (0.45 + 0.55 * share), 4)
        # فرمول را با نسبت می‌نویسیم نه اعداد بزرگ، تا در متن راست‌به‌چپ خوانا بماند
        x["score_components"] = {"urgency": round(x["weight"], 2),
                                 "value_share": round(share, 3),
                                 "value": x["value"], "value_max": round(mx),
                                 "score": x["score"]}
        x["score_formula"] = (f"فوریت {x['weight']:.2f} × (۰٫۴۵ + ۰٫۵۵ × سهم مبلغ "
                             f"{share:.2f}) = {x['score']:.3f}")
    pool.sort(key=lambda x: -x["score"])
    out, seen = [], set()
    for x in pool:
        if x["owner"] in seen and len(out) >= 2:
            continue
        seen.add(x["owner"])
        out.append({**x, "rank": len(out) + 1})
        if len(out) == top:
            break
    return out


# ═══════════════════════════════════════════════════ خلاصه و بینش
def summarise(p: dict, f: dict, risks, opps, nba, signals, preds) -> str:
    c, m, r = p["commercial"], p["margin"], p["receivables"]
    seg = p["identity"]["segment"]
    if not p["coverage"]["sales"]:
        return (f"مشتری {p['customer_id']} در بخش {seg} ثبت شده اما در بازهٔ داده هیچ "
                "خریدی نداشته است. پروفایل تجاری قابل ساخت نیست.")
    L = [
        f"مشتری {p['customer_id']} از بخش {seg}، رتبه {c['revenue_rank']} از ۶۴۴ با "
        f"{money(c['revenue_nominal'])} فروش ({qty(c['volume'])}) در "
        f"{c['active_months']} ماه فعال."
    ]
    if f.get("rfm_segment"):
        L.append(f"در RFM «{f['rfm_segment']}» (کد {f.get('RFM')}) و در چهارخانهٔ "
                 f"حاشیه-ریسک «{f.get('quadrant')}».")
    trend = ""
    if c["volume_trend_pct"] is not None:
        word = "رشد" if c["volume_trend_pct"] > 0 else "افت"
        trend = f" حجم شش ماه اخیر {word} {pct(abs(c['volume_trend_pct']), 0)} داشته."
    L.append(f"سود ناخالص {money(m['gross_profit'])} با حاشیه {pct(m['gross_margin_pct'])} "
             f"(میانهٔ سبد {pct(f.get('portfolio_median_margin'))}).{trend}")
    if f.get("ltv_total") is not None:
        L.append(f"ارزش طول عمر {money(f['ltv_total'])} (رتبه {f.get('ltv_rank')}): "
                 f"{money(f.get('ltv_historic'))} محقق‌شده به‌علاوهٔ "
                 f"{money(f.get('ltv_future'))} آیندهٔ تنزیل‌شده با احتمال ماندگاری "
                 f"{(f.get('retention') or 0):.0%}.")
    if r["uncollected_overdue"] > 0:
        L.append(f"مطالبات معوق {money(r['uncollected_overdue'])}"
                 + (f" و قدیمی‌ترین بدهی {r['oldest_overdue_days']} روز"
                    if r["oldest_overdue_days"] else "")
                 + f"؛ مشارکت خالص {money(r['net_contribution'])}.")
    else:
        L.append(f"مطالبات معوقی ندارد و نرخ وصول {pct(r['collection_rate_pct'])} است.")
    top_pred = preds[0] if preds else None
    if top_pred:
        L.append(f"محتمل‌ترین تصمیم بعدی: {top_pred['question']} — "
                 f"{top_pred['probability']:.0%}.")
    if risks:
        L.append(f"مهم‌ترین ریسک: {risks[0]['title']} (شدت {risks[0]['severity_fa']}).")
    if opps:
        L.append(f"مهم‌ترین فرصت: {opps[0]['title']}.")
    if nba:
        L.append(f"اقدام بعدی: {nba[0]['action']} — مسئول {nba[0]['owner']}.")
    return " ".join(L)


def commercial_block(p: dict, f: dict, opps: list[dict], nba: list[dict]) -> dict:
    """بخش «کامرشال» — مقدار پولی هر چیز، برای الزام ۷."""
    m, r, c = p["margin"], p["receivables"], p["commercial"]
    upside = sum(x["value"] for x in opps)
    return {
        "revenue_nominal": c["revenue_nominal"],
        "revenue_real": c["revenue_real"],
        "gross_profit": m["gross_profit"],
        "margin_pct": m["gross_margin_pct"],
        "portfolio_median_margin": f.get("portfolio_median_margin"),
        "gp_monthly": f.get("gp_monthly"),
        "overdue": r["uncollected_overdue"],
        "not_yet_due": r["uncollected_not_yet_due"],
        "net_contribution": r["net_contribution"],
        "ltv_historic": f.get("ltv_historic"),
        "ltv_future": f.get("ltv_future"),
        "ltv_total": f.get("ltv_total"),
        "ltv_rank": f.get("ltv_rank"),
        "revenue_rank": c["revenue_rank"],
        "rank_gap": f.get("rank_gap"),
        "rescue_value": f.get("rescue_value"),
        "opportunity_upside": round(upside),
        "action_value": round(sum(x["value"] for x in nba)),
        "gp_destroyed": m["gross_profit_destroyed"],
        "days_cash": f.get("days_cash"),
        "cost_of_money": f.get("cost_of_money"),
        "cost_of_money_pct": f.get("cost_of_money_pct"),
        "real_margin": f.get("real_margin"),
        "real_gp": f.get("real_gp"),
        "expected_writeoff": f.get("expected_writeoff"),
        "net_margin": f.get("net_margin"),
        "net_gp": f.get("net_gp"),
        "finance_rate_monthly": f.get("finance_rate_monthly"),
        "margin_rank": f.get("margin_rank"),
        "real_margin_rank": f.get("real_margin_rank"),
        "margin_rank_gap": f.get("margin_rank_gap"),
        "focus": f.get("focus"),
        "focus_rank": f.get("focus_rank"),
        "value_at_play": f.get("value_at_play"),
        "value_at_play_basis": f.get("value_at_play_basis"),
        "growth_potential": f.get("growth_potential"),
        "achievable_real_margin": f.get("achievable_real_margin"),
        "discount_factor": f.get("ltv_discount_factor"),
        "horizon_months": f.get("retention_horizon_months"),
    }


def enrich(p: dict, feat: dict) -> dict:
    import signals as SG
    sig = SG.extract_signals(p, feat)
    preds = SG.predict_decisions(p, feat, sig)
    risks = find_risks(p, feat)
    opps = find_opportunities(p, feat)
    nba = next_best_actions(p, feat, risks, opps)
    return {
        **p,
        "features": feat,
        "signals": sig,
        "predictions": preds,
        "risks": risks,
        "opportunities": opps,
        "next_best_actions": nba,
        "commercial": {**p["commercial"]},
        "commercial_summary": commercial_block(p, feat, opps, nba),
        "summary": summarise(p, feat, risks, opps, nba, sig, preds),
        "risk_score": round(sum(URGENCY[x["severity"]] for x in risks), 2),
        "opportunity_score": round(sum(URGENCY[x["potential"]] for x in opps), 2),
        "signal_score": round(sum(x["strength"] for x in sig if x["direction"] == "منفی"), 2),
        "reference_count": (sum(len(x["references"]) for x in risks)
                            + sum(len(x["references"]) for x in opps)
                            + sum(len(x["references"]) for x in sig)
                            + sum(len(x["references"]) for x in preds)),
    }


def enrich_all(profiles: dict[str, dict], F) -> dict[str, dict]:
    import features as FT
    out = {}
    for cid, p in profiles.items():
        feat = FT.features_to_dict(F.loc[cid]) if cid in F.index else {}
        out[cid] = enrich(p, feat)
    return out
