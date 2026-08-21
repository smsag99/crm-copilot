"""دستیار هوشمند — اتصال Gemini به لایهٔ ابزار با function calling.

سه اصل طراحی:
  ۱. مدل محاسبه نمی‌کند. هر عدد از ابزار می‌آید، پس قابل راستی‌آزمایی است.
  ۲. اگر کلید API نباشد یا شبکه قطع باشد، دستیار به حالت قطعی برمی‌گردد و
     همان ابزارها را با تطبیق قاعده‌محور صدا می‌زند. دموی هکاتون نباید بمیرد.
  ۳. سه هشدار دادهٔ اجباری در پرامپت سیستم قفل شده‌اند: تورم، مبنای بهای
     تمام‌شده، و پرچم نشتی وضعیت مشتری.
"""
from __future__ import annotations

import os
import re
from typing import Any

from store import Store, norm

MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]

SYSTEM_PROMPT = """تو دستیار تحلیل مشتریان یک تولیدکنندهٔ نخ پلی‌استر (POY) هستی.
به پرسش‌های مدیران و کارشناسان فروش دربارهٔ مشتریان پاسخ می‌دهی.

قواعد الزامی:
- هیچ عددی را خودت محاسبه یا حدس نزن. همیشه ابزار مناسب را صدا بزن و فقط
  اعدادی را بگو که ابزار برگردانده است. اگر ابزار عددی نداد، بگو در دسترس نیست.
- پاسخ‌ها را کوتاه و عملیاتی بنویس. جدول یا فهرست نشانه‌دار بهتر از پاراگراف است.
- همیشه فارسی پاسخ بده.
- برای پرسش کلی دربارهٔ کل کسب‌وکار از portfolio_summary استفاده کن، نه جمع‌زدن
  پروفایل‌ها.
- برای یافتن مشتری «که فلان مشکل را دارد» از search_customers با پارامتر
  has_risk یا has_opportunity استفاده کن.
- برای پرسش‌هایی که به متن اشاره دارند (شکایت دربارهٔ فلان موضوع، گزارش
  کارشناس، درخواست فنی) از search_text استفاده کن.
- برای «چه سیگنالی داریم» یا «احتمالاً چه می‌کند» از get_signals_and_predictions.
- برای ارزش، سودآوری یا LTV یک مشتری از get_value_breakdown.
- برای دسته‌بندی مشتریان از segment_overview.
- برای «چه الگویی کشف شد» یا «مدل چقدر دقیق است» از data_patterns.
- برای سودآوری واقعی، هزینهٔ پول، اینکه وقت تیم کجا برود یا کدام مشتری را رها کنیم،
  از focus_list استفاده کن.
- برای «الان چه کار کنم»، «با این مشتری چطور تماس بگیرم»، «در جلسه چه بگویم» یا
  «کار امروز چیست» از work_card استفاده کن و شناسهٔ مشتری را بده.
- برای هر پرسش دوره‌ای — «این ماه چطور بود»، «نسبت به دورهٔ قبل»، «دورهٔ بعد چه
  می‌شود»، «الان سراغ کدام مشتری بروم» — از period_summary استفاده کن و طول دوره
  را از خود پرسش استخراج کن.
- برای «به چه کسی آفر بدهیم»، «چقدر تخفیف»، «چرا این آفر به این مشتری» یا «مهلت
  آفر چقدر باشد» از offer_plan استفاده کن. هرگز نگو تخفیف بیشتر پذیرش را بالا
  می‌برد — روی این داده آزموده و رد شده است (p=۰٫۹۰).

**رفرنس‌دهی الزامی است.** ابزارها زیر هر ادعا خط «↳ منبع:» می‌گذارند که نام شیت،
شناسهٔ رکورد، تاریخ و فیلد را نشان می‌دهد. این خطوط را در پاسخت نگه دار یا
بازنویسی کن؛ هر عددی که می‌گویی باید منبعش معلوم باشد. اگر ابزار رفرنس نداد،
بگو «منبع این عدد در خروجی ابزار نیامده».

**پاسخ را با Markdown قالب‌بندی کن**: تیتر با ##، تأکید با **، فهرست با -، و
جدول Markdown برای مقایسه. رابط کاربری Markdown را رندر می‌کند.

**مهم‌ترین یافتهٔ این پروژه:** حاشیهٔ ناخالص مشتریان را از هم جدا نمی‌کند. پول این سبد
به‌طور میانگین ۵۴ روز نزد مشتری می‌ماند و با نرخ ۴٪ ماهانه، هزینهٔ تأمین مالی
(۴۶۹ میلیون) از کل سود ناخالص (۴۴۳ میلیون) بیشتر است — یعنی سود واقعی سبد منفی است.
آزمون قیمت نشان داد مارک‌آپ اعتبار در قیمت ثبت نشده (برای شرط ۹۰ روزه، انتظار ۱۲٪ و
مشاهده ۲٪ بدون معناداری آماری). پس هر جا از سودآوری حرف می‌زنی، **حاشیهٔ واقعی پس از
هزینهٔ پول** را مبنا بگیر، نه حاشیهٔ ناخالص، و قید کن که نرخ ۴٪ فرض بیرونی است.

چهار هشدار دادهٔ همیشگی — هر بار که این اعداد را نقل می‌کنی، قید کن:
۱. فروش اسمی است؛ قیمت میانگین واحد در مقایسهٔ هم‌ارز بهار ۱۳۹۹ تا بهار ۱۴۰۱ حدود
   ۸ برابر شده. برای
   روند، حجم (کیلوگرم) یا فروش حقیقی را مبنا بگیر و بگو کدام را استفاده کردی.
۲. حاشیه سود ترکیبی است: ۳۲٪ خطوط بر مبنای هزینهٔ تحقق‌یافته و بقیه بر مبنای
   هزینهٔ برآوردی که حاشیه را حدود ۵ واحد درصد خوش‌بینانه‌تر نشان می‌دهد.
۳. فیلد source_status_LEAKY همان رکود ۱۸۰ روزه است که برچسب دیگری خورده؛ هرگز
   به‌عنوان شاهد استفاده نکن.
۴. نرخ ۴٪ ماهانهٔ هزینهٔ پول یک فرض کسب‌وکاری بیرونی است، نه چیزی که از داده درآمده
   باشد؛ در داشبورد قابل تغییر است و رتبه‌بندی با آن جابه‌جا می‌شود.

تفاوت مطالبات: «معوق» سررسیدگذشته است و ریسک اعتباری؛ «سررسیدنشده» سرمایه در
گردش است و ریسک نیست. مشارکت خالص فقط بخش معوق را کسر می‌کند.

دربارهٔ احتمال‌ها: نرخ‌های پایه از شمارش رویدادهای واقعی این داده می‌آیند و ابزار
تعداد مشاهده را می‌گوید. دو استثنا را همیشه قید کن: «احتمال درخواست تخفیف» نرخ
پایهٔ تجربی ندارد و نسبی است؛ و «تأخیر پرداخت» تقریباً ساختاری است و سابقه خبر
کمی دارد.

دربارهٔ الگوها: دو الگو آزموده و **رد** شدند — شکایت و درخواست توسعه، هیچ‌کدام
پیش‌بین مستقل ریزش نیستند (اثر ظاهری‌شان از عمق رابطه می‌آمد). اگر کاربر خلافش را
فرض کرد، اصلاح کن. الگوی تأییدشده این است: خرید از ۲+ گروه کالا حدود ۲۰ واحد
درصد ماندگاری بیشتر می‌دهد.

بازهٔ داده تا ۹ تیر ۱۴۰۱ است. هرگز طوری پاسخ نده که گویی از بعد از آن خبر داری.
"""

