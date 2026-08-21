"""کاوش الگو — هر فرضیه با داده آزمایش می‌شود؛ فقط آن‌هایی می‌مانند که برقرارند."""
import numpy as np
import pandas as pd

import pipeline as P

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

D, rep = P.clean(P.load_raw())
AS_OF = P.DEFAULT_AS_OF
V = P.as_of_view(D, AS_OF)
S, C = V["sales"], V["customers"]
CMP, LINKS, CRM = V["complaints"], V["complaint_links"], V["crm"]
DEV, OFF, W, LAB = V["dev_requests"], V["offers"], V["wallet_share"], V["lab"]
COL = V["collections"]

print("=" * 90)
print("ساخت جدول ویژگی در سطح مشتری")
print("=" * 90)

g = S.groupby("Customer_ID")
F = pd.DataFrame(index=C.Customer_ID.unique())
F["segment"] = C.set_index("Customer_ID").Customer_Segment
F["terms"] = C.set_index("Customer_ID").Payment_Terms_Days
F["credit_limit"] = C.set_index("Customer_ID").Credit_Limit
F["rep"] = C.set_index("Customer_ID").Sales_Rep_ID
F["revenue"] = g.line_amount.sum()
F["revenue_real"] = g.line_amount_real.sum()
F["volume"] = g.qty.sum()
F["gp"] = g.gross_profit.sum()
F["margin"] = F.gp / F.revenue * 100
F["lines"] = g.Sales_Line_ID.count()
F["invoices"] = g.invoice_no.nunique()
F["months"] = g.month_key.nunique()
F["first"] = g.date.min()
F["last"] = g.date.max()
F["recency"] = (AS_OF - F["last"]).dt.days
F["tenure"] = (AS_OF - F["first"]).dt.days
F["span"] = (F["last"] - F["first"]).dt.days
F["products"] = g.Product_ID.nunique()
F["families"] = g.product_family.nunique()
F["avg_line"] = F.revenue / F.lines
F["lines_per_inv"] = F.lines / F.invoices
F["gp_per_month"] = F.gp / F.months
F["vol_per_month"] = F.volume / F.months
F["neg_lines"] = g.gross_profit.apply(lambda x: (x < 0).sum())
F["neg_line_pct"] = F.neg_lines / F.lines * 100
F["price_cv"] = g.unit_price.std() / g.unit_price.mean()
F["order_gap_mean"] = g.date.apply(lambda x: x.sort_values().diff().dt.days.mean())
def _gap_cv(x):
    d = x.sort_values().diff().dt.days
    return d.std() / d.mean() if d.notna().sum() > 1 and d.mean() else np.nan


F["order_gap_cv"] = g.date.apply(_gap_cv)

# روند شش‌ماهه و دوازده‌ماهه
for w, name in [(182, "v6"), (365, "v12")]:
    cut = AS_OF - pd.Timedelta(days=w)
    F[name] = S[S.date > cut].groupby("Customer_ID").qty.sum().reindex(F.index).fillna(0)
prior6 = S[(S.date > AS_OF - pd.Timedelta(days=365)) & (S.date <= AS_OF - pd.Timedelta(days=182))]
F["v6_prior"] = prior6.groupby("Customer_ID").qty.sum().reindex(F.index).fillna(0)
F["vol_trend"] = np.where(F.v6_prior > 0, (F.v6 - F.v6_prior) / F.v6_prior * 100, np.nan)
F["active_last6"] = F.v6 > 0

# مطالبات
terms = C.set_index("Customer_ID").Payment_Terms_Days
inv = S.groupby(["Customer_ID", "invoice_no"]).agg(amt=("line_amount", "sum"),
                                                   dt=("date", "min")).reset_index()
