# golf_search_scheduler.py
import requests
import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict
from telegram.ext import Updater, CommandHandler
from golfmon_just import fetch_region_items, format_korean_time
from golpang_just import crawl_golfpang

BOT_TOKEN = "7601969886:AAHUXG1YLBs8x9GlKCXVrV3audyC_yJ-A2Y"
CHAT_ID = "5803438487"

watch_conditions = []

EXCLUDED_COURSES = [
    "제이퍼블릭(P6)", "올데이", "옥스필드cc", "남양주cc (P9)", "아세코(시흥)gc",
    "캐슬파인cc", "신안P(오렌지p9*2)", "한림안성P(9홀*2)", "더반cc(P9)"
]

GOLFMON_REGION_CODE = {
    "경기북부": 1, "경기동부": 2, "경기남부": 3, "충청": 4,
    "강원": 5, "전라": 6, "경상": 7, "제주": 8
}

GOLFPANG_REGION_MAP = {
    "경기북부": "강북/경춘", "경기동부": "강북/경춘", "경기남부": "한강이남",
    "충청": "충청", "강원": "원주/영동", "전라": "영호남/제주",
    "제주": "영호남/제주", "경상": None
}

def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"❌ 텔레그램 오류: {e}")

def send_safe_telegram(message: str):
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    for chunk in chunks:
        send_telegram_message(chunk)

def fetch_all_data(date, region_name, hour_range, max_price):
    results = []
    code = GOLFMON_REGION_CODE[region_name]
    for t_type in ["1", "2"]:
        items = fetch_region_items(date, code, t_type)
        for _, item in items:
            name = item.get("name", "").strip()
            if any(ex in name for ex in EXCLUDED_COURSES): continue
            time_raw = item.get("dates", "")
            try: hour = int(time_raw.split(" ")[1].split(":"))[0]
            except: hour = 99
            if hour_range and not(hour_range[0] <= hour <= hour_range[1]): continue
            fee_str = item.get("greenFee", "0")
            if not fee_str.isdigit(): continue
            fee = int(fee_str)
            if max_price and fee > max_price: continue
            tee_time = format_korean_time(time_raw)
            price = f"{fee:,}원"
            tag = "양도" if t_type == "1" else "조인"
            results.append(["골프몬", region_name, tag, name, tee_time, price, fee])

    pang_region = GOLFPANG_REGION_MAP.get(region_name)
    if pang_region:
        pang_items = crawl_golfpang(pang_region, date)
        for row in pang_items:
            name = row[3].strip()
            if any(ex in name for ex in EXCLUDED_COURSES): continue
            try:
                hour = int(row[0].split(":"))[0]
                fee = int(row[5].replace(",", "").replace("원", ""))
            except:
                hour = 99; fee = 999999
            if hour_range and not(hour_range[0] <= hour <= hour_range[1]): continue
            if max_price and fee > max_price: continue
            results.append(["골팡", region_name, row[2], name, row[0], row[5], fee])
    return results

def start_watch():
    if not watch_conditions:
        send_telegram_message("⛔ 감시할 조건이 없습니다.")
        return

    seen = {}
    grouped = defaultdict(lambda: defaultdict(list))
    for cond in watch_conditions:
        for date in cond['dates']:
            rows = fetch_all_data(date, cond['region'], cond['hour_range'], cond['max_price'])
            for r in rows:
                key = (date, r[1], r[3], r[4], r[2])
                seen[key] = r[6]
                grouped[date][r[1]].append(r)
    for d, reg in grouped.items():
        for rname, items in reg.items():
            msg = f"<b>📅 {d} 신규 티타임 모음</b>\n📍 {rname}\n"
            for r in sorted(items, key=lambda x: x[6]):
                msg += f"• [{r[0]}] {r[2]} | {r[3]} | {r[4]} | {r[5]}\n"
            send_safe_telegram(msg.strip())

    def loop():
        while True:
            new = defaultdict(lambda: defaultdict(list))
            for cond in watch_conditions:
                for date in cond['dates']:
                    rows = fetch_all_data(date, cond['region'], cond['hour_range'], cond['max_price'])
                    for r in rows:
                        key = (date, r[1], r[3], r[4], r[2])
                        if key not in seen:
                            seen[key] = r[6]
                            new[date][r[1]].append(r)
                        elif seen[key] > r[6]:
                            old = seen[key]
                            seen[key] = r[6]
                            msg = f"💰 <b>가격 하락</b> <code>[{r[0]}]</code>\n📅 {date}\n📍 {r[1]}\n🏌️‍♂️ {r[3]} ({r[2]})\n⏰ {r[4]}\n💸 {old:,}원 → {r[6]:,}원"
                            send_telegram_message(msg)
            for d, reg in new.items():
                msg = f"<b>📅 {d} 신규 티타임 모음</b>\n"
                for rname, items in reg.items():
                    msg += f"\n📍 {rname}\n"
                    for r in sorted(items, key=lambda x: x[6]):
                        msg += f"• [{r[0]}] {r[2]} | {r[3]} | {r[4]} | {r[5]}\n"
                send_safe_telegram(msg.strip())
            time.sleep(60)

    threading.Thread(target=loop).start()

# 텔레그램 핸들러들
def cmd_add(update, context):
    try:
        _, region, date, hour_str, price = update.message.text.split()
        h1, h2 = map(int, hour_str.split(","))
        watch_conditions.append({
            "label": f"{region} - {date}",
            "dates": [date],
            "hour_range": (h1, h2),
            "region": region,
            "max_price": int(price)
        })
        update.message.reply_text(f"✅ 추가: {region} {date} {h1}-{h2}시 {price}원")
    except:
        update.message.reply_text("❌ 예시: /add 경기북부 2025-08-08 9,13 80000")

def cmd_list(update, context):
    if not watch_conditions:
        update.message.reply_text("⚠️ 조건 없음")
        return
    msg = "<b>📋 감시 조건:</b>\n"
    for i, cond in enumerate(watch_conditions, 1):
        msg += f"{i}. {cond['label']} / {cond['region']} / {','.join(cond['dates'])} / {cond['hour_range']} / {cond['max_price']}\n"
    update.message.reply_text(msg, parse_mode="HTML")

def cmd_remove(update, context):
    try:
        idx = int(update.message.text.split()[1]) - 1
        cond = watch_conditions.pop(idx)
        update.message.reply_text(f"🗑 삭제: {cond['label']}")
    except:
        update.message.reply_text("❌ 예시: /remove 1")

def cmd_start(update, context):
    update.message.reply_text("⏱ 감시 시작됨")
    start_watch()

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("add", cmd_add))
    dp.add_handler(CommandHandler("list", cmd_list))
    dp.add_handler(CommandHandler("remove", cmd_remove))
    dp.add_handler(CommandHandler("start", cmd_start))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
