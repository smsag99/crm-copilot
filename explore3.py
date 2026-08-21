"""اعتبارسنجی امتیاز ماندگاری با نتیجهٔ واقعی — کاری که موتور «در تاریخ» ممکن می‌کند.

ویژگی‌ها را در ۹ تیر ۱۴۰۰ می‌سازیم، بعد نگاه می‌کنیم چه کسی در ۱۲ ماه بعد
واقعاً خرید کرد. این تفاوت «امتیاز حدسی» و «پیش‌بین سنجیده‌شده» است.
"""
import numpy as np
import pandas as pd

import pipeline as P

pd.set_option("display.width", 200)

D, _ = P.clean(P.load_raw())
CUT = pd.Timestamp("2021-06-30")          # تاریخ ساخت ویژگی
END = pd.Timestamp("2022-06-06")          # آخرین روز داده
S_ALL = D["sales"]


def build_features(as_of: pd.Timestamp) -> pd.DataFrame:
    V = P.as_of_view(D, as_of)
    S, C = V["sales"], V["customers"]
    g = S.groupby("Customer_ID")
    F = pd.DataFrame(index=sorted(S.Customer_ID.unique()))
    F["revenue"] = g.line_amount.sum()
    F["gp"] = g.gross_profit.sum()
    F["margin"] = F.gp / F.revenue * 100
    F["volume"] = g.qty.sum()
    F["months"] = g.month_key.nunique()
    F["invoices"] = g.invoice_no.nunique()
    F["families"] = g.product_family.nunique()
    F["products"] = g.Product_ID.nunique()
    F["last"] = g.date.max()
    F["first"] = g.date.min()
    F["recency"] = (as_of - F["last"]).dt.days
    F["tenure"] = (as_of - F["first"]).dt.days
    six, twelve = as_of - pd.Timedelta(days=182), as_of - pd.Timedelta(days=365)
    F["v6"] = S[S.date > six].groupby("Customer_ID").qty.sum().reindex(F.index).fillna(0)
    F["v6p"] = (S[(S.date > twelve) & (S.date <= six)].groupby("Customer_ID").qty.sum()
                .reindex(F.index).fillna(0))
    F["vol_trend"] = np.where(F.v6p > 0, (F.v6 - F.v6p) / F.v6p * 100, np.nan)

    terms = C.set_index("Customer_ID").Payment_Terms_Days
    inv = S.groupby(["Customer_ID", "invoice_no"]).agg(amt=("line_amount", "sum"),
                                                       dt=("date", "min")).reset_index()
    got = V["collections"].groupby("invoice_no").collected_amount.sum()
    inv["got"] = inv.invoice_no.map(got).fillna(0)
    inv["due"] = inv.dt + pd.to_timedelta(inv.Customer_ID.map(terms).fillna(0), unit="D")
    inv["open"] = (inv.amt - inv.got).clip(lower=0)
    inv["overdue"] = np.where(inv.due <= as_of, inv["open"], 0)
    F["invoiced"] = inv.groupby("Customer_ID").amt.sum()
    F["collected"] = inv.groupby("Customer_ID").got.sum()
    F["overdue"] = inv.groupby("Customer_ID").overdue.sum().fillna(0)
    F["collection_rate"] = F.collected / F.invoiced * 100

    F["cmp_open"] = (V["complaints"][V["complaints"].Complaint_Status != "closed"]
                     .groupby("Customer_ID").size().reindex(F.index).fillna(0))
    F["dev_reqs"] = V["dev_requests"].groupby("Customer_ID").size().reindex(F.index).fillna(0)
    F["last_touch"] = (as_of - V["crm"].groupby("Customer_ID").Event_Time.max()).dt.days
    W = V["wallet_share"]
    W = W.assign(share=np.where(W.Estimated_Total_Purchase > 0,
                                W.Nafis_Purchase / W.Estimated_Total_Purchase * 100, np.nan))
    F["wallet"] = W.groupby("Customer_ID").share.mean()
    return F


def retention_score(row) -> float:
    """امتیاز ماندگاری — وزن‌های شفاف و قابل بازرسی، بدون آموزش روی برچسب."""
    s = 0.5
    r = row.recency
    s += 0.22 if r <= 45 else 0.12 if r <= 90 else 0.0 if r <= 180 else -0.22 if r <= 365 else -0.34
    t = row.vol_trend
    if pd.notna(t):
        s += 0.12 if t > 25 else 0.04 if t > -25 else -0.08 if t > -60 else -0.14
    s += 0.10 if row.families >= 3 else 0.05 if row.families == 2 else -0.05
    if pd.notna(row.wallet):
        s += 0.10 if row.wallet >= 30 else 0.04 if row.wallet >= 10 else -0.04
    s += 0.06 if row.dev_reqs >= 3 else 0.03 if row.dev_reqs >= 1 else 0.0
    if pd.notna(row.last_touch) and row.last_touch > 270:
        s -= 0.08
    if row.cmp_open > 0:
        s -= 0.06
    if pd.notna(row.collection_rate):
        s -= 0.08 if row.collection_rate < 70 else 0.04 if row.collection_rate < 85 else 0.0
    return float(np.clip(s, 0.02, 0.97))


