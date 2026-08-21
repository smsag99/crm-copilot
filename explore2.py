"""آزمون دوم — کنترل مخدوش‌کننده‌ها و ساخت RFM و LTV."""
import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
F = pd.read_pickle("features_explore.pkl")

print("=" * 92)
print("الگوی ۱ بازآزمایی: آیا «شکایت ⇒ ماندگاری» بعد از کنترل عمق رابطه باقی می‌ماند؟")
print("=" * 92)
print("مخدوش‌کننده واضح: مشتری یک‌بارمصرف نه شکایت می‌کند نه برمی‌گردد.")
print("پس فقط داخل مشتریانی مقایسه می‌کنیم که عمق رابطهٔ مشابه دارند.\n")
F["depth"] = pd.cut(F.months, [0, 2, 6, 12, 100],
                    labels=["۱-۲ ماه فعال", "۳-۶ ماه", "۷-۱۲ ماه", "۱۳+ ماه"])
tab = F.groupby(["depth", "has_cmp"], observed=True).agg(
    n=("revenue", "size"), dormant=("recency", lambda x: (x > 180).mean()),
    recency=("recency", "median"), collection=("collection_rate", "median"),
    margin=("margin", "median")).round(3)
print(tab.to_string())
print("\nنتیجه: اثر داخل هر لایهٔ عمق بررسی شود، نه روی کل جامعه.")

print("\n" + "=" * 92)
print("الگوی ۲ بازآزمایی: شکایت باز و نرخ وصول، با کنترل اندازه")
print("=" * 92)
F["size_q"] = pd.qcut(F.revenue, 4, labels=["کوچک", "متوسط", "بزرگ", "بسیار بزرگ"])
print(F[F.has_cmp].groupby(["size_q", "cmp_state"], observed=True).agg(
    n=("revenue", "size"), collection=("collection_rate", "median"),
    overdue_pct=("overdue", lambda x: x.median()),
    days_late=("days_late", "median")).round(2).to_string())
print("\nمقایسهٔ مستقیم داخل مشتریان دارای شکایت: باز در برابر همه‌بسته")
for q in ["بزرگ", "بسیار بزرگ"]:
    sub = F[(F.size_q == q) & F.has_cmp]
    a = sub[sub.cmp_state == "دارای شکایت باز"].collection_rate.median()
    b = sub[sub.cmp_state == "همه بسته"].collection_rate.median()
    na = (sub.cmp_state == "دارای شکایت باز").sum()
    nb = (sub.cmp_state == "همه بسته").sum()
    print(f"  {q}: باز {a:.1f}٪ (n={na}) در برابر بسته {b:.1f}٪ (n={nb}) → اختلاف {a - b:+.1f} واحد")

print("\n" + "=" * 92)
print("الگوی ۴ بازآزمایی: تنوع گروه کالا و ماندگاری، با کنترل تعداد ماه فعال")
print("=" * 92)
print("اگر اثر فقط از «بیشتر خریدن» باشد، داخل لایهٔ ماه یکسان محو می‌شود.")
F["fam2"] = np.where(F.families >= 2, "۲+ گروه", "۱ گروه")
print(F.groupby(["depth", "fam2"], observed=True).agg(
    n=("revenue", "size"), dormant=("recency", lambda x: (x > 180).mean()),
    recency=("recency", "median"), gp=("gp", "median"),
    margin=("margin", "median")).round(3).to_string())

print("\n" + "=" * 92)
print("الگوی ۹ بازآزمایی: شرایط پرداخت، حاشیه و وصول با کنترل اندازه")
print("=" * 92)
print(F.groupby(["size_q", "pay_mode"], observed=True).agg(
    n=("revenue", "size"), margin=("margin", "median"),
    collection=("collection_rate", "median")).round(2).to_string())

