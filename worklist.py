"""کارتابل — «الان دقیقاً چه کاری باید انجام دهم؟»

سه ستون در هر سطر: **هدف** ارتباط، **مشتری کیست**، و **بهترین کانال ارتباط**.
هر سه از داده می‌آیند:

  هدف   ← خانوادهٔ مشکل اصلی مشتری و مبلغی که در آن گیر است
  کیست  ← بخش، رتبهٔ فروش، بخش RFM، طول همکاری
  کانال ← ترکیب «کانالی که این مشتری تاریخاً با آن پیگیری شده» (فیلد Next_Action
          در CRM) با کانالی که نوع مشکل ایجاب می‌کند

دستور کار جلسه و تماس هم از همین داده ساخته می‌شود: عنوان شکایت باز، شمارهٔ فاکتور
معوق، دلیل آفر بی‌پاسخ، شکاف سهم سبد. توصیهٔ رفتاری از اهمیت حساب و نوع مشکل
می‌آید و عمداً کوتاه است.
"""
from __future__ import annotations

import pandas as pd

from pipeline import fa

# ═══════════════════════════════ خانوادهٔ مشکل
FAMILIES: dict[str, dict] = {
    "وصول": {
        "codes": ["overdue_exceeds_gp", "overdue_aged", "low_collection_rate",
                  "bounced_cheques", "over_credit_limit"],
        "goal": "وصول مطالبات معوق",
        "channel": "phone_followup",
        "color": "critical",
    },
    "سودآوری": {
        "codes": ["negative_real_margin", "high_cost_of_money", "thin_margin",
                  "many_negative_lines"],
        "goal": "اصلاح شرایط پرداخت یا قیمت",
        "channel": "price_meeting",
        "color": "warning",
    },
    "ریزش": {
        "codes": ["dormant", "volume_collapse", "rfm_drop", "quality_linked_decline"],
        "goal": "بازگرداندن جریان سفارش",
        "channel": "visit",
        "color": "serious",
    },
    "کیفیت": {
        "codes": ["open_severe_complaint"],
        "goal": "بستن پروندهٔ کیفی",
        "channel": "technical_visit",
        "color": "critical",
    },
    "رقابت": {
        "codes": ["competitor_dominant"],
        "goal": "پس‌گرفتن سهم از رقیب",
        "channel": "price_meeting",
        "color": "neu",
    },
    "رابطه": {
        "codes": ["uncontacted_active", "no_crm_history", "single_family_dependency"],
        "goal": "بازسازی رابطه و گسترش سبد",
        "channel": "phone_followup",
        "color": "low",
    },
}
CODE_FAMILY = {c: f for f, v in FAMILIES.items() for c in v["codes"]}

CHANNEL_FA = {
    "phone_followup": {"label": "تماس تلفنی", "kind": "call"},
    "technical_visit": {"label": "بازدید فنی", "kind": "meeting"},
    "price_meeting": {"label": "جلسهٔ قیمت", "kind": "meeting"},
    "visit": {"label": "بازدید حضوری", "kind": "meeting"},
    "send_sample": {"label": "ارسال نمونه و پیگیری فنی", "kind": "call"},
}
PRIORITY_FA = {"P1": "با ارزش · بحرانی", "P2": "با ارزش · عادی",
               "P3": "کم‌ارزش · بحرانی", "P4": "کم‌ارزش · غیربحرانی"}
PRIORITY_ORDER = ["P1", "P2", "P3", "P4"]


def _money(v) -> str:
    v = float(v or 0)
    s = "−" if v < 0 else ""
    a = abs(v)
    if a >= 1e9:
        return f"{s}{a / 1e9:,.2f} میلیارد"
    if a >= 1e6:
        return f"{s}{a / 1e6:,.1f} میلیون"
    if a >= 1e3:
        return f"{s}{a / 1e3:,.0f} هزار"
    return f"{s}{a:,.0f}"


