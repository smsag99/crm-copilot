"""نرخ‌های پایهٔ تجربی — پایهٔ عددی پیش‌بینی تصمیم بعدی مشتری.

هیچ احتمالی در این پروژه از حدس نمی‌آید؛ همه از شمارش رویدادهای واقعی در داده
محاسبه می‌شوند. این اسکریپت آن شمارش‌ها را انجام و چاپ می‌کند تا در signals.py
به‌عنوان ثابت با ذکر منبع استفاده شوند.
"""
import numpy as np
import pandas as pd

import pipeline as P

pd.set_option("display.width", 200)
D, _ = P.clean(P.load_raw())
S = D["sales"]
CM, DV, OF, CO = D["complaints"], D["dev_requests"], D["offers"], D["collections"]
END = S.date.max()

print("=" * 92)
print("۱. احتمال سفارش مجدد در ۹۰ روز، بر پایهٔ رکود فعلی")
print("=" * 92)
print("روش: هر ماه را یک نقطهٔ مشاهده می‌گیریم؛ رکود آن لحظه را می‌سنجیم و")
print("نگاه می‌کنیم آیا در ۹۰ روز بعد خریدی رخ داد.\n")
obs = []
for cut in pd.date_range("2020-06-30", END - pd.Timedelta(days=90), freq="MS"):
    past = S[S.date <= cut]
    if past.empty:
        continue
    last = past.groupby("Customer_ID").date.max()
    gap = past.groupby("Customer_ID").date.apply(
        lambda x: x.sort_values().diff().dt.days.mean())
    fut = set(S[(S.date > cut) & (S.date <= cut + pd.Timedelta(days=90))].Customer_ID)
    for cid, ld in last.items():
        obs.append({"cut": cut, "cid": cid, "recency": (cut - ld).days,
                    "gap": gap.get(cid), "bought": int(cid in fut)})
O = pd.DataFrame(obs)
O["silence"] = O.recency / O.gap.replace(0, np.nan)
print(f"{len(O):,} مشاهدهٔ مشتری-ماه در {O.cut.nunique()} تاریخ برش\n")
O["rband"] = pd.cut(O.recency, [-1, 30, 60, 90, 150, 240, 365, 10000],
                    labels=["۰-۳۰", "۳۱-۶۰", "۶۱-۹۰", "۹۱-۱۵۰", "۱۵۱-۲۴۰", "۲۴۱-۳۶۵", "۳۶۵+"])
t = O.groupby("rband", observed=True).agg(n=("bought", "size"), p_reorder=("bought", "mean"))
print(t.round(3).to_string())
print("\nREORDER_BY_RECENCY =", {str(k): round(float(v), 3)
                                for k, v in t.p_reorder.items()})

print("\nهمان احتمال، بر پایهٔ «نسبت سکوت» (رکود تقسیم بر فاصلهٔ معمول سفارش):")
O["sband"] = pd.cut(O.silence, [-0.01, 0.5, 1, 2, 4, 8, 1000],
                    labels=["<۰.۵", "۰.۵-۱", "۱-۲", "۲-۴", "۴-۸", "۸+"])
t2 = O.groupby("sband", observed=True).agg(n=("bought", "size"), p_reorder=("bought", "mean"))
print(t2.round(3).to_string())
print("\nSILENCE_RATIO_REORDER =", {str(k): round(float(v), 3)
                                   for k, v in t2.p_reorder.items()})

print("\n" + "=" * 92)
print("۲. نتیجهٔ آفر بر پایهٔ دلیل آفر — آیا «ریزن» خبر دارد؟")
print("=" * 92)
dec = OF[OF.Result.isin(["accepted", "rejected", "expired"])]
t = dec.groupby("Offer_Reason").agg(
    n=("Offer_ID", "size"),
    accepted=("Result", lambda x: (x == "accepted").mean()),
    rejected=("Result", lambda x: (x == "rejected").mean()),
    expired=("Result", lambda x: (x == "expired").mean()),
    avg_discount=("Offer_Discount_Pct", "mean"))
t = t.sort_values("accepted", ascending=False)
print(t.round(3).to_string())
overall = (dec.Result == "accepted").mean()
print(f"\nنرخ پذیرش کل: {overall:.3f}")
print(f"دامنهٔ نرخ پذیرش بین دلایل: {t.accepted.min():.3f} تا {t.accepted.max():.3f} "
      f"(اختلاف {t.accepted.max() - t.accepted.min():.3f})")
# آزمون کای‌دو دستی
tab = pd.crosstab(dec.Offer_Reason, dec.Result)
exp = np.outer(tab.sum(1), tab.sum(0)) / tab.values.sum()
chi2 = ((tab.values - exp) ** 2 / exp).sum()
dof = (tab.shape[0] - 1) * (tab.shape[1] - 1)
print(f"کای‌دو = {chi2:.1f} با {dof} درجه آزادی "
      f"(آستانهٔ ۵٪ برای {dof} درجه ≈ {1.571 * dof ** 0.5 + dof:.0f})")