def auc(y: np.ndarray, score: np.ndarray) -> float:
    """AUC از رتبه‌ها (آماره U مان-ویتنی)."""
    order = np.argsort(score)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(score) + 1)
    # میانگین رتبه برای مقادیر مساوی
    df = pd.DataFrame({"s": score, "r": ranks})
    ranks = df.groupby("s").r.transform("mean").values
    n1, n0 = y.sum(), (1 - y).sum()
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


print("=" * 92)
print(f"ساخت ویژگی در {CUT.date()} و سنجش با نتیجهٔ واقعی تا {END.date()}")
print("=" * 92)
F = build_features(CUT)
F["score"] = F.apply(retention_score, axis=1)

future = S_ALL[(S_ALL.date > CUT) & (S_ALL.date <= END)]
F["bought_after"] = F.index.isin(future.Customer_ID.unique()).astype(int)
F["future_gp"] = future.groupby("Customer_ID").gross_profit.sum().reindex(F.index).fillna(0)
F["future_vol"] = future.groupby("Customer_ID").qty.sum().reindex(F.index).fillna(0)

print(f"{len(F)} مشتری در تاریخ برش | {F.bought_after.sum()} نفر ({F.bought_after.mean():.1%}) "
      f"در ۱۲ ماه بعد خرید کردند")
a = auc(F.bought_after.values, F.score.values)
print(f"\nAUC امتیاز ماندگاری: {a:.3f}")
print("مقایسه با پیش‌بین‌های تک‌متغیره:")
for col, sign in [("recency", -1), ("v6", 1), ("wallet", 1), ("months", 1),
                  ("families", 1), ("dev_reqs", 1), ("revenue", 1)]:
    v = F[col].fillna(F[col].median()).values * sign
    print(f"    {col:16} AUC={auc(F.bought_after.values, v):.3f}")

print("\nجدول کالیبراسیون — امتیاز در برابر نرخ واقعی بازگشت:")
F["band"] = pd.cut(F.score, [0, .2, .35, .5, .65, .8, 1.0],
                   labels=["۰-۰٫۲", "۰٫۲-۰٫۳۵", "۰٫۳۵-۰٫۵", "۰٫۵-۰٫۶۵", "۰٫۶۵-۰٫۸", "۰٫۸-۱"])
cal = F.groupby("band", observed=True).agg(
    n=("score", "size"), score_mean=("score", "mean"),
    actual=("bought_after", "mean"), future_gp=("future_gp", "sum")).round(3)
print(cal.to_string())
print("\nتفسیر: اگر ستون actual با score_mean هم‌جهت و نزدیک باشد، امتیاز کالیبره است.")

print("\n" + "=" * 92)
print("آزمون الگو با نتیجهٔ واقعی: تنوع گروه کالا و بازگشت")
print("=" * 92)
F["depth"] = pd.cut(F.months, [0, 2, 6, 12, 100],
                    labels=["۱-۲ ماه", "۳-۶ ماه", "۷-۱۲ ماه", "۱۳+ ماه"])
F["fam2"] = np.where(F.families >= 2, "۲+ گروه", "۱ گروه")
print(F.groupby(["depth", "fam2"], observed=True).agg(
    n=("score", "size"), بازگشت=("bought_after", "mean"),
    سود_آینده=("future_gp", "median")).round(3).to_string())
print("\nاگر داخل هر لایهٔ عمق، «۲+ گروه» بازگشت بالاتری دارد، اثر واقعی است.")

print("\n" + "=" * 92)
print("آزمون الگو با نتیجهٔ واقعی: شکایت و بازگشت (با کنترل عمق)")
print("=" * 92)
V = P.as_of_view(D, CUT)
F["has_cmp"] = F.index.isin(V["complaints"].Customer_ID.unique())
print(F.groupby(["depth", "has_cmp"], observed=True).agg(
    n=("score", "size"), بازگشت=("bought_after", "mean"),
    سود_آینده=("future_gp", "median")).round(3).to_string())

print("\n" + "=" * 92)
print("آزمون الگو با نتیجهٔ واقعی: درخواست توسعه و بازگشت (با کنترل عمق)")
print("=" * 92)
F["dev2"] = np.where(F.dev_reqs >= 1, "دارای درخواست", "بدون درخواست")
print(F.groupby(["depth", "dev2"], observed=True).agg(
    n=("score", "size"), بازگشت=("bought_after", "mean"),
    سود_آینده=("future_gp", "median")).round(3).to_string())

print("\n" + "=" * 92)
print("آزمون الگو با نتیجهٔ واقعی: سهم از سبد و بازگشت (با کنترل عمق)")
print("=" * 92)
F["wal2"] = pd.cut(F.wallet.fillna(-1), [-2, 0.5, 10, 30, 101],
                   labels=["نامعلوم/صفر", "۱-۱۰٪", "۱۰-۳۰٪", "۳۰٪+"])
print(F.groupby(["depth", "wal2"], observed=True).agg(
    n=("score", "size"), بازگشت=("bought_after", "mean")).round(3).to_string())

F.to_pickle("validation.pkl")
print("\nذخیره شد: validation.pkl")
