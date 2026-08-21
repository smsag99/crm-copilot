"""آموزش روی پنجرهٔ قدیمی‌تر، سنجش روی پنجرهٔ تازه‌تر — انضباط خارج‌از‌زمان.

پنجرهٔ آموزش: ویژگی در ۱۳۹۹/۱۰/۱۱، نتیجه در ۱۲ ماه بعد.
پنجرهٔ آزمون:  ویژگی در ۱۴۰۰/۰۴/۰۹، نتیجه تا آخر داده.
هدف: بفهمیم امتیاز ماندگاری واقعاً چقدر خبر دارد، و سقف ممکن کجاست.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

import pipeline as P
from explore3 import auc, build_features, retention_score

pd.set_option("display.width", 200)
D, _ = P.clean(P.load_raw())
S_ALL = D["sales"]
END = pd.Timestamp("2022-06-06")

TRAIN_CUT = pd.Timestamp("2020-12-31")
TEST_CUT = pd.Timestamp("2021-06-30")
HORIZON_DAYS = 341          # همان طول افق برای هر دو پنجره (تا سقف داده)

FEATS = ["recency", "months", "families", "products", "v6", "vol_trend",
         "collection_rate", "cmp_open", "dev_reqs", "last_touch", "margin", "revenue"]


def labelled(cut: pd.Timestamp) -> pd.DataFrame:
    F = build_features(cut)
    end = min(cut + pd.Timedelta(days=HORIZON_DAYS), END)
    fut = S_ALL[(S_ALL.date > cut) & (S_ALL.date <= end)]
    F["y"] = F.index.isin(fut.Customer_ID.unique()).astype(int)
    F["future_gp"] = fut.groupby("Customer_ID").gross_profit.sum().reindex(F.index).fillna(0)
    F["score"] = F.apply(retention_score, axis=1)
    F["horizon_end"] = end
    return F


print("=" * 92)
print("ساخت دو پنجره")
print("=" * 92)
TR = labelled(TRAIN_CUT)
TE = labelled(TEST_CUT)
for name, X, cut in [("آموزش", TR, TRAIN_CUT), ("آزمون", TE, TEST_CUT)]:
    print(f"{name}: برش {cut.date()} → افق تا {X.horizon_end.iloc[0].date()} | "
          f"{len(X)} مشتری | نرخ بازگشت {X.y.mean():.1%}")

print("\n" + "=" * 92)
print("سنجش خارج‌از‌زمان: AUC روی پنجرهٔ آزمون")
print("=" * 92)
res = []
res.append(("امتیاز ماندگاری (افزایشی، دست‌ساز)", auc(TE.y.values, TE.score.values)))
res.append(("رکود تنها (منفی روز)", auc(TE.y.values, -TE.recency.fillna(9999).values)))
res.append(("حجم شش ماه اخیر تنها", auc(TE.y.values, TE.v6.fillna(0).values)))

med = TR[FEATS].median()
Xtr = TR[FEATS].fillna(med)
Xte = TE[FEATS].fillna(med)
mu, sd = Xtr.mean(), Xtr.std().replace(0, 1)
lr = LogisticRegression(max_iter=2000, C=0.5)
lr.fit((Xtr - mu) / sd, TR.y)
TE["p_lr"] = lr.predict_proba((Xte - mu) / sd)[:, 1]
res.append(("رگرسیون لجستیک (آموزش‌دیده روی پنجرهٔ قدیمی)", auc(TE.y.values, TE.p_lr.values)))

for name, a in res:
    print(f"  {a:.3f}   {name}")
print("\nوزن‌های رگرسیون (استانداردشده) — برای مقایسه با شهود دست‌ساز:")
for f, w in sorted(zip(FEATS, lr.coef_[0]), key=lambda x: -abs(x[1])):
    print(f"    {f:16} {w:+.3f}")

print("\n" + "=" * 92)
print("کالیبراسیون امتیاز افزایشی روی پنجرهٔ آموزش، اعمال روی پنجرهٔ آزمون")
print("=" * 92)
bins = [0, .2, .35, .5, .65, .8, 1.01]
TR["band"] = pd.cut(TR.score, bins, right=False)
cal = TR.groupby("band", observed=True).agg(n=("y", "size"), score=("score", "mean"),
                                            actual=("y", "mean"))
print("روی پنجرهٔ آموزش:")
print(cal.round(3).to_string())
mapping = cal.actual.to_dict()
centers = {iv: (iv.left + iv.right) / 2 for iv in cal.index}
xs = np.array([centers[iv] for iv in cal.index])
ys = cal.actual.values


def calibrate(s: float) -> float:
    return float(np.clip(np.interp(s, xs, ys), 0.01, 0.99))


TE["p_cal"] = TE.score.apply(calibrate)
TE["band"] = pd.cut(TE.score, bins, right=False)
print("\nروی پنجرهٔ آزمون — احتمال کالیبره در برابر واقعیت:")
chk = TE.groupby("band", observed=True).agg(n=("y", "size"), score=("score", "mean"),
                                            p_cal=("p_cal", "mean"), actual=("y", "mean"),
                                            future_gp=("future_gp", "sum"))
print(chk.round(3).to_string())
err_raw = abs(chk.score - chk.actual).mean()
err_cal = abs(chk.p_cal - chk.actual).mean()
print(f"\nمیانگین خطای مطلق کالیبراسیون: خام {err_raw:.3f} → کالیبره {err_cal:.3f}")
print("نقاط درون‌یابی (برای کد نهایی):")
print("  xs =", [round(float(x), 3) for x in xs])
print("  ys =", [round(float(y), 3) for y in ys])

print("\n" + "=" * 92)
print("ارزش عملی: اگر بر پایهٔ امتیاز اولویت‌بندی کنیم، چقدر سود آیندهٔ در معرض را می‌پوشانیم؟")
print("=" * 92)
TE["gp_at_risk"] = TE.future_gp
tot = TE.gp_at_risk.sum()
for k in [20, 50, 100]:
    top = TE.nsmallest(k, "score")
    print(f"  {k} مشتری با پایین‌ترین امتیاز: {top.gp_at_risk.sum() / tot:.1%} سود آیندهٔ سبد، "
          f"نرخ ریزش واقعی {1 - top.y.mean():.1%}")
print("  برای مقایسه، نرخ ریزش کل جامعه:", f"{1 - TE.y.mean():.1%}")

print("\nترکیب امتیاز و سود ماهانه — فهرست «نجات فوری» چقدر درست بود؟")
TE["gp_monthly"] = TE.gp / TE.months.clip(lower=1)
TE["rescue_rank"] = (TE.gp_monthly * (1 - TE.score)).rank(ascending=False)
r20 = TE.nsmallest(20, "rescue_rank")
print(f"  ۲۰ مشتری اول فهرست نجات: نرخ ریزش واقعی {1 - r20.y.mean():.1%} | "
      f"سود آیندهٔ ازدست‌رفته {(r20[r20.y == 0].gp_monthly * 12).sum():,.0f}")

print("\n" + "=" * 92)
print("بازآزمایی الگوی تنوع گروه کالا روی پنجرهٔ آموزش (تکرارپذیری)")
print("=" * 92)
for name, X in [("آموزش", TR), ("آزمون", TE)]:
    X = X.copy()
    X["depth"] = pd.cut(X.months, [0, 2, 6, 12, 100], labels=["۱-۲", "۳-۶", "۷-۱۲", "۱۳+"])
    X["fam2"] = np.where(X.families >= 2, "۲+", "۱")
    t = X.groupby(["depth", "fam2"], observed=True).agg(n=("y", "size"), ret=("y", "mean"))
    print(f"\n{name}:")
    print(t.round(3).to_string())