print("=> اگر کای‌دو از آستانه کمتر باشد، دلیل آفر هم مثل عمق تخفیف بی‌سیگنال است.")
print("\nنتیجه بر پایهٔ نوع آفر:")
print(dec.groupby("Offer_Type").agg(n=("Offer_ID", "size"),
                                    accepted=("Result", lambda x: (x == "accepted").mean())
                                    ).round(3).to_string())
print("\nOFFER_ACCEPT_BY_REASON =", {k: round(float(v), 3) for k, v in t.accepted.items()})

print("\n" + "=" * 92)
print("۳. احتمال ثبت شکایت جدید در ۱۸۰ روز، بر پایهٔ سابقهٔ شکایت و حجم")
print("=" * 92)
obs = []
for cut in pd.date_range("2020-12-31", END - pd.Timedelta(days=180), freq="QS"):
    past_s = S[S.date <= cut]
    past_c = CM[CM.Created_At <= cut]
    fut_c = set(CM[(CM.Created_At > cut) & (CM.Created_At <= cut + pd.Timedelta(days=180))].Customer_ID)
    active = set(S[(S.date > cut - pd.Timedelta(days=180)) & (S.date <= cut)].Customer_ID)
    ncmp = past_c.groupby("Customer_ID").size()
    for cid in active:
        obs.append({"cid": cid, "prior": int(ncmp.get(cid, 0)), "new": int(cid in fut_c)})
CO2 = pd.DataFrame(obs)
CO2["pband"] = pd.cut(CO2.prior, [-1, 0, 1, 3, 100], labels=["۰", "۱", "۲-۳", "۴+"])
t = CO2.groupby("pband", observed=True).agg(n=("new", "size"), p_new=("new", "mean"))
print(t.round(3).to_string())
print("\nCOMPLAINT_RATE_BY_HISTORY =", {str(k): round(float(v), 3) for k, v in t.p_new.items()})

print("\n" + "=" * 92)
print("۴. احتمال درخواست توسعهٔ جدید در ۱۸۰ روز، بر پایهٔ سابقه")
print("=" * 92)
obs = []
for cut in pd.date_range("2020-12-31", END - pd.Timedelta(days=180), freq="QS"):
    past_d = DV[DV.Created_At <= cut]
    fut_d = set(DV[(DV.Created_At > cut) & (DV.Created_At <= cut + pd.Timedelta(days=180))].Customer_ID)
    active = set(S[(S.date > cut - pd.Timedelta(days=180)) & (S.date <= cut)].Customer_ID)
    nd = past_d.groupby("Customer_ID").size()
    for cid in active:
        obs.append({"cid": cid, "prior": int(nd.get(cid, 0)), "new": int(cid in fut_d)})
DO = pd.DataFrame(obs)
DO["pband"] = pd.cut(DO.prior, [-1, 0, 1, 3, 100], labels=["۰", "۱", "۲-۳", "۴+"])
t = DO.groupby("pband", observed=True).agg(n=("new", "size"), p_new=("new", "mean"))
print(t.round(3).to_string())
print("\nDEV_REQUEST_RATE_BY_HISTORY =", {str(k): round(float(v), 3) for k, v in t.p_new.items()})

print("\n" + "=" * 92)
print("۵. احتمال تأخیر پرداخت بالای میانه در فاکتور بعدی، بر پایهٔ تأخیر گذشته")
print("=" * 92)
c = CO.sort_values("collection_date").copy()
med = c.days_late.median()
c["late"] = (c.days_late > med).astype(int)
c["prev_mean"] = (c.groupby("Customer_ID").late
                  .transform(lambda x: x.shift().expanding().mean()))
c2 = c.dropna(subset=["prev_mean"])
c2["pband"] = pd.cut(c2.prev_mean, [-0.01, 0.2, 0.4, 0.6, 0.8, 1.01],
                     labels=["۰-۲۰٪", "۲۰-۴۰٪", "۴۰-۶۰٪", "۶۰-۸۰٪", "۸۰-۱۰۰٪"])
t = c2.groupby("pband", observed=True).agg(n=("late", "size"), p_late=("late", "mean"))
print(f"میانهٔ تأخیر سبد: {med:.0f} روز — «تأخیر» یعنی بیش از این\n")
print(t.round(3).to_string())
print("\nLATE_PAYMENT_BY_HISTORY =", {str(k): round(float(v), 3) for k, v in t.p_late.items()})

print("\n" + "=" * 92)
print("۶. اثر چک برگشتی بر رفتار پرداخت بعدی")
print("=" * 92)
b = CO.groupby("Customer_ID").agg(bounced=("bounced_cheque", lambda x: (x == "yes").sum()),
                                  late=("days_late", "mean"), n=("Collection_ID", "size"))
b["has_b"] = b.bounced > 0
print(b.groupby("has_b").agg(customers=("n", "size"), avg_late=("late", "mean"),
                             events=("n", "mean")).round(2).to_string())