got = COL.groupby("invoice_no").collected_amount.sum()
inv["got"] = inv.invoice_no.map(got).fillna(0)
inv["due"] = inv.dt + pd.to_timedelta(inv.Customer_ID.map(terms).fillna(0), unit="D")
inv["open"] = (inv.amt - inv.got).clip(lower=0)
inv["overdue"] = np.where(inv.due <= AS_OF, inv["open"], 0)
F["invoiced"] = inv.groupby("Customer_ID").amt.sum()
F["collected"] = inv.groupby("Customer_ID").got.sum()
F["overdue"] = inv.groupby("Customer_ID").overdue.sum().fillna(0)
F["collection_rate"] = F.collected / F.invoiced * 100
F["net_contrib"] = F.gp - F.overdue
F["days_late"] = COL.groupby("Customer_ID").days_late.mean()
F["bounced"] = COL.groupby("Customer_ID").bounced_cheque.apply(lambda x: (x == "yes").sum())
F["credit_util"] = F.overdue / F.credit_limit * 100

# دامنه‌های دیگر
F["complaints"] = CMP.groupby("Customer_ID").size().reindex(F.index).fillna(0)
F["cmp_open"] = CMP[CMP.Complaint_Status != "closed"].groupby("Customer_ID").size().reindex(F.index).fillna(0)
F["cmp_severe"] = CMP[CMP.Severity.isin(["high", "critical"])].groupby("Customer_ID").size().reindex(F.index).fillna(0)
F["interactions"] = CRM.groupby("Customer_ID").size().reindex(F.index).fillna(0)
F["last_touch"] = (AS_OF - CRM.groupby("Customer_ID").Event_Time.max()).dt.days
F["chase_share"] = (CRM[CRM.Interaction_Type == "receivables_chase"].groupby("Customer_ID").size()
                    .reindex(F.index).fillna(0) / F.interactions.replace(0, np.nan) * 100)
F["quality_touch"] = (CRM[CRM.Interaction_Type == "product_quality"].groupby("Customer_ID").size()
                      .reindex(F.index).fillna(0))
F["dev_reqs"] = DEV.groupby("Customer_ID").size().reindex(F.index).fillna(0)
F["dev_approved"] = DEV[DEV.Status == "sample_approved"].groupby("Customer_ID").size().reindex(F.index).fillna(0)
F["offers"] = OFF.groupby("Customer_ID").size().reindex(F.index).fillna(0)
F["off_acc"] = OFF[OFF.Result == "accepted"].groupby("Customer_ID").size().reindex(F.index).fillna(0)
F["off_rate"] = F.off_acc / F.offers.replace(0, np.nan) * 100
F["off_disc"] = OFF.groupby("Customer_ID").Offer_Discount_Pct.mean() * 100
W2 = W.assign(share=np.where(W.Estimated_Total_Purchase > 0,
                             W.Nafis_Purchase / W.Estimated_Total_Purchase * 100, np.nan))
F["wallet"] = W2.groupby("Customer_ID").share.mean()
F["wallet_last"] = W2.sort_values("Month_Key").groupby("Customer_ID").share.last()
F["wallet_trend"] = F.wallet_last - F.wallet
F["est_purchase"] = W2.groupby("Customer_ID").Estimated_Total_Purchase.mean()
lab2 = LAB.merge(S[["Sales_Line_ID", "Customer_ID"]], on="Sales_Line_ID")
F["lab_n"] = lab2.groupby("Customer_ID").size().reindex(F.index).fillna(0)
F["lab_fail"] = lab2[lab2.Lab_Result == "rejected"].groupby("Customer_ID").size().reindex(F.index).fillna(0)
F["cv_evenness"] = lab2.groupby("Customer_ID").Evenness_CV_Pct.mean()

F = F[F.revenue.notna()].copy()
print(f"{len(F)} مشتری با سابقهٔ خرید، {F.shape[1]} ویژگی")