# ═══════════════════════════════ بهترین کانال ارتباط
def _channel(p: dict, family: str, priority: str) -> dict:
    """کانالی که نوع مشکل ایجاب می‌کند، تعدیل‌شده با سابقهٔ خود مشتری."""
    want = FAMILIES[family]["channel"]
    if family == "ریزش" and priority.startswith("P1"):
        want = "visit"
    if family == "رابطه" and (p["development"]["requests"] or 0) > 0:
        want = "send_sample"

    hist = p["engagement"].get("open_next_actions") or {}
    hist = {k: v for k, v in hist.items() if k != "no_action"}
    top = max(hist, key=hist.get) if hist else None
    n = hist.get(top, 0) if top else 0
    label = CHANNEL_FA.get(want, CHANNEL_FA["phone_followup"])
    why = (f"نوع مشکل این کانال را می‌طلبد؛ سابقهٔ خود مشتری "
           f"{CHANNEL_FA.get(top, {}).get('label', '—')} × {n} است"
           if top and n else "بدون سابقهٔ کانال در CRM؛ کانال از نوع مشکل انتخاب شد")
    if top and top == want and n:
        why = f"هم نوع مشکل و هم سابقهٔ {n} پیگیری این مشتری، همین کانال را می‌گوید"
    return {"key": want, "label": label["label"], "kind": label["kind"], "why": why,
            "history": {CHANNEL_FA.get(k, {}).get("label", k): int(v)
                        for k, v in sorted(hist.items(), key=lambda kv: -kv[1])}}


# ═══════════════════════════════ دستور کار جلسه و تماس
def _talking_points(p: dict, f: dict, family: str) -> list[str]:
    """نکته‌هایی که باید مطرح شود — همه از رکورد واقعی این مشتری."""
    pts: list[str] = []
    r, c, m = p["receivables"], p["commercial"], p["margin"]
    od = r["uncollected_overdue"]
    if od > 0:
        oi = (r.get("overdue_invoices") or [])[:2]
        ids = "، ".join(str(x["invoice_no"]) for x in oi)
        pts.append(f"مانده معوق {_money(od)}"
                   + (f" — فاکتور {ids}" if ids else "")
                   + (f"، قدیمی‌ترین {r['oldest_overdue_days']} روز"
                      if r["oldest_overdue_days"] else ""))
    if f.get("cost_of_money_pct") and (f.get("real_margin") or 0) < (f.get("margin") or 0):
        pts.append(f"چرخهٔ نقد {float(f.get('days_cash') or 0):.0f} روز؛ "
                   f"هزینهٔ پول {float(f['cost_of_money_pct']):.1f}٪ و سود واقعی "
                   f"{float(f.get('real_margin') or 0):.1f}٪")
    open_cp = [x for x in p["complaints"]["items"] if x["status"] != "closed"][:2]
    for x in open_cp:
        pts.append(f"شکایت باز «{x['title']}» با شدت {fa(x['severity'])}")
    op = (p["offers"].get("open_items") or [])[:1]
    for x in op:
        pts.append(f"آفر باز {x['id']} با دلیل {fa(x['reason'])} و تخفیف "
                   f"{float(x['discount_pct'] or 0):.1f}٪ — تعیین تکلیف")
    pend = [x for x in p["development"]["items"] if x["status"] in
            ("under_review", "in_development")][:1]
    for x in pend:
        pts.append(f"درخواست فنی بی‌پاسخ: {fa(x['type'])}")
    ws = p["wallet_share"]
    if ws["avg_share_pct"] is not None and ws["segment_avg_share_pct"] is not None \
            and ws["avg_share_pct"] < ws["segment_avg_share_pct"]:
        comp = max(ws["main_competitors"], key=ws["main_competitors"].get) \
            if ws["main_competitors"] else None
        pts.append(f"سهم ما {ws['avg_share_pct']:.0f}٪ در برابر میانهٔ بخش "
                   f"{ws['segment_avg_share_pct']:.0f}٪"
                   + (f"؛ رقیب اصلی {fa(comp)}" if comp else ""))
    d = c["days_since_last_purchase"]
    if d is not None and d > 90:
        pts.append(f"{d} روز بی‌سفارش — علت را بپرسید، پیشنهاد ندهید")
    if not pts:
        pts.append(f"مرور سبد خرید و برنامهٔ دورهٔ بعد؛ فروش {_money(c['revenue_nominal'])}"
                   f" با حاشیهٔ واقعی {float(f.get('real_margin') or 0):.1f}٪")
    return pts[:5]


