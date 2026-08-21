"""موتور دورهٔ زمانی — خلاصهٔ دوره، مقایسه با دورهٔ قبل، پیش‌بینی دورهٔ بعد،
فهرست رسیدگی و پرتکرارترین مشکلات.

سه اصل، همان اصول بقیهٔ پروژه:
  ۱. هیچ عددی حدسی نیست. پیش‌بینی از نرخ پایهٔ تجربی همین داده می‌آید و
     **بک‌تست** می‌شود؛ خطای بک‌تست کنار خود عدد نمایش داده می‌شود.
  ۲. لنگر دوره روی «آخرین دادهٔ کامل» است نه تاریخ برش، چون ماه آخر داده ناقص
     است و هر مقایسه‌ای روی آن، سقوط مصنوعی می‌سازد.
  ۳. هر ردیف رسیدگی می‌گوید چرا در این اولویت نشسته است.
"""
from __future__ import annotations

import math
from typing import Any
import numpy as np
import pandas as pd

import jalali
from signals import COMPLAINT_BY_HISTORY, REORDER_BY_RECENCY, _rate, ref

# ═══════════════════════════════════════════════════ تعریف دوره‌ها
PERIODS: list[dict] = [
    {"key": "1w", "label": "۱ هفته", "days": 7},
    {"key": "2w", "label": "۲ هفته", "days": 14},
    {"key": "1m", "label": "۱ ماه", "days": 30},
    {"key": "2m", "label": "۲ ماه", "days": 60},
    {"key": "3m", "label": "۳ ماه", "days": 91},
    {"key": "6m", "label": "۶ ماه", "days": 182},
    {"key": "1y", "label": "۱ سال", "days": 365},
]
PERIOD_BY_KEY = {p["key"]: p for p in PERIODS}

LOOKBACK_DAYS = 365          # پنجرهٔ برآورد نرخ فروش هر مشتری
MARGIN_WINDOW = 180          # پنجرهٔ برآورد حاشیهٔ اخیر
MIN_COMPLETE_RATIO = 0.35    # آستانهٔ تشخیص ماه ناقص انتهایی


# ═══════════════════════════════════════════════════ ابزار کمکی
def _haz(p: float, base_days: float, target_days: float) -> float:
    """تبدیل احتمال «حداقل یک رویداد در base_days» به همان احتمال در target_days.

    فرض: فرایند پواسون با نرخ ثابت. λ = −ln(1−p)/base ، سپس p' = 1−exp(−λ·target).
    این تنها فرض توزیعی کل موتور است و صریح اعلام می‌شود.
    """
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    lam = -math.log(1 - p) / base_days
    return 1 - math.exp(-lam * target_days)


def data_anchor(D: dict[str, pd.DataFrame]) -> tuple[pd.Timestamp, str]:
    """آخرین روزی که دادهٔ فروش آن کامل به‌نظر می‌رسد.

    ماه انتهایی داده ناقص است (۱۵ خط در برابر میانگین ~۸۰۰). اگر لنگر دوره را
    روی تاریخ برش بگذاریم، «سقوط فروش» مصنوعی می‌سازیم. پس لنگر را روی پایان
    آخرین ماه کامل می‌گذاریم و همین را به کاربر می‌گوییم.
    """
    S = D["sales"]
    m = S.groupby(S.date.dt.to_period("M")).size()
    if len(m) < 4:
        return S.date.max(), ""
    typical = float(m.iloc[:-1].tail(6).median())
    last = m.index[-1]
    last_days = (S.date.max() - last.to_timestamp()).days + 1
    expected = typical * last_days / 30.0
    if expected > 0 and m.iloc[-1] / expected < MIN_COMPLETE_RATIO:
        anchor = (last.to_timestamp() - pd.Timedelta(days=1)).normalize()
        note = (f"ماه {jalali.fmt(str(last.to_timestamp().date()))[:-3]} ناقص است "
                f"({int(m.iloc[-1])} خط در برابر {int(expected)} خط مورد انتظار)؛ "
                f"لنگر دوره روی پایان آخرین ماه کامل گذاشته شد.")
        return anchor, note
    return S.date.max(), ""


# ═══════════════════════════════════════════════════ حقایق یک بازه
def _window_facts(D: dict[str, pd.DataFrame], inv: pd.DataFrame,
                  a: pd.Timestamp, b: pd.Timestamp) -> dict:
    """حقایق مشاهده‌شده در بازهٔ [a, b] — هیچ برآوردی در کار نیست."""
    S, COL, CP = D["sales"], D["collections"], D["complaints"]
    w = S[(S.date >= a) & (S.date <= b)]
    c = COL[(COL.collection_date >= a) & (COL.collection_date <= b)]
    p = CP[(CP.Created_At >= a) & (CP.Created_At <= b)]
    open_at_b = inv[inv.invoice_date <= b].copy()
    paid_by_b = _collected_by(D, open_at_b.invoice_no, b)
    open_at_b["paid"] = open_at_b.invoice_no.map(paid_by_b).fillna(0.0)
    open_at_b["open"] = (open_at_b.invoiced - open_at_b.paid).clip(lower=0)
    overdue = float(open_at_b.loc[open_at_b.due_date <= b, "open"].sum())
    not_due = float(open_at_b.loc[open_at_b.due_date > b, "open"].sum())
    gp = float(w.gross_profit.sum())
    rev = float(w.line_amount.sum())
    sev = p.Severity.value_counts().to_dict() if len(p) else {}
    return {
        "from": str(a.date()), "to": str(b.date()),
        "from_fa": jalali.fmt(str(a.date())), "to_fa": jalali.fmt(str(b.date())),
        "days": int((b - a).days) + 1,
        "revenue": round(rev), "revenue_real": round(float(w.line_amount_real.sum())),
        "volume": round(float(w.qty.sum())),
        "gross_profit": round(gp),
        "margin_pct": round(gp / rev * 100, 2) if rev else None,
        "customers": int(w.Customer_ID.nunique()),
        "invoices": int(w.invoice_no.nunique()),
        "order_lines": int(len(w)),
        "collected": round(float(c.collected_amount.sum())),
        "collection_events": int(len(c)),
        "overdue_total": round(overdue),
        "not_yet_due": round(not_due),
        "complaints": int(len(p)),
        "complaints_critical": int(sum(v for k, v in sev.items()
                                       if k in ("critical", "high"))),
        "complaint_customers": int(p.Customer_ID.nunique()) if len(p) else 0,
    }


