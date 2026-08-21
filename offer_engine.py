"""موتور آفر — انتخاب و زمان‌بندی، نه اقناع.

پنج فرضیهٔ رایج دربارهٔ آفر را روی ۲٬۵۰۰ آفر همین شرکت آزمودیم. **چهارتا رد شد،
یکی ماند** — و همان یکی کل طراحی این موتور را تعیین کرد.

    رد شد   عمق تخفیف            χ²=۱٫۱   df=۴   p=۰٫۹۰   (همبستگی −۰٫۰۲)
    رد شد   دلیل آفر             χ²=۱۰٫۶  df=۱۲  p=۰٫۵۶
    رد شد   نوع آفر              χ²=۴٫۰   df=۲   p=۰٫۱۴
    رد شد   سابقهٔ پذیرش مشتری   χ²=۳٫۳   df=۳   p=۰٫۳۵
    ماند    طول اعتبار آفر       χ²=۳۴٫۴  df=۳   p<۰٫۰۰۰۱

پذیرش در پنجرهٔ **۸ تا ۱۴ روزه ۶۲٫۲٪** است و بیرون از آن **۴۵٫۲٪** — ۱۷ واحد درصد
اختلاف، بدون یک ریال تخفیف بیشتر. این اثر در **هر سه نوع آفر جداگانه** تکرار
می‌شود و با عمق تخفیف هم‌بسته نیست (میانگین تخفیف در چهار باند ۴٫۶٪ تا ۴٫۹٪).
شرکت امروز فقط **۲۶٪** آفرهایش را در این پنجره می‌دهد؛ میانهٔ اعتبار ۱۸ روز است.

    اهرم، مهلت است — نه تخفیف.

سه نتیجهٔ طراحی:

  ۱. تخفیف را **کمینه** می‌کنیم (صدک ۲۵ آفرهای پذیرفته‌شده)، چون عمق تخفیف چیزی
     نمی‌خرد و سقفش از حاشیهٔ واقعی **پس از هزینهٔ پول** می‌آید.
  ۲. مهلت را روی **۱۰ روز** می‌گذاریم — وسط پنجرهٔ برنده.
  ۳. تنها اهرم باقی‌مانده **انتخاب** است: به چه کسی و برای چه چیزی آفر بدهیم.

و یک صداقت لازم: پذیرش آفر در این داده به خرید بیشتر ترجمه **نمی‌شود** — سهم
خرید همان گروه کالا در ۳۰ روز بعد برای آفر پذیرفته‌شده ۷۰٫۲٪ و برای آفر ردشده
۶۹٫۶٪ است (Fisher p=۰٫۸۶). پس ستون پول در این تب **هدف** است، نه لیفت
اندازه‌گیری‌شده؛ همه‌جا با همین برچسب نوشته می‌شود.
"""
from __future__ import annotations

# ═════════════════════ ثابت‌های تجربی — همه از همین داده، هیچ‌کدام فرضی
ACCEPT_WINDOW = 0.6217           # پذیرش در پنجرهٔ ۸–۱۴ روزه (۳۴۱ آفر تصمیم‌شده)
ACCEPT_BASE = 0.4958             # پذیرش کل آفرهای تصمیم‌شده (۱٬۳۱۳ مورد)
ACCEPT_OUTSIDE = 0.4516          # پذیرش بیرون از پنجره (۹۷۲ مورد)
RECOMMENDED_VALIDITY = 10        # روز — وسط پنجرهٔ برنده
WINDOW_LO, WINDOW_HI = 8, 14

MIN_VIABLE_DISCOUNT = 2.83       # صدک ۲۵ تخفیفِ آفرهای پذیرفته‌شده
OBSERVED_DISCOUNT_MAX = 8.5      # بیشترین تخفیف مشاهده‌شده در تاریخ آفرها
MARGIN_FLOOR = 0.0               # زیر این حاشیهٔ واقعی، آفر نمی‌دهیم
CURRENT_WINDOW_SHARE = 26.1      # ٪ آفرهایی که امروز در پنجرهٔ درست داده می‌شوند
MEDIAN_VALIDITY_TODAY = 18       # روز