# لحن از لیبل اولویت و نوع کانال می‌آید. این بخش از داده در نمی‌آید و
# قاعدهٔ ارتباط مؤثر است — در مستند صریح گفته شده.
TONE = {
    ("P1", "meeting"): ["مدیر فروش شخصاً برود؛ ارجاع به کارشناس، پیام «مهم نیستید» می‌دهد",
                        "اول گوش کنید و یادداشت بردارید؛ عدد را وسط جلسه بیاورید نه در دقیقهٔ اول",
                        "بدن باز و رو به مخاطب، بدون دست‌به‌سینه؛ تماس چشمی پیوسته ولی نه خیره"],
    ("P1", "call"): ["خودتان تماس بگیرید، نه دفتر؛ وقت را از قبل هماهنگ کنید",
                     "اول بپرسید «الان وقت مناسبی است؟»، بعد وارد موضوع شوید",
                     "آرام و شمرده حرف بزنید؛ بعد از گفتن عدد سکوت کنید تا او پاسخ دهد"],
    ("P2", "meeting"): ["کارشناس ارشد کافی است؛ جلسه را کوتاه و ساختارمند نگه دارید",
                        "با نتیجهٔ مثبت شروع کنید، بعد درخواست را بگذارید",
                        "لحن هم‌تراز، نه معذرت‌خواهانه و نه دستوری"],
    ("P2", "call"): ["تماس برنامه‌ریزی‌شده، نه سرزده",
                     "با نتیجهٔ مثبت شروع کنید، بعد درخواست را بگذارید",
                     "لحن هم‌تراز؛ در پایان جمع‌بندی را خودتان بگویید"],
    ("P3", "meeting"): ["جلسهٔ کوتاه و فقط اگر مشکل بدون حضور حل نمی‌شود",
                        "مستقیم سر اصل مطلب بروید؛ مقدمه‌چینی وقت هر دو طرف را می‌گیرد",
                        "لحن قاطع و محترم؛ مهلت مشخص بدهید"],
    ("P3", "call"): ["تماس کوتاه کافی است؛ جلسهٔ حضوری هزینهٔ توجیه‌ناپذیر دارد",
                     "در سی ثانیهٔ اول بگویید چرا زنگ زده‌اید",
                     "لحن قاطع و محترم؛ مهلت مشخص بدهید"],
    ("P4", "meeting"): ["جلسه نگذارید؛ اگر ناچارید، آنلاین و ربع‌ساعته",
                        "یک درخواست، یک مهلت",
                        "بدون مذاکره؛ شرط را اعلام کنید"],
    ("P4", "call"): ["پیگیری مکتوب کافی است؛ منابع فروش را اینجا نگذارید",
                     "یک پیام روشن با یک درخواست و یک مهلت",
                     "بدون مذاکره؛ شرط را اعلام کنید"],
}
CLOSE = {
    "وصول": "تعهد پرداخت با تاریخ و مبلغ مشخص، مکتوب و پیش از پایان گفت‌وگو",
    "سودآوری": "توافق روی شرط پرداخت جدید یا مارک‌آپ اعتبار، با تاریخ اجرا",
    "ریزش": "یک سفارش آزمایشی با تاریخ مشخص",
    "کیفیت": "مالک رسیدگی و مهلت پاسخ، و تاریخ اعلام نتیجه به مشتری",
    "رقابت": "تعهد تناژ در برابر پلهٔ قیمتی، با سقف زمانی",
    "رابطه": "تعیین تاریخ تماس بعدی و موضوعش",
}
OPENERS = {
    "وصول": "«برای تسویهٔ فاکتورهای سررسیدشده تماس گرفتم» — بدون مقدمه",
    "سودآوری": "«می‌خواهم دربارهٔ شرایط پرداخت با هم به یک عدد برسیم»",
    "ریزش": "«چند وقتی سفارشی نداشتیم؛ می‌خواستم بدانم از سمت ما چه چیزی درست نبوده»",
    "کیفیت": "«دربارهٔ پروندهٔ کیفی باز تماس گرفتم و می‌خواهم تکلیفش را روشن کنم»",
    "رقابت": "«می‌خواهم بدانم برای گرفتن سهم بیشتر از سبد شما چه چیزی لازم است»",
    "رابطه": "«تماس گرفتم ببینم برنامهٔ خریدتان برای دورهٔ بعد چیست»",
}