print("\n" + "=" * 92)
print("ساخت RFM — ارزش پولی بر پایهٔ فروش حقیقی (تعدیل تورم)، نه اسمی")
print("=" * 92)
# R: رکود کمتر = بهتر ؛ F: تعداد ماه فعال ؛ M: فروش حقیقی
F["R"] = pd.qcut(-F.recency, 5, labels=[1, 2, 3, 4, 5]).astype(int)
F["Fq"] = pd.qcut(F.months.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
F["M"] = pd.qcut(F.revenue_real.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
F["RFM"] = F.R.astype(str) + F.Fq.astype(str) + F.M.astype(str)


def rfm_segment(r, f, m):
    fm = (f + m) / 2
    if r >= 4 and fm >= 4:
        return "قهرمانان"
    if r >= 3 and fm >= 3:
        return "وفادار"
    if r >= 4 and fm >= 2:
        return "وفادار بالقوه"
    if r >= 4 and fm < 2:
        return "تازه‌وارد"
    if r == 3 and fm < 3:
        return "نیازمند توجه"
    if r == 2 and fm >= 4:
        return "نمی‌توان از دست داد"
    if r == 2 and fm >= 2:
        return "در معرض ریزش"
    if r == 2:
        return "در حال خواب"
    if r == 1 and fm >= 4:
        return "ازدست‌رفتهٔ باارزش"
    if r == 1 and fm >= 2:
        return "خفته"
    return "ازدست‌رفته"


F["rfm_seg"] = [rfm_segment(r, f, m) for r, f, m in zip(F.R, F.Fq, F.M)]
print(F.groupby("rfm_seg").agg(
    n=("revenue", "size"), R=("R", "mean"), F=("Fq", "mean"), M=("M", "mean"),
    revenue=("revenue", "sum"), gp=("gp", "sum"), overdue=("overdue", "sum"),
    margin=("margin", "median"), recency=("recency", "median"))
      .sort_values("gp", ascending=False).round(2).to_string())

print("\n" + "=" * 92)
print("ساخت LTV — تجزیه‌شده و قابل توضیح")
print("=" * 92)
HORIZON = 24
MONTHLY_DISCOUNT = 0.015


def retention_score(row):
    """احتمال ماندگاری در افق ۲۴ ماه — از نشانه‌های قابل مشاهده، وزن‌دهی شفاف."""
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
    if pd.notna(row.last_touch):
        s -= 0.08 if row.last_touch > 270 else 0.0
    s -= 0.06 if row.cmp_open > 0 else 0.0
    if pd.notna(row.collection_rate):
        s -= 0.08 if row.collection_rate < 70 else 0.04 if row.collection_rate < 85 else 0.0
    return float(np.clip(s, 0.02, 0.97))


F["retention"] = F.apply(retention_score, axis=1)
F["gp_monthly"] = F.gp / F.months.clip(lower=1)
disc = sum((1 / (1 + MONTHLY_DISCOUNT) ** i) for i in range(1, HORIZON + 1))
F["exp_months"] = F.retention * HORIZON
F["ltv_future"] = F.gp_monthly * F.retention * disc * (F.collection_rate.fillna(90) / 100)
F["ltv_hist"] = F.gp - F.overdue
F["ltv_total"] = F.ltv_hist + F.ltv_future
print(f"ضریب تنزیل {HORIZON} ماه با نرخ ماهانه {MONTHLY_DISCOUNT:.1%} = {disc:.2f}")
print(f"\nLTV کل سبد: {F.ltv_total.sum():,.0f}  "
      f"(تاریخی {F.ltv_hist.sum():,.0f} + آیندهٔ تنزیل‌شده {F.ltv_future.sum():,.0f})")
print(f"ماندگاری میانه: {F.retention.median():.2f} | مشتریان با LTV منفی: {(F.ltv_total < 0).sum()}")
print("\nده مشتری برتر بر پایهٔ LTV کل:")
print(F.nlargest(10, "ltv_total")[["segment", "revenue", "gp", "overdue", "retention",
                                   "ltv_hist", "ltv_future", "ltv_total", "rfm_seg"]]
      .round(2).to_string())
print("\nتفاوت رتبه‌بندی: چند مشتری از ۲۰ تای اول فروش، در ۲۰ تای اول LTV نیستند؟")
top_rev = set(F.nlargest(20, "revenue").index)
top_ltv = set(F.nlargest(20, "ltv_total").index)
print(f"  {len(top_rev - top_ltv)} مشتری از ۲۰ اول فروش در ۲۰ اول LTV نیستند: "
      f"{'، '.join(sorted(top_rev - top_ltv))}")

print("\n" + "=" * 92)
print("دسته‌بندی چهارخانه: حاشیه سود در برابر ریسک از دست دادن")
print("=" * 92)
med_margin = F.margin.median()
F["good_margin"] = F.margin >= med_margin
F["at_risk"] = F.retention < 0.5
F["quadrant"] = np.select(
    [F.good_margin & ~F.at_risk, F.good_margin & F.at_risk,
     ~F.good_margin & ~F.at_risk, ~F.good_margin & F.at_risk],
    ["رشد بده", "نجات فوری", "اصلاح قیمت", "بازبینی رابطه"], default="—")
print(f"میانهٔ حاشیه سبد: {med_margin:.2f}٪ | آستانهٔ ریسک: ماندگاری < ۰٫۵\n")
print(F.groupby("quadrant").agg(
    n=("revenue", "size"), revenue=("revenue", "sum"), gp=("gp", "sum"),
    ltv=("ltv_total", "sum"), margin=("margin", "median"),
    retention=("retention", "median"), recency=("recency", "median"),
    overdue=("overdue", "sum")).round(2).to_string())
print("\n«نجات فوری» — حاشیه خوب ولی در حال از دست رفتن. ده مشتری بزرگ این خانه:")
print(F[F.quadrant == "نجات فوری"].nlargest(10, "gp")[
    ["segment", "revenue", "gp", "margin", "recency", "vol_trend", "retention", "ltv_total"]]
      .round(1).to_string())

F.to_pickle("features_explore.pkl")
print("\nذخیره شد.")