# ═════════════════════ آزمون پنجره — تنها عامل مثبت
WINDOW_CURVE = [
    {"band": "۴ تا ۷ روز", "lo": 4, "hi": 7, "n": 160, "accept": 53.1},
    {"band": "۸ تا ۱۰ روز", "lo": 8, "hi": 10, "n": 127, "accept": 60.6},
    {"band": "۱۱ تا ۱۴ روز", "lo": 11, "hi": 14, "n": 214, "accept": 63.1},
    {"band": "۱۵ تا ۱۸ روز", "lo": 15, "hi": 18, "n": 198, "accept": 46.5},
    {"band": "۱۹ تا ۲۱ روز", "lo": 19, "hi": 21, "n": 164, "accept": 42.7},
    {"band": "۲۲ روز و بیشتر", "lo": 22, "hi": 60, "n": 450, "accept": 42.7},
]
WINDOW_BY_TYPE = [
    {"type": "حجمی", "in_window": 60.9, "outside": 42.7, "n": 415},
    {"type": "قیمتی", "in_window": 61.5, "outside": 43.6, "n": 415},
    {"type": "مدت‌دار", "in_window": 63.7, "outside": 49.4, "n": 483},
]
WINDOW_TEST = {
    "factor": "طول اعتبار آفر", "chi2": 34.4, "df": 3, "p": 0.00001,
    "verdict": "پیش‌بین است",
    "detail": (f"پذیرش در پنجرهٔ {WINDOW_LO}–{WINDOW_HI} روزه ۶۲٫۲٪ در برابر ۴۵٫۲٪ "
               "بیرون از آن؛ ۳۴۱ در برابر ۹۷۲ آفر تصمیم‌شده. اثر در هر سه نوع آفر "
               "جداگانه تکرار می‌شود و با عمق تخفیف هم‌بسته نیست."),
}

NEGATIVE_TESTS = [
    {"factor": "عمق تخفیف", "chi2": 1.1, "df": 4, "p": 0.90, "verdict": "پیش‌بین نیست",
     "detail": "میانهٔ تخفیف آفر پذیرفته‌شده ۴٫۷۴٪ و آفر ردشده ۴٫۸۶٪. همبستگی نقطه‌ای−دورشته‌ای −۰٫۰۲."},
    {"factor": "دلیل آفر", "chi2": 10.6, "df": 12, "p": 0.56, "verdict": "پیش‌بین نیست",
     "detail": "۱۳ دلیل ثبت‌شده؛ پذیرش همه حول ۴۹٪ ثابت است."},
    {"factor": "نوع آفر", "chi2": 4.0, "df": 2, "p": 0.14, "verdict": "پیش‌بین نیست",
     "detail": "حجمی، قیمتی و مدت‌دار تفاوت معنادار ندارند."},
    {"factor": "سابقهٔ پذیرش خود مشتری", "chi2": 3.3, "df": 3, "p": 0.35, "verdict": "پیش‌بین نیست",
     "detail": "نرخ پذیرش گذشتهٔ مشتری (فقط با نگاه به عقب) پذیرش بعدی را پیش‌بینی نمی‌کند."},
    {"factor": "پذیرش ← خرید بیشتر", "chi2": None, "df": None, "p": 0.857,
     "verdict": "اثبات نشد",
     "detail": ("خرید همان گروه کالا در ۳۰ روز پس از تصمیم: آفر پذیرفته‌شده ۷۰٫۲٪، "
                "آفر ردشده ۶۹٫۶٪ (Fisher p=۰٫۸۶). پس آوردهٔ آفر در این داده "
                "اندازه‌گیری نشده و ستون پول «هدف» است، نه لیفت."),
     "critical": True},
]

MONEY_LABEL = "آوردهٔ هدف در صورت پذیرش"
MONEY_CAVEAT = ("این مبلغ **هدف** است، نه لیفت اندازه‌گیری‌شده: در دادهٔ آفرهای گذشته، "
                "پذیرش آفر با خرید بیشتر همراه نبوده (۷۰٫۲٪ در برابر ۶۹٫۶٪، p=۰٫۸۶). "
                "عدد را سقفِ آنچه می‌خواهیم بگیریم بدانید و همان را در جلسه تعهد کنید.")

