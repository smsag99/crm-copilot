"""مهندسی ویژگی، RFM، امتیاز ماندگاری، ارزش طول عمر و دسته‌بندی چهارخانه

هر عدد این ماژول تجزیه‌پذیر است: امتیاز ماندگاری فهرست سهم هر نشانه را
برمی‌گرداند و LTV اجزایش را. دلیل: کارشناس فروش باید بتواند بپرسد «چرا؟» و
جواب عددی بگیرد، نه جعبهٔ سیاه.

اعتبارسنجی خارج‌از‌زمان (اسکریپت validate_model.py):
  پنجرهٔ آموزش  : ویژگی در ۱۳۹۹/۱۰/۱۱، نتیجه ۱۱ ماه بعد  (۴۴۸ مشتری، بازگشت ۶۲.۷٪)
  پنجرهٔ آزمون  : ویژگی در ۱۴۰۰/۰۴/۰۹، نتیجه تا پایان داده (۵۲۶ مشتری، بازگشت ۵۴.۲٪)
  AUC امتیاز افزایشی      ۰.۸۳۱
  AUC رکود تنها           ۰.۸۵۲   ← تک‌متغیره از امتیاز ترکیبی بهتر است
  AUC رگرسیون لجستیک      ۰.۸۶۸   ← سقف عملی
  خطای کالیبراسیون        ۰.۰۹۸ → ۰.۰۴۰ پس از کالیبره کردن
امتیاز افزایشی را نگه داشتیم چون تجزیه‌پذیر است، و این را صریح گزارش می‌کنیم.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

import money as MN

LTV_HORIZON_MONTHS = 24
MONTHLY_DISCOUNT = 0.015
DISCOUNT_FACTOR = sum(1 / (1 + MONTHLY_DISCOUNT) ** i for i in range(1, LTV_HORIZON_MONTHS + 1))

# نقاط کالیبراسیون از پنجرهٔ آموزش (امتیاز خام → نرخ واقعی بازگشت)
CAL_X = [0.10, 0.275, 0.425, 0.575, 0.725, 0.905]
CAL_Y = [0.287, 0.353, 0.518, 0.611, 0.815, 0.966]

MODEL_CARD = {
    "target": "خرید مشتری در ۱۲ ماه پس از تاریخ برش",
    "method": "امتیاز افزایشی با وزن‌های دستی، کالیبره‌شده روی پنجرهٔ قدیمی‌تر",
    "train_window": "ویژگی در ۱۳۹۹/۱۰/۱۱ — ۴۴۸ مشتری، نرخ بازگشت ۶۲.۷٪",
    "test_window": "ویژگی در ۱۴۰۰/۰۴/۰۹ — ۵۲۶ مشتری، نرخ بازگشت ۵۴.۲٪",
    "auc_additive": 0.831,
    "auc_recency_only": 0.852,
    "auc_logistic": 0.868,
    "calibration_error_raw": 0.098,
    "calibration_error_calibrated": 0.040,
    "honest_note": ("رکود تنها (AUC ۰.۸۵۲) از امتیاز ترکیبی (۰.۸۳۱) بهتر پیش‌بینی می‌کند و "
                    "رگرسیون لجستیک تا ۰.۸۶۸ می‌رسد. امتیاز افزایشی را نگه داشتیم چون "
                    "سهم هر نشانه در آن قابل نمایش و بازرسی است؛ برای تصمیم انسانی، "
                    "توضیح‌پذیری بر ۰.۰۴ واحد AUC ارجحیت دارد."),
    "limitation": ("سهم از سبد در پنجرهٔ اعتبارسنجی قابل استفاده نبود، چون دادهٔ آن از "
                   "تیر ۱۴۰۰ شروع می‌شود — یعنی پس از تاریخ برش آموزش."),
}

# ═══════════════════════════════════════════════ وزن‌های امتیاز ماندگاری
# هر مؤلفه: (نام فارسی، تابع سهم، متن دلیل)
RETENTION_BASE = 0.50


def _band(v, cuts, vals):
    for c, x in zip(cuts, vals):
        if v <= c:
            return x
    return vals[-1]


def retention_components(f: pd.Series) -> list[dict]:
    """سهم هر نشانه در امتیاز ماندگاری — همین است که در رابط کاربری نشان می‌دهیم."""
    C: list[dict] = []

    def add(name, value_fa, delta, why):
        C.append({"name": name, "value": value_fa, "delta": round(float(delta), 3), "why": why})

    r = f.recency
    d = _band(r, [45, 90, 180, 365], [0.22, 0.12, 0.0, -0.22, -0.34])
    add("رکود خرید", f"{int(r)} روز از آخرین خرید", d,
        "رکود قوی‌ترین پیش‌بین تک‌متغیره است (AUC ۰.۸۵۲)")

    t = f.vol_trend
    if pd.notna(t):
        d = 0.12 if t > 25 else 0.04 if t > -25 else -0.08 if t > -60 else -0.14
        add("روند حجم شش‌ماهه", f"{t:+.0f}٪", d, "جهت حجم، مستقل از تورم قیمت")

    fam = int(f.families)
    d = 0.10 if fam >= 3 else 0.05 if fam == 2 else -0.05
    add("تنوع گروه کالا", f"{fam} گروه", d,
        "الگوی سنجیده: خرید از ۲+ گروه کالا حدود ۲۰ واحد درصد بازگشت بیشتر، "
        "در هر دو پنجرهٔ اعتبارسنجی تکرار شد")

    if pd.notna(f.wallet):
        d = 0.10 if f.wallet >= 30 else 0.04 if f.wallet >= 10 else -0.04
        add("سهم از سبد خرید", f"{f.wallet:.0f}٪", d, "برآورد کارشناس از عمق رابطه")

    dv = int(f.dev_reqs)
    if dv:
        d = 0.06 if dv >= 3 else 0.03
        add("درخواست توسعه محصول", f"{dv} درخواست", d,
            "نشانهٔ درگیری فنی — توجه: در اعتبارسنجی اثر مستقل بر بازگشت نداشت")

    if pd.notna(f.last_touch) and f.last_touch > 270:
        add("فاصله از آخرین تعامل", f"{int(f.last_touch)} روز", -0.08,
            "قطع ارتباط ثبت‌شده در CRM")

    if f.cmp_open > 0:
        add("شکایت باز", f"{int(f.cmp_open)} مورد", -0.06,
            "پروندهٔ رسیدگی‌نشده — توجه: در اعتبارسنجی اثر مستقل بر بازگشت نداشت")

    if pd.notna(f.collection_rate):
        d = -0.08 if f.collection_rate < 70 else -0.04 if f.collection_rate < 85 else 0.0
        if d:
            add("نرخ وصول", f"{f.collection_rate:.0f}٪", d, "کیفیت پرداخت")

    return C


def calibrate(score: float) -> float:
    return float(np.clip(np.interp(score, CAL_X, CAL_Y), 0.01, 0.99))


# ══════════════════════════════════════════════════════════ RFM
RFM_SEGMENTS_FA = {
    "قهرمانان": "اخیراً خرید کرده، پرتکرار و پرارزش — ستون فروش",
    "وفادار": "خرید منظم و ارزش خوب",
    "وفادار بالقوه": "اخیراً فعال، ارزش در حال ساخت",
    "تازه‌وارد": "خرید تازه ولی سابقهٔ کم",
    "نیازمند توجه": "میانهٔ همه‌چیز؛ بدون اقدام به سمت ریزش می‌رود",
    "نمی‌توان از دست داد": "پرارزش ولی مدتی است نیامده — اولویت بازیابی",
    "در معرض ریزش": "ارزش متوسط و رکود در حال رشد",
    "در حال خواب": "فعالیت کم و در حال کاهش",
    "ازدست‌رفتهٔ باارزش": "پرارزش بوده و رفته — بیشترین زیان نهفته",
    "خفته": "مدت‌ها بی‌خرید، ارزش متوسط",
    "ازدست‌رفته": "بی‌خرید و کم‌ارزش",
}


def rfm_segment(r: int, fq: int, m: int) -> str:
    fm = (fq + m) / 2
    if r >= 4 and fm >= 4:
        return "قهرمانان"
    if r >= 3 and fm >= 3:
        return "وفادار"
    if r >= 4 and fm >= 2:
        return "وفادار بالقوه"
    if r >= 4:
        return "تازه‌وارد"
    if r == 3:
        return "نیازمند توجه"
    if r == 2 and fm >= 4:
        return "نمی‌توان از دست داد"
    if r == 2 and fm >= 2:
        return "در معرض ریزش"
    if r == 2:
        return "در حال خواب"
    if fm >= 4:
        return "ازدست‌رفتهٔ باارزش"
    if fm >= 2:
        return "خفته"
    return "ازدست‌رفته"


# ═══════════════════════════ فهرست تمرکز (اسکناریوی F راهنمای داوران)
FOCUS_FA = {
    "رشد بده": {
        "desc": "سود واقعی بالای میانه و ظرفیت رشد باز",
        "play": "بهترین نیروها را اینجا بگذارید؛ فروش مکمل و افزایش سهم از سبد",
        "color": "good"},
    "حفظ کن": {
        "desc": "سود واقعی بالای میانه و سهم از سبد تقریباً پر",
        "play": "تلاش کم، مراقبت زیاد؛ فقط نشانه‌های هشدار زودهنگام را رصد کنید",
        "color": "neu"},
    "اصلاح کن": {
        "desc": "حجم هست ولی سود واقعی نیست، و ظرفیت رشد وجود دارد",
        "play": "بازمذاکرهٔ قیمت یا شرایط پرداخت با مهلت مشخص؛ اگر تا مهلت اصلاح نشد، به «کاهش بده» برود",
        "color": "warning"},
    "کاهش بده": {
        "desc": "سود واقعی منفی، ظرفیت کم و هزینهٔ خدمت‌دهی بالا",
        "play": "به خودخدمتی یا تماس کم‌بسامد منتقل شود؛ پیگیری فعال متوقف شود",
        "color": "critical"},
}

QUADRANTS_FA = {
    "رشد بده": {
        "desc": "حاشیه سود بالای میانه و ریسک از دست دادن کم",
        "play": "سرمایه‌گذاری برای رشد حجم و سهم از سبد؛ قرارداد بلندمدت ببندید",
        "color": "good"},
    "نجات فوری": {
        "desc": "حاشیه سود بالای میانه ولی در حال از دست رفتن — گران‌ترین خانه",
        "play": "تماس مدیر فروش در هفتهٔ جاری؛ ریشهٔ قطع خرید را پیدا کنید",
        "color": "critical"},
    "اصلاح قیمت": {
        "desc": "پایدار ولی حاشیه زیر میانه",
        "play": "بازنگری قیمت یا حذف کدهای زیان‌ده؛ رابطه تحمل اصلاح را دارد",
        "color": "warning"},
    "بازبینی رابطه": {
        "desc": "حاشیه زیر میانه و در حال از دست رفتن",
        "play": "هزینهٔ بازیابی را با ارزش بسنجید؛ اولویت آخر منابع فروش",
        "color": "serious"},
}


# ═══════════════════════════════════════════════ ساخت جدول ویژگی
def build_features(D: dict[str, pd.DataFrame], as_of: pd.Timestamp) -> pd.DataFrame:
    """ویژگی‌های مهندسی‌شده در سطح مشتری، در تاریخ داده‌شده."""
    import pipeline as P
    V = P.as_of_view(D, as_of)
    S, C = V["sales"], V["customers"]
    g = S.groupby("Customer_ID")
    F = pd.DataFrame(index=sorted(C.Customer_ID.unique()))

    F["segment"] = C.set_index("Customer_ID").Customer_Segment
    F["terms"] = C.set_index("Customer_ID").Payment_Terms_Days
    F["credit_limit"] = C.set_index("Customer_ID").Credit_Limit
    F["rep"] = C.set_index("Customer_ID").Sales_Rep_ID

    # ── بنیادی
    F["revenue"] = g.line_amount.sum()
    F["revenue_real"] = g.line_amount_real.sum()
    F["volume"] = g.qty.sum()
    F["gp"] = g.gross_profit.sum()
    F["lines"] = g.Sales_Line_ID.count()
    F["invoices"] = g.invoice_no.nunique()
    F["months"] = g.month_key.nunique()
    F["products"] = g.Product_ID.nunique()
    F["families"] = g.product_family.nunique()
    F["quality_classes"] = g.Quality_Class_ID.nunique()
    F["first"] = g.date.min()
    F["last"] = g.date.max()

    # ── مشتق: نسبت‌ها و شدت‌ها
    F["margin"] = F.gp / F.revenue * 100
    F["recency"] = (as_of - F["last"]).dt.days
    F["tenure"] = (as_of - F["first"]).dt.days
    F["span"] = (F["last"] - F["first"]).dt.days
    F["avg_line"] = F.revenue / F.lines
    F["lines_per_invoice"] = F.lines / F.invoices
    F["gp_monthly"] = F.gp / F.months.clip(lower=1)
    F["vol_monthly"] = F.volume / F.months.clip(lower=1)
    F["rev_monthly_real"] = F.revenue_real / F.months.clip(lower=1)
    F["active_ratio"] = F.months / (F.span / 30.44).clip(lower=1)   # نظم حضور
    F["neg_lines"] = g.gross_profit.apply(lambda x: int((x < 0).sum()))
    F["neg_line_pct"] = F.neg_lines / F.lines * 100
    F["gp_destroyed"] = g.gross_profit.apply(lambda x: float(x[x < 0].sum()))
    F["price_cv"] = (g.unit_price.std() / g.unit_price.mean()).fillna(0)
    F["qty_cv"] = (g.qty.std() / g.qty.mean()).fillna(0)
    F["top_family_share"] = g.apply(
        lambda x: float(x.groupby("product_family").line_amount.sum().max() / x.line_amount.sum()) * 100,
        include_groups=False)
    F["realized_cost_share"] = g.cost_basis.apply(lambda x: float((x == "realized").mean()) * 100)

    # فاصلهٔ سفارش باید روی تاریخ‌های *متمایز* حساب شود: یک فاکتور چند خط دارد
    # و همهٔ خطوطش یک تاریخ دارند، پس diff روی سطح خط صفر می‌دهد.
    def _gap(x):
        d = x.drop_duplicates().sort_values().diff().dt.days
        return d.mean() if d.notna().sum() >= 1 else np.nan

    def _gap_cv(x):
        d = x.drop_duplicates().sort_values().diff().dt.days
        return d.std() / d.mean() if d.notna().sum() > 1 and d.mean() else np.nan

    F["order_gap"] = g.date.apply(_gap)
    F["order_gap_cv"] = g.date.apply(_gap_cv)
    # چند برابر فاصلهٔ معمول سفارش، ساکت بوده؟ نشانهٔ ریزش زودهنگام
    # نسبت سکوت تنها برای مشتریانی معنا دارد که الگوی سفارش قابل تشخیص دارند
    F["silence_ratio"] = np.where(F.order_gap >= 3, F.recency / F.order_gap, np.nan)

    # ── روند
    six, twelve = as_of - pd.Timedelta(days=182), as_of - pd.Timedelta(days=365)
    F["v6"] = S[S.date > six].groupby("Customer_ID").qty.sum().reindex(F.index).fillna(0)
    F["v6_prior"] = (S[(S.date > twelve) & (S.date <= six)].groupby("Customer_ID").qty.sum()
                     .reindex(F.index).fillna(0))
    F["vol_trend"] = np.where(F.v6_prior > 0, (F.v6 - F.v6_prior) / F.v6_prior * 100, np.nan)
    F["gp6"] = S[S.date > six].groupby("Customer_ID").gross_profit.sum().reindex(F.index).fillna(0)
    F["gp6_prior"] = (S[(S.date > twelve) & (S.date <= six)].groupby("Customer_ID")
                      .gross_profit.sum().reindex(F.index).fillna(0))
    F["margin6"] = np.where(F.v6 > 0,
                            F.gp6 / S[S.date > six].groupby("Customer_ID").line_amount.sum()
                            .reindex(F.index).replace(0, np.nan) * 100, np.nan)
    F["margin_drift"] = F.margin6 - F.margin

    # ── مطالبات
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
    F["overdue"] = inv.groupby("Customer_ID").overdue.sum().reindex(F.index).fillna(0)
    F["collection_rate"] = F.collected / F.invoiced * 100
    F["net_contrib"] = F.gp - F.overdue
    F["days_late"] = V["collections"].groupby("Customer_ID").days_late.mean()
    F["bounced"] = (V["collections"].groupby("Customer_ID").bounced_cheque
                    .apply(lambda x: int((x == "yes").sum())).reindex(F.index).fillna(0))
    F["credit_util"] = F.overdue / F.credit_limit.replace(0, np.nan) * 100
    od = inv[inv.overdue > 0].groupby("Customer_ID").due.min()
    F["oldest_overdue_days"] = (as_of - od).dt.days

    # ── دامنه‌های دیگر
    CM = V["complaints"]
    F["complaints"] = CM.groupby("Customer_ID").size().reindex(F.index).fillna(0)
    F["cmp_open"] = (CM[CM.Complaint_Status != "closed"].groupby("Customer_ID").size()
                     .reindex(F.index).fillna(0))
    F["cmp_severe"] = (CM[CM.Severity.isin(["high", "critical"])].groupby("Customer_ID").size()
                       .reindex(F.index).fillna(0))
    F["cmp_last_days"] = (as_of - CM.groupby("Customer_ID").Created_At.max()).dt.days

    CR = V["crm"]
    F["interactions"] = CR.groupby("Customer_ID").size().reindex(F.index).fillna(0)
    F["last_touch"] = (as_of - CR.groupby("Customer_ID").Event_Time.max()).dt.days
    F["touch_per_month"] = F.interactions / F.months.clip(lower=1)
    for t, col in [("receivables_chase", "chase_n"), ("product_quality", "quality_n"),
                   ("price_and_discount", "price_talk_n"), ("purchase_plan", "plan_n"),
                   ("product_sample", "sample_n")]:
        F[col] = CR[CR.Interaction_Type == t].groupby("Customer_ID").size().reindex(F.index).fillna(0)
    F["chase_share"] = F.chase_n / F.interactions.replace(0, np.nan) * 100
    F["open_actions"] = (CR[CR.Next_Action != "no_action"].groupby("Customer_ID").size()
                         .reindex(F.index).fillna(0))

    DV = V["dev_requests"]
    F["dev_reqs"] = DV.groupby("Customer_ID").size().reindex(F.index).fillna(0)
    F["dev_approved"] = (DV[DV.Status == "sample_approved"].groupby("Customer_ID").size()
                         .reindex(F.index).fillna(0))
    F["dev_rejected"] = (DV[DV.Status == "technically_rejected"].groupby("Customer_ID").size()
                         .reindex(F.index).fillna(0))
    F["dev_pending"] = (DV[DV.Status.isin(["under_review", "in_development"])]
                        .groupby("Customer_ID").size().reindex(F.index).fillna(0))

    OF = V["offers"]
    F["offers"] = OF.groupby("Customer_ID").size().reindex(F.index).fillna(0)
    F["off_accepted"] = (OF[OF.Result == "accepted"].groupby("Customer_ID").size()
                         .reindex(F.index).fillna(0))
    F["off_rejected"] = (OF[OF.Result == "rejected"].groupby("Customer_ID").size()
                         .reindex(F.index).fillna(0))
    F["off_pending"] = (OF[OF.Result.isin(["pending", "negotiating"])].groupby("Customer_ID")
                        .size().reindex(F.index).fillna(0))
    dec = OF[OF.Result.isin(["accepted", "rejected", "expired"])]
    F["off_accept_rate"] = (dec[dec.Result == "accepted"].groupby("Customer_ID").size()
                            .reindex(F.index).fillna(0)
                            / dec.groupby("Customer_ID").size().reindex(F.index).replace(0, np.nan)) * 100
    F["off_discount"] = OF.groupby("Customer_ID").Offer_Discount_Pct.mean() * 100

    W = V["wallet_share"].copy()
    W["share"] = np.where(W.Estimated_Total_Purchase > 0,
                          W.Nafis_Purchase / W.Estimated_Total_Purchase * 100, np.nan)
    F["wallet"] = W.groupby("Customer_ID").share.mean()
    F["wallet_last"] = W.sort_values("Month_Key").groupby("Customer_ID").share.last()
    F["wallet_trend"] = F.wallet_last - F.wallet
    F["est_purchase"] = W.groupby("Customer_ID").Estimated_Total_Purchase.mean()
    F["wallet_months"] = W.groupby("Customer_ID").size().reindex(F.index).fillna(0)

    LB = V["lab"].merge(S[["Sales_Line_ID", "Customer_ID"]], on="Sales_Line_ID", how="inner")
    F["lab_n"] = LB.groupby("Customer_ID").size().reindex(F.index).fillna(0)
    F["lab_fail"] = (LB[LB.Lab_Result == "rejected"].groupby("Customer_ID").size()
                     .reindex(F.index).fillna(0))
    F["cv_evenness"] = LB.groupby("Customer_ID").Evenness_CV_Pct.mean()

    MS = V["market_signals"].dropna(subset=["Customer_ID"])
    F["market_signals"] = MS.groupby("Customer_ID").size().reindex(F.index).fillna(0)
    F["price_pressure_signals"] = (MS[MS.Market_Trend == "price_pressure"]
                                   .groupby("Customer_ID").size().reindex(F.index).fillna(0))

    # ── میانگین بخش، برای سنجش نسبی
    F["segment_avg_margin"] = F.groupby("segment").margin.transform("median")
    F["segment_avg_wallet"] = F.groupby("segment").wallet.transform("median")
    F["margin_vs_segment"] = F.margin - F.segment_avg_margin

    return F


# ═══════════════════════════ حرکت RFM (نکتهٔ صریح راهنمای داوران)
RFM_MOVE_DAYS = 91          # یک فصل — بازهٔ مقایسهٔ حرکت

def add_rfm_movement(F: pd.DataFrame, F_prev: pd.DataFrame) -> pd.DataFrame:
    """تغییر امتیاز RFM نسبت به یک فصل پیش.

    راهنمای داوران: «امتیاز امروز از تغییر آن نسبت به فصل گذشته کم‌ارزش‌تر است.
    مشتری‌ای که از ۵-۵-۵ به ۳-۴-۵ افتاده، ارزشمندترین هشدار کل سامانه است.»

    هر دوره **مستقل** امتیازدهی می‌شود؛ پس افت امتیاز یعنی افت نسبت به هم‌گروه‌ها،
    نه فقط افت مطلق.
    """
    F = F.copy()
    for c, pc in [("R", "R_prev"), ("Fq", "Fq_prev"), ("M", "M_prev")]:
        F[pc] = F.index.map(F_prev[c]) if c in F_prev.columns else np.nan
    F["RFM_prev"] = F.apply(
        lambda r: ("".join(str(int(r[c])) for c in ("R_prev", "Fq_prev", "M_prev"))
                   if pd.notna(r.get("R_prev")) and pd.notna(r.get("Fq_prev"))
                   and pd.notna(r.get("M_prev")) else None), axis=1)
    # اجزای خام دورهٔ قبل، تا بُعد پولی در داشبورد با هر نرخی بازمحاسبه شود.
    # بدون این‌ها، پنل حرکت RFM روی نرخ لحظهٔ ساخت کش یخ می‌زند.
    for src, dst in [("revenue", "prev_revenue"), ("margin", "prev_margin"),
                     ("days_cash", "prev_days_cash")]:
        F[dst] = F.index.map(F_prev[src]) if src in F_prev.columns else np.nan
    F["dR"] = F.R - F.R_prev
    F["dF"] = F.Fq - F.Fq_prev
    F["dM"] = F.M - F.M_prev
    F["rfm_move"] = F[["dR", "dF", "dM"]].sum(axis=1, min_count=1)
    F["rfm_move_days"] = RFM_MOVE_DAYS

    def label(r):
        if pd.isna(r.rfm_move):
            return "بدون سابقهٔ مقایسه"
        if r.rfm_move <= -3:
            return "افت شدید"
        if r.rfm_move <= -1:
            return "افت"
        if r.rfm_move >= 3:
            return "رشد قوی"
        if r.rfm_move >= 1:
            return "رشد"
        return "بدون تغییر"

    F["rfm_move_label"] = F.apply(label, axis=1)
    # هشدار طلایی: مشتری پرارزشی که امتیازش افتاده
    F["rfm_alert"] = ((F.M_prev >= 4) & (F.rfm_move <= -2)).fillna(False)
    return F


def _add_focus(A: pd.DataFrame) -> pd.DataFrame:
    """چهار خانهٔ راهنمای داوران: رشد بده / حفظ کن / اصلاح کن / کاهش بده.

    محور یکم — **سود واقعی**، نه فروش و نه حاشیهٔ ناخالص.
    محور دوم — **ظرفیت رشد**: شکاف سهم از سبد، و اگر نبود، گروه‌های کالای
                فروخته‌نشده به‌عنوان جایگزین.
    محور سوم (فقط برای «کاهش بده») — **هزینهٔ خدمت‌دهی**.
    """
    A = A.copy()
    # ── ظرفیت رشد به ریال سالانه
    # حاشیهٔ «قابل دستیابی» مبنا قرار می‌گیرد، نه حاشیهٔ خرابِ فعلی: اگر شرایط
    # پرداخت این مشتری به نقدی برود و قیمتش میانهٔ سبد باشد، این حاشیه را می‌گیریم.
    cash_days = float(A.days_cash.quantile(0.10))
    achievable = float(A.margin.median() - A.finance_rate_monthly.iloc[0] * 100 * cash_days / 30)
    A["achievable_real_margin"] = round(achievable, 2)
    price = (A.revenue / A.volume.replace(0, np.nan)).fillna(0)
    marg = max(achievable, 1.0) / 100
    gap = (A.get("segment_avg_wallet", pd.Series(np.nan, index=A.index))
           - A.get("wallet", pd.Series(np.nan, index=A.index))).clip(lower=0).fillna(0)
    wallet_head = (A.get("est_purchase", pd.Series(0.0, index=A.index)).fillna(0)
                   * gap / 100 * price * marg * 12)
    xs = A.get("cross_sell_n", pd.Series(0.0, index=A.index)).fillna(0)
    fam_total = A.families.fillna(0) + xs
    fam_head = (A.real_gp.clip(lower=0) / A.months.clip(lower=1) * 12
                * (xs / fam_total.replace(0, np.nan)).fillna(0))
    A["growth_potential"] = np.maximum(wallet_head, fam_head).round()
    A["potential_basis"] = np.where(wallet_head >= fam_head,
                                    "شکاف سهم از سبد", "گروه کالای فروخته‌نشده")

    # ── هزینهٔ خدمت‌دهی: شکایت، پیگیری وصول و برگشتی، نرمال‌شده
    cs = (A.get("open_complaints", pd.Series(0.0, index=A.index)).fillna(0) * 2
          + A.get("complaints", pd.Series(0.0, index=A.index)).fillna(0)
          + A.get("chase_n", pd.Series(0.0, index=A.index)).fillna(0) / 2
          + A.get("chase_share", pd.Series(0.0, index=A.index)).fillna(0) / 10
          + A.get("bounced", pd.Series(0.0, index=A.index)).fillna(0) * 2)
    A["cost_to_serve_score"] = cs.round(2)

    med_profit = A.real_gp.median()
    med_pot = A.growth_potential[A.growth_potential > 0].median()
    if not np.isfinite(med_pot):
        med_pot = 0.0
    A["focus_profit_high"] = A.real_gp >= med_profit
    A["focus_potential_high"] = A.growth_potential >= med_pot
    hi_cs = A.cost_to_serve_score >= A.cost_to_serve_score.quantile(0.75)
    A["focus"] = np.select(
        [A.focus_profit_high & A.focus_potential_high,
         A.focus_profit_high & ~A.focus_potential_high,
         ~A.focus_profit_high & A.focus_potential_high,
         ~A.focus_profit_high & ~A.focus_potential_high],
        ["رشد بده", "حفظ کن", "اصلاح کن", "کاهش بده"], default="—")
    A["high_cost_to_serve"] = hi_cs

    # ── «پولی که در این مشتری در حرکت است» — مبنای برش فهرست
    # سالانه‌سازی برای مشتری تازه اغراق می‌کند؛ به کل مقدار مشاهده‌شده محدود می‌شود
    ann = np.minimum(12 / A.months.clip(lower=1), 1.0) * 12 / 12
    ann = np.where(A.months >= 12, 12 / A.months.clip(lower=1), 1.0)
    keep = (A.real_gp.clip(lower=0) * ann * (1 - A.retention)).fillna(0)   # با رفتنش چقدر می‌رود
    grow = A.growth_potential.fillna(0)             # با رشد چقدر می‌آید
    # با بردن شرایط پرداخت به مبنای نقدی، چقدر از هزینهٔ پول آزاد می‌شود
    rate = float(A.finance_rate_monthly.iloc[0])
    rev_year = A.revenue * ann
    fixv = (rev_year * rate * (A.days_cash.fillna(cash_days) - cash_days).clip(lower=0)
            / 30).fillna(0)
    A["value_at_play"] = np.maximum.reduce([keep.values, grow.values, fixv.values]).round()
    A["value_at_play_basis"] = np.select(
        [keep.values >= np.maximum(grow.values, fixv.values),
         grow.values >= fixv.values],
        ["نگهداشت سود در معرض رفتن", "ظرفیت رشد"], default="اصلاح شرایط پرداخت")
    A["focus_rank"] = A.value_at_play.rank(ascending=False, method="min").astype(int)
    return A


def cut_reason(row) -> str:
    """چرا این مشتری از فهرست تمرکز حذف شد — و چه چیزی نظر ما را عوض می‌کند."""
    if row.get("focus") == "کاهش بده":
        return ("سود واقعی زیر میانه و ظرفیت رشد کم"
                + ("، با هزینهٔ خدمت‌دهی بالا" if row.get("high_cost_to_serve") else "")
                + ". نظرمان عوض می‌شود اگر: شرایط پرداخت به نقدی تغییر کند، یا برآورد "
                  "سهم از سبد با منبع معتبرتری به‌روز شود.")
    if row.get("focus") == "حفظ کن":
        return ("سودآور است ولی ظرفیت رشد باز ندارد؛ تماس کم‌بسامد کافی است. "
                "نظرمان عوض می‌شود اگر نشانهٔ ریزش ببینیم یا برآورد سهم از سبد بالا برود.")
    return ("پول در حرکت این مشتری کمتر از آستانهٔ فهرست است؛ نه ریسک بزرگی در معرض "
            "است نه ظرفیت رشد بزرگی. نظرمان عوض می‌شود اگر رکود بشکند یا شکایت "
            "بحرانی ثبت شود.")


def add_scores(F: pd.DataFrame, MONEY: pd.DataFrame | None = None,
               FINANCE_RATE: float = MN.FINANCE_RATE_MONTHLY) -> pd.DataFrame:
    """RFM، هزینهٔ پول، ماندگاری، LTV، چهارخانه و فهرست تمرکز."""
    F = F.copy()
    has = F.revenue.notna()
    A = F[has].copy()

    # ── هزینهٔ پول باید پیش از RFM محاسبه شود، چون بُعد M روی سود واقعی است
    if MONEY is not None:
        A = MN.add_money_columns(A, MONEY, FINANCE_RATE)

    # ── RFM
    # دام ۱ راهنمای داوران: «M روی فروش، تله است. مشتری بزرگ با تخفیف عمیق و
    # برگشتی زیاد می‌تواند ۵-۵-۵ بگیرد و باز هم برای شما زیان‌ده باشد.»
    # پس بُعد پولی روی **سود واقعی پس از هزینهٔ پول** است، نه فروش.
    A["R"] = pd.qcut(-A.recency, 5, labels=[1, 2, 3, 4, 5], duplicates="drop").astype(int)
    A["Fq"] = pd.qcut(A.months.rank(method="first"), 5, labels=[1, 2, 3, 4, 5],
                      duplicates="drop").astype(int)
    m_basis = A.real_gp if "real_gp" in A.columns else A.revenue_real
    A["M"] = pd.qcut(m_basis.rank(method="first"), 5, labels=[1, 2, 3, 4, 5],
                     duplicates="drop").astype(int)
    A["m_basis"] = "سود واقعی پس از هزینهٔ پول" if "real_gp" in A.columns else "فروش حقیقی"
    A["RFM"] = A.R.astype(str) + A.Fq.astype(str) + A.M.astype(str)
    A["rfm_segment"] = [rfm_segment(r, f, m) for r, f, m in zip(A.R, A.Fq, A.M)]

    # ── ماندگاری، تجزیه‌شده
    comps = A.apply(retention_components, axis=1)
    A["retention_components"] = comps
    A["retention_raw"] = [float(np.clip(RETENTION_BASE + sum(c["delta"] for c in cs), 0.02, 0.97))
                          for cs in comps]
    A["retention"] = A.retention_raw.apply(calibrate)

    # ── LTV، تجزیه‌شده
    A["ltv_historic"] = A.gp - A.overdue
    A["ltv_collection_factor"] = (A.collection_rate.fillna(90) / 100).clip(0, 1)
    A["ltv_future"] = A.gp_monthly * A.retention * DISCOUNT_FACTOR * A.ltv_collection_factor
    A["ltv_total"] = A.ltv_historic + A.ltv_future
    A["ltv_rank"] = A.ltv_total.rank(ascending=False, method="min").astype(int)
    A["revenue_rank"] = A.revenue.rank(ascending=False, method="min").astype(int)
    A["gp_rank"] = A.gp.rank(ascending=False, method="min").astype(int)
    A["rank_gap"] = A.revenue_rank - A.ltv_rank      # مثبت = LTV بهتر از رتبهٔ فروش

    # ── رتبه‌بندی حاشیهٔ واقعی در برابر حاشیهٔ ناخالص
    if MONEY is not None:
        A["real_gp_monthly"] = A.real_gp / A.months.clip(lower=1)
        A["net_gp_monthly"] = A.net_gp / A.months.clip(lower=1)
        A["real_margin_rank"] = A.real_margin.rank(ascending=False, method="min").astype(int)
        A["margin_rank"] = A.margin.rank(ascending=False, method="min").astype(int)
        A["margin_rank_gap"] = A.margin_rank - A.real_margin_rank

    # ── چهارخانه
    med = A.margin.median()
    A["portfolio_median_margin"] = med
    good = A.margin >= med
    risk = A.retention < 0.5
    A["quadrant"] = np.select(
        [good & ~risk, good & risk, ~good & ~risk, ~good & risk],
        ["رشد بده", "نجات فوری", "اصلاح قیمت", "بازبینی رابطه"], default="—")
    # اولویت نجات: سود ماهانه × احتمال از دست دادن
    A["rescue_value"] = A.gp_monthly * (1 - A.retention) * 12
    A["rescue_rank"] = A.rescue_value.rank(ascending=False, method="min").astype(int)

    # ═══ فهرست تمرکز — «کدام مشتری‌ها باید توجه کمتری بگیرند؟»
    if MONEY is not None:
        A = _add_focus(A)

    for c in A.columns:
        if c not in F.columns:
            F[c] = pd.Series(dtype=A[c].dtype) if c != "retention_components" else None
    for c in A.columns:
        F.loc[A.index, c] = A[c]
    return F


def features_to_dict(f: pd.Series) -> dict[str, Any]:
    """ویژگی‌های یک مشتری، آمادهٔ JSON."""
    def n(v):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return None
        if isinstance(v, (np.bool_, bool)):
            return bool(v)
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return round(float(v), 4)
        if isinstance(v, pd.Timestamp):
            return str(v.date())
        return v

    keep = [
        "R", "Fq", "M", "RFM", "rfm_segment", "retention", "retention_raw",
        "R_prev", "Fq_prev", "M_prev", "RFM_prev", "dR", "dF", "dM",
        "rfm_move", "rfm_move_label", "rfm_alert", "rfm_move_days", "m_basis",
        "days_cash", "open_balance", "expected_writeoff", "cost_of_money_pct",
        "cost_of_money", "real_margin", "real_gp", "writeoff_pct", "net_margin",
        "net_gp", "finance_rate_monthly", "real_gp_monthly", "net_gp_monthly",
        "real_margin_rank", "margin_rank", "margin_rank_gap",
        "focus", "focus_profit_high", "focus_potential_high", "high_cost_to_serve",
        "growth_potential", "potential_basis", "cost_to_serve_score",
        "achievable_real_margin", "value_at_play", "value_at_play_basis", "focus_rank",
        "ltv_historic", "ltv_future", "ltv_total", "ltv_rank", "ltv_collection_factor",
        "revenue_rank", "gp_rank", "rank_gap", "quadrant", "rescue_value", "rescue_rank",
        "portfolio_median_margin", "margin_vs_segment", "segment_avg_margin",
        "gp_monthly", "vol_monthly", "rev_monthly_real", "order_gap", "order_gap_cv",
        "silence_ratio", "active_ratio", "top_family_share", "price_cv", "qty_cv",
        "families", "products", "quality_classes", "lines_per_invoice", "avg_line",
        "margin6", "margin_drift", "touch_per_month", "chase_share", "open_actions",
        "oldest_overdue_days", "credit_util", "wallet_trend", "wallet_last",
        "realized_cost_share", "cv_evenness", "price_pressure_signals",
    ]
    out = {k: n(f.get(k)) for k in keep if k in f.index}
    comps = f.get("retention_components")
    out["retention_components"] = comps if isinstance(comps, list) else []
    out["retention_horizon_months"] = LTV_HORIZON_MONTHS
    out["ltv_discount_factor"] = round(DISCOUNT_FACTOR, 2)
    return out


# ═══════════════════════════════════ الگوهای سنجیده‌شده (برای نمایش)
VALIDATED_PATTERNS = [
    {
        "id": "family_breadth",
        "title": "خرید از دو گروه کالا یا بیشتر، ماندگاری را حدود ۲۰ واحد درصد بالا می‌برد",
        "status": "تأییدشده",
        "evidence": ("در پنجرهٔ آزمون، داخل مشتریان ۳ تا ۶ ماه فعال: تک‌گروه ۵۱٪ بازگشت در "
                     "برابر چندگروه ۷۱٪. داخل ۷ تا ۱۲ ماه فعال: ۶۱٪ در برابر ۸۳٪. "
                     "در پنجرهٔ آموزش هم تکرار شد (۶۰٪ در برابر ۷۹٪ و ۸۱٪ در برابر ۹۷٪)."),
        "control": "با کنترل عمق رابطه (تعداد ماه فعال) باقی می‌ماند، پس اثر «بیشتر خریدن» نیست.",
        "action": "فروش مکمل یک گروه کالای دوم، بالاترین اهرم ماندگاری در این سبد است.",
        "caveat": "حاشیه سود چندگروه حدود یک واحد درصد کمتر است؛ ماندگاری با هزینهٔ حاشیه می‌آید.",
    },
    {
        "id": "complaint_no_signal",
        "title": "شکایت، به‌تنهایی پیش‌بین ریزش نیست",
        "status": "رد شد",
        "evidence": ("در نگاه اول مشتریان شاکی ماندگارتر به نظر می‌رسند (۳۴٪ راکد در برابر ۶۹٪)، "
                     "ولی این کاملاً از عمق رابطه می‌آید: مشتری یک‌بارمصرف نه شکایت می‌کند نه "
                     "برمی‌گردد. با کنترل عمق، اثر محو می‌شود — ۷ تا ۱۲ ماه فعال: "
                     "۷۹٪ بازگشت بی‌شکایت در برابر ۷۴٪ با شکایت."),
        "control": "کنترل‌شده با تعداد ماه فعال و آزموده با نتیجهٔ واقعی ۱۲ ماه بعد.",
        "action": "شکایت را برای خودش رسیدگی کنید، نه به‌عنوان زنگ خطر ریزش.",
        "caveat": "مقایسهٔ پیش/پس از شکایت در سطح یک مشتری خاص هنوز معنادار است؛ آن پرسش دیگری است.",
    },
    {
        "id": "dev_no_signal",
        "title": "درخواست توسعه محصول هم پیش‌بین مستقل ریزش نیست",
        "status": "رد شد",
        "evidence": ("ظاهراً قوی بود (۷۰٪ راکد بدون درخواست در برابر ۲۰٪ با ۳+ درخواست)، ولی "
                     "با کنترل عمق ناپدید شد: ۷ تا ۱۲ ماه فعال، ۷۹٪ بازگشت بدون درخواست در "
                     "برابر ۷۷٪ با درخواست."),
        "control": "کنترل‌شده با تعداد ماه فعال، آزموده با نتیجهٔ واقعی.",
        "action": "درخواست بی‌پاسخ را به‌عنوان فرصت فروش پیگیری کنید، نه شاخص ریسک.",
        "caveat": "",
    },
    {
        "id": "long_term_terms",
        "title": "شرایط پرداخت بلندمدت هم حاشیه و هم وصول را بدتر می‌کند",
        "status": "نشانهٔ ضعیف",
        "evidence": ("در بزرگ‌ترین چارک: بلندمدت حاشیه ۷.۸٪ و وصول ۸۱.۳٪، در برابر "
                     "نقدی ۹.۰٪/۸۷.۵٪ و کوتاه‌مدت ۹.۲٪/۸۶.۹٪. جهت اثر در همهٔ چارک‌های "
                     "اندازه یکسان است."),
        "control": "با کنترل چارک اندازه بررسی شد.",
        "action": "پیش از تمدید شرایط بلندمدت، اثر دوگانه‌اش را در قیمت لحاظ کنید.",
        "caveat": "تنها ۲۱ مشتری بلندمدت‌اند؛ جهت اثر پایدار است ولی نمونه کوچک است.",
    },
    {
        "id": "new_customer_loss",
        "title": "مشتریان تازه‌وارد در مجموع زیان‌ده‌اند",
        "status": "تأییدشده",
        "evidence": "بخش «تازه‌وارد» در RFM با ۲۳ مشتری، سود ناخالص انباشتهٔ منفی دارد.",
        "control": "مستقیم از تجمیع سود ناخالص همان بخش.",
        "action": "قیمت‌گذاری سفارش نخست را بازبینی کنید؛ جذب با قیمت زیر بهای تمام‌شده انجام می‌شود.",
        "caveat": "",
    },
]
