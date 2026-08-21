"""اعتبارسنجی دستی سه حساب — «سه حساب را بردارید و با دست حساب کنید.»

راهنمای داوران این را صریح می‌خواهد: «اگر محصول شما با حساب دستی خودتان نخواند،
محصول اشتباه است. داوران دقیقاً همین را می‌پرسند.»

این ماژول برای سه مشتری، هر عدد کلیدی را **مستقل از موتور محصول** و مستقیم از
شیت‌های خام دوباره حساب می‌کند، و نتیجه را کنار خروجی محصول می‌گذارد. خروجی هم در
داشبورد و هم در `verify.py` استفاده می‌شود.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import money as MN

TOL = 0.005          # اختلاف نسبی قابل قبول: نیم درصد


def _fmt(v, kind="money"):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "—"
    if kind == "pct":
        return f"{v:,.2f}٪"
    if kind == "days":
        return f"{v:,.1f} روز"
    if kind == "int":
        return f"{v:,.0f}"
    return f"{v:,.0f}"


def hand_check(D: dict[str, pd.DataFrame], as_of: pd.Timestamp, cid: str,
               product: dict) -> dict:
    """همهٔ اعداد کلیدی یک مشتری، دوباره و از صفر، مستقیم از شیت خام."""
    S = D["sales"][D["sales"].Customer_ID == cid]
    COL = D["collections"][D["collections"].Customer_ID == cid]
    CP = D["complaints"][D["complaints"].Customer_ID == cid]

    rev = float(S.line_amount.sum())
    qty = float(S.qty.sum())
    cost = float((S.qty * S.unit_cost).sum())
    gp = float(S.gross_profit.sum())
    gm = gp / rev * 100 if rev else np.nan

    inv = S.groupby("invoice_no").agg(invoiced=("line_amount", "sum"),
                                      idate=("date", "min"))
    paid = COL.groupby("invoice_no").collected_amount.sum()
    inv["paid"] = pd.Series(inv.index.map(paid), index=inv.index).fillna(0.0).clip(
        upper=inv.invoiced)
    inv["open"] = (inv.invoiced - inv.paid).clip(lower=0)
    inv["age"] = (as_of - inv.idate).dt.days.astype(float)
    dso = COL.groupby("invoice_no").apply(
        lambda d: np.average((d.collection_date - d.invoice_date).dt.days,
                             weights=d.collected_amount.clip(lower=1)),
        include_groups=False) if len(COL) else pd.Series(dtype=float)
    inv["dso"] = pd.Series(inv.index.map(dso), index=inv.index)
    money_days = float((inv.paid * inv.dso.fillna(inv.age).clip(lower=0)
                        + inv.open * inv.age).sum())
    days_cash = money_days / float(inv.invoiced.sum()) if inv.invoiced.sum() else np.nan
    rate = float(product.get("finance_rate_monthly") or MN.FINANCE_RATE_MONTHLY)
    com_pct = rate * 100 * days_cash / 30
    real_margin = gm - com_pct

    checks = [
        {"metric": "فروش اسمی", "kind": "money",
         "hand": rev, "product": product.get("revenue"),
         "how": f"جمع ستون «مبلغ خط» روی {len(S):,} خط فروش این مشتری"},
        {"metric": "حجم (کیلوگرم)", "kind": "int",
         "hand": qty, "product": product.get("volume"),
         "how": "جمع ستون «مقدار»"},
        {"metric": "بهای تمام‌شده", "kind": "money",
         "hand": cost, "product": (product.get("revenue") or 0) - (product.get("gross_profit") or 0),
         "how": "جمع «مقدار × بهای واحد»؛ بهای واحد = تحقق‌یافته اگر بسته شده، وگرنه برآورد ماهانه"},
        {"metric": "سود ناخالص", "kind": "money",
         "hand": gp, "product": product.get("gross_profit"),
         "how": "فروش منهای بهای تمام‌شده"},
        {"metric": "حاشیهٔ ناخالص", "kind": "pct",
         "hand": gm, "product": product.get("margin_pct"),
         "how": "سود ناخالص ÷ فروش"},
        {"metric": "مانده باز", "kind": "money",
         "hand": float(inv.open.sum()), "product": product.get("open_ar"),
         "how": f"جمع (فاکتورشده − وصول‌شده) روی {len(inv):,} فاکتور، کف صفر"},
        {"metric": "روزهای پول قفل‌شده", "kind": "days",
         "hand": days_cash, "product": product.get("days_cash"),
         "how": "میانگین وزنی: بخش وصول‌شده با فاصلهٔ فاکتور تا وصول، بخش باز با فاصله تا تاریخ برش"},
        {"metric": "هزینهٔ پول", "kind": "pct",
         "hand": com_pct, "product": product.get("cost_of_money_pct"),
         "how": f"{rate * 100:.0f}٪ ماهانه × روزهای پول قفل‌شده ÷ ۳۰"},
        {"metric": "حاشیهٔ واقعی", "kind": "pct",
         "hand": real_margin, "product": product.get("real_margin"),
         "how": "حاشیهٔ ناخالص منهای هزینهٔ پول"},
        {"metric": "تعداد شکایت", "kind": "int",
         "hand": float(len(CP)), "product": product.get("complaints"),
         "how": "شمارش ردیف‌های شیت شکایات برای این مشتری"},
    ]
    for c in checks:
        h, p = c["hand"], c["product"]
        ok = (h is not None and p is not None
              and abs(float(h) - float(p)) <= max(abs(float(h)), 1.0) * TOL)
        c["ok"] = bool(ok)
        c["hand_fa"] = _fmt(h, c["kind"])
        c["product_fa"] = _fmt(p if p is None else float(p), c["kind"])
        c["diff"] = None if (h is None or p is None) else round(float(p) - float(h), 4)
    return {"customer_id": cid, "checks": checks,
            "passed": int(sum(c["ok"] for c in checks)), "total": len(checks),
            "invoices": int(len(inv)), "lines": int(len(S)),
            "collections": int(len(COL))}


def pick_cases(frame: pd.DataFrame, n: int = 3) -> list[str]:
    """سه حساب با سه پروفایل متفاوت انتخاب می‌شوند، نه سه حساب شبیه هم.

    یکی بزرگ و پرمعوق، یکی با هزینهٔ پول بالا، یکی کوچک و سالم — تا آزمون
    دستی هر سه گوشهٔ منطق را لمس کند.
    """
    A = frame[frame.revenue.notna()]
    out = []
    big = A.nlargest(1, "revenue")
    out += list(big.index)
    costly = A[~A.index.isin(out)].nlargest(1, "cost_of_money_pct")
    out += list(costly.index)
    healthy = A[(~A.index.isin(out)) & (A.real_margin > 5) & (A.revenue > A.revenue.median())]
    out += list(healthy.nlargest(1, "real_margin").index) if len(healthy) else \
        list(A[~A.index.isin(out)].nlargest(1, "real_margin").index)
    return out[:n]


def run(D: dict[str, pd.DataFrame], as_of: pd.Timestamp,
        frame: pd.DataFrame, n: int = 3) -> dict:
    ids = pick_cases(frame, n)
    cases = []
    roles = ["بزرگ‌ترین حساب سبد", "گران‌ترین حساب از نظر هزینهٔ پول",
             "حساب سالم با سود واقعی مثبت"]
    for i, cid in enumerate(ids):
        row = frame.loc[cid]
        prod = {k: (None if pd.isna(row.get(k)) else row.get(k))
                for k in ("revenue", "volume", "gross_profit", "margin_pct", "open_ar",
                          "days_cash", "cost_of_money_pct", "real_margin", "complaints",
                          "finance_rate_monthly")}
        prod["finance_rate_monthly"] = MN.FINANCE_RATE_MONTHLY
        c = hand_check(D, as_of, cid, prod)
        c["role"] = roles[i] if i < len(roles) else "حساب نمونه"
        cases.append(c)
    return {"cases": cases,
            "passed": sum(c["passed"] for c in cases),
            "total": sum(c["total"] for c in cases),
            "tolerance_pct": TOL * 100,
            "method": ("هر عدد مستقل از موتور محصول و مستقیم از شیت خام دوباره "
                       "محاسبه شده است. اختلاف تا نیم درصد قابل قبول است "
                       "(گردکردن)، بیشتر از آن یعنی اشکال.")}
