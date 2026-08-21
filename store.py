"""لایهٔ ابزار — همان توابعی که هم داشبورد و هم مدل زبانی صدا می‌زنند.

قاعده: مدل هیچ‌گاه محاسبه نمی‌کند. مدل انتخاب می‌کند و توضیح می‌دهد؛ محاسبه
اینجا انجام می‌شود. هر خروجی متنی فارسی و آمادهٔ خواندن است، و هر ادعا رفرنس دارد.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

import features as FT
import insights as I
import jalali
from pipeline import fa

BASE = Path(__file__).parent
CACHE = BASE / "cache"

_AR2FA = str.maketrans({"ي": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه", "أ": "ا",
                        "إ": "ا", "آ": "ا", "ؤ": "و", "‌": " ", "ً": "",
                        "ٌ": "", "ٍ": "", "َ": "", "ُ": "", "ِ": "", "ّ": "", "ْ": "", "\u0654": "", "\u0670": ""})
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def norm(s: Any) -> str:
    """یکسان‌سازی «ي/ی»، «ك/ک»، نیم‌فاصله، اعراب و ارقام فارسی."""
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).translate(_AR2FA).translate(_FA_DIGITS)).strip().lower()


def _fmt_refs(refs: list[dict], indent: str = "      ") -> list[str]:
    """رفرنس‌ها را به متن قابل خواندن تبدیل می‌کند — الزام ۲ و ۴."""
    out = []
    for r in refs:
        head = f"{indent}↳ منبع: شیت «{r['sheet']}»"
        if r.get("record_id"):
            head += f" رکورد {r['record_id']}"
        if r.get("date_fa"):
            head += f" ({r['date_fa']})"
        out.append(head)
        if r.get("fields"):
            out.append(indent + "   " + "، ".join(
                f"{f['name_fa']}: {f['value']}" for f in r["fields"]))
        if r.get("note"):
            out.append(indent + "   یادداشت: " + r["note"])
    return out


class Store:
    def __init__(self, enriched: dict[str, dict], portfolio: dict,
                 periods: dict | None = None):
        self.P = enriched
        self.portfolio = portfolio
        self.periods = periods or {}
        self.worklist = (portfolio or {}).get("worklist") or {}
        self.offers = (portfolio or {}).get("offers_engine") or {}
        self.experts = (portfolio or {}).get("experts") or []
        rows = []
        for cid, p in enriched.items():
            c, m, r = p["commercial"], p["margin"], p["receivables"]
            f = p.get("features") or {}
            rows.append({
                "customer_id": cid, "segment": p["identity"]["segment"],
                "location_id": p["identity"]["location_id"],
                "sales_rep_id": p["identity"]["sales_rep_id"],
                "revenue": c["revenue_nominal"], "revenue_real": c["revenue_real"],
                "revenue_rank": c["revenue_rank"], "volume": c["volume"],
                "gross_profit": m["gross_profit"], "margin_pct": m["gross_margin_pct"],
                "negative_line_pct": m["negative_margin_line_pct"],
                "overdue": r["uncollected_overdue"], "open_ar": r["uncollected"],
                "collection_rate": r["collection_rate_pct"],
                "net_contribution": r["net_contribution"],
                "oldest_overdue_days": r["oldest_overdue_days"],
                "bounced": r["bounced_cheques"],
                "days_since_purchase": c["days_since_last_purchase"],
                "volume_trend": c["volume_trend_pct"],
                "complaints": p["complaints"]["total"], "open_complaints": p["complaints"]["open"],
                "interactions": p["engagement"]["interactions"],
                "dev_requests": p["development"]["requests"],
                "wallet_share": p["wallet_share"]["avg_share_pct"],
                # ── ویژگی‌های تازه
                "ltv_total": f.get("ltv_total"), "ltv_future": f.get("ltv_future"),
                "ltv_historic": f.get("ltv_historic"), "ltv_rank": f.get("ltv_rank"),
                "rank_gap": f.get("rank_gap"), "retention": f.get("retention"),
                "rfm": f.get("RFM"), "rfm_segment": f.get("rfm_segment"),
                "R": f.get("R"), "F": f.get("Fq"), "M": f.get("M"),
                "quadrant": f.get("quadrant"), "rescue_value": f.get("rescue_value"),
                "rescue_rank": f.get("rescue_rank"), "gp_monthly": f.get("gp_monthly"),
                "order_gap": f.get("order_gap"), "silence_ratio": f.get("silence_ratio"),
                "families": f.get("families"),
                # ── هزینهٔ پول و فهرست تمرکز
                "days_cash": f.get("days_cash"),
                "cost_of_money": f.get("cost_of_money"),
                "cost_of_money_pct": f.get("cost_of_money_pct"),
                "real_margin": f.get("real_margin"), "real_gp": f.get("real_gp"),
                "net_margin": f.get("net_margin"), "net_gp": f.get("net_gp"),
                "expected_writeoff": f.get("expected_writeoff"),
                "margin_rank": f.get("margin_rank"),
                "real_margin_rank": f.get("real_margin_rank"),
                "margin_rank_gap": f.get("margin_rank_gap"),
                "focus": f.get("focus"), "focus_rank": f.get("focus_rank"),
                "value_at_play": f.get("value_at_play"),
                "value_at_play_basis": f.get("value_at_play_basis"),
                "growth_potential": f.get("growth_potential"),
                "cost_to_serve_score": f.get("cost_to_serve_score"),
                "rfm_prev": f.get("RFM_prev"), "rfm_move": f.get("rfm_move"),
                "rfm_move_label": f.get("rfm_move_label"), "rfm_alert": f.get("rfm_alert"),
                "risk_score": p["risk_score"], "opportunity_score": p["opportunity_score"],
                "signal_score": p["signal_score"], "reference_count": p["reference_count"],
                "risk_codes": "|".join(x["code"] for x in p["risks"]),
                "opp_codes": "|".join(x["code"] for x in p["opportunities"]),
                "signal_codes": "|".join(x["code"] for x in p["signals"]),
                "top_risk": p["risks"][0]["title"] if p["risks"] else "",
                "top_opportunity": p["opportunities"][0]["title"] if p["opportunities"] else "",
                "top_signal": p["signals"][0]["name"] if p["signals"] else "",
                "next_action": p["next_best_actions"][0]["action"] if p["next_best_actions"] else "",
                "next_owner": p["next_best_actions"][0]["owner"] if p["next_best_actions"] else "",
                "p_reorder": next((x["probability"] for x in p["predictions"]
                                   if x["code"] == "reorder_90d"), None),
                "p_churn": next((x["probability"] for x in p["predictions"]
                                 if x["code"] == "churn"), None),
                "p_complaint": next((x["probability"] for x in p["predictions"]
                                     if x["code"] == "new_complaint"), None),
                "p_discount": next((x["probability"] for x in p["predictions"]
                                    if x["code"] == "discount_request"), None),
            })
        self.frame = pd.DataFrame(rows).set_index("customer_id")

        # نمایهٔ متن آزاد
        self.text_index: list[dict] = []
        for cid, p in enriched.items():
            for x in p["complaints"]["items"]:
                self.text_index.append({
                    "customer_id": cid, "kind": "شکایت", "date": x["date"], "id": x.get("id"),
                    "title": x["title"],
                    "text": " ".join(filter(None, [x["title"], x["text"], x["resolution"]])),
                    "meta": f"شدت {fa(x['severity'])} / وضعیت {fa(x['status'])}"})
            for x in p["engagement"]["items"]:
                self.text_index.append({
                    "customer_id": cid, "kind": "تعامل CRM", "date": x["date"], "id": x.get("id"),
                    "title": fa(x["type"]), "text": x["summary"],
                    "meta": f"اقدام بعدی {fa(x['next_action'])} / کارشناس {x['rep']}"})
            for x in p["development"]["items"]:
                self.text_index.append({
                    "customer_id": cid, "kind": "درخواست توسعه", "date": x["date"],
                    "id": x.get("id"), "title": fa(x["type"]),
                    "text": " ".join(filter(None, [x["requirement"], x["outcome"]])),
                    "meta": f"وضعیت {fa(x['status'])} / مالک {fa(x['owner'])}"})
        for d in self.text_index:
            d["_n"] = norm(str(d["text"]) + " " + str(d["title"]))

    # ══════════════════════════════════════════════════════════ ابزار ۱
    def get_customer_profile(self, customer_id: str) -> str:
        """پروفایل کامل یک مشتری به فارسی."""
        p = self.P.get(customer_id.strip().upper())
        if not p:
            near = [c for c in self.P if customer_id.strip().upper() in c][:5]
            return (f"مشتری «{customer_id}» یافت نشد."
                    + (f" شناسه‌های نزدیک: {'، '.join(near)}" if near else ""))
        return render_profile_fa(p)

    # ══════════════════════════════════════════════════════════ ابزار ۲
    def search_customers(self, sort_by: str = "revenue", ascending: bool = False,
                         limit: int = 10, segment: str | None = None,
                         has_risk: str | None = None, has_opportunity: str | None = None,
                         has_signal: str | None = None, rfm_segment: str | None = None,
                         quadrant: str | None = None, min_revenue: float | None = None,
                         dormant_days_min: int | None = None) -> str:
        """رتبه‌بندی و پالایش سبد مشتریان. جدول فشرده برمی‌گرداند، نه پروفایل کامل."""
        f = self.frame
        if segment:
            f = f[f.segment == segment.strip().upper()]
        if has_risk:
            f = f[f["risk_codes"].str.contains(has_risk, na=False)]
        if has_opportunity:
            f = f[f["opp_codes"].str.contains(has_opportunity, na=False)]
        if has_signal:
            f = f[f["signal_codes"].str.contains(has_signal, na=False)]
        if rfm_segment:
            f = f[f["rfm_segment"] == rfm_segment]
        if quadrant:
            f = f[f["quadrant"] == quadrant]
        if min_revenue is not None:
            f = f[f.revenue >= min_revenue]
        if dormant_days_min is not None:
            f = f[f.days_since_purchase >= dormant_days_min]
        if sort_by not in f.columns:
            return f"ستون «{sort_by}» وجود ندارد. ستون‌های مجاز: {', '.join(list(f.columns)[:24])}"
        f = f.sort_values(sort_by, ascending=ascending, na_position="last").head(int(limit))
        if f.empty:
            return "هیچ مشتری با این شرایط یافت نشد."
        L = [f"{len(f)} مشتری (از {len(self.frame)}) — مرتب بر اساس {sort_by}:", ""]
        for cid, r in f.iterrows():
            L.append(
                f"• {cid} | بخش {r.segment} | فروش {I.money(r.revenue)} "
                f"(رتبه {int(r.revenue_rank) if pd.notna(r.revenue_rank) else '—'}) | "
                f"حاشیه {I.pct(r.margin_pct)} | LTV {I.money(r.ltv_total)} "
                f"(رتبه {int(r.ltv_rank) if pd.notna(r.ltv_rank) else '—'}) | "
                f"معوق {I.money(r.overdue)} | ماندگاری "
                f"{f'{r.retention:.0%}' if pd.notna(r.retention) else '—'} | "
                f"{int(r.days_since_purchase) if pd.notna(r.days_since_purchase) else '—'} روز از خرید"
                + (f"\n    RFM: {r.rfm_segment} ({r.rfm}) | چهارخانه: {r.quadrant}"
                   if pd.notna(r.rfm_segment) else "")
                + (f"\n    ریسک اصلی: {r.top_risk}" if r.top_risk else "")
                + (f"\n    فرصت اصلی: {r.top_opportunity}" if r.top_opportunity else "")
                + (f"\n    اقدام بعدی: {r.next_action} ({r.next_owner})" if r.next_action else ""))
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════ ابزار ۳
    def get_risks_and_actions(self, customer_id: str) -> str:
        """ریسک، فرصت و اقدام بعدی — با استدلال و رفرنس کامل."""
        p = self.P.get(customer_id.strip().upper())
        if not p:
            return f"مشتری «{customer_id}» یافت نشد."
        L = [f"◆ {customer_id} — {p['summary']}", ""]
        if p["risks"]:
            L.append("▸ ریسک‌ها")
            for x in p["risks"]:
                L.append(f"  [{x['severity_fa']}] {x['title']}")
                L.append(f"      شاهد: {x['evidence']}")
                L.append(f"      استدلال: {x['logic']}")
                L.append(f"      اقدام: {x['action']} — {x['owner']}")
                L += _fmt_refs(x["references"])
        if p["opportunities"]:
            L.append("\n▸ فرصت‌ها")
            for x in p["opportunities"]:
                L.append(f"  [{x['potential_fa']}] {x['title']}")
                L.append(f"      شاهد: {x['evidence']}")
                L.append(f"      استدلال: {x['logic']}")
                L.append(f"      اقدام: {x['action']} — {x['owner']}"
                         + (f" | ارزش برآوردی {I.money(x['value'])}" if x["value"] else ""))
                L += _fmt_refs(x["references"])
        if p["next_best_actions"]:
            L.append("\n▸ اقدام بعدی پیشنهادی (به ترتیب اولویت)")
            for x in p["next_best_actions"]:
                L.append(f"  {x['rank']}. {x['action']}")
                L.append(f"      مسئول: {x['owner']} | نوع: {x['kind_fa']} | "
                         f"مبلغ در معرض: {I.money(x['value'])}")
                L.append(f"      چرا: {x['logic']}")
                L.append(f"      امتیاز: {x['score_formula']}")
                L += _fmt_refs(x["references"])
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════ ابزار ۴
    def get_signals_and_predictions(self, customer_id: str) -> str:
        """سیگنال‌های مشتری، تفسیرشان، و پیش‌بینی تصمیم بعدی — الزام ۳."""
        p = self.P.get(customer_id.strip().upper())
        if not p:
            return f"مشتری «{customer_id}» یافت نشد."
        L = [f"◆ سیگنال‌ها و پیش‌بینی تصمیم — {customer_id}", ""]
        if p["signals"]:
            by_dom: dict[str, list] = {}
            for s in p["signals"]:
                by_dom.setdefault(s["domain"], []).append(s)
            for dom, items in by_dom.items():
                L.append(f"▸ حوزهٔ {dom}")
                for s in items:
                    L.append(f"  [{s['direction']} · شدت {s['strength']:.2f}] {s['name']}: {s['value']}")
                    L.append(f"      تفسیر: {s['interpretation']}")
                    L += _fmt_refs(s["references"])
        else:
            L.append("هیچ سیگنال قابل استخراجی برای این مشتری وجود ندارد.")
        if p["predictions"]:
            L.append("\n▸ تصمیم‌های احتمالی دورهٔ بعد")
            for x in p["predictions"]:
                L.append(f"  {x['probability']:.0%} — {x['question']} (اعتماد {x['confidence']})")
                L.append(f"      نرخ پایه: {x['base']}")
                for mm in x["modifiers"]:
                    L.append(f"      تعدیل {mm['delta']:+.2f}: {mm['name']} — {mm['why']}")
                if x.get("note"):
                    L.append(f"      هشدار: {x['note']}")
                L += _fmt_refs(x["references"])
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════ ابزار ۵
    def get_value_breakdown(self, customer_id: str) -> str:
        """ارزش طول عمر و بخش کامرشال — الزام ۵ و ۷."""
        p = self.P.get(customer_id.strip().upper())
        if not p:
            return f"مشتری «{customer_id}» یافت نشد."
        cs, f = p["commercial_summary"], p.get("features") or {}
        L = [f"◆ ارزش و سودآوری — {customer_id}", "",
             f"فروش اسمی {I.money(cs['revenue_nominal'])} | حقیقی {I.money(cs['revenue_real'])}",
             f"سود ناخالص {I.money(cs['gross_profit'])} با حاشیه {I.pct(cs['margin_pct'])} "
             f"(میانهٔ سبد {I.pct(cs['portfolio_median_margin'])})",
             f"سود ماهانه {I.money(cs['gp_monthly'])}",
             "",
             "▸ ارزش طول عمر (LTV)",
             f"  محقق‌شده: {I.money(cs['ltv_historic'])} = سود ناخالص منهای معوق",
             f"  آیندهٔ تنزیل‌شده: {I.money(cs['ltv_future'])}",
             f"    = سود ماهانه {I.money(cs['gp_monthly'])} × احتمال ماندگاری "
             f"{(f.get('retention') or 0):.0%} × ضریب تنزیل {cs['discount_factor']} "
             f"({cs['horizon_months']} ماه با نرخ ۱٫۵٪ ماهانه) × ضریب وصول "
             f"{(f.get('ltv_collection_factor') or 0):.2f}",
             f"  **جمع LTV: {I.money(cs['ltv_total'])}** — رتبه {cs['ltv_rank']} از ۶۴۴",
             f"  رتبهٔ فروش {cs['revenue_rank']} در برابر رتبهٔ LTV {cs['ltv_rank']}: "
             f"اختلاف {cs['rank_gap']:+.0f} پله",
             "",
             "▸ مطالبات",
             f"  معوق {I.money(cs['overdue'])} | سررسیدنشده {I.money(cs['not_yet_due'])} | "
             f"مشارکت خالص {I.money(cs['net_contribution'])}",
             "",
             "▸ اقدام‌ها به زبان پول",
             f"  ارزش نجات (اگر از دست برود): {I.money(cs['rescue_value'])} در سال",
             f"  مجموع ارزش فرصت‌های شناسایی‌شده: {I.money(cs['opportunity_upside'])}",
             f"  زیان انباشتهٔ خطوط زیان‌ده: {I.money(abs(cs['gp_destroyed'] or 0))}"]
        if f.get("retention_components"):
            L += ["", "▸ اجزای احتمال ماندگاری"]
            L += [f"  {c['name']}: {c['value']} → {c['delta']:+.2f} ({c['why']})"
                  for c in f["retention_components"]]
            L.append(f"  امتیاز خام {f.get('retention_raw'):.2f} → کالیبره‌شده "
                     f"{(f.get('retention') or 0):.0%}")
            L.append(f"  اعتبارسنجی: AUC {FT.MODEL_CARD['auc_additive']} روی پنجرهٔ "
                     f"خارج‌از‌زمان، خطای کالیبراسیون "
                     f"{FT.MODEL_CARD['calibration_error_calibrated']}")
        L += ["", "▸ بخش‌بندی",
              f"  RFM: {f.get('rfm_segment')} (کد {f.get('RFM')}؛ R={f.get('R')} "
              f"F={f.get('Fq')} M={f.get('M')})",
              f"  چهارخانهٔ حاشیه-ریسک: {f.get('quadrant')}"]
        q = FT.QUADRANTS_FA.get(f.get("quadrant") or "")
        if q:
            L.append(f"    {q['desc']} → {q['play']}")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════ ابزار ۶
    def search_text(self, query: str, limit: int = 12, kind: str | None = None) -> str:
        """جست‌وجو در متن آزاد: شکایت، گزارش کارشناس فروش، درخواست توسعه."""
        terms = [t for t in norm(query).split() if len(t) > 2]
        if not terms:
            return "عبارت جست‌وجو خیلی کوتاه است."
        hits = []
        for d in self.text_index:
            if kind and d["kind"] != kind:
                continue
            score = sum(1 for t in terms if t in d["_n"])
            if score:
                hits.append((score, d))
        if not hits:
            return f"هیچ متنی شامل «{query}» یافت نشد."
        hits.sort(key=lambda x: (-x[0], x[1]["date"] or ""))
        by_cust: dict[str, int] = {}
        for _, d in hits:
            by_cust[d["customer_id"]] = by_cust.get(d["customer_id"], 0) + 1
        L = [f"{len(hits)} رکورد متنی در {len(by_cust)} مشتری شامل «{query}» یافت شد.",
             "پرتکرارترین مشتریان: " + "، ".join(
                 f"{c} ({n})" for c, n in sorted(by_cust.items(), key=lambda x: -x[1])[:6]), ""]
        for _, d in hits[:int(limit)]:
            L.append(f"• [{d['kind']}] {d['customer_id']} رکورد {d.get('id') or '—'} — "
                     f"{jalali.fmt(d['date'])} | {d['meta']}\n    {str(d['text'])[:240]}")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════ ابزار ۷
    def portfolio_summary(self) -> str:
        s, f = self.portfolio, self.frame
        h = s.get("half_years") or []
        hline = ""
        if len(h) >= 2:
            a, b = h[0], h[-1]
            hline = (f"• مقایسهٔ هم‌ارز فصل بهار ({a['label']} → {b['label']}): "
                     f"حجم {I.qty(a['volume'])} → {I.qty(b['volume'])} (شاخص {b['volume_index']}) | "
                     f"فروش اسمی شاخص {b['revenue_index']} | مشتری فعال {a['customers']} → "
                     f"{b['customers']} | قیمت واحد {b['price_index'] / 100:.1f} برابر\n"
                     f"  ⇒ رشد فروش از قیمت است، نه از بازار.\n")
        ltv = f.ltv_total.sum()
        return (
            f"وضعیت کل سبد در تاریخ {jalali.fmt(s['as_of'], 'long')}:\n" + hline
            + f"• {s['customers']} مشتری ({s['customers_with_sales']} با سابقهٔ خرید) | "
              f"فروش اسمی {I.money(s['revenue_nominal'])} | حجم {I.qty(s['volume'])}\n"
            + f"• سود ناخالص {I.money(s['gross_profit'])} با حاشیه "
              f"{I.pct(s['gross_margin_pct'])} ({I.pct(s['realized_cost_share_pct'], 0)} خطوط "
              f"بر مبنای هزینهٔ تحقق‌یافته)\n"
            + f"• مطالبات معوق {I.money(s['overdue'])} = {I.pct(s['overdue_pct_of_revenue'])} "
              f"فروش و {s['overdue_x_gross_profit']} برابر کل سود ناخالص\n"
            + f"• ارزش طول عمر کل سبد {I.money(ltv)} = محقق‌شده "
              f"{I.money(f.ltv_historic.sum())} + آیندهٔ تنزیل‌شده {I.money(f.ltv_future.sum())}\n"
            + f"• {int((f.ltv_total < 0).sum())} مشتری LTV منفی | "
              f"{s['net_negative_customers']} مشتری مشارکت خالص منفی "
              f"({I.pct(s['net_negative_revenue_share_pct'])} فروش)\n"
            + f"• تمرکز: ۱۰ مشتری اول {I.pct(s['top10_revenue_share_pct'])} فروش | "
              f"{s['dormant_180d']} مشتری بیش از ۱۸۰ روز راکد\n"
            + "• چهارخانهٔ حاشیه-ریسک: " + " | ".join(
                f"{k}: {v['customers']} مشتری، سود {I.money(v['gross_profit'])}، "
                f"LTV {I.money(v['ltv'])}" for k, v in (s.get("quadrants") or {}).items()) + "\n"
            + "• بخش‌های RFM بزرگ: " + "، ".join(
                f"{k} ({v['customers']})" for k, v in list((s.get("rfm") or {}).items())[:5])
        )

    # ══════════════════════════════════════════════════════════ ابزار ۸
    def segment_overview(self, kind: str = "quadrant") -> str:
        """نمای بخش‌بندی: چهارخانهٔ حاشیه-ریسک یا بخش‌های RFM — الزام ۸ و ۹."""
        s = self.portfolio
        if kind == "rfm":
            L = ["▸ بخش‌بندی RFM (ارزش پولی بر پایهٔ فروش حقیقی، نه اسمی)", ""]
            for k, v in (s.get("rfm") or {}).items():
                L.append(f"• {k} — {v['customers']} مشتری | فروش {I.money(v['revenue'])} | "
                         f"سود {I.money(v['gross_profit'])} | LTV {I.money(v['ltv'])} | "
                         f"معوق {I.money(v['overdue'])} | رکود میانه {v['recency']:.0f} روز")
                L.append(f"    {FT.RFM_SEGMENTS_FA.get(k, '')}")
            return "\n".join(L)
        L = ["▸ چهارخانهٔ حاشیه سود در برابر ریسک از دست دادن", "",
             f"محور اول: حاشیه سود بالای میانهٔ سبد "
             f"({I.pct(s.get('median_margin'))}) یا زیر آن",
             "محور دوم: احتمال ماندگاری کمتر از ۵۰٪ یعنی «در حال از دست رفتن»", ""]
        for k, v in (s.get("quadrants") or {}).items():
            q = FT.QUADRANTS_FA.get(k, {})
            L.append(f"• {k} — {v['customers']} مشتری | فروش {I.money(v['revenue'])} | "
                     f"سود {I.money(v['gross_profit'])} | LTV {I.money(v['ltv'])} | "
                     f"حاشیه میانه {I.pct(v['margin'])} | ماندگاری میانه {v['retention']:.0%}")
            L.append(f"    {q.get('desc', '')}")
            L.append(f"    اقدام: {q.get('play', '')}")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════ ابزار ۹
    def data_patterns(self) -> str:
        """الگوهای سنجیده‌شده در داده — شامل آن‌هایی که رد شدند — الزام ۶."""
        L = ["▸ الگوهای آزموده‌شده روی این داده", "",
             "روش: هر فرضیه با کنترل مخدوش‌کننده (عمق رابطه یا اندازه) و آزمون روی "
             "نتیجهٔ واقعی دورهٔ بعد بررسی شد. الگوهایی که نگذشتند هم گزارش می‌شوند.", ""]
        for p in FT.VALIDATED_PATTERNS:
            L.append(f"• [{p['status']}] {p['title']}")
            L.append(f"    شاهد: {p['evidence']}")
            L.append(f"    کنترل: {p['control']}")
            L.append(f"    اقدام: {p['action']}")
            if p["caveat"]:
                L.append(f"    هشدار: {p['caveat']}")
        mc = FT.MODEL_CARD
        L += ["", "▸ کارت مدل پیش‌بینی ماندگاری",
              f"    هدف: {mc['target']}",
              f"    روش: {mc['method']}",
              f"    پنجرهٔ آموزش: {mc['train_window']}",
              f"    پنجرهٔ آزمون: {mc['test_window']}",
              f"    AUC امتیاز افزایشی {mc['auc_additive']} | رکود تنها "
              f"{mc['auc_recency_only']} | رگرسیون لجستیک {mc['auc_logistic']}",
              f"    خطای کالیبراسیون {mc['calibration_error_raw']} → "
              f"{mc['calibration_error_calibrated']}",
              f"    نکتهٔ صادقانه: {mc['honest_note']}",
              f"    محدودیت: {mc['limitation']}"]
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════ ابزار ۱۱
    def period_summary(self, period: str = "") -> str:
        """خلاصهٔ یک دورهٔ زمانی: مقایسه با دورهٔ قبل، پیش‌بینی دورهٔ بعد،
        فهرست رسیدگی و پرتکرارترین مشکلات — الزام تب خلاصه."""
        PP = self.periods
        if not PP:
            return "تحلیل دوره‌ای در کش موجود نیست."
        key = (period or "").strip().lower()
        alias = {"هفته": "1w", "week": "1w", "دوهفته": "2w", "ماه": "1m", "month": "1m",
                 "دوماه": "2m", "سه ماه": "3m", "quarter": "3m", "فصل": "3m",
                 "شش ماه": "6m", "سال": "1y", "year": "1y"}
        key = alias.get(key, key)
        if key not in PP["data"]:
            key = PP["recommended"]
        d = PP["data"][key]
        c, pv, cmpr, fc, bt = d["current"], d["previous"], d["compare"], d["forecast"], d["backtest"]

        def sign(k, fmt=lambda v: f"{v:,.0f}"):
            x = cmpr.get(k) or {}
            return (f"{fmt(c.get(k) or 0)} ({x.get('pct'):+.1f}٪ نسبت به دورهٔ قبل)"
                    if x.get("pct") is not None else fmt(c.get(k) or 0))

        L = [f"▸ خلاصهٔ دورهٔ «{d['label']}» — {c['from_fa']} تا {c['to_fa']}",
             f"  لنگر دوره: {PP['anchor_fa']}"
             + (f" ({PP['anchor_note']})" if PP["anchor_note"] else ""), "",
             f"• فروش: {sign('revenue')}",
             f"• سود ناخالص: {sign('gross_profit')} — حاشیه {c['margin_pct']}٪",
             f"• وصول در دوره: {sign('collected')}",
             f"• معوق کل در پایان دوره: {sign('overdue_total')}"
             f" | سررسیدنشده {c['not_yet_due']:,.0f}"
             f" (دورهٔ قبل: معوق {pv['overdue_total']:,.0f})",
             f"• شکایت: {sign('complaints', lambda v: f'{v:,.0f} مورد')}"
             f" ({c['complaints_critical']} با شدت زیاد یا بحرانی)",
             f"• مشتری فعال: {sign('customers', lambda v: f'{v:,.0f}')}",
             "  ↳ منبع: شیت فروش، وصول و شکایات، بازهٔ همین دوره", "",
             f"▸ پیش‌بینی دورهٔ بعد ({d['days']} روز آینده)",
             f"• فروش {fc['revenue']:,.0f} | سود ناخالص {fc['gross_profit']:,.0f}"
             f" | وصول {fc['collected']:,.0f} | معوق پایان دوره {fc['overdue_total']:,.0f}"
             f" | شکایت {fc['complaints']:.0f} مورد",
             f"  خطای بک‌تست خارج از نمونه: فروش {bt['revenue']}٪، سود {bt['gross_profit']}٪، "
             f"وصول {bt['collected']}٪، شکایت {bt['complaints']}٪ ({bt['rounds']} دور)",
             "  ↳ منبع: مدل پایین‌به‌بالای سطح مشتری روی نرخ پایهٔ تجربی رکود، "
             "با برون‌یابی سطح قیمت", "",
             f"▸ رسیدگی — {d['attention_counts']['all']} مشتری نیازمند اقدام",
             f"  با ارزش·بحرانی {d['attention_counts']['P1']} | "
             f"با ارزش·عادی {d['attention_counts']['P2']} | "
             f"کم‌ارزش·بحرانی {d['attention_counts']['P3']} | "
             f"کم‌ارزش·غیربحرانی {d['attention_counts']['P4']}"]
        for r in d["attention"][:8]:
            L.append(f"• {r['customer_id']} [{r['priority_fa']}] {r['problem_generic']} — "
                     f"در خطر {r['at_risk']:,.0f} | RFM {r['rfm']} | LTV {r['ltv_total']:,.0f}")
            L.append(f"    چرا: {r['why']}")
            L.append(f"    اقدام: {r['action']} (مسئول {r['owner']})")
            L += _fmt_refs(r["references"])
        L += ["", "▸ سه مشکل پرتکرار دوره"]
        for b in d["problems"]:
            L.append(f"• {b['title']} — {b['customers']} مشتری "
                     f"({b['in_period']} با رویداد تازه در همین دوره)، "
                     f"پول در خطر {b['at_risk']:,.0f}")
            L.append(f"    فرمول: {b['formula']} | مسئول اصلی: {b['owner']}")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════ ابزار ۱۲
    def focus_list(self, limit: int = 15) -> str:
        """فهرست تمرکز و هزینهٔ پول — «الان وقت تیم را کجا بگذاریم و کجا نگذاریم؟»"""
        s = self.portfolio
        fl = s.get("focus_list") or {}
        cp = s.get("credit_pricing") or {}
        L = [f"▸ هزینهٔ پول و سود واقعی سبد (نرخ {s.get('finance_rate_monthly', 0.04) * 100:.0f}٪ ماهانه)",
             f"• سود ناخالص {s.get('gross_profit', 0):,.0f} ({s.get('gross_margin_pct')}٪)",
             f"• هزینهٔ پول {s.get('cost_of_money', 0):,.0f} ({s.get('cost_of_money_pct')}٪ فروش) — "
             f"پول به‌طور میانگین {s.get('days_cash_median')} روز نزد مشتری می‌ماند",
             f"• **سود واقعی {s.get('real_gross_profit', 0):,.0f} ({s.get('real_margin_pct')}٪)**",
             f"• ذخیرهٔ مطالبات مشکوک‌الوصول {s.get('expected_writeoff', 0):,.0f} → "
             f"سود خالص {s.get('net_gross_profit', 0):,.0f} ({s.get('net_margin_pct')}٪)",
             f"• مشتری زیان‌ده: {s.get('negative_gross_margin_customers')} روی حاشیهٔ ناخالص، "
             f"{s.get('negative_real_margin_customers')} روی حاشیهٔ واقعی",
             f"• دامنهٔ حاشیه: {s.get('margin_spread_gross')} واحد ناخالص → "
             f"{s.get('margin_spread_real')} واحد واقعی",
             "  ↳ منبع: شیت فروش و وصول؛ نرخ ۴٪ ماهانه فرض بیرونی از راهنمای داوران است، "
             "نه استخراج از داده", "",
             "▸ آزمون قیمت‌گذاری اعتبار"]
        for r in cp.get("rows", []):
            L.append(f"• شرط {r['terms']}: مارک‌آپ مورد انتظار {r['expected_pct']}٪، "
                     f"مشاهده‌شده {r['observed_weighted_pct']}٪ (t={r['t_stat']}, "
                     f"{'معنادار' if r['significant'] else 'بی‌معنا'}) — {r['cells']:,} سلول کالا-ماه")
        L.append("  " + str(cp.get("verdict", "")).replace("**", ""))
        L += ["", f"▸ چهار خانهٔ تمرکز"]
        for k, v in (s.get("focus") or {}).items():
            L.append(f"• {k}: {v['customers']} مشتری | سود ناخالص {v['gross_profit']:,.0f} → "
                     f"سود واقعی {v['real_gp']:,.0f} | پول در حرکت {v['value_at_play']:,.0f}")
        L += ["", f"▸ فهرست تمرکز: از {fl.get('total_customers')} مشتری به {fl.get('size')}",
              f"  این فهرست {fl.get('kept_revenue_share')}٪ فروش و "
              f"{fl.get('kept_value', 0):,.0f} از {fl.get('total_value', 0):,.0f} پول در حرکت را پوشش می‌دهد.",
              f"  قاعدهٔ برش: {fl.get('rule')}"]
        for r in (fl.get("kept") or [])[:limit]:
            L.append(f"• {r['rank']}. {r['customer_id']} [{r['focus']}] "
                     f"حاشیهٔ ناخالص {r['margin_pct']:.1f}٪ − هزینهٔ پول {r['cost_of_money_pct']:.1f}٪ "
                     f"= سود واقعی {r['real_margin']:.1f}٪ | پول در حرکت {r['value_at_play']:,.0f}")
            L.append(f"    اقدام: {r['action']} (مسئول {r['owner']})")
        L += ["", "▸ چه کسانی حذف شدند و چرا"]
        for b in (fl.get("cuts") or []):
            L.append(f"• {b['focus']}: {b['customers']} مشتری، فروش {b['revenue']:,.0f}، "
                     f"سود واقعی {b['real_gp']:,.0f}")
            L.append(f"    {b['reason']}")
        v = s.get("validation") or {}
        if v:
            L += ["", f"▸ اعتبارسنجی دستی: {v.get('passed')} از {v.get('total')} بررسی روی "
                      f"{len(v.get('cases', []))} حساب منطبق است."]
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════ ابزار ۱۳
    def work_card(self, customer_id: str = "", family: str = "", limit: int = 10) -> str:
        """کارتابل: کار امروز. با شناسهٔ مشتری، کارت کامل و دستور کار تماس یا جلسه."""
        w = self.worklist or {}
        if not w:
            return "کارتابل در کش موجود نیست."
        rows = w.get("rows") or []
        cid = (customer_id or "").strip().upper()
        if cid:
            r = next((x for x in rows if x["customer_id"] == cid), None)
            if not r:
                return f"مشتری {cid} در کارتابل نیست (کار بازی برایش ثبت نشده)."
            ag = r.get("agenda") or {}
            L = [f"▸ {r['customer_id']} — {r['priority_fa']} · مشکل {r['family']}",
                 f"• هدف: {r['goal']} — {r['goal_amount']:,.0f}",
                 f"• مشتری کیست: {r['who']}",
                 f"• بهترین ارتباط: {r['channel']} ({r['channel_why']})",
                 f"• مشکل باز {r['problems']} مورد | شکایت {r['complaints']} "
                 f"({r['open_complaints']} باز) | LTV {r['ltv_total']:,.0f} "
                 f"(رتبه {r['ltv_rank']}) | RFM {r['rfm_segment']} {r['rfm']}",
                 f"• حاشیهٔ واقعی {r['real_margin']}٪ پس از هزینهٔ پول "
                 f"{r['cost_of_money_pct']}٪ | معوق {r['overdue']:,.0f} | "
                 f"رکود {r['recency']} روز",
                 "", "▸ کارها"]
            for i, t in enumerate(r.get("tasks") or [], 1):
                L.append(f"  {i}. {t} — {(r.get('owners') or [''] * i)[i - 1]}")
            L += ["", f"▸ همین حالا: {r['now']}  (مسئول {r['now_owner']})",
                  "", f"▸ {ag.get('title', 'دستور کار')} — کانال {ag.get('channel')}",
                  f"  شروع: {ag.get('opener')}"]
            for p in ag.get("points") or []:
                L.append(f"  • {p}")
            L += [f"  بستن با: {ag.get('close')}", "  رفتار و لحن:"]
            for t in ag.get("tone") or []:
                L.append(f"    − {t}")
            L.append(f"  {ag.get('record')}")
            L += _fmt_refs(r.get("references") or [])
            return "\n".join(L)

        L = ["▸ کارتابل — مشکلات سبد", ""]
        for c in w.get("cards") or []:
            L.append(f"• {c['family']}: {c['customers']} مشتری "
                     f"({c['primary']} با همین مشکل اصلی، {c['p1']} اولویت اول) — "
                     f"هدف: {c['goal']} — {c['amount']:,.0f} در گیر")
        pc = w.get("priority_counts") or {}
        L += ["", "▸ اولویت‌ها: "
              + "، ".join(f"{w['priority_fa'][k]} {v}" for k, v in pc.items()),
              "", "▸ سطرهای اول کارتابل"]
        sel = [x for x in rows if not family or x["family"] == family][:limit]
        for x in sel:
            L.append(f"• {x['customer_id']} [{x['priority_fa']}] {x['goal']} "
                     f"{x['goal_amount']:,.0f} | {x['channel']} | همین حالا: {x['now']}")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════ ابزار ۱۴
    def offer_plan(self, customer_id: str = "", play: str = "", limit: int = 10) -> str:
        """آفر: چه کسی، چه آفری، چه تخفیفی، چه مهلتی — با دلیل داده‌محور."""
        o = self.offers or {}
        if not o:
            return "موتور آفر در کش موجود نیست."
        cid = (customer_id or "").strip().upper()
        if cid:
            sel = [x for x in (o.get("rows") or []) + (o.get("blocked") or [])
                   if x["customer_id"] == cid]
            if not sel:
                return (f"برای {cid} آفری پیشنهاد نمی‌شود: نه افت حجمی دارد، نه گروه "
                        "کالای فروخته‌نشده، نه شکاف سهم سبد.")
            L = [f"▸ آفرهای {cid}"]
            for x in sel:
                L += ["", f"• {x['play']} — {x['goal']}",
                      f"  آفر: {x['offer']}",
                      f"  در ازای: {x['ask']}",
                      f"  تخفیف پیشنهادی {x['suggested_discount_pct']}٪ "
                      f"(سقف {x['headroom_pct']}٪ از حاشیهٔ واقعی {x['real_margin']}٪) | "
                      f"مهلت {x['validity_days']} روز",
                      f"  {o['money_label']}: {x['gp_if_accepted']:,.0f} | "
                      f"ارزش انتظاری {x['expected_value']:,.0f} "
                      f"(احتمال {x['accept_rate'] * 100:.1f}٪)",
                      f"  چرا این مشتری: {x['evidence']}"]
                if not x["feasible"]:
                    L.append(f"  ⚠ مسدود: {x['block_reason']}")
                L += _fmt_refs(x.get("references") or [])
            L += ["", f"▸ سیاست: {o['policy']}", f"▸ هشدار: {o['money_caveat']}"]
            return "\n".join(L)

        L = ["▸ موتور آفر", f"• {o['headline']}", "",
             f"• {o['total']} آفر برای {o['customers']} مشتری | "
             f"{o['money_label']} {o['gp_total']:,.0f} | "
             f"ارزش انتظاری {o['expected_value_total']:,.0f}",
             f"• سود مهلت درست: {o['window_gain']:,.0f} تومان فقط از تغییر "
             f"{o['median_validity_today']} روز به {o['validity_days']} روز",
             f"• {o['blocked_total']} آفر مسدود ({o['blocked_customers']} مشتری): "
             "حاشیهٔ واقعی فضای تخفیف ندارد", "", "▸ بازی‌ها"]
        for c in o.get("cards") or []:
            L.append(f"• {c['play']}: {c['customers']} مشتری — "
                     f"هدف {c['gp_if_accepted']:,.0f} | انتظاری {c['expected_value']:,.0f}")
        L += ["", "▸ آنچه آزمودیم"]
        wt = o.get("window_test") or {}
        L.append(f"• {wt.get('factor')}: χ²={wt.get('chi2')} p<۰٫۰۰۰۱ → {wt.get('verdict')}")
        for t in o.get("negative_tests") or []:
            L.append(f"• {t['factor']}: p={t['p']} → {t['verdict']}")
        sel = [x for x in (o.get("rows") or []) if not play or x["play"] == play][:limit]
        L += ["", "▸ سطرهای اول"]
        for x in sel:
            L.append(f"• {x['customer_id']} [{x['priority_fa']}] {x['play']} | "
                     f"تخفیف {x['suggested_discount_pct']}٪ | "
                     f"انتظاری {x['expected_value']:,.0f}")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════ ابزار ۱۰
    def compare_customers(self, customer_ids: list[str]) -> str:
        ids = [c.strip().upper() for c in customer_ids if c.strip().upper() in self.frame.index]
        if not ids:
            return "هیچ‌کدام از شناسه‌ها یافت نشد."
        cols = [("بخش", "segment", str), ("فروش", "revenue", I.money),
                ("سود ناخالص", "gross_profit", I.money), ("حاشیه", "margin_pct", I.pct),
                ("LTV", "ltv_total", I.money), ("رتبهٔ LTV", "ltv_rank", lambda v: f"{v:.0f}"),
                ("ماندگاری", "retention", lambda v: f"{v:.0%}"),
                ("معوق", "overdue", I.money), ("مشارکت خالص", "net_contribution", I.money),
                ("RFM", "rfm_segment", str), ("چهارخانه", "quadrant", str),
                ("شکایت", "complaints", lambda v: str(int(v))),
                ("سهم از سبد", "wallet_share", I.pct)]
        L = ["مقایسهٔ " + "، ".join(ids), ""]
        for label, col, fmt in cols:
            L.append(f"{label}: " + " | ".join(
                f"{c}={fmt(self.frame.at[c, col]) if pd.notna(self.frame.at[c, col]) else '—'}"
                for c in ids))
        return "\n".join(L)


# ═══════════════════════════════════════════════════ رندر فارسی پروفایل
def render_profile_fa(p: dict) -> str:
    i, c, m, r = p["identity"], p["commercial"], p["margin"], p["receivables"]
    f = p.get("features") or {}
    L = [f"# پروفایل مشتری {p['customer_id']} — در تاریخ {jalali.fmt(p['as_of'], 'long')}",
         "",
         f"بخش {i['segment']} | موقعیت {i['location_id']} | کارشناس {i['sales_rep_id']} | "
         f"سقف اعتبار {I.money(i['credit_limit'])} | مهلت پرداخت {i['payment_terms_days']} روز | "
         f"سابقهٔ همکاری از {jalali.fmt(i['relationship_start'])}",
         "", "## خلاصه وضعیت", "", p["summary"]]

    if not p["coverage"]["sales"]:
        return "\n".join(L)

    cs = p["commercial_summary"]
    L += ["", "## کامرشال — ارزش به زبان پول", "",
          f"| شاخص | مقدار |", "| --- | --- |",
          f"| فروش اسمی | {I.money(cs['revenue_nominal'])} (رتبه {cs['revenue_rank']}) |",
          f"| فروش حقیقی (تعدیل تورم) | {I.money(cs['revenue_real'])} |",
          f"| سود ناخالص | {I.money(cs['gross_profit'])} ({I.pct(cs['margin_pct'])}) |",
          f"| سود ماهانه | {I.money(cs['gp_monthly'])} |",
          f"| معوق / سررسیدنشده | {I.money(cs['overdue'])} / {I.money(cs['not_yet_due'])} |",
          f"| مشارکت خالص | {I.money(cs['net_contribution'])} |",
          f"| **ارزش طول عمر** | **{I.money(cs['ltv_total'])}** (رتبه {cs['ltv_rank']}) |",
          f"| ارزش نجات سالانه | {I.money(cs['rescue_value'])} |",
          f"| مجموع ارزش فرصت‌ها | {I.money(cs['opportunity_upside'])} |",
          "",
          f"LTV = محقق‌شده {I.money(cs['ltv_historic'])} + آیندهٔ تنزیل‌شده "
          f"{I.money(cs['ltv_future'])} (احتمال ماندگاری {(f.get('retention') or 0):.0%}، "
          f"افق {cs['horizon_months']} ماه، ضریب تنزیل {cs['discount_factor']})",
          f"بخش‌بندی: RFM «{f.get('rfm_segment')}» کد {f.get('RFM')} | چهارخانه "
          f"«{f.get('quadrant')}»"]

    L += ["", "## عملکرد تجاری", "",
          f"حجم {I.qty(c['volume'])} در {c['order_lines']} خط و {c['invoices']} فاکتور | "
          f"{c['active_months']} ماه فعال | فاصلهٔ معمول سفارش "
          f"{f.get('order_gap'):.0f} روز" if f.get("order_gap") else "",
          f"از {jalali.fmt(c['first_purchase'])} تا {jalali.fmt(c['last_purchase'])} "
          f"({c['days_since_last_purchase']} روز پیش)"
          + (f" | روند حجم شش‌ماهه {I.pct(c['volume_trend_pct'], 0)}"
             if c["volume_trend_pct"] is not None else "")]
    if c["product_family_mix"]:
        L.append("ترکیب گروه کالا: " + "، ".join(
            f"{k} {I.pct(v, 0)}" for k, v in list(c["product_family_mix"].items())[:5]))
    if c["top_products"]:
        L += ["", "محصولات اصلی:"]
        L += [f"- {x['desc']} ({x['product_id']}): {I.money(x['revenue'])}، "
              f"{I.qty(x['qty'])}، حاشیه {I.pct(x['margin_pct'])}" for x in c["top_products"][:3]]

    if p["signals"]:
        L += ["", "## سیگنال‌ها و تفسیر", ""]
        for s in p["signals"]:
            L.append(f"- **{s['name']}** ({s['domain']} · {s['direction']} · شدت "
                     f"{s['strength']:.2f}): {s['value']}")
            L.append(f"  - تفسیر: {s['interpretation']}")
            for rr in s["references"][:2]:
                L.append(f"  - منبع: شیت «{rr['sheet']}»"
                         + (f" رکورد {rr['record_id']}" if rr.get("record_id") else "")
                         + (f" ({rr['date_fa']})" if rr.get("date_fa") else "")
                         + ((" — " + "، ".join(f"{x['name_fa']}: {x['value']}"
                                               for x in rr["fields"])) if rr.get("fields") else ""))

    if p["predictions"]:
        L += ["", "## تصمیم‌های احتمالی دورهٔ بعد", "",
              "| تصمیم | احتمال | اعتماد | نرخ پایه |", "| --- | --- | --- | --- |"]
        L += [f"| {x['question']} | {x['probability']:.0%} | {x['confidence']} | {x['base']} |"
              for x in p["predictions"]]

    if p["risks"]:
        L += ["", "## ریسک‌ها", ""]
        for x in p["risks"]:
            L.append(f"- **[{x['severity_fa']}] {x['title']}**")
            L.append(f"  - شاهد: {x['evidence']}")
            L.append(f"  - استدلال: {x['logic']}")
            L.append(f"  - اقدام: {x['action']} — {x['owner']}")
    if p["opportunities"]:
        L += ["", "## فرصت‌ها", ""]
        for x in p["opportunities"]:
            L.append(f"- **[{x['potential_fa']}] {x['title']}**"
                     + (f" — ارزش {I.money(x['value'])}" if x["value"] else ""))
            L.append(f"  - شاهد: {x['evidence']}")
            L.append(f"  - استدلال: {x['logic']}")
            L.append(f"  - اقدام: {x['action']} — {x['owner']}")
    if p["next_best_actions"]:
        L += ["", "## اقدام بعدی پیشنهادی", ""]
        for x in p["next_best_actions"]:
            L.append(f"{x['rank']}. **{x['action']}** — مسئول {x['owner']}، مبلغ در معرض "
                     f"{I.money(x['value'])}")
            L.append(f"   - چرا: {x['logic']}")
            L.append(f"   - امتیاز: {x['score_formula']}")

    cp = p["complaints"]
    if cp["total"]:
        L += ["", "## شکایات و کیفیت", "",
              f"{cp['total']} شکایت ({cp['open']} باز) | " + "، ".join(
                  f"{fa(k)}×{v}" for k, v in cp["by_severity"].items())]
        imp = cp.get("purchase_impact")
        if imp and imp.get("change_pct") is not None:
            L.append(f"اثر بر خرید: {I.qty(imp['volume_before'])} → "
                     f"{I.qty(imp['volume_after'])} ({I.pct(imp['change_pct'], 0)}) در پنجرهٔ "
                     f"{imp['window_days']} روزه حول نخستین شکایت")
        L += [f"- {jalali.fmt(x['date'])} [{fa(x['severity'])}/{fa(x['status'])}] "
              f"{x['title']}: {str(x['text'])[:140]}" for x in cp["items"][:4]]

    e = p["engagement"]
    if e["interactions"]:
        L += ["", "## تعاملات ثبت‌شده", "",
              f"{e['interactions']} تعامل | آخرین {jalali.fmt(e['last_interaction'])} "
              f"({e['days_since_last_interaction']} روز پیش)"]
        L += [f"- {jalali.fmt(x['date'])} [{fa(x['type'])}] {x['summary']}"
              for x in e["items"][:4]]

    dv = p["development"]
    if dv["requests"]:
        L += ["", "## درخواست‌های توسعه محصول", "",
              f"{dv['requests']} درخواست | {dv['approved']} نمونه تأیید، "
              f"{dv['rejected']} رد فنی، {dv['pending']} در جریان"]
        L += [f"- {jalali.fmt(x['date'])} [{fa(x['status'])}] {x['requirement']}"
              for x in dv["items"][:4]]

    o = p["offers"]
    if o["total"]:
        L += ["", "## آفرها", "",
              f"{o['total']} آفر | {o['accepted']} قبول، {o['rejected']} رد، "
              f"{o['expired']} منقضی، {o['pending']} بی‌پاسخ | نرخ پذیرش "
              f"{I.pct(o['acceptance_rate_pct'])}"]
        if o.get("open_items"):
            L += [f"- آفر باز {x['id']} ({jalali.fmt(x['date'])}) دلیل «{fa(x['reason'])}»، "
                  f"تخفیف {I.pct(x['discount_pct'], 1)}، {x['days_since']} روز از صدور "
                  f"(اعتبار {x['validity_days']} روز)" for x in o["open_items"][:3]]

    w = p["wallet_share"]
    if w["months_observed"]:
        L += ["", "## سهم از سبد خرید", "",
              f"میانگین {I.pct(w['avg_share_pct'])} در {w['months_observed']} ماه "
              f"(آخرین {I.pct(w['latest_share_pct'])}، میانهٔ بخش "
              f"{I.pct(w['segment_avg_share_pct'])}) | خرید برآوردی "
              f"{I.qty(w['estimated_total_purchase'])} در ماه"]

    q = p["quality"]
    if q["lab_records"]:
        L += ["", "## کیفیت آزمایشگاهی", "",
              f"{q['lab_records']} رکورد، {q['lab_failures']} رد | استحکام "
              f"{q['avg_tensile_cN_dtex']} cN/dtex | کشش {I.pct(q['avg_elongation_pct'])} | "
              f"CV یکنواختی {I.pct(q['avg_evenness_cv_pct'])}"]
    return "\n".join(x for x in L if x is not None)


# ═════════════════════════════════════════════════════════ ساخت / خواندن کش
def _py(o):
    """numpy/pandas → انواع پایتونی، تا JSON بی‌صدا نشکند."""
    import numpy as _np
    if isinstance(o, dict):
        return {k: _py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_py(v) for v in o]
    if isinstance(o, (_np.bool_, bool)):
        return bool(o)
    if isinstance(o, (_np.integer,)):
        return int(o)
    if isinstance(o, (_np.floating, float)):
        f = float(o)
        return None if not _np.isfinite(f) else f
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    if o is pd.NaT or (o is not None and not isinstance(o, str) and pd.isna(o)):
        return None
    return o


FOCUS_LIST_SIZE = 40


def _focus_list(frame: pd.DataFrame, top: int = FOCUS_LIST_SIZE) -> dict:
    """اسکناریوی F راهنمای داوران: از کل سبد به فهرستی که وقت تیم را می‌ارزد.

    برش روی «پولی که در این حساب در حرکت است» انجام می‌شود، و برای هر حسابِ
    بیرون‌مانده دلیل حذف و «چه چیزی نظرمان را عوض می‌کند» نوشته می‌شود.
    """
    import features as FT2
    A = frame[frame.revenue.notna()].copy()
    A = A.sort_values("value_at_play", ascending=False)
    keep = A.head(top)
    drop = A.iloc[top:]
    rows = []
    for i, (cid, r) in enumerate(keep.iterrows(), 1):
        rows.append({
            "rank": i, "customer_id": cid, "segment": r.segment,
            "focus": r.focus, "rfm": r.rfm_segment, "rfm_move": r.rfm_move_label,
            "revenue": r.revenue, "margin_pct": r.margin_pct,
            "cost_of_money_pct": r.cost_of_money_pct, "real_margin": r.real_margin,
            "days_cash": r.days_cash, "real_gp": r.real_gp,
            "value_at_play": r.value_at_play, "basis": r.value_at_play_basis,
            "action": r.next_action, "owner": r.next_owner,
            "why": (f"{r.value_at_play_basis} — سالانه {r.value_at_play:,.0f} در حرکت است؛ "
                    f"حاشیهٔ ناخالص {r.margin_pct:.1f}٪ منهای هزینهٔ پول "
                    f"{r.cost_of_money_pct:.1f}٪ یعنی سود واقعی {r.real_margin:.1f}٪ "
                    f"({r.days_cash:.0f} روز پول قفل‌شده)")})
    cuts = {}
    for cid, r in drop.iterrows():
        reason = FT2.cut_reason(r)
        b = cuts.setdefault(r.focus, {"focus": r.focus, "customers": 0, "revenue": 0.0,
                                      "real_gp": 0.0, "value_at_play": 0.0,
                                      "reason": reason, "examples": []})
        num = lambda v: 0.0 if v is None or pd.isna(v) else float(v)
        b["customers"] += 1
        b["revenue"] += num(r.revenue)
        b["real_gp"] += num(r.real_gp)
        b["value_at_play"] += num(r.value_at_play)
        if len(b["examples"]) < 4:
            b["examples"].append({"customer_id": cid, "revenue": r.revenue,
                                  "real_margin": r.real_margin,
                                  "value_at_play": r.value_at_play})
    for b in cuts.values():
        for k in ("revenue", "real_gp", "value_at_play"):
            b[k] = round(b[k]) if pd.notna(b[k]) else 0
    return {
        "size": top, "total_customers": int(len(A)),
        "kept": rows,
        "kept_value": round(float(keep.value_at_play.sum())),
        "total_value": round(float(A.value_at_play.sum())),
        "kept_revenue_share": round(float(keep.revenue.sum() / A.revenue.sum() * 100), 1),
        "kept_real_gp": round(float(keep.real_gp.sum())),
        "cuts": sorted(cuts.values(), key=lambda b: -b["customers"]),
        "rule": ("برش روی «پول در حرکت» است: بیشینهٔ سه عدد — سودی که با رفتن مشتری "
                 "از دست می‌رود، سودی که با رشد به دست می‌آید، و سودی که با اصلاح "
                 "شرایط پرداخت آزاد می‌شود."),
    }


def build_cache(as_of: str | None = None) -> Store:
    import pipeline as P
    ts = pd.Timestamp(as_of) if as_of else P.DEFAULT_AS_OF
    import money as MN
    D, rep = P.clean(P.load_raw())
    V = P.as_of_view(D, ts)
    profiles = P.build_profiles(D, ts)
    P.add_complaint_impact(D, profiles, ts)

    # ── هزینهٔ پول: روزهای واقعی قفل‌شدن پول، در تاریخ برش و یک فصل پیش از آن
    md = MN.money_days(V, ts)
    F = FT.add_scores(FT.build_features(D, ts), md)
    prev_ts = ts - pd.Timedelta(days=FT.RFM_MOVE_DAYS)
    md_prev = MN.money_days(P.as_of_view(D, prev_ts), prev_ts)
    F_prev = FT.add_scores(FT.build_features(D, prev_ts), md_prev)
    F = FT.add_rfm_movement(F, F_prev)
    enriched = I.enrich_all(profiles, F)
    portfolio = P.portfolio_stats(profiles, D, ts)

    # آمار بخش‌بندی برای نمای کل
    A = F[F.revenue.notna()]
    portfolio["median_margin"] = round(float(A.margin.median()), 2)
    portfolio["ltv_total"] = round(float(A.ltv_total.sum()))
    portfolio["ltv_historic"] = round(float(A.ltv_historic.sum()))
    portfolio["ltv_future"] = round(float(A.ltv_future.sum()))
    portfolio["negative_ltv_customers"] = int((A.ltv_total < 0).sum())
    portfolio["retention_median"] = round(float(A.retention.median()), 3)
    portfolio["model_card"] = FT.MODEL_CARD
    portfolio["patterns"] = FT.VALIDATED_PATTERNS
    portfolio["quadrant_meta"] = FT.QUADRANTS_FA
    portfolio["rfm_meta"] = FT.RFM_SEGMENTS_FA
    portfolio["quadrants"] = {
        k: {"customers": int(len(g)), "revenue": round(float(g.revenue.sum())),
            "gross_profit": round(float(g.gp.sum())), "ltv": round(float(g.ltv_total.sum())),
            "overdue": round(float(g.overdue.sum())), "margin": round(float(g.margin.median()), 2),
            "retention": round(float(g.retention.median()), 3),
            "recency": round(float(g.recency.median())),
            "rescue_value": round(float(g.rescue_value.sum()))}
        for k, g in A.groupby("quadrant")}
    portfolio["rfm"] = {
        k: {"customers": int(len(g)), "revenue": round(float(g.revenue.sum())),
            "gross_profit": round(float(g.gp.sum())), "ltv": round(float(g.ltv_total.sum())),
            "overdue": round(float(g.overdue.sum())), "margin": round(float(g.margin.median()), 2),
            "recency": round(float(g.recency.median())),
            "R": round(float(g.R.mean()), 2), "F": round(float(g.Fq.mean()), 2),
            "M": round(float(g.M.mean()), 2)}
        for k, g in sorted(A.groupby("rfm_segment"), key=lambda kv: -kv[1].gp.sum())}
    # ماتریس RFM برای نقشهٔ حرارتی: R × F با میانگین M و شمارش
    portfolio["rfm_matrix"] = [
        {"R": int(r), "F": int(fq), "customers": int(len(g)),
         "gp": round(float(g.gp.sum())), "ltv": round(float(g.ltv_total.sum())),
         "M": round(float(g.M.mean()), 2)}
        for (r, fq), g in A.groupby(["R", "Fq"])]
    # پراکندگی چهارخانه برای نمودار
    portfolio["quadrant_points"] = [
        {"id": cid, "margin": round(float(row.margin), 2),
         "retention": round(float(row.retention), 3),
         "gp": round(float(row.gp)), "ltv": round(float(row.ltv_total)),
         "quadrant": row.quadrant, "segment": row.segment}
        for cid, row in A.iterrows()]

    # ── هزینهٔ پول در سطح سبد + آزمون قیمت‌گذاری اعتبار
    Am = F[F.revenue.notna()]
    rate = MN.FINANCE_RATE_MONTHLY
    portfolio["finance_rate_monthly"] = rate
    portfolio["finance_rate_source"] = MN.RATE_SOURCE
    portfolio["cost_of_money"] = round(float(Am.cost_of_money.sum()))
    portfolio["cost_of_money_pct"] = round(float(Am.cost_of_money.sum() / Am.revenue.sum() * 100), 2)
    portfolio["real_gross_profit"] = round(float(Am.real_gp.sum()))
    portfolio["real_margin_pct"] = round(float(Am.real_gp.sum() / Am.revenue.sum() * 100), 2)
    portfolio["expected_writeoff"] = round(float(Am.expected_writeoff.sum()))
    portfolio["net_gross_profit"] = round(float(Am.net_gp.sum()))
    portfolio["net_margin_pct"] = round(float(Am.net_gp.sum() / Am.revenue.sum() * 100), 2)
    portfolio["negative_real_margin_customers"] = int((Am.real_margin < 0).sum())
    portfolio["negative_gross_margin_customers"] = int((Am.margin < 0).sum())
    portfolio["days_cash_median"] = round(float(Am.days_cash.median()), 1)
    portfolio["days_cash_benchmark"] = round(float(Am.days_cash.quantile(0.10)), 1)
    portfolio["achievable_real_margin"] = round(float(Am.achievable_real_margin.iloc[0]), 2)
    portfolio["margin_spread_gross"] = round(float(Am.margin.quantile(.95) - Am.margin.quantile(.05)), 1)
    portfolio["margin_spread_real"] = round(float(Am.real_margin.quantile(.95) - Am.real_margin.quantile(.05)), 1)
    portfolio["credit_pricing"] = MN.credit_pricing_test(V, rate)
    portfolio["payment_profile"] = MN.payment_type_profile(V)
    portfolio["recovery_curve"] = [
        {"band": b, "recovery": r, "invoices": n} for _, r, b, n in MN.RECOVERY_BY_AGE]
    portfolio["recovery_note"] = MN.RECOVERY_NOTE
    portfolio["focus_meta"] = FT.FOCUS_FA
    portfolio["focus"] = {
        k: {"customers": int(len(g)), "revenue": round(float(g.revenue.sum())),
            "gross_profit": round(float(g.gp.sum())), "real_gp": round(float(g.real_gp.sum())),
            "cost_of_money": round(float(g.cost_of_money.sum())),
            "value_at_play": round(float(g.value_at_play.sum())),
            "real_margin": round(float(g.real_margin.median()), 2),
            "cost_to_serve": round(float(g.cost_to_serve_score.median()), 2)}
        for k, g in Am.groupby("focus")}
    portfolio["rfm_movement"] = {
        k: int(v) for k, v in Am.rfm_move_label.value_counts().items()}
    portfolio["rfm_alerts"] = int(Am.rfm_alert.fillna(False).sum())
    portfolio["rfm_m_basis"] = str(Am.m_basis.iloc[0])
    portfolio["margin_points"] = [
        {"id": cid, "margin": round(float(r.margin), 2),
         "real_margin": round(float(r.real_margin), 2),
         "cost_of_money_pct": round(float(r.cost_of_money_pct), 2),
         "days_cash": round(float(r.days_cash), 1) if pd.notna(r.days_cash) else None,
         "revenue": round(float(r.revenue)), "real_gp": round(float(r.real_gp)),
         "value_at_play": round(float(r.value_at_play)), "focus": r.focus}
        for cid, r in Am.iterrows()]

    # ── تحلیل دوره‌ای برای تب خلاصه (هر ۷ طول دوره، یک‌بار)
    import period as PD
    periods = PD.build_all(P.as_of_view(D, ts), enriched)

    st = Store(enriched, portfolio, periods)
    import worklist as WL
    portfolio["worklist"] = _py(WL.build(enriched, st.frame))
    st.worklist = portfolio["worklist"]
    # ── موتور آفر (به کارتابل برای اولویت مشتری نیاز دارد)
    import offer_engine as OE
    portfolio["offers_engine"] = _py(OE.build(enriched, st.worklist))
    st.offers = portfolio["offers_engine"]
    # ── روستر کارشناسان برای لایهٔ ارجاع
    import assignments as AS
    portfolio["experts"] = _py(AS.build_experts(enriched, st.worklist, str(ts.date())))
    portfolio["specialisation_note"] = AS.SPECIALISATION_NOTE
    st.experts = portfolio["experts"]
    # ── اعتبارسنجی دستی سه حساب (بعد از ساخت فریم، چون به آن نیاز دارد)
    import validate_cases as VC
    portfolio["validation"] = VC.run(V, ts, st.frame)
    portfolio["focus_list"] = _focus_list(st.frame)

    CACHE.mkdir(exist_ok=True)
    (CACHE / "profiles.json").write_text(json.dumps(enriched, ensure_ascii=False), encoding="utf-8")
    (CACHE / "portfolio.json").write_text(
        json.dumps(_py(portfolio), ensure_ascii=False), encoding="utf-8")
    (CACHE / "periods.json").write_text(json.dumps(periods, ensure_ascii=False), encoding="utf-8")
    return st


def load_store(rebuild: bool = False) -> Store:
    if rebuild or not (CACHE / "profiles.json").exists() or not (CACHE / "periods.json").exists():
        return build_cache()
    enriched = json.loads((CACHE / "profiles.json").read_text(encoding="utf-8"))
    portfolio = json.loads((CACHE / "portfolio.json").read_text(encoding="utf-8"))
    periods = json.loads((CACHE / "periods.json").read_text(encoding="utf-8"))
    return Store(enriched, portfolio, periods)


if __name__ == "__main__":
    import sys
    import time
    t = time.time()
    st = build_cache(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"کش ساخته شد در {time.time() - t:.1f} ثانیه — {len(st.P)} پروفایل، "
          f"{len(st.text_index)} رکورد متنی، "
          f"{int(st.frame.reference_count.sum()):,} رفرنس\n")
    print(st.portfolio_summary())
    print("\n" + "─" * 80 + "\n")
    print(st.segment_overview("quadrant"))
    print("\n" + "─" * 80 + "\n")
    print(st.get_value_breakdown("C_245948")[:2000])