PLAYS = {
    "بازگشت": {
        "goal": "بازگرداندن حجم خرید به سطح خودش",
        "trigger": "مشتری باسابقه که حجم خریدش افت کرده یا از الگوی سفارش خودش عقب افتاده",
        "offer": "پلهٔ حجمی بازگشت: قیمت در برابر تعهد تناژ دورهٔ بعد",
        "ask": "تعهد تناژ دورهٔ بعد، کتبی، پیش از صدور فاکتور",
        "color": "serious",
    },
    "فروش مکمل": {
        "goal": "افزودن یک گروه کالای تازه به سبد",
        "trigger": "گروه کالایی که هم‌بخشی‌های او می‌خرند و او نمی‌خرد",
        "offer": "قیمت معرفی برای نخستین سفارش گروه کالای جدید",
        "ask": "یک سفارش آزمایشی با تناژ حداقلی و بازخورد فنی",
        "color": "neu",
    },
    "افزایش سهم": {
        "goal": "پس‌گرفتن سهم از رقیب",
        "trigger": "سهم ما از سبد خرید مشتری زیر میانهٔ بخش است و برآورد خرید کل موجود است",
        "offer": "پلهٔ قیمتی در برابر جابه‌جایی تدریجی سهم",
        "ask": "جابه‌جایی نصف شکاف سهم در دو دورهٔ سفارش",
        "color": "warning",
    },
}

PRIORITY_ORDER = ["P1", "P2", "P3", "P4"]


def _num(v, d=0.0) -> float:
    try:
        return d if v is None else float(v)
    except (TypeError, ValueError):
        return d


def _headroom(real_margin: float) -> float:
    """چقدر می‌توانیم تخفیف بدهیم بدون اینکه سود واقعی منفی شود."""
    return max(0.0, min(real_margin - MARGIN_FLOOR, OBSERVED_DISCOUNT_MAX))