print("\n" + "=" * 90)
print("۱. آزمون الگو: آیا شکایت با ریزش بعدی مرتبط است؟")
print("=" * 90)
first_cmp = CMP.groupby("Customer_ID").Created_At.min()
F["has_cmp"] = F.index.isin(first_cmp.index)
for label, mask in [("با شکایت", F.has_cmp), ("بی‌شکایت", ~F.has_cmp)]:
    sub = F[mask]
    print(f"{label:12} n={len(sub):3}  رکود میانه={sub.recency.median():6.0f} روز  "
          f"روند حجم میانه={sub.vol_trend.median():7.1f}٪  "
          f"سهم راکد>۱۸۰={(sub.recency > 180).mean():5.1%}  "
          f"حاشیه میانه={sub.margin.median():5.1f}٪")
# کنترل اندازه: شکایت با مشتری بزرگ همبسته است
big = F[F.revenue > F.revenue.median()]
for label, mask in [("بزرگ+شکایت", big.has_cmp), ("بزرگ بی‌شکایت", ~big.has_cmp)]:
    sub = big[mask]
    print(f"  {label:16} n={len(sub):3}  رکود میانه={sub.recency.median():6.0f}  "
          f"روند حجم میانه={sub.vol_trend.median():7.1f}٪  راکد={(sub.recency > 180).mean():5.1%}")

print("\n" + "=" * 90)
print("۲. آزمون الگو: شدت شکایت در برابر رفتار بعدی")
print("=" * 90)
sev = CMP.groupby("Customer_ID").Severity.apply(
    lambda x: "critical" if "critical" in set(x) else "high" if "high" in set(x) else "mild")
F["worst_sev"] = F.index.map(sev).fillna("none")
print(F.groupby("worst_sev").agg(n=("revenue", "size"), recency=("recency", "median"),
                                 trend=("vol_trend", "median"), margin=("margin", "median"),
                                 dormant=("recency", lambda x: (x > 180).mean())).round(2).to_string())

print("\n" + "=" * 90)
print("۳. آزمون الگو: شکایت باز در برابر بسته‌شده")
print("=" * 90)
openc = CMP[CMP.Complaint_Status != "closed"].Customer_ID.unique()
closedonly = set(CMP.Customer_ID) - set(openc)
F["cmp_state"] = np.where(F.index.isin(openc), "دارای شکایت باز",
                          np.where(F.index.isin(closedonly), "همه بسته", "بی‌شکایت"))
print(F.groupby("cmp_state").agg(n=("revenue", "size"), recency=("recency", "median"),
                                 trend=("vol_trend", "median"), margin=("margin", "median"),
                                 dormant=("recency", lambda x: (x > 180).mean()),
                                 collection=("collection_rate", "median")).round(2).to_string())

print("\n" + "=" * 90)
print("۴. آزمون الگو: پیگیری وصول در CRM به‌عنوان پیش‌نشانهٔ نکول")
print("=" * 90)
F["chase_bucket"] = pd.cut(F.chase_share.fillna(0), [-0.1, 0, 15, 30, 101],
                           labels=["بدون پیگیری", "کم", "متوسط", "زیاد"])
print(F.groupby("chase_bucket", observed=True).agg(
    n=("revenue", "size"), collection=("collection_rate", "median"),
    overdue_ratio=("overdue", lambda x: x.median()), days_late=("days_late", "median"),
    bounced=("bounced", "mean"), recency=("recency", "median")).round(2).to_string())

print("\n" + "=" * 90)
print("۵. آزمون الگو: درخواست توسعه به‌عنوان نشانهٔ تعهد")
print("=" * 90)
F["dev_bucket"] = pd.cut(F.dev_reqs, [-0.1, 0, 2, 5, 100], labels=["هیچ", "۱-۲", "۳-۵", "۶+"])
print(F.groupby("dev_bucket", observed=True).agg(
    n=("revenue", "size"), revenue=("revenue", "median"), margin=("margin", "median"),
    recency=("recency", "median"), trend=("vol_trend", "median"),
    wallet=("wallet", "median"), dormant=("recency", lambda x: (x > 180).mean())).round(1).to_string())