TOOLS_SPEC = [
    {
        "name": "portfolio_summary",
        "description": "آمار کل سبد مشتریان: فروش، سود، حاشیه، مطالبات معوق، تمرکز، تعداد مشتری راکد و آمار بخش‌ها. برای هر پرسشی که دربارهٔ کل کسب‌وکار است و نه یک مشتری خاص.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_customer_profile",
        "description": "پروفایل کامل یک مشتری: عملکرد تجاری، سودآوری و بهای تمام‌شده، مطالبات، شکایات و کیفیت، تعاملات، درخواست‌های توسعه، آفرها و سهم از سبد.",
        "parameters": {
            "type": "object",
            "properties": {"customer_id": {"type": "string",
                                           "description": "شناسهٔ مشتری، مثل C_937594"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_risks_and_actions",
        "description": "ریسک‌ها، فرصت‌ها و اقدام بعدی پیشنهادی یک مشتری، هر کدام همراه شاهد عددی و واحد مسئول.",
        "parameters": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_signals_and_predictions",
        "description": "سیگنال‌های یک مشتری (خرید، قیمت، کیفیت، پرداخت، توسعه، رقابت، ارتباط)، تفسیر هر سیگنال، و پیش‌بینی تصمیم‌های احتمالی دورهٔ بعد با نرخ پایهٔ تجربی و رفرنس به رکورد منبع. برای پرسش‌هایی مثل «چه سیگنالی از این مشتری داریم» یا «احتمال دارد چه کاری بکند».",
        "parameters": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_value_breakdown",
        "description": "ارزش طول عمر (LTV) یک مشتری با تجزیهٔ کامل اجزا، اجزای احتمال ماندگاری، بخش‌بندی RFM و چهارخانهٔ حاشیه-ریسک، و همهٔ اعداد کامرشال. برای هر پرسشی دربارهٔ ارزش، سودآوری یا LTV یک مشتری.",
        "parameters": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "segment_overview",
        "description": "نمای بخش‌بندی کل سبد: چهارخانهٔ حاشیه سود در برابر ریسک از دست دادن (رشد بده / نجات فوری / اصلاح قیمت / بازبینی رابطه) یا بخش‌های RFM. برای پرسش دربارهٔ دسته‌بندی مشتریان.",
        "parameters": {
            "type": "object",
            "properties": {"kind": {"type": "string", "enum": ["quadrant", "rfm"]}},
        },
    },
    {
        "name": "data_patterns",
        "description": "الگوهای آزموده‌شده روی این داده — شامل الگوهایی که رد شدند — و کارت مدل پیش‌بینی ماندگاری با AUC و خطای کالیبراسیون. برای پرسش دربارهٔ اینکه چه چیزی در داده کشف شده یا مدل چقدر دقیق است.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "search_customers",
        "description": "رتبه‌بندی و پالایش سبد مشتریان. پیش از get_customer_profile از این استفاده کن تا بفهمی کدام مشتری‌ها را باید بررسی کنی.",
        "parameters": {
            "type": "object",
            "properties": {
                "sort_by": {"type": "string",
                            "enum": ["ltv_total", "rescue_value", "revenue", "gross_profit",
                                     "margin_pct", "retention", "p_churn", "p_reorder",
                                     "overdue", "net_contribution", "days_since_purchase",
                                     "volume", "complaints", "open_complaints", "wallet_share",
                                     "risk_score", "opportunity_score", "signal_score",
                                     "volume_trend", "collection_rate", "oldest_overdue_days",
                                     "silence_ratio", "rank_gap"],
                            "description": "ستون مرتب‌سازی"},
                "ascending": {"type": "boolean", "description": "صعودی؟ برای بدترین‌ها true"},
                "limit": {"type": "integer"},
                "segment": {"type": "string", "enum": ["A", "B", "C"]},
                "has_risk": {"type": "string",
                             "description": "کد ریسک: overdue_exceeds_gp، overdue_aged، bounced_cheques، over_credit_limit، low_collection_rate، dormant، volume_collapse، quality_linked_decline، open_severe_complaint، thin_margin، many_negative_lines، uncontacted_active، no_crm_history، competitor_dominant، market_price_pressure، single_family_dependency"},
                "has_opportunity": {"type": "string",
                                    "description": "کد فرصت: wallet_share_gap، approved_sample_idle، pending_dev_request، pending_offers، offer_responsive، cross_sell، growing، repricing_upside، recovered_trust، win_back"},
                "has_signal": {"type": "string",
                               "description": "کد سیگنال: silence_gap، volume_trend، purchase_plan، price_talk، complaint_history، quality_purchase_link، overdue، chase، bounced، dev_history، wallet_gap، wallet_falling، no_crm، uncontacted_buyer، open_actions"},
                "rfm_segment": {"type": "string",
                                "description": "نام بخش RFM: قهرمانان، وفادار، نمی‌توان از دست داد، در معرض ریزش، ازدست‌رفتهٔ باارزش، خفته، نیازمند توجه، وفادار بالقوه، تازه‌وارد، در حال خواب، ازدست‌رفته"},
                "quadrant": {"type": "string",
                             "description": "خانهٔ حاشیه-ریسک: «رشد بده» یا «نجات فوری» یا «اصلاح قیمت» یا «بازبینی رابطه»"},
                "min_revenue": {"type": "number"},
                "dormant_days_min": {"type": "integer",
                                     "description": "حداقل روز از آخرین خرید"},
            },
        },
    },
    {
        "name": "search_text",
        "description": "جست‌وجو در متن آزاد سازمان: متن شکایت‌های مشتریان، گزارش‌های کارشناسان فروش در CRM و شرح درخواست‌های توسعه محصول. برای پرسش‌هایی مثل «کدام مشتری‌ها از شید رنگ شکایت کردند» یا «چه کسی درخواست بسته‌بندی خاص داشت».",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "عبارت فارسی برای جست‌وجو"},
                "limit": {"type": "integer"},
                "kind": {"type": "string", "enum": ["شکایت", "تعامل CRM", "درخواست توسعه"]},
            },
            "required": ["query"],
        },
    },
    {
        "name": "work_card",
        "description": ("کارتابل: کار امروز. با شناسهٔ مشتری، کارت کامل او را می‌دهد — "
                        "هدف ارتباط، هویت، بهترین کانال، کارها، «همین حالا چه کن»، و "
                        "دستور کار تماس یا جلسه با نکته‌های واقعی همان مشتری. بدون "
                        "شناسه، کارت‌های مشکل و سطرهای اول کارتابل را می‌دهد."),
        "parameters": {"type": "object", "properties": {
            "customer_id": {"type": "string", "description": "مثل C_245948؛ اختیاری"},
            "family": {"type": "string",
                       "description": "خانوادهٔ مشکل: وصول، سودآوری، ریزش، کیفیت، رقابت، رابطه"},
            "limit": {"type": "integer"}}},
    },
    {
        "name": "focus_list",
        "description": ("هزینهٔ پول، سود واقعی، آزمون قیمت‌گذاری اعتبار، چهار خانهٔ تمرکز "
                        "و فهرست کوتاه‌شدهٔ مشتریانی که وقت تیم را می‌ارزند — با دلیل هر حذف. "
                        "برای پرسش‌هایی مثل «کدام مشتری واقعاً سودآور است»، «هزینهٔ پول چقدر "
                        "است»، «وقت تیم را کجا بگذاریم»، «کدام مشتری‌ها را رها کنیم»."),
        "parameters": {"type": "object",
                       "properties": {"limit": {"type": "integer",
                                                "description": "تعداد سطر فهرست، پیش‌فرض ۱۵"}}},
    },
    {
        "name": "period_summary",
        "description": ("خلاصهٔ یک دورهٔ زمانی: فروش، سود، وصول، معوق و شکایت در دوره، "
                        "مقایسه با دورهٔ قبل، پیش‌بینی دورهٔ بعد با خطای بک‌تست، فهرست "
                        "مشتریان نیازمند رسیدگی و سه مشکل پرتکرار. برای پرسش‌هایی مثل "
                        "«این ماه چطور بود»، «نسبت به دورهٔ قبل»، «دورهٔ بعد چه می‌شود» "
                        "و «الان باید سراغ کدام مشتری بروم»."),
        "parameters": {
            "type": "object",
            "properties": {
                "period": {"type": "string",
                           "description": ("طول دوره: 1w، 2w، 1m، 2m، 3m، 6m یا 1y. "
                                           "اگر ندهی، دورهٔ پیشنهادی داده استفاده می‌شود.")},
            },
        },
    },
    {
        "name": "offer_plan",
        "description": ("موتور آفر: به چه مشتری، چه آفری، با چه تخفیف و چه مهلتی — و "
                        "دلیل داده‌محورش. یافتهٔ کلیدی: پذیرش در پنجرهٔ ۸ تا ۱۴ روزه "
                        "۶۲٪ و بیرون از آن ۴۵٪ است، ولی عمق تخفیف هیچ اثری ندارد. "
                        "برای پرسش‌هایی مثل «به چه کسی آفر بدهیم»، «چقدر تخفیف بدهیم»، "
                        "«چرا این آفر به این مشتری»، «کدام مشتری فضای تخفیف ندارد»."),
        "parameters": {"type": "object", "properties": {
            "customer_id": {"type": "string", "description": "مثل C_245948؛ اختیاری"},
            "play": {"type": "string", "enum": ["بازگشت", "فروش مکمل", "افزایش سهم"]},
            "limit": {"type": "integer"}}},
    },
    {
        "name": "compare_customers",
        "description": "مقایسهٔ دو تا پنج مشتری روی شاخص‌های تصمیم‌ساز.",
        "parameters": {
            "type": "object",
            "properties": {"customer_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["customer_ids"],
        },
    },
]


class Copilot:
    def __init__(self, store: Store, api_key: str | None = None, model: str | None = None):
        self.store = store
        self.dispatch = {
            "portfolio_summary": lambda **k: store.portfolio_summary(),
            "get_customer_profile": store.get_customer_profile,
            "get_risks_and_actions": store.get_risks_and_actions,
            "get_signals_and_predictions": store.get_signals_and_predictions,
            "get_value_breakdown": store.get_value_breakdown,
            "segment_overview": store.segment_overview,
            "data_patterns": lambda **k: store.data_patterns(),
            "search_customers": store.search_customers,
            "search_text": store.search_text,
            "compare_customers": store.compare_customers,
            "period_summary": store.period_summary,
            "focus_list": store.focus_list,
            "work_card": store.work_card,
            "offer_plan": store.offer_plan,
        }
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.model = model or os.environ.get("GEMINI_MODEL") or MODELS[0]
        self.client = None
        self.last_error: str | None = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as exc:                     # noqa: BLE001
                self.last_error = f"راه‌اندازی Gemini ناموفق بود: {exc}"

    @property
    def mode(self) -> str:
        return "gemini" if self.client else "deterministic"

    # ───────────────────────────────────────────────── حالت مدل زبانی
    def _ask_gemini(self, question: str, history: list[dict] | None = None,
                    max_turns: int = 6) -> dict:
        from google.genai import types

        tools = [types.Tool(function_declarations=[
            types.FunctionDeclaration(name=t["name"], description=t["description"],
                                      parameters=t["parameters"]) for t in TOOLS_SPEC])]
        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT, tools=tools, temperature=0.2,
            max_output_tokens=2048)

        contents = []
        for h in (history or [])[-6:]:
            contents.append(types.Content(role="user" if h["role"] == "user" else "model",
                                          parts=[types.Part(text=h["content"])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=question)]))

        trace: list[dict] = []
        for _ in range(max_turns):
            resp = self.client.models.generate_content(
                model=self.model, contents=contents, config=cfg)
            cand = resp.candidates[0] if resp.candidates else None
            parts = list(cand.content.parts or []) if cand and cand.content else []
            calls = [p.function_call for p in parts if getattr(p, "function_call", None)]
            if not calls:
                text = "".join(p.text for p in parts if getattr(p, "text", None)) or \
                       "پاسخی تولید نشد."
                return {"answer": text, "trace": trace, "mode": "gemini", "model": self.model}

            contents.append(cand.content)
            results = []
            for fc in calls:
                args = dict(fc.args or {})
                try:
                    out = self.dispatch[fc.name](**args)
                except Exception as exc:                 # noqa: BLE001
                    out = f"خطا در اجرای ابزار: {exc}"
                trace.append({"tool": fc.name, "args": args, "chars": len(str(out))})
                results.append(types.Part.from_function_response(
                    name=fc.name, response={"result": str(out)}))
            contents.append(types.Content(role="user", parts=results))
        return {"answer": "به سقف مراحل رسیدیم بدون پاسخ نهایی.", "trace": trace,
                "mode": "gemini", "model": self.model}

    # ─────────────────────────────────── حالت قطعی (پشتیبان بدون شبکه)
    _CID = re.compile(r"\bC[_-]?(\d{4,6})\b", re.I)

    def _ask_deterministic(self, question: str) -> dict:
        """تطبیق قاعده‌محور روی همان ابزارها. برای وقتی شبکه یا کلید نیست."""
        q = norm(question)
        trace: list[dict] = []

        def run(tool: str, **kw):
            trace.append({"tool": tool, "args": kw})
            return self.dispatch[tool](**kw)

        m = self._CID.search(question)
        if m:
            cid = f"C_{m.group(1).zfill(6)}"
            if any(w in q for w in [norm(x) for x in
                                    ["سیگنال", "پیش بینی", "پیشبینی", "احتمال", "چه می کند",
                                     "تصمیم"]]):
                return {"answer": run("get_signals_and_predictions", customer_id=cid),
                        "trace": trace, "mode": "deterministic"}
            if any(w in q for w in [norm(x) for x in
                                    ["ارزش طول عمر", "ltv", "سودآوری", "ارزش", "کامرشال"]]):
                return {"answer": run("get_value_breakdown", customer_id=cid),
                        "trace": trace, "mode": "deterministic"}
            if any(w in q for w in [norm(x) for x in
                                    ["چه کار", "چطور تماس", "جلسه", "تماس", "دستور کار",
                                     "کارتابل", "امروز"]]):
                return {"answer": run("work_card", customer_id=cid),
                        "trace": trace, "mode": "deterministic"}
            if any(w in q for w in [norm(x) for x in
                                    ["آفر", "تخفیف", "پیشنهاد قیمت", "مهلت"]]):
                return {"answer": run("offer_plan", customer_id=cid),
                        "trace": trace, "mode": "deterministic"}
            if any(w in q for w in [norm(x) for x in
                                    ["ریسک", "فرصت", "اقدام", "خطر", "پیشنهاد", "چه کنم"]]):
                return {"answer": run("get_risks_and_actions", customer_id=cid),
                        "trace": trace, "mode": "deterministic"}
            return {"answer": run("get_customer_profile", customer_id=cid),
                    "trace": trace, "mode": "deterministic"}

        def hasw(*words) -> bool:
            return any(norm(w) in q for w in words)

        if hasw("این دوره", "دوره قبل", "دوره بعد", "این ماه", "ماه گذشته", "این هفته",
                "هفته گذشته", "پیش بینی دوره", "خلاصه دوره", "روند دوره", "سه ماه اخیر",
                "سراغ کدام", "رسیدگی", "چه کاری", "الان باید", "اولویت امروز",
                "مشکل پرتکرار", "پرتکرارترین مشکل", "کدام مشتری را اول"):
            per = ("1w" if hasw("هفته") and not hasw("دو هفته") else
                   "2w" if hasw("دو هفته") else
                   "3m" if hasw("سه ماه", "فصل") else
                   "6m" if hasw("شش ماه") else
                   "1y" if hasw("سال") else
                   "2m" if hasw("دو ماه") else "1m" if hasw("ماه") else "")
            return {"answer": run("period_summary", period=per), "trace": trace,
                    "mode": "deterministic"}
        if hasw("هزینه پول", "حاشیه واقعی", "سود واقعی", "فهرست تمرکز", "رها کنیم",
                "وقت تیم", "کدام مشتری سودآور", "توجه کمتر", "کاهش بده", "تامین مالی",
                "شرایط پرداخت"):
            return {"answer": run("focus_list"), "trace": trace, "mode": "deterministic"}
        if hasw("آفر", "تخفیف", "مهلت آفر", "پیشنهاد قیمتی", "کمپین", "چه کسی آفر"):
            play = ("بازگشت" if hasw("بازگشت", "برگرداندن", "افت خرید") else
                    "فروش مکمل" if hasw("مکمل", "کالای جدید", "محصول جدید") else
                    "افزایش سهم" if hasw("سهم", "رقیب") else "")
            return {"answer": run("offer_plan", play=play), "trace": trace,
                    "mode": "deterministic"}
        if hasw("الگو", "پترن", "کشف", "مدل چقدر", "دقت مدل", "auc", "اعتبارسنجی"):
            return {"answer": run("data_patterns"), "trace": trace, "mode": "deterministic"}
        if hasw("rfm", "بخش بندی", "دسته بندی", "چهارخانه"):
            kind = "rfm" if hasw("rfm") else "quadrant"
            return {"answer": run("segment_overview", kind=kind), "trace": trace,
                    "mode": "deterministic"}
        if hasw("حاشیه خوب", "در حال از دست", "نجات"):
            return {"answer": run("search_customers", quadrant="نجات فوری",
                                  sort_by="rescue_value", limit=12),
                    "trace": trace, "mode": "deterministic"}
        if hasw("ارزش طول عمر", "ltv"):
            return {"answer": run("search_customers", sort_by="ltv_total", limit=12),
                    "trace": trace, "mode": "deterministic"}
        if hasw("آفر باز", "آفر بی پاسخ", "آفر بیپاسخ"):
            return {"answer": run("search_customers", has_opportunity="offer_",
                                  sort_by="revenue", limit=12),
                    "trace": trace, "mode": "deterministic"}
        if hasw("یک گروه کالا", "تک محصول", "تک گروه"):
            return {"answer": run("search_customers", has_risk="single_family_dependency",
                                  sort_by="revenue", limit=12),
                    "trace": trace, "mode": "deterministic"}

        # الگوهای ترکیبی، مرتب از خاص به عام
        if hasw("شکایت", "کیفیت") and hasw("کم", "کاهش", "افت", "ریزش", "پایین"):
            code = "quality_linked_decline"
        elif hasw("چک برگشتی", "چک"):
            code = "bounced_cheques"
        elif hasw("سقف اعتبار", "اعتبار"):
            code = "over_credit_limit"
        elif hasw("راکد", "بی خرید", "قطع خرید", "برنگشته", "ریزش مشتری", "بازیابی"):
            code = "dormant"
        elif hasw("معوق", "مطالبات", "وصول", "بدهی", "طلب"):
            code = "overdue_exceeds_gp"
        elif hasw("حاشیه", "زیان", "سودآوری", "ضرر", "سود منفی"):
            code = "thin_margin"
        elif hasw("ریزش حجم", "کاهش خرید", "افت حجم", "افت فروش"):
            code = "volume_collapse"
        else:
            code = None
        if code:
            return {"answer": run("search_customers", has_risk=code,
                                  sort_by="revenue", limit=10),
                    "trace": trace, "mode": "deterministic"}

        if hasw("فرصت", "رشد", "سهم از سبد", "نمونه تایید", "فروش مکمل"):
            opp = ("wallet_share_gap" if hasw("سهم از سبد") else
                   "approved_sample_idle" if hasw("نمونه") else
                   "growing" if hasw("رشد") else
                   "cross_sell" if hasw("مکمل") else None)
            return {"answer": run("search_customers", has_opportunity=opp,
                                  sort_by="opportunity_score", limit=10)
                    if opp else run("search_customers", sort_by="opportunity_score", limit=10),
                    "trace": trace, "mode": "deterministic"}

        if hasw("شید رنگ", "پرز", "استحکام", "بسته بندی", "دنیر", "فیلامنت", "رگه",
                "گزارش کارشناس", "متن", "شکایت درباره"):
            return {"answer": run("search_text", query=question, limit=10),
                    "trace": trace, "mode": "deterministic"}

        if hasw("کل سبد", "کل مشتریان", "خلاصه", "وضعیت شرکت", "مجموع", "پرتفو",
                "کل کسب و کار", "وضعیت کلی"):
            return {"answer": run("portfolio_summary"), "trace": trace,
                    "mode": "deterministic"}

        # پیش‌فرض: بدترین مشارکت خالص، چون همیشه پرسش درست کسب‌وکار است
        return {"answer": "پرسش را دقیق‌تر متوجه نشدم؛ این مشتریان بیشترین ارزش‌سوزی را "
                          "دارند:\n\n" + run("search_customers", sort_by="net_contribution",
                                             ascending=True, limit=8),
                "trace": trace, "mode": "deterministic"}

    # ────────────────────────────────────────────────────────── ورودی اصلی
    def ask(self, question: str, history: list[dict] | None = None) -> dict:
        if self.client:
            try:
                return self._ask_gemini(question, history)
            except Exception as exc:                      # noqa: BLE001
                self.last_error = str(exc)
                out = self._ask_deterministic(question)
                out["fallback_reason"] = f"Gemini پاسخ نداد ({type(exc).__name__})؛ " \
                                         "پاسخ از حالت قطعی تولید شد."
                return out
        return self._ask_deterministic(question)