def _agenda(p: dict, f: dict, family: str, priority: str, channel: dict) -> dict:
    kind = channel["kind"]
    pts = _talking_points(p, f, family)
    return {
        "kind": kind,
        "title": "دستور کار جلسه" if kind == "meeting" else "دستور کار تماس",
        "channel": channel["label"],
        "opener": OPENERS.get(family, OPENERS["رابطه"]),
        "points": pts,
        "close": CLOSE.get(family, CLOSE["رابطه"]),
        "close_label": "با چه چیزی جلسه را ببندید" if kind == "meeting"
                       else "با چه چیزی تماس را ببندید",
        "tone": TONE.get((priority, kind), TONE[("P3", kind)]),
        "record": "همان لحظه در CRM ثبت کنید: تعهد گرفته‌شده، تاریخ، و اقدام بعدی",
    }


# ═══════════════════════════════ ساخت کارتابل
def build(profiles: dict[str, dict], frame: pd.DataFrame, limit: int = 120) -> dict:
    rows = []
    for cid, p in profiles.items():
        if not p["coverage"]["sales"] or not p.get("risks"):
            continue
        f = p.get("features") or {}
        top = p["risks"][0]
        family = CODE_FAMILY.get(top["code"], "رابطه")
        # پروندهٔ کیفی باز با شدت بحرانی/زیاد، هر گفت‌وگوی دیگری را مسدود می‌کند.
        # پس اگر چنین پرونده‌ای هست، مشکل اصلی همان است — حتی اگر ریسک پولی‌تری
        # بالاتر نشسته باشد.
        qc = next((x for x in p["risks"] if x["code"] == "open_severe_complaint"), None)
        if qc and p["complaints"]["open"]:
            family, top = "کیفیت", qc
        row = frame.loc[cid] if cid in frame.index else None
        valuable = bool(f.get("focus") in ("رشد بده", "حفظ کن")
                        or (p["commercial"]["revenue_rank"] or 999) <= 100)
        # «بحرانی» را سخت‌گیرانه تعریف می‌کنیم، وگرنه چون ریسک‌ها بر شدت مرتب‌اند
        # تقریباً همهٔ مشتری‌ها بحرانی می‌شوند و لیبل اولویت بی‌معنا می‌شود.
        critical = bool(top["severity"] == "critical"
                        or p["complaints"]["critical_or_high"] and p["complaints"]["open"]
                        or float(f.get("retention") or 1) < 0.25)
        priority = ("P1" if valuable and critical else "P2" if valuable else
                    "P3" if critical else "P4")
        ch = _channel(p, family, priority)
        # «همین حالا» باید با هدف بخواند: اقدامِ همان ریسکی که هدف را تعیین کرده،
        # نه لزوماً اقدام اول فهرست اولویت.
        nbas = p.get("next_best_actions") or []
        nba = (next((x for x in nbas if x.get("code") == top["code"]), None)
               or {"action": top["action"], "owner": top["owner"],
                   "references": top["references"]})
        at_stake = max(float(top.get("value_at_stake") or 0),
                       float(f.get("value_at_play") or 0))
        i, c, m, r = p["identity"], p["commercial"], p["margin"], p["receivables"]
        rows.append({
            "customer_id": cid,
            "priority": priority, "priority_fa": PRIORITY_FA[priority],
            "family": family, "family_color": FAMILIES[family]["color"],
            # ستون ۱ — هدف
            "goal": FAMILIES[family]["goal"],
            "goal_amount": round(at_stake),
            "goal_detail": top["title"],
            # ستون ۲ — مشتری کیست
            "who": (f"بخش {i['segment']} · رتبهٔ {c['revenue_rank']} فروش · "
                    f"{f.get('rfm_segment') or '—'} · {c['active_months']} ماه فعال"),
            "segment": i["segment"], "revenue_rank": c["revenue_rank"],
            "rfm_segment": f.get("rfm_segment"), "rfm": f.get("RFM"),
            "rfm_prev": f.get("RFM_prev"), "rfm_move_label": f.get("rfm_move_label"),
            "ltv_total": f.get("ltv_total"), "ltv_rank": f.get("ltv_rank"),
            # ستون ۳ — بهترین ارتباط
            "channel": ch["label"], "channel_kind": ch["kind"],
            "channel_why": ch["why"], "channel_history": ch["history"],
            # کارت جزئیات
            "problems": len(p["risks"]), "complaints": p["complaints"]["total"],
            "open_complaints": p["complaints"]["open"],
            "revenue": c["revenue_nominal"], "margin_pct": m["gross_margin_pct"],
            "real_margin": f.get("real_margin"), "cost_of_money_pct": f.get("cost_of_money_pct"),
            "days_cash": f.get("days_cash"), "overdue": r["uncollected_overdue"],
            "recency": c["days_since_last_purchase"], "retention": f.get("retention"),
            "focus": f.get("focus"), "value_at_play": f.get("value_at_play"),
            "tasks": ([nba["action"]] + [x["action"] for x in nbas
                                         if x["action"] != nba["action"]])[:4],
            "owners": ([nba["owner"]] + [x["owner"] for x in nbas
                                         if x["action"] != nba["action"]])[:4],
            "now": nba.get("action") or top["action"],
            "now_owner": nba.get("owner") or top["owner"],
            "references": (nba.get("references") or top["references"])[:3],
            "agenda": _agenda(p, f, family, priority, ch),
        })
    rows.sort(key=lambda x: (PRIORITY_ORDER.index(x["priority"]), -x["goal_amount"]))
    # کارت‌های بالای صفحه: هر مشتری که **دست‌کم یک** ریسک از آن خانواده دارد
    # شمرده می‌شود، نه فقط جایی که مشکل اصلی‌اش است. پس جمع کارت‌ها از تعداد
    # مشتری بیشتر است — و همین درست است: یک مشتری می‌تواند هم‌زمان مشکل وصول و
    # کیفیت داشته باشد.
    fam_count: dict[str, dict] = {
        k: {"family": k, "color": v["color"], "goal": v["goal"],
            "customers": 0, "amount": 0.0, "p1": 0, "primary": 0}
        for k, v in FAMILIES.items()}
    for cid, p in profiles.items():
        if not p["coverage"]["sales"] or not p.get("risks"):
            continue
        fams = {CODE_FAMILY.get(x["code"]) for x in p["risks"]} - {None}
        row = next((x for x in rows if x["customer_id"] == cid), None)
        for fam in fams:
            b = fam_count[fam]
            b["customers"] += 1
            if row and row["priority"] == "P1":
                b["p1"] += 1
            if row and row["family"] == fam:
                b["primary"] += 1
                b["amount"] += float(row["goal_amount"] or 0)
    cards = sorted((b for b in fam_count.values() if b["customers"]),
                   key=lambda b: -b["customers"])
    for b in cards:
        b["amount"] = round(b["amount"])
    return {
        "cards": cards,
        "rows": rows[:limit],
        "total": len(rows),
        "shown": min(limit, len(rows)),
        "priority_counts": {k: sum(1 for x in rows if x["priority"] == k)
                            for k in PRIORITY_ORDER},
        "priority_fa": PRIORITY_FA,
    }