def _build_one(cid: str, p: dict, prio: dict) -> list[dict]:
    f = p.get("features") or {}
    c, ws = p["commercial"], p["wallet_share"]
    rm = _num(f.get("real_margin"))
    months = max(_num(c["active_months"]), 1)
    rev_year = _num(c["revenue_nominal"]) * min(12 / months, 1.0)
    price = (_num(c["revenue_nominal"]) / _num(c["volume"], 1)) if _num(c["volume"]) else 0.0
    head = _headroom(rm)
    disc = min(MIN_VIABLE_DISCOUNT, head)
    out: list[dict] = []

    def add(play, inc_rev, evidence, refs):
        if inc_rev <= 0:
            return
        gp = inc_rev * (rm - disc) / 100
        feasible = bool(head >= MIN_VIABLE_DISCOUNT and gp > 0)
        out.append({
            "offer_key": f"{cid}:{play}",
            "customer_id": cid, "play": play,
            "goal": PLAYS[play]["goal"], "offer": PLAYS[play]["offer"],
            "ask": PLAYS[play]["ask"],
            "incremental_revenue": round(inc_rev),
            "real_margin": round(rm, 2),
            "headroom_pct": round(head, 2),
            "suggested_discount_pct": round(disc, 2),
            "margin_after_offer": round(rm - disc, 2),
            "validity_days": RECOMMENDED_VALIDITY,
            "accept_rate": ACCEPT_WINDOW,
            "gp_if_accepted": round(gp),
            "expected_value": round(gp * ACCEPT_WINDOW),
            "expected_value_base": round(gp * ACCEPT_BASE),
            "feasible": feasible,
            "block_reason": ("" if feasible else
                             ("حاشیهٔ واقعی این مشتری پس از هزینهٔ پول "
                              f"{rm:.1f}٪ است و فضای تخفیف ندارد؛ پیش از هر آفر "
                              "باید شرایط پرداخت اصلاح شود")),
            "evidence": evidence, "references": refs,
        })

    # ── بازگشت: مشتری باسابقه که افت کرده
    vt = c["volume_trend_pct"]
    d = c["days_since_last_purchase"]
    gap = _num(f.get("order_gap"))
    silent = bool(gap >= 3 and d is not None and d > gap * 2)
    if months >= 6 and ((vt is not None and vt <= -25) or silent):
        drop = abs(_num(vt)) / 100 if vt is not None else 0.25
        inc = rev_year * min(max(drop, 0.15), 0.6)
        ev = []
        if vt is not None and vt <= -25:
            ev.append(f"حجم شش ماه اخیر {vt:+.0f}٪ تغییر کرده")
        if silent:
            ev.append(f"{d} روز بی‌سفارش در برابر فاصلهٔ معمول {gap:.0f} روزهٔ خودش")
        ev.append(f"{int(months)} ماه سابقهٔ فعال — رابطه ارزش بازگرداندن دارد")
        add("بازگشت", inc, "؛ ".join(ev),
            [{"sheet": "فروش", "sheet_key": "sales", "record_id": None,
              "date": c["last_purchase"], "date_fa": None,
              "fields": [{"name": "vol_trend", "name_fa": "روند حجم",
                          "value": f"{_num(vt):+.0f}٪"},
                         {"name": "recency", "name_fa": "رکود", "value": f"{d} روز"}],
              "note": "مقایسهٔ شش ماه اخیر با شش ماه پیش از آن، بر پایهٔ کیلوگرم"}])

    # ── فروش مکمل: گروه کالایی که هم‌بخشی‌ها می‌خرند و او نمی‌خرد
    xs = c.get("cross_sell_families") or []
    if xs and d is not None and d <= 180:
        mix = c.get("product_family_mix") or {}
        typical = (sorted(mix.values(), reverse=True)[1] / 100
                   if len(mix) > 1 else 0.15)
        inc = rev_year * max(min(typical, 0.35), 0.08)
        add("فروش مکمل", inc,
            f"{len(xs)} گروه کالای فروخته‌نشده که هم‌بخشی‌ها می‌خرند: "
            + "، ".join(xs[:2])
            + "؛ الگوی سنجیده: خرید از ۲+ گروه حدود ۲۰ واحد درصد ماندگاری بیشتر",
            [{"sheet": "محاسبه‌شده", "sheet_key": "derived", "record_id": None,
              "date": None, "date_fa": None,
              "fields": [{"name": "families", "name_fa": "گروه کالا",
                          "value": f"{int(_num(f.get('families')))} گروه فعلی"},
                         {"name": "cross_sell", "name_fa": "گروه فروخته‌نشده",
                          "value": "، ".join(xs)}],
              "note": "مقایسه با سبد کالای هم‌بخشی‌های همین مشتری"}])

    # ── افزایش سهم: سهم ما از سبد او زیر میانهٔ بخش است
    share, seg = ws.get("avg_share_pct"), ws.get("segment_avg_share_pct")
    est = _num(ws.get("estimated_total_purchase"))
    if share is not None and seg is not None and est > 0 and share < seg - 5:
        kg = est * (seg - share) / 100 * 0.5 * 12       # نصف شکاف، سالانه
        inc = kg * price
        add("افزایش سهم", inc,
            f"سهم ما {share:.0f}٪ در برابر میانهٔ بخش {seg:.0f}٪؛ خرید برآوردی "
            f"{est:,.0f} کیلوگرم در ماه. هدف: نصف شکاف"
            + (f"؛ رقیب اصلی {max(ws['main_competitors'], key=ws['main_competitors'].get)}"
               if ws.get("main_competitors") else ""),
            [{"sheet": "سهم_سبد", "sheet_key": "wallet_share", "record_id": None,
              "date": None, "date_fa": None,
              "fields": [{"name": "Nafis_Purchase", "name_fa": "سهم ما",
                          "value": f"{share:.0f}٪"},
                         {"name": "Estimated_Total_Purchase",
                          "name_fa": "خرید کل برآوردی",
                          "value": f"{est:,.0f} کیلوگرم/ماه"}],
              "note": f"میانگین {ws.get('months_observed')} ماه برآورد کارشناس — "
                      "عدد را سقف بدانید، نه انتظار"}])

    for o in out:
        o.update({"priority": prio.get("priority", "P3"),
                  "priority_fa": prio.get("priority_fa", "—"),
                  "who": prio.get("who", ""),
                  "rfm_segment": f.get("rfm_segment"),
                  "ltv_total": f.get("ltv_total"),
                  "days_cash": round(_num(f.get("days_cash"))),
                  "cost_of_money_pct": _num(f.get("cost_of_money_pct")),
                  "focus": f.get("focus"), "segment": p["identity"]["segment"],
                  "revenue_rank": c["revenue_rank"]})
    return out


