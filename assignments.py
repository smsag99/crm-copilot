"""لایهٔ ارجاع — کارتابل مدیر فروش ← کارتابل کارشناس.

# منطق پیشنهاد کارشناس: چه چیزی در داده هست و چه چیزی نیست

**هست — مالکیت.** هر ۶۲۴ مشتری در فایل اصلی دقیقاً یک کارشناس دارند، و **هر
۴٬۱۸۴ تعامل CRM را همان کارشناس مالک ثبت کرده است**؛ هیچ مشتری‌ای دو کارشناس
نداشته. پس «کارشناس مالک» یک واقعیت اندازه‌گیری‌شده است، نه قرارداد ما.

**هست — بار کاری.** تعامل ۹۰ روز اخیر بین ۲۵ و ۶۸ در نوسان است (REP-007 نزدیک
سه برابر REP-001). این تفاوت واقعی است و می‌شود روی آن تصمیم گرفت.

**نیست — تخصص.** ترکیب نوع تعامل در هر هشت کارشناس تقریباً یکسان است: سهم
«کیفیت محصول» بین ۱۲٫۱٪ و ۱۷٫۳٪ و سهم «وصول مطالبات» بین ۱۲٫۴٪ و ۱۷٫۶٪. یعنی
در این داده **کسی متخصص کیفیت یا متخصص وصول نیست**. اگر بنویسیم «این کار را به
REP-004 بدهید چون متخصص کیفیت است»، عددی پشتش نیست. پس نمی‌نویسیم — و همین را
روی صفحه اعلام می‌کنیم.

قاعدهٔ نهایی، به همین ترتیب:

    ۱. پیش‌فرض = کارشناس مالک مشتری. (اطمینان: بالا)
    ۲. اگر بار ۹۰ روزهٔ مالک بالای صدک ۷۵ باشد **و** کار از نوع پیگیری تلفنی
       عمومی باشد، سبک‌ترین کارشناس پیشنهاد می‌شود و دلیلش نوشته می‌شود.
       (اطمینان: متوسط — این یک انتخاب عملیاتی است، نه یافتهٔ داده)
    ۳. برای کار حساس (P1، یا پروندهٔ کیفی باز) هرگز از مالک عبور نمی‌کنیم؛
       تاریخچه نزد اوست.

فقط کارِ «تماسی» ارجاع‌پذیر است. جلسهٔ قیمت و بازدید حضوری در کارتابل مدیر
می‌ماند، چون تصمیم قیمت و تعهد تجاری کار مدیر فروش است.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from datetime import datetime, timezone

CACHE = Path(__file__).parent / "cache"
STATE = CACHE / "assignments.json"
_LOCK = threading.Lock()

REFERRABLE_KINDS = {"call"}          # فقط کار تماسی ارجاع می‌شود
SENSITIVE_PRIORITIES = {"P1"}        # از مالک عبور نمی‌کنیم

STATUS = ["ارجاع‌شده", "در دست اقدام", "گزارش ارسال شد", "بسته شد"]
STATUS_COLOR = {"ارجاع‌شده": "warning", "در دست اقدام": "neu",
                "گزارش ارسال شد": "good", "بسته شد": "muted"}

# ═══════════════ قالب گزارش کارشناس — چه چیزهایی باید ذکر شود
REPORT_FIELDS = [
    {"key": "outcome", "label": "نتیجهٔ تماس", "type": "choice", "required": True,
     "options": ["برقرار شد و گفت‌وگو انجام شد", "پاسخ نداد",
                 "موکول شد به زمان دیگر", "شمارهٔ نادرست / تغییر مخاطب"],
     "hint": "یک گزینه — بدون توضیح اضافه"},
    {"key": "said", "label": "آنچه مشتری گفت", "type": "text", "required": True,
     "hint": "نقل قول کوتاه، نه تفسیر شما. دو خط کافی است."},
    {"key": "commitment", "label": "عدد یا تعهد گرفته‌شده", "type": "text",
     "required": True,
     "hint": "مبلغ، تاریخ، تناژ. اگر تعهدی گرفته نشد بنویسید «تعهدی گرفته نشد»."},
    {"key": "blocker", "label": "مانع باقی‌مانده", "type": "text", "required": True,
     "hint": "چه چیزی نگذاشت کار بسته شود — یک جمله."},
    {"key": "recommend", "label": "تصمیم پیشنهادی به مدیر", "type": "choice",
     "required": True,
     "options": ["مشکل حل شد — پرونده بسته شود",
                 "پیگیری مجدد در تاریخ مشخص",
                 "نیاز به تصمیم مدیر فروش (قیمت / شرایط پرداخت)",
                 "نیاز به جلسهٔ حضوری",
                 "ارجاع به واحد دیگر"],
     "hint": "تصمیم را شما پیشنهاد بدهید؛ مدیر تأیید یا تغییر می‌دهد"},
    {"key": "next_date", "label": "تاریخ پیگیری بعدی", "type": "date",
     "required": False, "hint": "اگر پیگیری لازم است"},
]
REPORT_NOTE = ("گزارش بدون این پنج مورد ناقص است. هدف این نیست که خاطره بنویسید؛ "
               "هدف این است که مدیر فروش بدون تماس دوباره بتواند تصمیم بگیرد.")

DECISION_OPTIONS = [
    {"key": "closed", "label": "مشکل حل شد — بسته شود", "color": "good"},
    {"key": "recheck", "label": "هفتهٔ بعد دوباره چک شود", "color": "warning"},
    {"key": "manager", "label": "خودم پیگیری می‌کنم", "color": "neu"},
    {"key": "meeting", "label": "جلسهٔ حضوری بگذاریم", "color": "neu"},
    {"key": "escalate", "label": "ارجاع به کمیتهٔ اعتباری / کیفیت", "color": "critical"},
]

SPECIALISATION_NOTE = (
    "تخصص کارشناسان در این داده قابل اندازه‌گیری نیست: سهم «کیفیت محصول» در هر هشت "
    "کارشناس بین ۱۲٫۱٪ و ۱۷٫۳٪ و سهم «وصول مطالبات» بین ۱۲٫۴٪ و ۱۷٫۶٪ است. پس "
    "پیشنهاد ما بر پایهٔ **مالکیت و بار کاری** است، نه تخصص ساختگی.")


# ═════════════════════════════════════════════ روستر کارشناسان
def build_experts(profiles: dict[str, dict], worklist: dict,
                  as_of: str | None = None) -> list[dict]:
    """روستر کارشناسان را از خود داده می‌سازد: مالکیت، بار ۹۰ روزه، بار کارتابل."""
    rows = worklist.get("rows") or []
    prio = {r["customer_id"]: r for r in rows}
    cut = ""
    if as_of:
        from datetime import date, timedelta
        y, m, d = (int(v) for v in str(as_of)[:10].split("-"))
        cut = str(date(y, m, d) - timedelta(days=90))
    agg: dict[str, dict] = {}
    for cid, p in profiles.items():
        rep = (p.get("identity") or {}).get("sales_rep_id")
        if not rep:
            continue
        a = agg.setdefault(rep, {"expert_id": rep, "customers": 0, "recent": 0,
                                 "pending": 0, "worklist": 0, "p1": 0, "revenue": 0.0,
                                 "open_complaints": 0})
        a["customers"] += 1
        a["revenue"] += float((p["commercial"] or {}).get("revenue_nominal") or 0)
        eng = p.get("engagement") or {}
        a["recent"] += sum(1 for it in (eng.get("items") or [])
                           if not cut or str(it.get("date") or "") >= cut)
        a["pending"] += sum(int(v) for v in (eng.get("open_next_actions") or {}).values())
        a["open_complaints"] += int((p.get("complaints") or {}).get("open") or 0)
        r = prio.get(cid)
        if r:
            a["worklist"] += 1
            if r.get("priority") == "P1":
                a["p1"] += 1
    out = sorted(agg.values(), key=lambda x: x["expert_id"])
    if out:
        loads = sorted(x["recent"] for x in out)
        q75 = loads[int(len(loads) * 0.75) - 1] if len(loads) > 3 else max(loads)
        for x in out:
            x["revenue"] = round(x["revenue"])
            x["busy"] = bool(x["recent"] > q75)
            x["load_label"] = ("پرکار" if x["recent"] > q75 else
                               "سبک" if x["recent"] <= loads[max(len(loads) // 4 - 1, 0)]
                               else "متعادل")
            x["name"] = f"کارشناس {x['expert_id'].replace('REP-', '')}"
    return out


def _q75(experts: list[dict]) -> int:
    loads = sorted(x["recent"] for x in experts)
    return loads[int(len(loads) * 0.75) - 1] if len(loads) > 3 else (max(loads) if loads else 0)


def suggest_expert(row: dict, owner_rep: str | None, experts: list[dict]) -> dict:
    """پیشنهاد کارشناس با دلیل داده‌محور و درجهٔ اطمینان."""
    by = {e["expert_id"]: e for e in experts}
    owner = by.get(owner_rep or "")
    alts = []
    if not owner:
        pick = min(experts, key=lambda e: e["recent"]) if experts else None
        return {"expert_id": pick["expert_id"] if pick else None,
                "reason": "کارشناس مالکی برای این مشتری ثبت نشده؛ سبک‌ترین کارتابل انتخاب شد",
                "confidence": "پایین", "alternatives": [], "rule": "fallback"}

    q75 = _q75(experts)
    lightest = min(experts, key=lambda e: e["recent"])
    sensitive = (row.get("priority") in SENSITIVE_PRIORITIES
                 or int(row.get("open_complaints") or 0) > 0)

    if owner["recent"] > q75 and not sensitive:
        alts = [{"expert_id": owner["expert_id"],
                 "why": f"مالک مشتری — اما {owner['recent']} تعامل در ۹۰ روز اخیر دارد"}]
        return {
            "expert_id": lightest["expert_id"],
            "reason": (f"کارشناس مالک ({owner['expert_id']}) با {owner['recent']} تعامل "
                       f"در ۹۰ روز اخیر بالای صدک ۷۵ بار کاری است؛ این کار "
                       f"{row.get('priority', 'P3')} و از نوع تماس عمومی است، پس "
                       f"{lightest['expert_id']} با {lightest['recent']} تعامل "
                       "سبک‌ترین کارتابل را دارد"),
            "confidence": "متوسط", "alternatives": alts, "rule": "load_balance"}

    if sensitive:
        why = ("پروندهٔ کیفی باز دارد" if int(row.get("open_complaints") or 0) > 0
               else "اولویت P1 است")
        reason = (f"کارشناس مالک این مشتری است و تمام "
                  f"تاریخچهٔ تعامل نزد اوست؛ چون این پرونده {why}، از مالک عبور "
                  "نمی‌کنیم")
    else:
        reason = (f"کارشناس مالک این مشتری است — در این شرکت **هر ۴٬۱۸۴ تعامل CRM "
                  f"را کارشناس مالک ثبت کرده** و بار او ({owner['recent']} تعامل در "
                  "۹۰ روز) زیر آستانه است")
    if lightest["expert_id"] != owner["expert_id"]:
        alts = [{"expert_id": lightest["expert_id"],
                 "why": f"سبک‌ترین کارتابل ({lightest['recent']} تعامل در ۹۰ روز) — "
                        "اگر مالک در دسترس نیست"}]
    return {"expert_id": owner["expert_id"], "reason": reason,
            "confidence": "بالا", "alternatives": alts, "rule": "owner"}


def referrable(row: dict) -> bool:
    return (row.get("channel_kind") in REFERRABLE_KINDS)


# ═════════════════════════════════════════════ حالت ماندگار
def _now() -> str:
    """زمان ثبت به تقویم جلالی — همان تقویمی که کل داشبورد با آن کار می‌کند."""
    t = datetime.now(timezone.utc).astimezone()
    try:
        import jalali
        return f"{jalali.fmt(t.date())} ساعت {t:%H:%M}"
    except Exception:
        return t.strftime("%Y-%m-%d %H:%M")


def _fa_date(iso: str | None) -> str:
    """ورودی تاریخ HTML میلادی می‌دهد؛ کل داشبورد جلالی است."""
    s = str(iso or "").strip()
    if len(s) < 10:
        return s
    try:
        import datetime as _dt

        import jalali
        return jalali.fmt(_dt.date.fromisoformat(s[:10]))
    except Exception:
        return s


REPORT_TITLE = "گزارش کارشناس به مدیر فروش"


def report_file(ref: dict) -> str:
    """گزارش را به یک فایل متنی قابل دانلود تبدیل می‌کند — همان فیلدهای الزامی."""
    r = ref.get("report") or {}
    L = [f"# {REPORT_TITLE}", "",
         f"- شناسهٔ ارجاع: {ref['id']}",
         f"- مشتری: {ref['customer_id']}  ({ref.get('who', '')})",
         f"- اولویت: {ref.get('priority_fa', '')}",
         f"- نوع کار: {ref.get('work_type', '')} — کانال {ref.get('channel', '')}",
         f"- کارشناس: {ref['expert_id']}",
         f"- ارجاع در: {ref.get('created_at', '')}",
         f"- ثبت گزارش در: {r.get('submitted_at', '—')}", "",
         f"## هدف ارجاع", ref.get("goal", "—"), "",
         "## گزارش"]
    for f in REPORT_FIELDS:
        L += [f"**{f['label']}:** {r.get(f['key']) or '—'}"]
    d = ref.get("decision")
    L += ["", "## تصمیم مدیر فروش",
          (f"{d['label']}" + (f" — تاریخ {d['date']}" if d.get("date") else "")
           + (f"\n\n{d['note']}" if d.get("note") else "") + f"\n\nثبت در {d['at']}")
          if d else "هنوز ثبت نشده."]
    if ref.get("manager_note"):
        L += ["", "## یادداشت مدیر هنگام ارجاع", ref["manager_note"]]
    return "\n".join(L) + "\n"


def get(rid: str) -> dict | None:
    return _find(load(), rid)


def _blank() -> dict:
    return {"referrals": [], "seq": 0}


def load() -> dict:
    with _LOCK:
        if STATE.exists():
            try:
                return json.loads(STATE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return _blank()


def _save(st: dict) -> None:
    CACHE.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


IMPORTANCE = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}


def create(row: dict, expert_id: str, suggestion: dict, note: str = "") -> dict:
    """ارجاع تازه از کارتابل مدیر به کارتابل کارشناس."""
    st = load()
    st["seq"] += 1
    ref = {
        "id": f"ARJ-{st['seq']:04d}",
        "customer_id": row["customer_id"],
        "created_at": _now(),
        "expert_id": expert_id,
        "suggested_expert": suggestion.get("expert_id"),
        "suggestion_reason": suggestion.get("reason", ""),
        "suggestion_confidence": suggestion.get("confidence", ""),
        "overridden": bool(expert_id != suggestion.get("expert_id")),
        "work_type": row.get("family", ""),
        "channel": row.get("channel", ""),
        "channel_kind": row.get("channel_kind", ""),
        "channel_why": row.get("channel_why", ""),
        "goal": row.get("goal", ""),
        "goal_amount": row.get("goal_amount"),
        "now": row.get("now", ""),
        "tasks": (row.get("tasks") or [])[:4],
        "priority": row.get("priority", "P3"),
        "priority_fa": row.get("priority_fa", ""),
        "who": row.get("who", ""),
        "value_at_play": row.get("value_at_play"),
        "agenda": row.get("agenda") or {},
        "manager_note": note,
        "status": "ارجاع‌شده",
        "report": None, "decision": None,
    }
    st["referrals"].append(ref)
    with _LOCK:
        _save(st)
    return ref


def _find(st: dict, rid: str) -> dict | None:
    return next((r for r in st["referrals"] if r["id"] == rid), None)


def submit_report(rid: str, report: dict) -> dict | None:
    st = load()
    r = _find(st, rid)
    if not r:
        return None
    missing = [f["label"] for f in REPORT_FIELDS
               if f["required"] and not str(report.get(f["key"]) or "").strip()]
    if missing:
        return {"error": "موارد الزامی گزارش تکمیل نشده: " + "، ".join(missing)}
    report["submitted_at"] = _now()
    report["next_date"] = _fa_date(report.get("next_date"))
    r["report"] = report
    r["status"] = "گزارش ارسال شد"
    with _LOCK:
        _save(st)
    return r


def set_status(rid: str, status: str) -> dict | None:
    st = load()
    r = _find(st, rid)
    if not r or status not in STATUS:
        return None
    r["status"] = status
    with _LOCK:
        _save(st)
    return r


def decide(rid: str, key: str, note: str = "", date: str = "") -> dict | None:
    st = load()
    r = _find(st, rid)
    if not r:
        return None
    opt = next((o for o in DECISION_OPTIONS if o["key"] == key), None)
    if not opt:
        return None
    r["decision"] = {"key": key, "label": opt["label"], "color": opt["color"],
                     "note": note, "date": _fa_date(date), "at": _now()}
    r["status"] = "بسته شد" if key == "closed" else "در دست اقدام"
    with _LOCK:
        _save(st)
    return r


def for_expert(expert_id: str) -> list[dict]:
    rows = [r for r in load()["referrals"] if r["expert_id"] == expert_id]
    rows.sort(key=lambda r: (r["status"] in ("بسته شد",),
                             IMPORTANCE.get(r["priority"], 3),
                             -float(r.get("value_at_play") or 0)))
    return rows


def all_referrals() -> list[dict]:
    rows = list(load()["referrals"])
    rows.sort(key=lambda r: (r["status"] == "بسته شد",
                             0 if r["status"] == "گزارش ارسال شد" else 1,
                             IMPORTANCE.get(r["priority"], 3),
                             -float(r.get("value_at_play") or 0)))
    return rows


def summary() -> dict:
    rows = load()["referrals"]
    by_status = {s: sum(1 for r in rows if r["status"] == s) for s in STATUS}
    return {"total": len(rows), "by_status": by_status,
            "awaiting_decision": sum(1 for r in rows
                                     if r["status"] == "گزارش ارسال شد" and not r["decision"]),
            "open": sum(1 for r in rows if r["status"] != "بسته شد")}
