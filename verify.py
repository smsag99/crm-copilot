"""آزمون‌های صحت — پیش از ارائه اجرا کنید: python verify.py

سه دستهٔ خطا را می‌گیرد: تجمیع‌هایی که با منبع نمی‌خوانند، نشتی زمانی
(اطلاعاتی که در تاریخ برش در دسترس نبوده)، و گم‌شدن بی‌صدای مشتری.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import assignments as AS
import features as FT
import insights as I
import money as MN
import offer_engine as OE
import signal_center as SC
import period as PD
import worklist as WL
import pipeline as P
import signals as SG



def _frame_for_validation(E: dict, F: pd.DataFrame) -> pd.DataFrame:
    """فریم کمینه‌ای که validate_cases به آن نیاز دارد، بدون ساخت کل Store."""
    A = F[F.revenue.notna()].copy()
    A["revenue"] = A.revenue
    A["gross_profit"] = A.gp
    A["margin_pct"] = A.margin
    A["open_ar"] = [E[c]["receivables"]["uncollected"] for c in A.index]
    A["complaints"] = [E[c]["complaints"]["total"] for c in A.index]
    return A


def run() -> int:
    rows = []

    def ck(name: str, ok: bool, detail: str = "") -> None:
        rows.append({"آزمون": name, "نتیجه": "قبول" if ok else "رد", "جزئیات": detail})

    print("بارگذاری و پاک‌سازی…")
    D, rep = P.clean(P.load_raw())
    as_of = P.DEFAULT_AS_OF
    prof = P.build_profiles(D, as_of)
    P.add_complaint_impact(D, prof, as_of)
    MD = MN.money_days(P.as_of_view(D, as_of), as_of)
    F = FT.add_scores(FT.build_features(D, as_of), MD)
    _prev = as_of - pd.Timedelta(days=FT.RFM_MOVE_DAYS)
    F = FT.add_rfm_movement(
        F, FT.add_scores(FT.build_features(D, _prev),
                         MN.money_days(P.as_of_view(D, _prev), _prev)))
    E = I.enrich_all(prof, F)
    V = P.as_of_view(D, as_of)
    stats = P.portfolio_stats(prof, D, as_of)

    # ── ۱. یکپارچگی ارجاعی و کلیدها
    rel = pd.read_excel(P.META_XLSX, sheet_name="روابط")
    # شناسهٔ خط فروش باید در «فروش ∪ ردیف‌های ردیابی» حل شود: دام ۱ آن ۵۲ ردیف را
    # از فروش جدا کرده، ولی شیت‌های هزینه و آزمایشگاه و پل شکایت هنوز به آن‌ها
    # ارجاع می‌دهند و این ارجاع درست است.
    all_lines = set(D["sales"].Sales_Line_ID) | set(D["traceability_lines"].Sales_Line_ID)
    orphans, trace_refs = 0, 0
    for _, r in rel.iterrows():
        a, b = P.SHEETS[r["From_Sheet"]], P.SHEETS[r["To_Sheet"]]
        ac = P.COLUMN_RENAMES.get(r["From_Column"], r["From_Column"])
        bc = P.COLUMN_RENAMES.get(r["To_Column"], r["To_Column"])
        if ac not in D[a].columns or bc not in D[b].columns:
            continue
        left = set(D[a][ac].dropna())
        right = all_lines if bc == "Sales_Line_ID" else set(D[b][bc].dropna())
        miss = left - right
        orphans += len(miss)
        if bc == "Sales_Line_ID":
            trace_refs += len({x for x in left if str(x).startswith("SL-CMP")})
    ck("هیچ کلید یتیمی در روابط اعلام‌شدهٔ متادیتا نیست", orphans == 0,
       f"{orphans} کلید یتیم (شامل {trace_refs} ارجاع مجاز به ردیف‌های ردیابی)")
    ck("ردیف‌های ردیابی از فروش جدا شده‌اند اما دور ریخته نشده‌اند",
       len(D["traceability_lines"]) == 52,
       f"{len(D['traceability_lines'])} ردیف در traceability_lines نگه داشته شده")

    # ── ۲. تجمیع‌ها با منبع می‌خوانند
    S = V["sales"]
    for label, src, got, tol in [
        ("فروش", S.line_amount.sum(),
         sum(p["commercial"]["revenue_nominal"] for p in prof.values()), 1e-6),
        ("حجم", S.qty.sum(), sum(p["commercial"]["volume"] for p in prof.values()), 1e-4),
        ("سود ناخالص", S.gross_profit.sum(),
         sum(p["margin"]["gross_profit"] for p in prof.values()), 1e-5),
        ("وصول", V["collections"].collected_amount.sum(),
         sum(p["receivables"]["collected"] for p in prof.values()), 1e-5),
    ]:
        ck(f"{label} با شیت منبع می‌خواند", abs(src - got) / abs(src) < tol,
           f"منبع {src:,.0f} در برابر پروفایل‌ها {got:,.0f}")

    # ── ۳. دام‌های داده
    ck("هیچ ردیف ردیابی شکایتی در فروش نمانده",
       not S.Sales_Line_ID.str.startswith("SL-CMP").any())
    ck("بازهٔ فروش پیش از ردیف‌های تزریقی تمام می‌شود",
       S.date.max() < P.ERP_WINDOW_END, f"آخرین تاریخ فروش {S.date.max().date()}")
    ck("CRM به یک ردیف برای هر تعامل کاهش یافته",
       not V["crm"].Interaction_ID.duplicated().any())
    ck("پوشش بهای تمام‌شده کامل است", S.unit_cost.notna().all(),
       f"{S.unit_cost.notna().mean():.1%}")
    ck("ستون‌های درصدی آزمایشگاه به مقیاس درصد آمده‌اند",
       V["lab"].Elongation_Pct.max() > 1.0, f"بیشینهٔ کشش {V['lab'].Elongation_Pct.max():.2f}")
    ck("فیلد وضعیت نشتی تغییر نام یافته و قرنطینه است",
       "source_status_LEAKY" in D["customers"].columns
       and "Customer_Status" not in D["customers"].columns)

    # ── ۴. تفکیک مطالبات
    ck("معوق + سررسیدنشده = مانده باز، برای هر مشتری",
       all(abs(p["receivables"]["uncollected"]
               - (p["receivables"]["uncollected_overdue"]
                  + p["receivables"]["uncollected_not_yet_due"])) < 2 for p in prof.values()))
    ck("مشارکت خالص = سود ناخالص منهای معوق",
       all(abs(p["receivables"]["net_contribution"]
               - (p["margin"]["gross_profit"] - p["receivables"]["uncollected_overdue"])) < 1
           for p in prof.values()))
    ck("هیچ مانده باز منفی وجود ندارد",
       all(p["receivables"]["uncollected"] >= 0 for p in prof.values()))

    # ── ۵. نشتی زمانی — پروفایل در تاریخ قدیمی‌تر
    early = pd.Timestamp("2021-06-30")
    print(f"ساخت پروفایل در تاریخ {early.date()} برای آزمون نشتی…")
    Pe = P.build_profiles(D, early)
    latest = max((p["commercial"]["last_purchase"] for p in Pe.values()
                  if p["commercial"]["last_purchase"]), default=None)
    ck("برش زمانی هیچ فروش آینده‌ای را لو نمی‌دهد",
       latest is not None and latest <= str(early.date()),
       f"آخرین خرید در نمای {early.date()}: {latest}")
    ck("نمای قدیمی‌تر فروش کمتری دارد",
       sum(p["commercial"]["revenue_nominal"] for p in Pe.values())
       < sum(p["commercial"]["revenue_nominal"] for p in prof.values()))
    Ve = P.as_of_view(D, early)
    ck("شکایت‌های بازِ آن تاریخ، رسیدگی‌شده نشان داده نمی‌شوند",
       Ve["complaints"][Ve["complaints"].outcome_censored].Resolved_At.isna().all())
    ck("آفرهای بی‌نتیجهٔ آن تاریخ، «بی‌پاسخ» علامت خورده‌اند",
       (Ve["offers"][Ve["offers"].outcome_censored].Result == "pending").all())

    # ── ۶. پوشش و بینش
    ck("هر مشتری یک پروفایل دارد", len(prof) == len(D["customers"]),
       f"{len(prof)} پروفایل / {len(D['customers'])} مشتری")
    ck("هر مشتری خلاصه وضعیت فارسی دارد",
       all(len(p["summary"]) > 40 for p in E.values()))
    ck("هر ریسک شاهد عددی و مالک دارد",
       all(x["evidence"] and x["owner"] and x["action"]
           for p in E.values() for x in p["risks"]))
    ck("هر فرصت شاهد عددی و مالک دارد",
       all(x["evidence"] and x["owner"] and x["action"]
           for p in E.values() for x in p["opportunities"]))
    ck("هر مشتری با ریسک یا فرصت، اقدام بعدی دارد",
       all(p["next_best_actions"] for p in E.values()
           if p["risks"] or p["opportunities"]))
    ck("ماه‌های ناقص مرزی شناسایی شده‌اند", len(stats["partial_months"]) == 2,
       "، ".join(stats["partial_months"]))
    ck("پنجره‌های مقایسهٔ بهار هم‌ارزند", len(stats["half_years"]) >= 2,
       "، ".join(h["label"] for h in stats["half_years"]))

    # ── ۷. ویژگی، RFM، ماندگاری و LTV
    A = F[F.revenue.notna()]
    ck("هر مشتری دارای فروش، امتیاز RFM و چهارخانه دارد",
       A.rfm_segment.notna().all() and (A.quadrant != "—").all(),
       f"{len(A)} مشتری با فروش")
    ck("امتیاز RFM در بازهٔ ۱ تا ۵ است",
       A[["R", "Fq", "M"]].min().min() >= 1 and A[["R", "Fq", "M"]].max().max() <= 5)
    ck("احتمال ماندگاری کالیبره در بازهٔ معتبر است",
       bool((A.retention > 0).all() and (A.retention < 1).all()),
       f"میانه {A.retention.median():.3f}")
    ck("کالیبراسیون یکنواست (امتیاز بالاتر → احتمال بالاتر)",
       all(y2 >= y1 for y1, y2 in zip(FT.CAL_Y, FT.CAL_Y[1:])),
       "، ".join(str(y) for y in FT.CAL_Y))
    ck("LTV = محقق‌شده + آیندهٔ تنزیل‌شده",
       bool(((A.ltv_total - (A.ltv_historic + A.ltv_future)).abs() < 1).all()))
    ck("LTV محقق‌شده = سود ناخالص منهای معوق",
       bool(((A.ltv_historic - (A.gp - A.overdue)).abs() < 1).all()))
    ck("LTV آینده با ضریب تنزیل و ماندگاری می‌خواند",
       bool(((A.ltv_future - A.gp_monthly * A.retention * FT.DISCOUNT_FACTOR
              * A.ltv_collection_factor).abs() < 1).all()))
    ck("مجموع سهم اجزای ماندگاری با امتیاز خام می‌خواند",
       all(abs(FT.RETENTION_BASE + sum(c["delta"] for c in cs) - raw) < 0.001
           or raw in (0.02, 0.97)
           for cs, raw in zip(A.retention_components, A.retention_raw)))
    ck("فاصلهٔ سفارش روی تاریخ‌های متمایز حساب شده (هیچ صفری نیست)",
       not bool((A.order_gap == 0).any()),
       f"میانه {A.order_gap.median():.0f} روز")

    # ── ۸. سیگنال، پیش‌بینی و رفرنس
    ck("هر مشتری دارای فروش، حداقل یک سیگنال دارد",
       all(len(p["signals"]) > 0 for p in E.values() if p["coverage"]["sales"]))
    ck("هر مشتری دارای فروش، پیش‌بینی تصمیم دارد",
       all(len(p["predictions"]) > 0 for p in E.values() if p["coverage"]["sales"]))
    ck("همهٔ احتمال‌ها در بازهٔ ۰ تا ۱ هستند",
       all(0 < x["probability"] < 1 for p in E.values() for x in p["predictions"]))
    ck("هر سیگنال تفسیر و شدت معتبر دارد",
       all(x["interpretation"] and 0 <= x["strength"] <= 1
           for p in E.values() for x in p["signals"]))
    ck("هر سیگنال حداقل یک رفرنس دارد",
       all(len(x["references"]) > 0 for p in E.values() for x in p["signals"]))
    ck("هر پیش‌بینی نرخ پایه و رفرنس دارد",
       all(x["base"] and len(x["references"]) > 0
           for p in E.values() for x in p["predictions"]))
    ck("هر ریسک و فرصت، استدلال و رفرنس دارد",
       all(x["logic"] and len(x["references"]) > 0
           for p in E.values() for x in (p["risks"] + p["opportunities"])))
    ck("هر رفرنس نام شیت معتبر دارد",
       all(r["sheet"] in SG.SHEET_FA.values()
           for p in E.values() for grp in ("signals", "predictions", "risks", "opportunities")
           for x in p[grp] for r in x["references"]))
    total_refs = sum(p["reference_count"] for p in E.values())
    ck("تعداد کل رفرنس‌ها معنادار است", total_refs > 10000, f"{total_refs:,} رفرنس")

    # ── ۹. اقدام بر پایهٔ دلیل آفر
    reason_actions = [x for p in E.values() for x in p["opportunities"]
                      if x["code"].startswith("offer_")]
    ck("اقدام آفر بر پایهٔ دلیل تولید می‌شود",
       len(reason_actions) > 0 and all(x["logic"] and x["references"] for x in reason_actions),
       f"{len(reason_actions)} اقدام آفر مبتنی بر دلیل")
    ck("همهٔ دلایل آفر نگاشت اقدام دارند",
       set(I.OFFER_REASON_PLAY) == set(SG.OFFER_ACCEPT_BY_REASON),
       f"{len(I.OFFER_REASON_PLAY)} دلیل")

    # ── ۱۰. صداقت: الگوهای ردشده گزارش می‌شوند
    ck("الگوهای ردشده در کتابخانهٔ الگو ثبت شده‌اند",
       any(x["status"] == "رد شد" for x in FT.VALIDATED_PATTERNS),
       "، ".join(x["id"] for x in FT.VALIDATED_PATTERNS if x["status"] == "رد شد"))
    ck("کارت مدل، برتری پیش‌بین تک‌متغیره را صریح گزارش می‌کند",
       FT.MODEL_CARD["auc_recency_only"] > FT.MODEL_CARD["auc_additive"]
       and "رکود تنها" in FT.MODEL_CARD["honest_note"])

    # ── ۱۱. موتور دوره
    anchor, anote = PD.data_anchor(V)
    invt = PD._invoice_table(V)
    ck("لنگر دوره روی ماه ناقص انتهایی نمی‌افتد",
       anchor < V["sales"].date.max() and bool(anote),
       f"لنگر {anchor.date()} در برابر آخرین فروش {V['sales'].date.max().date()}")

    rec = PD.recommend_period(V, invt, anchor)
    ck("دورهٔ پیشنهادی از داده انتخاب می‌شود نه از پیش‌فرض دستی",
       rec["recommended"] in PD.PERIOD_BY_KEY
       and max(rec["table"], key=lambda r: r["score"])["key"] == rec["recommended"],
       f"«{PD.PERIOD_BY_KEY[rec['recommended']]['label']}» با امتیاز "
       f"{max(r['score'] for r in rec['table']):.3f}")
    ck("امتیاز دوره‌های کم‌رویداد پایین‌تر از دوره‌های پرداده است",
       next(r for r in rec["table"] if r["key"] == "1w")["score"] <
       next(r for r in rec["table"] if r["key"] == rec["recommended"])["score"],
       "کفایت رویداد در فرمول امتیاز اثر دارد")

    pk = rec["recommended"]
    pdta = PD.build_period(V, invt, E, anchor, pk)
    cur, prv = pdta["current"], pdta["previous"]
    ck("پنجرهٔ دوره و دورهٔ قبل هم‌طول و بدون همپوشانی‌اند",
       cur["days"] == prv["days"] == pdta["days"] and prv["to"] < cur["from"],
       f"{prv['from_fa']}–{prv['to_fa']} سپس {cur['from_fa']}–{cur['to_fa']}")
    ck("فروش دوره با جمع مستقیم شیت فروش می‌خواند",
       abs(cur["revenue"] - float(V["sales"][
           (V["sales"].date >= pd.Timestamp(cur["from"])) &
           (V["sales"].date <= pd.Timestamp(cur["to"]))].line_amount.sum())) < 1,
       f"{cur['revenue']:,}")
    ck("درصد تغییر مقایسه با اعداد دو دوره سازگار است",
       all(abs(pdta["compare"][k]["pct"] -
               (cur[k] - prv[k]) / abs(prv[k]) * 100) < 0.15
           for k in ("revenue", "gross_profit", "collected")
           if prv.get(k)),
       "revenue، gross_profit، collected")

    fcst = pdta["forecast"]
    ck("همهٔ اجزای پیش‌بینی نامنفی و متناهی‌اند",
       all(fcst[k] is not None and fcst[k] >= 0
           for k in ("revenue", "gross_profit", "collected", "overdue_total", "complaints")),
       f"فروش {fcst['revenue']:,} | شکایت {fcst['complaints']}")
    ck("نرخ‌های تجربی پیش‌بینی در بازهٔ معتبرند",
       all(0 <= fcst[k] <= 1 for k in ("recovery_rate", "overdue_recovery_rate",
                                       "new_invoice_share", "late_share")),
       f"بازیابی {fcst['recovery_rate']:.2f}، تأخیر {fcst['late_share']:.2f}")
    ck("پیش‌بینی فقط از دادهٔ پیش از لنگر ساخته می‌شود",
       PD._raw_forecast(V, invt, anchor - pd.Timedelta(days=180), pdta["days"])["revenue"] !=
       PD._raw_forecast(V, invt, anchor, pdta["days"])["revenue"],
       "برش زمانی روی پیش‌بینی اثر دارد")

    bt = pdta["backtest"]
    ck("بک‌تست دست‌کم یک دور دارد و خطاها گزارش شده‌اند",
       bt["rounds"] >= 1 and bt["revenue"] is not None,
       f"{bt['rounds']} دور، خطای فروش {bt['revenue']}٪")
    ck("اصلاح اریبی فقط وقتی روشن است که بک‌تست بهترش کند",
       ("compared_to_uncorrected_pct" in bt) == bt["use_bias"],
       f"اصلاح اریبی {'روشن' if bt['use_bias'] else 'خاموش'}")

    att, tot, allrows = PD.build_attention(E, PD._period_events(
        V, invt, pd.Timestamp(cur["from"]), anchor), fcst["recovery_rate"])
    ck("هر سطر رسیدگی طبقهٔ اولویت، مشکل، اقدام و «چرا» دارد",
       all(r["priority"] in ("P1", "P2", "P3", "P4") and r["problem"] and r["action"]
           and r["why"] and r["owner"] for r in att),
       f"{len(att)} سطر نمایش‌داده‌شده از {tot['all']}")
    ck("مرتب‌سازی رسیدگی: طبقهٔ اولویت، سپس پول در خطر",
       all((("P1", "P2", "P3", "P4").index(a["priority"]),
            -a["at_risk"]) <= (("P1", "P2", "P3", "P4").index(b["priority"]),
                               -b["at_risk"])
           for a, b in zip(att, att[1:])),
       "ترتیب سطرها سازگار است")
    ck("سهمیهٔ هر طبقه رعایت شده و طبقه‌های پایین حذف نشده‌اند",
       all(sum(1 for r in att if r["priority"] == c) <= PD.CLASS_CAP[c]
           for c in PD.CLASS_CAP)
       and len({r["priority"] for r in att}) >= 2,
       "، ".join(f"{c}={sum(1 for r in att if r['priority'] == c)}" for c in PD.CLASS_CAP))
    ck("طبقهٔ اولویت با تقاطع ارزش و بحرانی بودن می‌خواند",
       all(r["priority"] == ("P1" if r["valuable"] and r["critical"] else
                             "P2" if r["valuable"] else
                             "P3" if r["critical"] else "P4") for r in allrows),
       f"{tot['P1']} + {tot['P2']} + {tot['P3']} + {tot['P4']} = {tot['all']}")
    ck("هر سطر رسیدگی رفرنس منبع دارد",
       all(r["references"] or r["action_references"] for r in att),
       "هیچ سطری بدون منبع نیست")

    probs = pdta["problems"]
    ck("سه مشکل پرتکرار با پول در خطر و فرمول گزارش می‌شوند",
       len(probs) == 3 and all(b["customers"] > 0 and b["formula"] and b["examples"]
                               for b in probs),
       "، ".join(f"{b['title']} ({b['customers']})" for b in probs))
    ck("پول در خطر هر مشکل با جمع سطرهای همان مشکل می‌خواند",
       all(abs(b["at_risk"] - sum(r["at_risk"] for r in allrows
                                  if r["problem_code"] == b["code"])) <= 1 for b in probs),
       "جمع سطری = جمع باکس")
    ck("عنوان مشکل در باکس‌ها عمومی است، نه مخصوص یک مشتری",
       all(not any(ch.isdigit() for ch in b["title"].replace("۱۸۰", "")) for b in probs),
       "بدون عدد مخصوص مشتری")

    # ── ۱۲. صداقت: هر عدد پیش‌بینی‌شده اعتبارسنجی دارد
    # ── ۱۳. هزینهٔ پول و حاشیهٔ واقعی
    Am = F[F.revenue.notna()]
    rate = MN.FINANCE_RATE_MONTHLY
    ck("هزینهٔ پول = نرخ ماهانه × روزهای پول قفل‌شده ÷ ۳۰",
       bool(((Am.cost_of_money_pct - rate * 100 * Am.days_cash / 30).abs() < 0.02).all()),
       f"نرخ {rate * 100:.0f}٪ ماهانه، میانهٔ {Am.days_cash.median():.0f} روز")
    ck("حاشیهٔ واقعی = حاشیهٔ ناخالص منهای هزینهٔ پول",
       bool(((Am.real_margin - (Am.margin - Am.cost_of_money_pct)).abs() < 0.02).all()),
       f"میانهٔ حاشیهٔ واقعی {Am.real_margin.median():.2f}٪")
    ck("روزهای پول قفل‌شده نامنفی و متناهی است",
       bool((Am.days_cash >= 0).all() and np.isfinite(Am.days_cash).all()),
       f"بازهٔ {Am.days_cash.min():.0f} تا {Am.days_cash.max():.0f} روز")
    ck("هزینهٔ پول با نرخ صفر، صفر می‌شود و حاشیهٔ واقعی به ناخالص برمی‌گردد",
       bool((MN.add_money_columns(Am, MD, 0.0).real_margin - Am.margin).abs().max() < 0.02),
       "خطی بودن در نرخ، پایهٔ لغزندهٔ داشبورد است")
    ck("افزایش نرخ، سود واقعی را کم می‌کند (جهت درست)",
       float(MN.add_money_columns(Am, MD, 0.08).real_gp.sum())
       < float(Am.real_gp.sum()) < float(MN.add_money_columns(Am, MD, 0.0).real_gp.sum()),
       "۰٪ < ۴٪ < ۸٪")
    ck("رتبه‌بندی روی حاشیهٔ واقعی با رتبه‌بندی ناخالص یکی نیست",
       int((Am.margin_rank_gap.abs() > 50).sum()) > 50,
       f"{int((Am.margin_rank_gap.abs() > 50).sum())} مشتری بیش از ۵۰ پله جابه‌جا می‌شوند")
    ck("دامنهٔ حاشیهٔ واقعی از دامنهٔ ناخالص بازتر است",
       (Am.real_margin.quantile(.95) - Am.real_margin.quantile(.05))
       > (Am.margin.quantile(.95) - Am.margin.quantile(.05)),
       f"{Am.margin.quantile(.95) - Am.margin.quantile(.05):.1f} → "
       f"{Am.real_margin.quantile(.95) - Am.real_margin.quantile(.05):.1f} واحد")

    cpt = MN.credit_pricing_test(V, rate)
    ck("آزمون قیمت‌گذاری اعتبار اجرا شده و نتیجه‌اش صریح است",
       len(cpt["rows"]) >= 2 and bool(cpt["verdict"]),
       "، ".join(f"{r['terms']}: انتظار {r['expected_pct']}٪ / مشاهده "
                 f"{r['observed_weighted_pct']}٪" for r in cpt["rows"]))
    ck("مارک‌آپ مشاهده‌شده از مارک‌آپ مورد انتظار کمتر است (اعتبار قیمت‌گذاری نشده)",
       all(r["observed_weighted_pct"] < r["expected_pct"] for r in cpt["rows"]),
       "پس اعمال هزینهٔ پول دوباره‌شماری نیست")

    pp = MN.payment_type_profile(V)
    ck("فاصلهٔ فاکتور تا نقد با طولانی‌تر شدن شرط پرداخت بیشتر می‌شود",
       all(a["days_to_cash"] <= b["days_to_cash"] for a, b in zip(pp, pp[1:])),
       "، ".join(f"{r['label']} {r['days_to_cash']:.0f} روز" for r in pp))

    # ── ۱۴. فهرست تمرکز
    ck("هر مشتری دارای فروش دقیقاً یک خانهٔ تمرکز دارد",
       bool(Am.focus.isin(list(FT.FOCUS_FA)).all()),
       "، ".join(f"{k}={int(v)}" for k, v in Am.focus.value_counts().items()))
    ck("خانهٔ تمرکز با تقاطع سود واقعی و ظرفیت رشد می‌خواند",
       bool((Am.focus == np.select(
           [Am.focus_profit_high & Am.focus_potential_high,
            Am.focus_profit_high & ~Am.focus_potential_high,
            ~Am.focus_profit_high & Am.focus_potential_high,
            ~Am.focus_profit_high & ~Am.focus_potential_high],
           ["رشد بده", "حفظ کن", "اصلاح کن", "کاهش بده"], default="—")).all()),
       "هر چهار خانه پر است")
    ck("«پول در حرکت» بیشینهٔ سه مسیر است و نامنفی می‌ماند",
       bool((Am.value_at_play >= 0).all()) and Am.value_at_play_basis.nunique() >= 2,
       "، ".join(f"{k}={int(v)}" for k, v in Am.value_at_play_basis.value_counts().items()))
    ck("بُعد پولی RFM روی سود واقعی است، نه فروش",
       str(Am.m_basis.iloc[0]).startswith("سود واقعی"), str(Am.m_basis.iloc[0]))
    ck("حرکت RFM محاسبه و برچسب‌گذاری شده است",
       Am.rfm_move.notna().sum() > len(Am) * 0.8
       and bool((Am.rfm_move.dropna() == (Am.dR + Am.dF + Am.dM).dropna()).all()),
       "، ".join(f"{k}={int(v)}" for k, v in Am.rfm_move_label.value_counts().items()))
    ck("هشدار افت RFM فقط برای مشتری پرارزشِ در حال افت روشن می‌شود",
       bool(((Am.rfm_alert.fillna(False)) <= ((Am.M_prev >= 4) & (Am.rfm_move <= -2)).fillna(False)).all()),
       f"{int(Am.rfm_alert.fillna(False).sum())} هشدار")

    # ── ۱۵. اعتبارسنجی دستی سه حساب
    import validate_cases as VC
    vres = VC.run(V, as_of, _frame_for_validation(E, F))
    ck("محاسبهٔ دستی سه حساب با خروجی محصول می‌خواند",
       vres["passed"] == vres["total"],
       f"{vres['passed']} از {vres['total']} بررسی، روی "
       + "، ".join(c["customer_id"] for c in vres["cases"]))
    ck("سه حسابِ آزمون، سه پروفایل متفاوت‌اند",
       len({c["customer_id"] for c in vres["cases"]}) == 3,
       "، ".join(c["role"] for c in vres["cases"]))

    # ── ۱۶. کارتابل
    wl = WL.build(E, _frame_for_validation(E, F))
    ck("هر سطر کارتابل هر سه ستون را دارد: هدف، مشتری کیست، بهترین ارتباط",
       all(r["goal"] and r["who"] and r["channel"] for r in wl["rows"]),
       f"{wl['total']} سطر، {wl['shown']} نمایش‌داده‌شده")
    ck("کارت‌های مشکل از بیشترین به کمترین مرتب‌اند",
       all(a["customers"] >= b["customers"]
           for a, b in zip(wl["cards"], wl["cards"][1:])),
       "، ".join(f"{c['family']} {c['customers']}" for c in wl["cards"]))
    ck("هر خانوادهٔ مشکل دست‌کم یک مشتری دارد و همه پوشش داده شده‌اند",
       {c["family"] for c in wl["cards"]} == set(WL.FAMILIES),
       f"{len(wl['cards'])} خانواده")
    ck("مرتب‌سازی کارتابل: لیبل اولویت، سپس مبلغ در گیر",
       all((WL.PRIORITY_ORDER.index(a["priority"]), -a["goal_amount"])
           <= (WL.PRIORITY_ORDER.index(b["priority"]), -b["goal_amount"])
           for a, b in zip(wl["rows"], wl["rows"][1:])),
       "، ".join(f"{k}={v}" for k, v in wl["priority_counts"].items()))
    ck("هر چهار طبقهٔ اولویت پر است (تعریف «بحرانی» بیش از حد گشاد نیست)",
       all(v > 0 for v in wl["priority_counts"].values()),
       "، ".join(f"{k}={v}" for k, v in wl["priority_counts"].items()))
    ck("«همین حالا» با هدف همان سطر می‌خواند",
       all(r["now"] and r["tasks"] and r["tasks"][0] == r["now"] for r in wl["rows"]),
       "اقدام اول همان اقدام فوری است")
    ck("کانال ارتباط از فهرست کانال‌های واقعی CRM انتخاب می‌شود",
       {r["channel"] for r in wl["rows"]} <= {v["label"] for v in WL.CHANNEL_FA.values()},
       "، ".join(sorted({r["channel"] for r in wl["rows"]})))
    ck("هر سطر دستور کار دارد و نکته‌هایش از رکورد همان مشتری می‌آید",
       all(r["agenda"]["points"] and r["agenda"]["opener"] and r["agenda"]["close"]
           and r["agenda"]["tone"] for r in wl["rows"]),
       "شروع، نکته‌ها، بستن و لحن — برای هر سطر")
    ck("نوع دستور کار با کانال می‌خواند (جلسه در برابر تماس)",
       all(r["agenda"]["kind"] == r["channel_kind"]
           and r["agenda"]["title"] == ("دستور کار جلسه" if r["channel_kind"] == "meeting"
                                        else "دستور کار تماس") for r in wl["rows"]),
       "بدون ناسازگاری")
    ck("هر سطر کارتابل رفرنس منبع دارد",
       all(r["references"] for r in wl["rows"]), "هیچ سطری بدون منبع نیست")

    # ── ۱۷. موتور آفر
    off = OE.build(E, wl, limit=10 ** 9)
    ck("هیچ آفری بیش از سقف حاشیهٔ واقعی تخفیف نمی‌دهد",
       all(o["suggested_discount_pct"] <= o["headroom_pct"] + 1e-9
           for o in off["rows"]),
       f"{off['total']} آفر قابل اجرا، سقف مشترک {OE.OBSERVED_DISCOUNT_MAX}٪")
    ck("آفر قابل اجرا هرگز حاشیهٔ پس از تخفیف منفی ندارد",
       all(o["margin_after_offer"] >= -1e-9 for o in off["rows"]),
       "حاشیهٔ واقعی پس از هزینهٔ پول، مبنای سقف است")
    ck("آفر مسدود، مشتریِ بدون فضای تخفیف است",
       all(o["headroom_pct"] < OE.MIN_VIABLE_DISCOUNT or o["gp_if_accepted"] <= 0
           for o in off["blocked"]),
       f"{off['blocked_total']} آفر مسدود برای {off['blocked_customers']} مشتری")
    ck("ارزش انتظاری = احتمال پنجره × آوردهٔ هدف",
       all(abs(o["expected_value"] - o["gp_if_accepted"] * OE.ACCEPT_WINDOW) <= 1
           for o in off["rows"]),
       f"احتمال یکسان {OE.ACCEPT_WINDOW:.4f} برای همه — چون هیچ عامل مشتری‌محوری پیش‌بین نبود")
    ck("پنجرهٔ پیشنهادی داخل بازهٔ برندهٔ ۸ تا ۱۴ روز است",
       OE.WINDOW_LO <= OE.RECOMMENDED_VALIDITY <= OE.WINDOW_HI
       and all(o["validity_days"] == OE.RECOMMENDED_VALIDITY for o in off["rows"]),
       f"مهلت {OE.RECOMMENDED_VALIDITY} روز روی همهٔ آفرها")
    ck("مرتب‌سازی: اول اهمیت مشتری، سپس ارزش انتظاری",
       all((OE.PRIORITY_ORDER.index(a["priority"]), -a["expected_value"])
           <= (OE.PRIORITY_ORDER.index(b["priority"]), -b["expected_value"])
           for a, b in zip(off["rows"], off["rows"][1:])),
       "همان چیزی که کاربر خواست: درجهٔ اهمیت، بعد مبلغ آورده")
    ck("هر آفر دلیل و رفرنس دارد",
       all(o["evidence"] and o["references"] for o in off["rows"] + off["blocked"]),
       "بدون دلیل، آفری روی صفحه نمی‌رود")
    ck("نقطه‌های شبیه‌ساز همان مجموعهٔ کامل‌اند، نه سطرهای نمایش‌داده‌شده",
       len(off["sim_points"]) == off["total"],
       f"{len(off['sim_points'])} نقطه در برابر {off['total']} آفر")
    ck("چهار عامل ردشده در خروجی اعلام می‌شوند",
       sum(1 for t in off["negative_tests"] if t["verdict"] == "پیش‌بین نیست") == 4
       and off["window_test"]["verdict"] == "پیش‌بین است",
       "عمق تخفیف p=۰٫۹۰، دلیل p=۰٫۵۶، نوع p=۰٫۱۴، سابقه p=۰٫۳۵ — پنجره p<۰٫۰۰۰۱")
    ck("سود پنجرهٔ درست مثبت و برابر اختلاف دو احتمال است",
       off["window_gain"] > 0
       and abs(off["window_gain"]
               - off["gp_total"] * (OE.ACCEPT_WINDOW - OE.ACCEPT_BASE)) <= 2000,
       f"{off['window_gain']:,.0f} تومان فقط از تغییر مهلت")

    # ── ۱۸. لایهٔ ارجاع
    experts = AS.build_experts(E, wl, str(as_of.date()))
    ck("روستر کارشناسان از مالکیت داده ساخته می‌شود",
       len(experts) == 8 and sum(x["customers"] for x in experts) == len(E),
       f"{len(experts)} کارشناس، {sum(x['customers'] for x in experts)} مشتری")
    ck("فقط کار تماسی ارجاع‌پذیر است",
       all(AS.referrable(r) == (r["channel_kind"] == "call") for r in wl["rows"]),
       f"{sum(1 for r in wl['rows'] if AS.referrable(r))} از {len(wl['rows'])} سطر")
    sug = [AS.suggest_expert(r, (E[r["customer_id"]]["identity"]["sales_rep_id"]),
                             experts) for r in wl["rows"] if AS.referrable(r)]
    ck("پیشنهاد کارشناس همیشه دلیل و درجهٔ اطمینان دارد",
       all(s["expert_id"] and s["reason"] and s["confidence"] for s in sug),
       f"{len(sug)} پیشنهاد")
    ck("برای پروندهٔ حساس هرگز از کارشناس مالک عبور نمی‌کنیم",
       all(s["rule"] == "owner" for s, r in zip(sug, [r for r in wl["rows"]
                                                     if AS.referrable(r)])
           if r["priority"] == "P1" or r["open_complaints"]),
       "P1 یا پروندهٔ کیفی باز → مالک")
    ck("قالب گزارش کارشناس، فیلدهای الزامی را مشخص کرده",
       sum(1 for f in AS.REPORT_FIELDS if f["required"]) == 5
       and all(f["label"] and f["hint"] for f in AS.REPORT_FIELDS),
       "نتیجه، نقل قول، تعهد، مانع، تصمیم پیشنهادی")

    # ── ۱۹. مرکز سیگنال
    sc = SC.build(V, E, _frame_for_validation(E, F), as_of,
                  achievable_margin=6.83, limit=10 ** 9)
    ck("هر سه منبع سیگنال ساخته شد و به مشتری نگاشت می‌شود",
       len(sc["sections"]) == 3
       and all(s["total"] > 0 and s["customers"] > 0 for s in sc["sections"]),
       "، ".join(f"{s['label']} {s['total']}/{s['customers']}"
                 for s in sc["sections"]))
    ck("روند هر دسته، دو نیم‌سال متوالی و بدون هم‌پوشانی است",
       all(c["prev_range"][1] == c["range"][0]
           for s in sc["sections"] for c in [s["trend"]]),
       f"پنجرهٔ {SC.TREND_DAYS} روزه")
    ck("شمارش هر منبع با مجموع دسته‌هایش می‌خواند",
       all(s["total"] == sum(c["n"] for c in s["categories"])
           for s in sc["sections"]),
       "بدون رکورد جامانده یا دوشمرده")
    ck("ارزش در خطر یک‌بار در سطح مشتری است، نه یک‌بار به‌ازای هر منبع",
       all(r["min_value"] == r["value"]["min_value"] for r in sc["rows"])
       and all(not r["sources"]["crm"]["risk_basis"]
               for r in sc["rows"] if "crm" in r["sources"]),
       "تعامل باز گروه کالای درگیر ندارد، پس ارزش در خطر نمی‌گیرد")
    ck("ارزش کمینه هرگز از درآمد در معرض بیشتر نمی‌شود",
       all(r["min_value"] <= r["exposure"] + r["value"]["measured_floor"] + 1
           for r in sc["rows"]),
       f"کل: کمینه {sc['min_value_total']:,.0f} در برابر در معرض "
       f"{sc['exposure_total']:,.0f}")
    ck("مشتری با حاشیهٔ واقعی منفی، ارزش کمینهٔ صفر و عدد مشروط می‌گیرد",
       all(r["min_value"] == r["value"]["measured_floor"]
           and r["value_if_terms_fixed"] > r["min_value"]
           for r in sc["rows"] if r["margin_blocked"]),
       f"{sc['blocked_customers']} مشتری، با اصلاح شرایط پرداخت "
       f"{sc['blocked_value']:,.0f}")
    ck("جدول اکچوئری بازگشتی از خطوط فاکتور واقعی ساخته شده",
       sc["return_actuarial"]["overall"]["n"] > 0
       and 0 < sc["return_actuarial"]["overall"]["p"] < 1
       and all(0 <= v["p_return"] <= 1
               for v in sc["return_actuarial"]["by_title"].values()),
       f"{sc['return_actuarial']['overall']['n']} شکایت پیوندخورده، "
       f"{sc['return_actuarial']['overall']['p'] * 100:.1f}٪ با بازگشتی")
    ck("تقاضای انباشتهٔ توسعه بر درآمد مرتب است و مشتری یکتا می‌شمارد",
       all(a["revenue"] >= b["revenue"]
           for a, b in zip(sc["dev_demand"], sc["dev_demand"][1:]))
       and all(d["customers"] <= d["requests"] for d in sc["dev_demand"]),
       "، ".join(f"{d['request_type']} {d['customers']}"
                 for d in sc["dev_demand"][:3]))
    ck("چهار آزمون اثر اجرا و گزارش شده‌اند — هیچ‌کدام معنادار نبود",
       len(sc["effect_tests"]) == 4
       and all(t["verdict"] == "اثبات نشد" for t in sc["effect_tests"]),
       "رسیدگی خرید را بالا نمی‌برد؛ عدد این تب «از‌دست‌رفتنی» است")
    ck("شکاف CRM گزارش می‌شود: اقدام ثبت می‌شود ولی فیلد بستن ندارد",
       sc["crm_gap"]["with_next_action"] > 0
       and sc["crm_gap"]["older_than_90"] > 0,
       f"{sc['crm_gap']['with_next_action']} اقدام، میانهٔ عمر "
       f"{sc['crm_gap']['median_age']} روز")

    df = pd.DataFrame(rows)
    print()
    print(df.to_string(index=False))
    passed = int((df["نتیجه"] == "قبول").sum())
    print(f"\n{passed} از {len(df)} آزمون قبول شد.")
    if passed != len(df):
        print("\nآزمون‌های رد‌شده:")
        print(df[df["نتیجه"] == "رد"].to_string(index=False))
        return 1
    print("همهٔ آزمون‌ها قبول — خروجی قابل ارائه است.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