SUGGESTED_QUESTIONS = [
    "وضعیت کل سبد مشتریان چطور است؟",
    "کدام مشتری‌ها حاشیه سود خوبی دارند ولی در حال از دست رفتن‌اند؟",
    "بالاترین ارزش طول عمر مال کدام مشتریان است؟",
    "چه سیگنالی از مشتری C_683666 داریم و احتمالاً چه می‌کند؟",
    "ارزش طول عمر C_245948 را تجزیه کن",
    "چه الگویی در این داده کشف شد و مدل چقدر دقیق است؟",
    "کدام مشتری‌ها آفر باز و بی‌پاسخ دارند؟",
    "بخش‌بندی RFM سبد را نشان بده",
    "شکایت‌های مربوط به شید رنگ در کدام مشتری‌ها ثبت شده؟",
    "کدام مشتری‌ها فقط از یک گروه کالا خرید می‌کنند؟",
    "خلاصهٔ این دوره چطور بود و دورهٔ بعد چه می‌شود؟",
    "الان باید سراغ کدام مشتری‌ها بروم؟",
    "برای C_245948 در جلسه چه چیزهایی را مطرح کنم؟",
    "با احتساب هزینهٔ پول، کدام مشتری‌ها واقعاً سودآورند؟",
    "کدام مشتری‌ها را باید رها کنیم و چرا؟",
    "به چه کسانی آفر بدهیم و چقدر تخفیف؟",
    "چرا به C_593639 آفر می‌دهیم و مهلتش چقدر باشد؟",
]

if __name__ == "__main__":
    import json
    import sys
    from store import load_store

    st = load_store()
    cp = Copilot(st)
    print(f"حالت دستیار: {cp.mode}" + (f" ({cp.model})" if cp.client else "")
          + (f" | خطا: {cp.last_error}" if cp.last_error else ""))
    qs = sys.argv[1:] or SUGGESTED_QUESTIONS[:3]
    for q in qs:
        print("\n" + "═" * 78 + f"\n❯ {q}\n" + "═" * 78)
        r = cp.ask(q)
        print(r["answer"][:2200])
        if r.get("trace"):
            print("\n[ابزارهای فراخوانی‌شده: " +
                  ", ".join(f"{t['tool']}({json.dumps(t.get('args', {}), ensure_ascii=False)})"
                            for t in r["trace"]) + "]")
        if r.get("fallback_reason"):
            print("[" + r["fallback_reason"] + "]")