def build(profiles: dict[str, dict], worklist: dict, limit: int = 120) -> dict:
    prio = {r["customer_id"]: r for r in (worklist.get("rows") or [])}
    rows: list[dict] = []
    for cid, p in profiles.items():
        if not p["coverage"]["sales"]:
            continue
        rows.extend(_build_one(cid, p, prio.get(cid, {})))
    rows.sort(key=lambda x: (PRIORITY_ORDER.index(x["priority"]) if x["priority"]
                             in PRIORITY_ORDER else 3, -x["expected_value"]))
    ok = [x for x in rows if x["feasible"]]
    blocked = [x for x in rows if not x["feasible"]]
    blocked.sort(key=lambda x: -x["incremental_revenue"])

    cards = []
    for play, meta in PLAYS.items():
        sel = [x for x in ok if x["play"] == play]
        cards.append({
            "play": play, "color": meta["color"], "goal": meta["goal"],
            "trigger": meta["trigger"], "offer": meta["offer"], "ask": meta["ask"],
            "customers": len({x["customer_id"] for x in sel}),
            "offers": len(sel),
            "gp_if_accepted": round(sum(x["gp_if_accepted"] for x in sel)),
            "expected_value": round(sum(x["expected_value"] for x in sel)),
        })
    cards.sort(key=lambda b: -b["expected_value"])

    ev_win = sum(x["expected_value"] for x in ok)
    ev_base = sum(x["expected_value_base"] for x in ok)
    blocked_cust = len({x["customer_id"] for x in blocked}
                       - {x["customer_id"] for x in ok})
    return {
        "cards": cards,
        "rows": ok[:limit],
        "blocked": blocked[:40],
        "total": len(ok), "blocked_total": len(blocked),
        "customers": len({x["customer_id"] for x in ok}),
        "blocked_customers": blocked_cust,
        "expected_value_total": round(ev_win),
        "expected_value_base": round(ev_base),
        "window_gain": round(ev_win - ev_base),
        "gp_total": round(sum(x["gp_if_accepted"] for x in ok)),
        "blocked_gp": round(sum(x["gp_if_accepted"] for x in blocked)),
        "accept_rate": ACCEPT_WINDOW,
        "accept_rate_base": ACCEPT_BASE,
        "accept_rate_outside": ACCEPT_OUTSIDE,
        "validity_days": RECOMMENDED_VALIDITY,
        "window_lo": WINDOW_LO, "window_hi": WINDOW_HI,
        "window_curve": WINDOW_CURVE,
        "window_by_type": WINDOW_BY_TYPE,
        "window_test": WINDOW_TEST,
        "current_window_share": CURRENT_WINDOW_SHARE,
        "median_validity_today": MEDIAN_VALIDITY_TODAY,
        "min_viable_discount": MIN_VIABLE_DISCOUNT,
        "observed_discount_max": OBSERVED_DISCOUNT_MAX,
        "negative_tests": NEGATIVE_TESTS,
        "money_label": MONEY_LABEL,
        "money_caveat": MONEY_CAVEAT,
        "plays": PLAYS,
        # نقطه‌های شبیه‌ساز: کل مجموعه، نه ۱۲۰ سطر نمایش‌داده‌شده،
        # تا لغزندهٔ تخفیف روی همان پایه‌ای حساب کند که عددهای بالای صفحه.
        "sim_points": [{"r": x["incremental_revenue"], "m": x["real_margin"],
                        "h": x["headroom_pct"]} for x in ok],
        "headline": ("اهرم، مهلت است نه تخفیف: پذیرش در پنجرهٔ ۸ تا ۱۴ روزه "
                     "۶۲٫۲٪ در برابر ۴۵٫۲٪ بیرون از آن، بدون یک ریال تخفیف بیشتر."),
        "policy": ("از پنج عاملی که آزمودیم فقط **طول اعتبار آفر** پذیرش را پیش‌بینی "
                   "کرد. پس سیاست این است: مهلت را روی ۱۰ روز "
                   "بگذار، تخفیف را روی کمینهٔ قابل‌قبول "
                   "(۲٫۸۳٪ — صدک ۲۵ آفرهای پذیرفته‌شده) و سقف را از "
                   "حاشیهٔ واقعی پس از هزینهٔ پول بگیر. رتبه‌بندی روی اهمیت مشتری و "
                   "سپس آوردهٔ هدف است، نه روی احتمال — چون احتمال برای همه یکسان است."),
    }