print("\n" + "=" * 90)
print("۶. آزمون الگو: نمونهٔ تأییدشده در برابر رد فنی")
print("=" * 90)
appr = set(DEV[DEV.Status == "sample_approved"].Customer_ID)
rej = set(DEV[DEV.Status == "technically_rejected"].Customer_ID) - appr
F["dev_out"] = np.where(F.index.isin(appr), "نمونه تأیید",
                        np.where(F.index.isin(rej), "رد فنی", "—"))
print(F[F.dev_out != "—"].groupby("dev_out").agg(
    n=("revenue", "size"), trend=("vol_trend", "median"), recency=("recency", "median"),
    wallet=("wallet", "median"), margin=("margin", "median")).round(1).to_string())

print("\n" + "=" * 90)
print("۷. آزمون الگو: سهم از سبد در برابر حاشیه و وفاداری")
print("=" * 90)
F["wallet_bucket"] = pd.cut(F.wallet, [-0.1, 1, 10, 30, 60, 101],
                            labels=["صفر", "۱-۱۰٪", "۱۰-۳۰٪", "۳۰-۶۰٪", "۶۰٪+"])
print(F.groupby("wallet_bucket", observed=True).agg(
    n=("revenue", "size"), revenue=("revenue", "median"), margin=("margin", "median"),
    recency=("recency", "median"), months=("months", "median"),
    dev=("dev_reqs", "median"), complaints=("complaints", "median")).round(1).to_string())

print("\n" + "=" * 90)
print("۸. آزمون الگو: نظم سفارش‌گذاری (ضریب تغییرات فاصلهٔ سفارش)")
print("=" * 90)
F["gap_bucket"] = pd.qcut(F.order_gap_cv, 4, labels=["منظم", "نسبتاً منظم", "نامنظم", "بی‌نظم"])
print(F.groupby("gap_bucket", observed=True).agg(
    n=("revenue", "size"), recency=("recency", "median"), trend=("vol_trend", "median"),
    margin=("margin", "median"), dormant=("recency", lambda x: (x > 180).mean()),
    collection=("collection_rate", "median")).round(2).to_string())

print("\n" + "=" * 90)
print("۹. آزمون الگو: تنوع محصول در برابر ماندگاری")
print("=" * 90)
F["fam_bucket"] = pd.cut(F.families, [0, 1, 2, 3, 10], labels=["۱ گروه", "۲ گروه", "۳ گروه", "۴+ گروه"])
print(F.groupby("fam_bucket", observed=True).agg(
    n=("revenue", "size"), revenue=("revenue", "median"), margin=("margin", "median"),
    months=("months", "median"), recency=("recency", "median"),
    dormant=("recency", lambda x: (x > 180).mean())).round(1).to_string())

print("\n" + "=" * 90)
print("۱۰. آزمون الگو: شرایط پرداخت در برابر حاشیه و وصول")
print("=" * 90)
pay = S.groupby("Customer_ID").payment_type.agg(lambda x: x.mode().iloc[0])
F["pay_mode"] = pay
print(F.groupby("pay_mode").agg(n=("revenue", "size"), margin=("margin", "median"),
                                collection=("collection_rate", "median"),
                                days_late=("days_late", "median"),
                                overdue_share=("overdue", "median")).round(2).to_string())

print("\n" + "=" * 90)
print("۱۱. همبستگی با ماندگاری و ارزش — کدام ویژگی‌ها واقعاً خبر دارند؟")
print("=" * 90)
num = F.select_dtypes(include=[np.number])
for target, tname in [(F.recency, "رکود (روز)"), (F.gp, "سود ناخالص"),
                      (F.margin, "حاشیه سود"), (F.vol_trend, "روند حجم")]:
    cor = num.corrwith(target, method="spearman").drop(
        [c for c in ["recency", "gp", "margin", "vol_trend"] if c in num.columns], errors="ignore")
    top = cor.abs().sort_values(ascending=False).head(9).index
    print(f"\n{tname}:")
    for k in top:
        print(f"    {k:18} ρ={cor[k]:+.3f}")

F.to_pickle("features_explore.pkl")
print("\nجدول ویژگی ذخیره شد: features_explore.pkl")