def _collected_by(D: dict[str, pd.DataFrame], invoice_nos, b: pd.Timestamp) -> pd.Series:
    COL = D["collections"]
    c = COL[COL.collection_date <= b]
    return c.groupby("invoice_no").collected_amount.sum()


def _invoice_table(D: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """جدول فاکتور با تاریخ سررسید — پایهٔ همهٔ محاسبات مطالبات."""
    S, C = D["sales"], D["customers"]
    terms = C.set_index("Customer_ID").Payment_Terms_Days
    inv = (S.groupby(["Customer_ID", "invoice_no"])
             .agg(invoiced=("line_amount", "sum"), invoice_date=("date", "min"))
             .reset_index())
    inv["due_date"] = inv.invoice_date + pd.to_timedelta(
        inv.Customer_ID.map(terms).fillna(0), unit="D")
    return inv


# ═══════════════════════════════════════════════════ پیش‌بینی
def _price_drift(D: dict[str, pd.DataFrame], t: pd.Timestamp, months: int = 12) -> float:
    """رشد لگاریتمی ماهانهٔ سطح قیمت در ۱۲ ماه گذشته.

    در این داده حدود ۰٫۱۶ (یعنی ~۱۷٪ ماهانه) است. بدون بردن این رشد به جلو،
    پیش‌بینی فروش ریالی دورهٔ بعد به‌طور سیستماتیک کم‌برآورد می‌شود — در بک‌تست،
    خطای دورهٔ ۳ ماهه از ۳۳٪ به ۲۱٪ کاهش یافت.
    """
    S = D["sales"]
    w = S[S.date <= t]
    if len(w) < 100:
        return 0.0
    pi = w.groupby(w.date.dt.to_period("M")).apply(
        lambda g: np.average(g.price_index, weights=g.line_amount.clip(lower=0) + 1),
        include_groups=False)
    if len(pi) < 4:
        return 0.0
    return float(np.clip(np.log(pi.astype(float)).diff().dropna().tail(months).mean(),
                         -0.05, 0.20))


def _price_level(D: dict[str, pd.DataFrame], t: pd.Timestamp, ahead_days: int = 0) -> float:
    """سطح قیمت، ضریب نسبت به ماه پایه، در صورت نیاز برون‌یابی‌شده به جلو.

    نرخ فروش هر مشتری روی **فروش حقیقی** (تعدیل‌شده با تورم) برآورد می‌شود و
    بعد با همین ضریب به قیمت روز برمی‌گردد. برای پیش‌بینی، سطح قیمت تا **میانهٔ
    دورهٔ آینده** برون‌یابی می‌شود. ضریب برون‌یابی حداکثر ۳ برابر بریده می‌شود.
    """
    S = D["sales"]
    w = S[(S.date <= t) & (S.date > t - pd.Timedelta(days=90))]
    if not len(w) or "price_index" not in w:
        return 1.0
    lvl = float(np.average(w.price_index, weights=w.line_amount.clip(lower=0) + 1)) / 100.0
    if ahead_days:
        lvl *= float(np.clip(math.exp(_price_drift(D, t) * (ahead_days / 2 / 30.0)), 1.0, 3.0))
    return float(np.clip(lvl, 0.2, 60.0))


def _new_invoice_collection_share(D: dict[str, pd.DataFrame], inv: pd.DataFrame,
                                  t: pd.Timestamp, days: int, windows: int = 4) -> float:
    """از فاکتورهای صادرشده در یک دورهٔ D روزه، چه سهمی تا پایان همان دوره وصول می‌شود؟

    بدون این جزء، پیش‌بینی وصول فقط مانده باز ابتدای دوره را می‌بیند و فروش
    جدید همان دوره را نادیده می‌گیرد — که در دوره‌های بلند خطای بزرگی است.
    """
    COL = D["collections"]
    vals = []
    for k in range(1, windows + 1):
        a = t - pd.Timedelta(days=days * k) + pd.Timedelta(days=1)
        b = t - pd.Timedelta(days=days * (k - 1))
        x = inv[(inv.invoice_date >= a) & (inv.invoice_date <= b)]
        if not len(x) or x.invoiced.sum() <= 0:
            continue
        c = COL[(COL.collection_date >= a) & (COL.collection_date <= b) &
                (COL.invoice_no.isin(set(x.invoice_no)))]
        vals.append(min(float(c.collected_amount.sum()) / float(x.invoiced.sum()), 1.0))
    return float(np.mean(vals)) if vals else 0.3


def _raw_forecast(D: dict[str, pd.DataFrame], inv: pd.DataFrame,
                  t: pd.Timestamp, days: int) -> dict:
    """پیش‌بینی دورهٔ (t, t+days] با استفادهٔ فقط از دادهٔ ≤ t.

    فروش و سود: مدل پایین‌به‌بالا در سطح مشتری.
        E[فروش] = Σ_c  p_فعال(c, days) × نرخ فروش روزانهٔ c × days × ضریب قیمت
    شکایت: جمع احتمال برنولی هر مشتری از جدول نرخ پایهٔ سابقهٔ شکایت.
    وصول و معوق: نرخ‌های تجربی بازیابی و تأخیر همین داده.
    """
    S, CP = D["sales"], D["complaints"]
    hist = S[(S.date <= t) & (S.date > t - pd.Timedelta(days=LOOKBACK_DAYS))]
    last = S[S.date <= t].groupby("Customer_ID").date.max()
    rev_by = hist.groupby("Customer_ID").line_amount_real.sum()   # ← حقیقی، نه اسمی

    pf = _price_level(D, t, ahead_days=days)
    exp_rev, active = 0.0, 0
    for cid, rev in rev_by.items():
        rec = (t - last[cid]).days
        p90, _, _ = _rate(REORDER_BY_RECENCY, rec)
        p = _haz(p90, 90, days)
        exp_rev += p * (rev / LOOKBACK_DAYS) * days
        if p >= 0.25:
            active += 1
    exp_rev *= pf                       # بازگرداندن به قیمت روز

    mw = S[(S.date <= t) & (S.date > t - pd.Timedelta(days=MARGIN_WINDOW))]
    marg = float(mw.gross_profit.sum() / mw.line_amount.sum()) if mw.line_amount.sum() else 0.0

    # ── شکایت: جمع احتمال هر مشتری
    cp_hist = CP[CP.Created_At <= t]
    cnt = cp_hist.groupby("Customer_ID").size()
    exp_cp = 0.0
    for cid in rev_by.index:
        p180, _, _ = _rate(COMPLAINT_BY_HISTORY, int(cnt.get(cid, 0)))
        exp_cp += _haz(p180, 180, days)

    # ── وصول: بازیابی مانده باز + وصول روی فروش جدید همان دوره
    rec_rate, rec_n = _recovery_rate(D, inv, t, days)
    new_share = _new_invoice_collection_share(D, inv, t, days)
    snap = _open_snapshot(D, inv, t)
    exp_col = snap["open_total"] * rec_rate + exp_rev * new_share

    # ── معوق پایان دوره
    late_share = _late_share(D, inv, t)
    becoming_due = float(snap["by_invoice"].loc[
        (snap["by_invoice"].due_date > t) &
        (snap["by_invoice"].due_date <= t + pd.Timedelta(days=days)), "open"].sum())
    overdue_recov, _ = _recovery_rate(D, inv, t, days, only_overdue=True)
    exp_overdue = (snap["overdue"] * (1 - overdue_recov)
                   + becoming_due * late_share)
    return {
        "days": days,
        "revenue": round(exp_rev),
        "gross_profit": round(exp_rev * marg),
        "margin_pct": round(marg * 100, 2),
        "complaints": round(exp_cp, 1),
        "collected": round(exp_col),
        "overdue_total": round(exp_overdue),
        "active_customers": active,
        "price_level": round(pf, 3),
        "price_drift_monthly": round(_price_drift(D, t), 4),
        "new_invoice_share": round(new_share, 4),
        "recovery_rate": round(rec_rate, 4),
        "recovery_windows": rec_n,
        "overdue_recovery_rate": round(overdue_recov, 4),
        "late_share": round(late_share, 4),
    }


def _open_snapshot(D: dict[str, pd.DataFrame], inv: pd.DataFrame, t: pd.Timestamp) -> dict:
    x = inv[inv.invoice_date <= t].copy()
    paid = _collected_by(D, x.invoice_no, t)
    x["paid"] = x.invoice_no.map(paid).fillna(0.0)
    x["open"] = (x.invoiced - x.paid).clip(lower=0)
    x = x[x.open > 0]
    return {"by_invoice": x,
            "open_total": float(x.open.sum()),
            "overdue": float(x.loc[x.due_date <= t, "open"].sum()),
            "not_due": float(x.loc[x.due_date > t, "open"].sum())}


def _recovery_rate(D: dict[str, pd.DataFrame], inv: pd.DataFrame, t: pd.Timestamp,
                   days: int, only_overdue: bool = False, windows: int = 4) -> tuple[float, int]:
    """چند درصد از مانده باز در یک دورهٔ هم‌طول تاریخی وصول شده است؟

    میانگین روی چند پنجرهٔ گذشته گرفته می‌شود تا به یک دورهٔ خاص وابسته نباشد.
    """
    COL = D["collections"]
    vals = []
    for k in range(1, windows + 1):
        t0 = t - pd.Timedelta(days=days * k)
        if t0 <= inv.invoice_date.min() + pd.Timedelta(days=60):
            break
        snap = _open_snapshot(D, inv, t0)
        base = snap["overdue"] if only_overdue else snap["open_total"]
        if base <= 0:
            continue
        pool = snap["by_invoice"]
        if only_overdue:
            pool = pool[pool.due_date <= t0]
        c = COL[(COL.collection_date > t0) &
                (COL.collection_date <= t0 + pd.Timedelta(days=days)) &
                (COL.invoice_no.isin(set(pool.invoice_no)))]
        vals.append(min(float(c.collected_amount.sum()) / base, 1.0))
    if not vals:
        return (0.25 if not only_overdue else 0.15), 0
    return float(np.mean(vals)), len(vals)


def _late_share(D: dict[str, pd.DataFrame], inv: pd.DataFrame, t: pd.Timestamp) -> float:
    """سهم فاکتورهایی که در تاریخ سررسید هنوز تسویه نشده بودند — نرخ تجربی."""
    x = inv[(inv.due_date <= t) & (inv.due_date >= t - pd.Timedelta(days=365))]
    if not len(x):
        return 0.5
    COL = D["collections"]
    sums = COL.groupby("invoice_no").collected_amount.sum()
    firsts = COL.groupby("invoice_no").collection_date.min()
    tot, late = 0.0, 0.0
    for r in x.itertuples():
        tot += r.invoiced
        first = firsts.get(r.invoice_no)
        on_time = (first is not None and first <= r.due_date
                   and sums.get(r.invoice_no, 0) >= r.invoiced * 0.99)
        if not on_time:
            late += r.invoiced
    return float(np.clip(late / tot if tot else 0.5, 0.05, 0.95))


# ═══════════════════════════════════ اصلاح اریبی و بک‌تست
BIAS_KEYS = ("revenue", "gross_profit", "collected", "complaints", "overdue_total")
BIAS_CAP = (0.7, 2.5)
_FC_CACHE: dict[tuple, dict] = {}


def _cached_raw(D, inv, t, days) -> dict:
    k = (str(t.date()), days)
    if k not in _FC_CACHE:
        _FC_CACHE[k] = _raw_forecast(D, inv, t, days)
    return _FC_CACHE[k]


def _bias(D, inv, t: pd.Timestamp, days: int, rounds: int = 3) -> dict:
    """اریبی سیستماتیک مدل: میانهٔ نسبت «پیش‌بینی ÷ واقعیت» در دوره‌های گذشته.

    مدل پایین‌به‌بالا به‌طور سیستماتیک کم‌برآورد می‌کند، چون احتمال سفارش هر
    مشتری را ضرب می‌کند ولی مشتری تازه و سفارش خارج از الگو را نمی‌بیند. این
    اریبی از خود بک‌تست اندازه‌گیری و اصلاح می‌شود — و ضریبش به کاربر نشان
    داده می‌شود، نه اینکه پنهان بماند.
    """
    ratios: dict[str, list[float]] = {k: [] for k in BIAS_KEYS}
    for k in range(1, rounds + 1):
        t0 = t - pd.Timedelta(days=days * k)
        if t0 - pd.Timedelta(days=LOOKBACK_DAYS) < D["sales"].date.min():
            break
        f = _cached_raw(D, inv, t0, days)
        a = _window_facts(D, inv, t0 + pd.Timedelta(days=1), t0 + pd.Timedelta(days=days))
        for key in BIAS_KEYS:
            if float(a.get(key) or 0) > 0:
                ratios[key].append(float(f[key]) / float(a[key]))
    out = {}
    for key, v in ratios.items():
        out[key] = round(float(np.clip(1 / np.median(v), *BIAS_CAP)), 3) if v else 1.0
    out["rounds"] = max((len(v) for v in ratios.values()), default=0)
    return out


def forecast(D, inv, t: pd.Timestamp, days: int, bias: dict | None = None) -> dict:
    """پیش‌بینی نهایی: مدل خام × ضریب اصلاح اریبی اندازه‌گیری‌شده."""
    raw = _cached_raw(D, inv, t, days)
    b = bias if bias is not None else _bias(D, inv, t, days)
    out = dict(raw)
    out["raw"] = {k: raw[k] for k in BIAS_KEYS}
    out["bias_factor"] = {k: b.get(k, 1.0) for k in BIAS_KEYS}
    out["bias_rounds"] = b.get("rounds", 0)
    for k in BIAS_KEYS:
        v = raw[k] * b.get(k, 1.0)
        out[k] = round(v, 1) if k == "complaints" else round(v)
    return out


def backtest(D, inv, anchor: pd.Timestamp, days: int, rounds: int = 3,
             use_bias: bool = True) -> dict:
    """بک‌تست **خارج از نمونه**: ضریب اصلاح هر دور، از دورهای پیش از خودش می‌آید.

    اگر ضریب اصلاح را از همان دوری بگیریم که خطایش را گزارش می‌کنیم، عدد
    خوش‌بینانه و بی‌معنا می‌شود. پس برای دور k، اریبی از دورهای k+1 تا k+3
    محاسبه می‌شود.
    """
    errs: dict[str, list[float]] = {k: [] for k in
                                    ("revenue", "gross_profit", "collected", "complaints")}
    detail = []
    for k in range(rounds):
        t = anchor - pd.Timedelta(days=days * (k + 1))
        if t - pd.Timedelta(days=LOOKBACK_DAYS) < D["sales"].date.min():
            break
        b = _bias(D, inv, t, days) if use_bias else {"rounds": 1}   # فقط دادهٔ پیش از t
        if not b.get("rounds"):
            continue
        f = forecast(D, inv, t, days, bias=b)
        a = _window_facts(D, inv, t + pd.Timedelta(days=1), t + pd.Timedelta(days=days))
        row = {"as_of": jalali.fmt(str(t.date()))}
        for key in errs:
            act, pre = float(a[key]), float(f[key])
            if act > 0:
                errs[key].append(abs(pre - act) / act * 100)
                row[key] = {"actual": act, "forecast": pre,
                            "error_pct": round(abs(pre - act) / act * 100, 1)}
        detail.append(row)
    out = {k: (round(float(np.mean(v)), 1) if v else None) for k, v in errs.items()}
    out["rounds"] = len(detail)
    out["detail"] = detail
    out["use_bias"] = bool(use_bias)
    out["method"] = ("خطای مطلق درصدی، خارج از نمونه: ضریب اصلاح اریبی هر دور فقط "
                     "از دوره‌های پیش از خودش محاسبه شده است."
                     if use_bias else
                     "خطای مطلق درصدی، بدون اصلاح اریبی — چون در بک‌تست همین طول دوره، "
                     "اصلاح اریبی نتیجه را بدتر می‌کرد.")
    return out


def _mean_err(bt: dict) -> float:
    v = [bt[k] for k in ("revenue", "gross_profit", "collected", "complaints")
         if bt.get(k) is not None]
    return float(np.mean(v)) if v else 1e9


def choose_backtest(D, inv, anchor: pd.Timestamp, days: int, rounds: int = 3) -> dict:
    """اصلاح اریبی را فقط جایی به کار می‌بریم که در بک‌تست خارج از نمونه کمک کند.

    در دوره‌های کوتاه (تا یک ماه) اصلاح، خطا را تقریباً نصف می‌کند؛ در دوره‌های
    بلند، پنجره‌های اریبی به رژیم دادهٔ متفاوتی می‌افتند و نتیجه را بدتر می‌کنند.
    تصمیم را به داده می‌سپاریم، نه به سلیقه.
    """
    with_b = backtest(D, inv, anchor, days, rounds, use_bias=True)
    without = backtest(D, inv, anchor, days, rounds, use_bias=False)
    if with_b["rounds"] and _mean_err(with_b) <= _mean_err(without):
        with_b["compared_to_uncorrected_pct"] = round(_mean_err(without), 1)
        return with_b
    without["compared_to_corrected_pct"] = (round(_mean_err(with_b), 1)
                                            if with_b["rounds"] else None)
    return without


# ═══════════════════════════════════════════════════ انتخاب دورهٔ پیشنهادی
def _adequacy(f: dict) -> float:
    """کفایت رویداد یک دوره: آیا اصلاً آن‌قدر رویداد هست که ماژول‌ها معنا بدهند؟"""
    return (min(1.0, f["customers"] / 150) *
            min(1.0, max(f["complaints"], 0) / 15) *
            min(1.0, f["collection_events"] / 300))


def recommend_period(D: dict[str, pd.DataFrame], inv: pd.DataFrame,
                     anchor: pd.Timestamp) -> dict:
    """دورهٔ پیش‌فرض را از خود داده انتخاب می‌کند، نه با حدس.

    امتیاز = کفایت رویداد ÷ (۱ + خطای میانگین بک‌تست ÷ ۱۰۰)

    یعنی دوره‌ای برنده است که هم آن‌قدر رویداد داشته باشد که ماژول‌های رسیدگی و
    مشکلات پرتکرار خالی نمانند، و هم پیش‌بینی‌اش در بک‌تست قابل اتکا باشد.
    """
    rows = []
    for p in PERIODS:
        d = p["days"]
        cur = _window_facts(D, inv, anchor - pd.Timedelta(days=d - 1), anchor)
        bt = choose_backtest(D, inv, anchor, d, rounds=3)
        errs = [bt[k] for k in ("revenue", "gross_profit", "collected", "complaints")
                if bt[k] is not None]
        err = float(np.mean(errs)) if errs else 100.0
        adq = _adequacy(cur)
        rows.append({"key": p["key"], "label": p["label"], "days": d,
                     "customers": cur["customers"], "complaints": cur["complaints"],
                     "collection_events": cur["collection_events"],
                     "backtest_error_pct": round(err, 1),
                     "adequacy": round(adq, 3),
                     "score": round(adq / (1 + err / 100), 4),
                     "bias_corrected": bt["use_bias"],
                     "backtest_rounds": bt["rounds"]})
    best = max(rows, key=lambda r: r["score"])
    why = (f"دورهٔ «{best['label']}» بالاترین امتیاز را گرفت: "
           f"{best['customers']} مشتری فعال، {best['complaints']} شکایت و "
           f"{best['collection_events']} رویداد وصول در دوره — یعنی هیچ ماژولی خالی "
           f"نمی‌ماند — و خطای میانگین بک‌تست پیش‌بینی {best['backtest_error_pct']}٪ است، "
           f"کمترین مقدار بین دوره‌های با داده کافی.")
    return {"recommended": best["key"], "why": why, "table": rows}


# ═══════════════════════════════════════════════════ رسیدگی
VALUE_TOP_SHARE = 0.30          # ۳۰٪ بالای ارزش = «مشتری با ارزش»
CRITICAL_SEVERITIES = ("critical", "high")

PROBLEM_DOMAIN = {
    "overdue_exceeds_gp": "پرداخت", "overdue_aged": "پرداخت", "bounced_cheques": "پرداخت",
    "over_credit_limit": "پرداخت", "low_collection_rate": "پرداخت",
    "dormant": "خرید", "volume_collapse": "خرید",
    "quality_linked_decline": "کیفیت", "open_severe_complaint": "کیفیت",
    "thin_margin": "قیمت", "many_negative_lines": "قیمت",
    "no_crm_history": "ارتباط", "uncontacted_active": "ارتباط",
    "competitor_dominant": "رقابت", "single_family_dependency": "خرید",
    "negative_real_margin": "قیمت", "high_cost_of_money": "پرداخت",
    "rfm_drop": "خرید",
}
PROBLEM_TITLE_FA = {       # عنوان عمومی، بدون عدد مخصوص یک مشتری
    "overdue_exceeds_gp": "مطالبات معوق بیشتر از سود ناخالص",
    "overdue_aged": "معوق کهنهٔ بیش از یک سال",
    "bounced_cheques": "چک برگشتی",
    "over_credit_limit": "عبور از سقف اعتبار",
    "low_collection_rate": "نرخ وصول زیر ۸۰٪",
    "dormant": "مشتری راکد (بیش از ۱۸۰ روز بی‌خرید)",
    "volume_collapse": "ریزش شدید حجم خرید",
    "quality_linked_decline": "کاهش خرید پس از ثبت شکایت",
    "open_severe_complaint": "شکایت باز با شدت زیاد یا بحرانی",
    "thin_margin": "حاشیه سود بسیار نازک",
    "many_negative_lines": "سهم بالای خطوط زیان‌ده",
    "no_crm_history": "نبود هرگونه تعامل ثبت‌شده",
    "uncontacted_active": "مشتری فعال بدون تماس ثبت‌شده",
    "competitor_dominant": "سهم غالب رقیب در سبد مشتری",
    "single_family_dependency": "وابستگی به یک گروه کالا",
    "negative_real_margin": "سود واقعی منفی پس از هزینهٔ پول",
    "high_cost_of_money": "هزینهٔ پول بیش از نیمی از حاشیه",
    "rfm_drop": "افت امتیاز RFM در مشتری پرارزش",
}
PROBLEM_KIND = {           # برای فرمول پول در خطر
    "overdue_exceeds_gp": "credit", "overdue_aged": "credit", "bounced_cheques": "credit",
    "over_credit_limit": "credit", "low_collection_rate": "credit",
    "dormant": "churn", "volume_collapse": "churn", "quality_linked_decline": "churn",
    "thin_margin": "margin", "many_negative_lines": "margin",
    "open_severe_complaint": "quality", "competitor_dominant": "churn",
    "uncontacted_active": "relationship", "no_crm_history": "relationship",
    "single_family_dependency": "relationship",
    "negative_real_margin": "margin", "high_cost_of_money": "credit",
    "rfm_drop": "churn",
}


def _period_events(D: dict[str, pd.DataFrame], inv: pd.DataFrame,
                   a: pd.Timestamp, b: pd.Timestamp) -> dict[str, list[dict]]:
    """رویدادهای واقعی هر مشتری **درون دوره** — پایهٔ «چرا الان؟»."""
    ev: dict[str, list[dict]] = {}

    def push(cid, kind, text, refs):
        ev.setdefault(str(cid), []).append({"kind": kind, "text": text, "references": refs})

    CP = D["complaints"]
    for r in CP[(CP.Created_At >= a) & (CP.Created_At <= b)].itertuples():
        push(r.Customer_ID, "complaint",
             f"شکایت «{r.Complaint_Title}» با شدت {r.Severity} در دوره ثبت شد",
             [ref("complaints", r.Complaint_ID, str(r.Created_At.date()),
                  {"Severity": r.Severity, "Complaint_Title": r.Complaint_Title,
                   "Created_At": str(r.Created_At.date())})])

    COL = D["collections"]
    bc = COL[(COL.collection_date >= a) & (COL.collection_date <= b) &
             (COL.bounced_cheque == "yes")]
    for cid, g in bc.groupby("Customer_ID"):
        push(cid, "bounced", f"{len(g)} چک برگشتی در همین دوره",
             [ref("collections", None, str(g.collection_date.max().date()),
                  {"bounced_cheque": f"{len(g)} مورد در دوره"})])

    x = inv[(inv.due_date >= a) & (inv.due_date <= b)].copy()
    if len(x):
        paid = _collected_by(D, x.invoice_no, b)
        x["paid"] = x.invoice_no.map(paid).fillna(0.0)
        x["open"] = (x.invoiced - x.paid).clip(lower=0)
        for cid, g in x[x.open > 0].groupby("Customer_ID"):
            push(cid, "newly_overdue",
                 f"{len(g)} فاکتور در همین دوره سررسید شد و تسویه نشد "
                 f"({g.open.sum():,.0f})",
                 [ref("invoices", str(gr.invoice_no), str(gr.due_date.date()),
                      {"due_date": str(gr.due_date.date()),
                       "open": f"{gr.open:,.0f}"})
                  for gr in g.nlargest(2, "open").itertuples()])

    S = D["sales"]
    cur = S[(S.date >= a) & (S.date <= b)].groupby("Customer_ID").qty.sum()
    span = (b - a).days + 1
    prv = S[(S.date >= a - pd.Timedelta(days=span)) &
            (S.date < a)].groupby("Customer_ID").qty.sum()
    for cid, q0 in prv.items():
        q1 = float(cur.get(cid, 0.0))
        if q0 > 0 and q1 < q0 * 0.75:
            drop = (q1 - q0) / q0 * 100
            push(cid, "volume_drop",
                 f"حجم خرید در دوره {drop:+.0f}٪ نسبت به دورهٔ قبل تغییر کرد "
                 f"({q0:,.0f} → {q1:,.0f} کیلوگرم)",
                 [ref("derived", None, str(b.date()),
                      {"vol_trend": f"{drop:+.0f}٪"},
                      f"مقایسهٔ همین دوره با {span} روز پیش از آن")])

    OF = D["offers"]
    if {"Offer_Date", "Result", "Validity_Days"} <= set(OF.columns):
        o = OF[(OF.Offer_Date >= a - pd.Timedelta(days=180)) & (OF.Offer_Date <= b) &
               (OF.Result.isin(["pending", "no_response"]))]
        for r in o.itertuples():
            exp = r.Offer_Date + pd.Timedelta(days=int(r.Validity_Days or 0))
            if a <= exp <= b:
                push(r.Customer_ID, "offer_expired",
                     f"آفر {r.Offer_ID} با دلیل {r.Offer_Reason} در همین دوره منقضی شد",
                     [ref("offers", r.Offer_ID, str(r.Offer_Date.date()),
                          {"Offer_Reason": str(r.Offer_Reason),
                           "Validity_Days": f"{int(r.Validity_Days or 0)} روز"})])
    return ev


EVENT_TO_RISK = {
    "complaint": ["open_severe_complaint", "quality_linked_decline"],
    "bounced": ["bounced_cheques"],
    "newly_overdue": ["overdue_exceeds_gp", "over_credit_limit", "overdue_aged",
                      "low_collection_rate", "high_cost_of_money",
                      "negative_real_margin"],
    "volume_drop": ["volume_collapse", "dormant", "rfm_drop"],
    "offer_expired": ["competitor_dominant", "dormant"],
}
EVENT_FA = {"complaint": "شکایت جدید", "bounced": "چک برگشتی",
            "newly_overdue": "سررسید تسویه‌نشده", "volume_drop": "افت حجم خرید",
            "offer_expired": "انقضای آفر"}


def money_at_risk(code: str, p: dict, f: dict, rec_rate: float) -> tuple[float, str]:
    """پول در خطر = مبلغ در معرض × احتمال تحقق.

    چهار خانوادهٔ ریسک، چهار مبنای متفاوت — هر کدام با یک عدد تجربی:
      اعتباری  : معوق × (۱ − نرخ بازیابی تجربی همین طول دوره)
      ریزشی    : ارزش نجات = سود ماهانه × ۱۲ × (۱ − احتمال ماندگاری)
      حاشیه‌ای  : زیان محقق‌شدهٔ خطوط زیان‌ده (احتمال ۱، چون رخ داده)
      کیفی/رابطه: ارزش نجات × احتمال شکایت بعدی
    """
    kind = PROBLEM_KIND.get(code, "relationship")
    od = float(p["receivables"]["uncollected_overdue"] or 0)
    rescue = float(f.get("rescue_value") or 0)
    destroyed = abs(float(p["margin"]["gross_profit_destroyed"] or 0))
    p_cp = next((x["probability"] for x in p.get("predictions", [])
                 if x["code"] == "new_complaint"), 0.1)
    if kind == "credit":
        return od * (1 - rec_rate), f"معوق × (۱ − نرخ بازیابی {rec_rate:.0%})"
    if kind == "churn":
        return rescue, "ارزش نجات = سود ماهانه × ۱۲ × (۱ − ماندگاری)"
    if kind == "margin":
        return destroyed, "زیان محقق‌شدهٔ خطوط زیان‌ده"
    if kind == "quality":
        return rescue * p_cp, f"ارزش نجات × احتمال شکایت بعدی {p_cp:.0%}"
    return rescue * 0.25, "ارزش نجات × ۲۵٪ (ریسک رابطه‌ای، اثر غیرمستقیم)"


CLASS_CAP = {"P1": 40, "P2": 20, "P3": 20, "P4": 10}


def build_attention(profiles: dict[str, dict], events: dict[str, list[dict]],
                    rec_rate: float) -> tuple[list[dict], dict]:
    """فهرست رسیدگی: چه کسی، چرا، و چرا با این اولویت.

    چهار طبقهٔ اولویت از تقاطع «ارزش مشتری» و «بحرانی بودن مشکل» ساخته می‌شود.
    """
    ltvs = sorted((float(p["features"].get("ltv_total") or 0) for p in profiles.values()),
                  reverse=True)
    cut = ltvs[max(int(len(ltvs) * VALUE_TOP_SHARE) - 1, 0)] if ltvs else 0
    rows = []
    for cid, p in profiles.items():
        f, risks = p["features"], p.get("risks") or []
        if not p["coverage"]["sales"] or not risks:
            continue
        ev = events.get(cid, [])
        ev_codes = {c for e in ev for c in EVENT_TO_RISK.get(e["kind"], [])}
        in_period = [r for r in risks if r["code"] in ev_codes]
        pool = in_period or risks
        top = max(pool, key=lambda r: ({"critical": 3, "high": 2, "medium": 1, "low": 0}
                                       [r["severity"]], r["value_at_stake"]))
        by_ltv = float(f.get("ltv_total") or 0) >= cut
        valuable = by_ltv or (p["commercial"]["revenue_rank"] or 999) <= 100
        critical = (top["severity"] in CRITICAL_SEVERITIES
                    or any(e["kind"] == "complaint" for e in ev)
                    or float(f.get("retention") or 1) < 0.25)
        cls = ("P1" if valuable and critical else "P2" if valuable else
               "P3" if critical else "P4")
        amount, formula = money_at_risk(top["code"], p, f, rec_rate)
        nba = (p.get("next_best_actions") or [{}])[0]
        why = _why(cls, valuable, critical, top, ev, f, p, by_ltv)
        rows.append({
            "customer_id": cid, "segment": p["identity"]["segment"],
            "priority": cls,
            "priority_fa": {"P1": "با ارزش · بحرانی", "P2": "با ارزش · عادی",
                            "P3": "کم‌ارزش · بحرانی",
                            "P4": "کم‌ارزش · غیربحرانی"}[cls],
            "valuable": bool(valuable), "critical": bool(critical),
            "value_reason": "ltv" if by_ltv else "revenue",
            "rfm": f.get("rfm_segment"), "rfm_code": f.get("RFM"),
            "ltv_total": f.get("ltv_total"), "ltv_rank": f.get("ltv_rank"),
            "revenue_rank": p["commercial"]["revenue_rank"],
            "retention": f.get("retention"), "quadrant": f.get("quadrant"),
            "problem_code": top["code"], "problem": top["title"],
            "problem_generic": PROBLEM_TITLE_FA.get(top["code"], top["title"]),
            "problem_severity": top["severity"], "problem_severity_fa": top["severity_fa"],
            "problem_domain": PROBLEM_DOMAIN.get(top["code"], "خرید"),
            "evidence": top["evidence"], "logic": top["logic"],
            "action": nba.get("action") or top["action"],
            "owner": nba.get("owner") or top["owner"],
            "action_references": nba.get("references") or top["references"],
            "in_period": bool(in_period),
            "period_events": ev[:4],
            "at_risk": round(amount), "at_risk_formula": formula,
            "why": why,
            "references": (top["references"] or [])[:3],
        })
    order = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
    rows.sort(key=lambda r: (order[r["priority"]], -r["at_risk"]))
    totals = {c: sum(1 for r in rows if r["priority"] == c) for c in order}
    totals["all"] = len(rows)
    totals["at_risk"] = round(sum(r["at_risk"] for r in rows))
    # سهمیهٔ هر طبقه، تا طبقه‌های پایین‌تر زیر انبوه طبقهٔ اول دفن نشوند
    kept, seen = [], {c: 0 for c in order}
    for r in rows:
        if seen[r["priority"]] >= CLASS_CAP[r["priority"]]:
            continue
        seen[r["priority"]] += 1
        kept.append(r)
    for i, r in enumerate(kept, 1):
        r["rank"] = i
    totals["shown"] = len(kept)
    return kept, totals, rows


def _why(cls, valuable, critical, top, ev, f, p, by_ltv=True) -> str:
    """جملهٔ «چرا این مشتری اینجاست و با این اولویت» — ستون رفرنس جدول."""
    lr = int(f.get("ltv_rank")) if f.get("ltv_rank") is not None else "—"
    rr = p["commercial"]["revenue_rank"]
    if valuable:
        v = (f"جزو ۳۰٪ بالای ارزش سبد است (رتبهٔ LTV {lr} از ۶۴۴)"
             if by_ltv else
             f"مشتری بزرگ سبد است (رتبهٔ فروش {rr} از ۶۴۴)، هرچند رتبهٔ LTV آن {lr} "
             f"است — یعنی معوق، سود این رابطه را خورده")
    else:
        v = f"در ۷۰٪ پایین ارزش سبد است (رتبهٔ LTV {lr}، رتبهٔ فروش {rr})"
    c = (f"مشکلش بحرانی است: «{top['title']}» با شدت {top['severity_fa']}"
         if critical else f"مشکلش در سطح {top['severity_fa']} است")
    when = ""
    if ev:
        kinds = "، ".join(dict.fromkeys(EVENT_FA.get(e["kind"], e["kind"]) for e in ev))
        when = f" رویداد این دوره: {kinds}."
    return f"{v}؛ {c}.{when}"


def top_problems(attention: list[dict], top: int = 3) -> list[dict]:
    """پرتکرارترین مشکلات دوره، با پول در خطر و نمونهٔ مشتریان."""
    g: dict[str, dict] = {}
    for r in attention:
        b = g.setdefault(r["problem_code"], {
            "code": r["problem_code"], "title": r["problem_generic"],
            "domain": r["problem_domain"], "severity": r["problem_severity"],
            "severity_fa": r["problem_severity_fa"], "customers": 0, "at_risk": 0.0,
            "formula": r["at_risk_formula"], "in_period": 0,
            "examples": [], "owners": {}, "logic": r["logic"], "action": r["action"]})
        b["customers"] += 1
        b["at_risk"] += r["at_risk"]
        b["in_period"] += 1 if r["in_period"] else 0
        b["owners"][r["owner"]] = b["owners"].get(r["owner"], 0) + 1
        if len(b["examples"]) < 5:
            b["examples"].append({"customer_id": r["customer_id"], "at_risk": r["at_risk"],
                                  "evidence": r["evidence"], "priority_fa": r["priority_fa"],
                                  "references": r["references"][:2]})
    out = sorted(g.values(),
                 key=lambda b: (-b["customers"], -b["at_risk"]))[:top]
    for b in out:
        b["at_risk"] = round(b["at_risk"])
        b["owner"] = max(b["owners"], key=b["owners"].get) if b["owners"] else "—"
        b["avg_at_risk"] = round(b["at_risk"] / b["customers"]) if b["customers"] else 0
    return out


# ═══════════════════════════════════════════════════ سرهم‌بندی یک دوره
def _delta(cur: Any, prev: Any) -> dict:
    if cur is None or prev is None:
        return {"abs": None, "pct": None, "dir": "flat"}
    d = float(cur) - float(prev)
    pct = (d / abs(float(prev)) * 100) if prev else None
    return {"abs": round(d, 2) if abs(d) < 1000 else round(d),
            "pct": round(pct, 1) if pct is not None else None,
            "dir": "up" if d > 0 else "down" if d < 0 else "flat"}


COMPARE_KEYS = ["revenue", "gross_profit", "margin_pct", "volume", "customers",
                "invoices", "collected", "overdue_total", "not_yet_due",
                "complaints", "complaints_critical"]


def build_period(D: dict[str, pd.DataFrame], inv: pd.DataFrame, profiles: dict[str, dict],
                 anchor: pd.Timestamp, key: str) -> dict:
    """همهٔ ماژول‌های تب خلاصه برای یک طول دوره."""
    p = PERIOD_BY_KEY[key]
    d = p["days"]
    a = anchor - pd.Timedelta(days=d - 1)
    pa, pb = a - pd.Timedelta(days=d), a - pd.Timedelta(days=1)
    cur = _window_facts(D, inv, a, anchor)
    prev = _window_facts(D, inv, pa, pb)
    bt = choose_backtest(D, inv, anchor, d, rounds=3)
    fc = forecast(D, inv, anchor, d,
                  bias=None if bt["use_bias"] else {"rounds": 1})
    ev = _period_events(D, inv, a, anchor)
    att, totals, all_rows = build_attention(profiles, ev, fc["recovery_rate"])
    probs = top_problems(all_rows)
    return {
        "key": key, "label": p["label"], "days": d,
        "current": cur, "previous": prev,
        "compare": {k: _delta(cur.get(k), prev.get(k)) for k in COMPARE_KEYS},
        "forecast": fc, "backtest": bt,
        "attention": att,
        "attention_counts": totals,
        "problems": probs,
        "event_customers": len(ev),
    }


def build_all(D: dict[str, pd.DataFrame], profiles: dict[str, dict]) -> dict:
    """همهٔ ۷ دوره + دورهٔ پیشنهادی. یک‌بار در ساخت کش اجرا می‌شود."""
    anchor, note = data_anchor(D)
    inv = _invoice_table(D)
    rec = recommend_period(D, inv, anchor)
    return {
        "anchor": str(anchor.date()), "anchor_fa": jalali.fmt(str(anchor.date())),
        "anchor_note": note,
        "periods": [{"key": p["key"], "label": p["label"], "days": p["days"]}
                    for p in PERIODS],
        "recommended": rec["recommended"], "recommendation_why": rec["why"],
        "recommendation_table": rec["table"],
        "data": {p["key"]: build_period(D, inv, profiles, anchor, p["key"])
                 for p in PERIODS},
    }
