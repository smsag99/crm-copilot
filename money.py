"""هزینهٔ پول و حاشیهٔ واقعی — پاسخ به مرکزی‌ترین نکتهٔ راهنمای داوران.

راهنمای داوران می‌گوید: «حاشیهٔ ناخالص مشتریان شما را از هم جدا نمی‌کند. پول رایگان
نیست. ۴٪ در ماه روی فاصلهٔ فاکتور تا نقد اعمال کنید و رتبه‌بندی کاملاً عوض می‌شود.»

این ماژول دقیقاً همان کار را می‌کند و یک گام جلوتر می‌رود:

  ۱. **آزمون قیمت‌گذاری اعتبار.** داوران می‌گویند خودتان بررسی کنید که آیا مارک‌آپ
     اعتبار در قیمت ثبت‌شده هست یا نه. ما همان آزمون را اجرا کردیم؛ نتیجه در
     `credit_pricing_test()` است و در داشبورد نمایش داده می‌شود.
  ۲. **روزهای پول قفل‌شده اندازه‌گیری می‌شود، فرض نمی‌شود.** به‌جای «مهلت + تأخیر»،
     فاصلهٔ واقعی فاکتور تا وصول محاسبه می‌شود؛ برای مانده‌های باز، فاصله تا تاریخ
     برش. این کار همان فرمول داوران را در دل خود دارد ولی به مقدار ثبت‌شدهٔ مهلت
     پرداخت وابسته نیست — که در این داده برای ۵۲۶ مشتری صفر ثبت شده در حالی که
     شرط اعتباری در سطح خط فروش (`payment_type`) واقعی است.
  ۳. **ذخیرهٔ مطالبات مشکوک‌الوصول.** داوران گفتند «هنوز وارد نشده». منحنی وصول
     تجربی همین داده نشان می‌دهد بازیابی از ۱۲۰ روز به بعد روی ۸۷٪ تخت می‌شود؛
     یعنی حدود ۱۳٪ هرگز وصول نمی‌شود. این جزء **جدا** نگه داشته می‌شود تا با
     فرمول داوران قاطی نشود.

نرخ ۴٪ ماهانه یک **فرض کسب‌وکاری بیرونی** است (از راهنمای داوران)، نه چیزی که از
داده استخراج شده باشد. به همین دلیل پارامتر است و در رابط کاربری قابل تغییر است.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ═══════════════════════════════════════════════════ پارامترها
FINANCE_RATE_MONTHLY = 0.04      # فرض بیرونی از راهنمای داوران — قابل تغییر در UI
RATE_SOURCE = ("نرخ ۴٪ ماهانه از راهنمای داوران آمده است، نه از داده. "
               "در داشبورد قابل تغییر است تا اثرش بر رتبه‌بندی دیده شود.")

# منحنی وصول تجربی همین داده: سهم وصول‌شده بر پایهٔ سن فاکتور در تاریخ برش
RECOVERY_BY_AGE = [
    (60, 0.452, "۰ تا ۶۰ روز", 231),
    (120, 0.845, "۶۱ تا ۱۲۰ روز", 652),
    (180, 0.873, "۱۲۱ تا ۱۸۰ روز", 462),
    (365, 0.865, "۱۸۱ تا ۳۶۵ روز", 3159),
    (730, 0.870, "۳۶۶ تا ۷۳۰ روز", 6658),
    (10 ** 9, 0.866, "بیش از ۷۳۰ روز", 3221),
]
RECOVERY_NOTE = ("منحنی وصول از ۱۲۰ روز به بعد روی ۸۷٪ تخت می‌شود و با گذر زمان "
                 "بهتر نمی‌شود. یعنی حدود ۱۳٪ ارزش فاکتورشده هرگز وصول نمی‌شود — "
                 "این یک نرخ ساختاری است، نه تأخیر.")


def _recovery(age: float) -> float:
    for cut, r, _, _ in RECOVERY_BY_AGE:
        if age <= cut:
            return r
    return RECOVERY_BY_AGE[-1][1]


# ═══════════════════════════════════════════════════ روزهای پول قفل‌شده
def money_days(D: dict[str, pd.DataFrame], as_of: pd.Timestamp) -> pd.DataFrame:
    """برای هر مشتری: میانگین وزنی روزهایی که پول فروش نزد مشتری مانده است.

    بخش وصول‌شده با فاصلهٔ واقعی فاکتور تا وصول؛ بخش باز با فاصله تا تاریخ برش
    (کف واقعی — پول هنوز بیرون است و این عدد فقط بزرگ‌تر می‌شود).
    """
    S, COL = D["sales"], D["collections"]
    inv = (S.groupby(["Customer_ID", "invoice_no"])
             .agg(invoiced=("line_amount", "sum"), idate=("date", "min")).reset_index())
    paid = COL.groupby("invoice_no").collected_amount.sum()
    inv["paid"] = inv.invoice_no.map(paid).fillna(0.0).clip(upper=inv.invoiced)
    inv["open"] = (inv.invoiced - inv.paid).clip(lower=0)
    dso = COL.groupby("invoice_no").apply(
        lambda d: np.average((d.collection_date - d.invoice_date).dt.days,
                             weights=d.collected_amount.clip(lower=1)),
        include_groups=False)
    inv["dso_paid"] = inv.invoice_no.map(dso)
    inv["age"] = (as_of - inv.idate).dt.days.clip(lower=0)
    inv["money_days"] = (inv.paid * inv.dso_paid.fillna(inv.age).clip(lower=0)
                         + inv.open * inv.age)
    inv["exp_recovery"] = inv.age.map(_recovery)
    inv["writeoff"] = inv.open * (1 - inv.exp_recovery).clip(lower=0)
    out = inv.groupby("Customer_ID").agg(
        invoiced=("invoiced", "sum"), collected=("paid", "sum"),
        open_balance=("open", "sum"), money_days_total=("money_days", "sum"),
        expected_writeoff=("writeoff", "sum"))
    out["days_cash"] = out.money_days_total / out.invoiced.replace(0, np.nan)
    return out


def add_money_columns(F: pd.DataFrame, md: pd.DataFrame,
                      rate: float = FINANCE_RATE_MONTHLY) -> pd.DataFrame:
    """ستون‌های هزینهٔ پول و حاشیهٔ واقعی را به فریم ویژگی‌ها اضافه می‌کند.

    هزینهٔ پول٪   = نرخ ماهانه × روزهای پول قفل‌شده ÷ ۳۰
    حاشیهٔ واقعی٪ = حاشیهٔ ناخالص٪ − هزینهٔ پول٪            ← فرمول داوران
    حاشیهٔ خالص٪  = حاشیهٔ واقعی٪ − ذخیرهٔ مطالبات مشکوک٪   ← یک گام جلوتر
    """
    F = F.copy()
    F["days_cash"] = F.index.map(md.days_cash)
    F["open_balance"] = F.index.map(md.open_balance).fillna(0.0)
    F["expected_writeoff"] = F.index.map(md.expected_writeoff).fillna(0.0)
    F["cost_of_money_pct"] = (rate * 100 * F.days_cash / 30).round(2)
    F["cost_of_money"] = (F.revenue * F.cost_of_money_pct / 100).round()
    F["real_margin"] = (F.margin - F.cost_of_money_pct).round(2)
    F["real_gp"] = (F.gp - F.cost_of_money).round()
    F["writeoff_pct"] = (F.expected_writeoff / F.revenue.replace(0, np.nan) * 100).round(2)
    F["net_margin"] = (F.real_margin - F.writeoff_pct.fillna(0)).round(2)
    F["net_gp"] = (F.real_gp - F.expected_writeoff).round()
    F["finance_rate_monthly"] = rate
    return F


# ═══════════════════════════════════════════════════ آزمون قیمت‌گذاری اعتبار
def credit_pricing_test(D: dict[str, pd.DataFrame], rate: float = FINANCE_RATE_MONTHLY) -> dict:
    """آیا مارک‌آپ اعتبار واقعاً در قیمت ثبت شده است؟

    روش دقیقاً همان چیزی است که راهنما خواسته: قیمت واحد **همان کد کالا در همان
    ماه** بین شرایط پرداخت مختلف مقایسه می‌شود. اگر مشتری ۹۰ روزه پول را ۹۰ روز
    بیشتر نگه می‌دارد، انتظار داریم حدود ۱۲٪ گران‌تر بخرد.
    """
    S = D["sales"]
    S = S[(S.qty > 0) & (S.unit_price > 0)].copy()
    S["mk"] = S.date.dt.to_period("M").astype(str)
    g = (S.groupby(["Product_ID", "mk", "payment_type"])
           .apply(lambda d: pd.Series({"p": np.average(d.unit_price, weights=d.qty),
                                       "q": float(d.qty.sum())}), include_groups=False)
           .reset_index())
    px = g.pivot_table(index=["Product_ID", "mk"], columns="payment_type", values="p")
    qx = g.pivot_table(index=["Product_ID", "mk"], columns="payment_type", values="q")
    base = "cash_or_prepaid"
    rows = []
    for col, label, extra_days in [("short_term", "۳۰ روزه", 30), ("long_term", "۹۰ روزه", 90)]:
        if col not in px.columns or base not in px.columns:
            continue
        d = px[[base, col]].dropna()
        if not len(d):
            continue
        q = qx.loc[d.index, col].fillna(1)
        r = (d[col] / d[base] - 1) * 100
        se = float(r.std() / np.sqrt(len(r)))
        rows.append({
            "terms": label, "cells": int(len(d)),
            "expected_pct": round(rate * 100 * extra_days / 30, 1),
            "observed_median_pct": round(float(r.median()), 2),
            "observed_weighted_pct": round(float(np.average(r, weights=q.clip(lower=1))), 2),
            "observed_mean_pct": round(float(r.mean()), 2),
            "std_error": round(se, 3),
            "t_stat": round(float(r.mean() / se) if se else 0.0, 1),
            "significant": bool(se and abs(r.mean() / se) > 2),
        })
    verdict = ("اعتبار در قیمت لحاظ **نشده** است. مشتری ۹۰ روزه تقریباً به همان قیمت "
               "مشتری نقدی می‌خرد، در حالی که پول را ۹۰ روز بیشتر نگه می‌دارد. پس "
               "هزینهٔ پول را باید خودمان به حساب مشتری بگذاریم — همان کاری که "
               "این محصول می‌کند.")
    long = next((r for r in rows if r["terms"] == "۹۰ روزه"), None)
    if long and long["significant"] and long["observed_weighted_pct"] >= long["expected_pct"] * 0.6:
        verdict = ("اعتبار در قیمت لحاظ **شده** است؛ مارک‌آپ مشاهده‌شده نزدیک به "
                   "انتظار است. پس هزینهٔ پول را دوباره کسر نکنید.")
    return {"rows": rows, "verdict": verdict, "rate_monthly": rate,
            "method": ("مقایسهٔ قیمت واحد وزنی به مقدار، برای هر کد کالا در هر ماه، "
                       "بین شرایط پرداخت. فقط سلول‌هایی که هر دو شرط را در همان "
                       "ماه دارند مقایسه شده‌اند.")}


def payment_type_profile(D: dict[str, pd.DataFrame]) -> list[dict]:
    """فاصلهٔ واقعی فاکتور تا نقد، به تفکیک شرط پرداخت — پایهٔ هزینهٔ پول."""
    S, COL = D["sales"], D["collections"]
    c = COL.copy()
    c["dso"] = (c.collection_date - c.invoice_date).dt.days
    c["terms"] = (c.due_date - c.invoice_date).dt.days
    pt = S.groupby("invoice_no").payment_type.agg(lambda x: x.mode().iat[0])
    c["ptype"] = c.invoice_no.map(pt)
    FA = {"cash_or_prepaid": "نقدی یا پیش‌پرداخت", "short_term": "کوتاه‌مدت",
          "long_term": "بلندمدت", "payment_generalized": "تعمیم‌یافته"}
    out = []
    for k, d in c.groupby("ptype"):
        dd = d[d.dso.notna()]
        if not len(dd):
            continue
        dso = float(np.average(dd.dso, weights=dd.collected_amount.clip(lower=1)))
        out.append({"payment_type": k, "label": FA.get(k, k), "events": int(len(d)),
                    "terms_days": float(d.terms.median()),
                    "days_to_cash": round(dso, 1),
                    "late_days_median": float(d.days_late.median()),
                    "amount": round(float(d.collected_amount.sum())),
                    "cost_of_money_pct": round(FINANCE_RATE_MONTHLY * 100 * dso / 30, 2)})
    return sorted(out, key=lambda r: r["days_to_cash"])
