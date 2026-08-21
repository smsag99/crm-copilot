"""چند ارجاع نمونه می‌سازد تا بخش «پیگیری کارشناسان» در دمو خالی نباشد.

هر سه ارجاع از سطرهای واقعی کارتابل ساخته می‌شوند — همان مشتری، همان هدف،
همان کانال و همان دستور کار تماس. فقط متن گزارش کارشناس ساختگی است و برای
اینکه با عدد اشتباه گرفته نشود، در خودِ گزارش نوشته می‌شود «نمونهٔ دمو».

    python seed_referrals.py            # بازنویسی از صفر
"""
from __future__ import annotations

import json
from pathlib import Path

import assignments as AS

DEMO = "«نمونهٔ دمو — این گزارش برای نمایش گردش کار ثبت شده است.»"


def main() -> None:
    p = Path("cache/portfolio.json")
    port = json.loads(p.read_text(encoding="utf-8"))
    prof = json.loads(Path("cache/profiles.json").read_text(encoding="utf-8"))
    experts = port["experts"]
    rows = [r for r in port["worklist"]["rows"] if AS.referrable(r)]
    if not rows:
        print("سطر تماسی در کارتابل نیست."); return

    AS.STATE.unlink(missing_ok=True)
    picks = rows[:3]
    made = []
    for r in picks:
        owner = (prof.get(r["customer_id"]) or {}).get("identity", {}).get("sales_rep_id")
        s = AS.suggest_expert(r, owner, experts)
        made.append(AS.create(r, s["expert_id"], s,
                              "پیش از تماس، آخرین فاکتور باز را جلوی دستتان بگذارید."))

    # ۱) تازه ارجاع‌شده — دست‌نخورده می‌ماند
    # ۲) گزارش داده، منتظر تصمیم مدیر
    AS.submit_report(made[1]["id"], {
        "outcome": "برقرار شد و گفت‌وگو انجام شد",
        "said": f"«نقدینگی این ماه درگیر خرید مواد اولیه است؛ تا پانزدهم تسویه می‌کنم.» {DEMO}",
        "commitment": "پرداخت بخشی از معوق تا پانزدهم ماه، مبلغ در گفت‌وگو تعیین شد",
        "blocker": "چک برگشتی قبلی هنوز در پرونده باز است و اعتبار جدید را قفل کرده",
        "recommend": "پیگیری مجدد در تاریخ مشخص",
        "next_date": "2022-07-06",
    })
    # ۳) گزارش داده و مدیر تصمیم گرفته — پرونده بسته
    AS.submit_report(made[2]["id"], {
        "outcome": "برقرار شد و گفت‌وگو انجام شد",
        "said": f"«مشکل کیفی لات قبلی با تعویض حل شد؛ سفارش بعدی را ثبت می‌کنیم.» {DEMO}",
        "commitment": "ثبت سفارش دورهٔ بعد با همان کد کالا",
        "blocker": "تعهدی گرفته نشد",
        "recommend": "مشکل حل شد — پرونده بسته شود",
        "next_date": "",
    })
    AS.decide(made[2]["id"], "closed", "گزارش کنترل کیفیت هم تأیید کرد.")

    for r in AS.all_referrals():
        print(f"{r['id']}  {r['customer_id']}  {r['expert_id']}  {r['status']}")


if __name__ == "__main__":
    main()
