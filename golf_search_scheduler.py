import time
import requests
from datetime import datetime, timedelta
from golfmon_just import fetch_region_items, format_korean_time
from golpang_just import crawl_golfpang
from collections import defaultdict

# 제외할 골프장 목록 (완전일치 기준)
EXCLUDED_COURSES = ["제이퍼블릭(P6)", "올데이", "옥스필드cc","남양주cc (P9)","아세코(시흥)gc","캐슬파인cc","신안P(오렌지p9*2)","남양주cc (P9)","한림안성P(9홀*2)","더반cc(P9)"]

# 텔레그램 설정
BOT_TOKEN = "7601969886:AAHUXG1YLBs8x9GlKCXVrV3audyC_yJ-A2Y"
CHAT_ID = "5803438487"

def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"❌ 텔레그램 전송 오류: {e}")

def send_safe_telegram(message: str):
    max_len = 4000
    chunks = [message[i:i+max_len] for i in range(0, len(message), max_len)]
    for chunk in chunks:
        send_telegram_message(chunk)

# 지역 코드 매핑
GOLFMON_REGION_CODE = {
    "경기북부": 1,
    "경기동부": 2,
    "경기남부": 3,
    "충청": 4,
    "강원": 5,
    "전라": 6,
    "경상": 7,
    "제주": 8,
}

GOLFPANG_REGION_MAP = {
    "경기북부": "강북/경춘",
    "경기동부": "강북/경춘",
    "경기남부": "한강이남",
    "충청": "충청",
    "강원": "원주/영동",
    "전라": "영호남/제주",
    "제주": "영호남/제주",
    "경상": None
}

watch_conditions = []

def generate_date_range(days):
    today = datetime.now()
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
def view_alerts():
    if not watch_conditions:
        print("⚠️ 현재 등록된 일정이 없습니다.\n")
        return
    print("\n📋 등록된 일정 목록:")
    for idx, cond in enumerate(watch_conditions, 1):
        print(f"{idx}. [{cond['label']}] 날짜={cond['dates']} / 시간={cond['hour_range']} / 지역={cond['region']} / 최대금액={cond['max_price']}")

def delete_alert():
    view_alerts()
    if not watch_conditions:
        return
    try:
        idx = int(input("🗑️ 삭제할 일정 번호를 입력하세요: ").strip()) - 1
        if 0 <= idx < len(watch_conditions):
            removed = watch_conditions.pop(idx)
            print(f"✅ 삭제 완료: {removed['label']}")
        else:
            print("❌ 번호 오류")
    except:
        print("❌ 입력 오류")

def add_alert():
    print("\n📆 감시할 날짜를 설정하세요:")
    print("   → 방식 선택 (days 또는 dates)")
    print("[예: days 오늘부터 특정일, dates: 특정일 지정]:")
    mode = input("입력: ").strip().lower()

    if mode == "days":
        try:
            days = int(input("   → 오늘부터 며칠간 감시할지 입력 [예: 2]: ").strip())
            dates = generate_date_range(days)
        except:
            print("❌ 숫자 오류. 다시 시도해주세요.")
            return
    elif mode == "dates":
        raw = input("   → 감시할 날짜들 쉼표로 입력 [예: 2025-05-07,2025-05-08]: ").strip()
        dates = [d.strip() for d in raw.split(",")]
    else:
        print("❌ 'days' 또는 'dates'만 입력 가능합니다.")
        return

    hour_range = None
    time_choice = input("⏰ 특정 시간대만 찾을까요? (y/n): ").strip().lower()
    if time_choice == "y":
        time_input = input("   → 시간 범위 입력 (24시간 기준, 쉼표로 구분) [예: 9,13]: ").strip()
        try:
            start, end = map(int, time_input.split(","))
            hour_range = (start, end)
        except:
            print("❌ 잘못된 형식입니다. 시간 조건 없음으로 진행됩니다.")

    print("\n📍 감시할 지역을 선택하세요:")
    print("0. 전체 지역")
    region_list = list(GOLFMON_REGION_CODE.keys())
    for idx, region in enumerate(region_list, 1):
        print(f"{idx}. {region}")
    sel = input("입력 (예: 1,2 또는 0): ").strip()

    if sel == "0":
        selected_regions = region_list
    else:
        try:
            indices = [int(x.strip()) - 1 for x in sel.split(",")]
            selected_regions = [region_list[i] for i in indices if 0 <= i < len(region_list)]
        except:
            print("❌ 지역 입력 오류")
            return

    try:
        max_price = int(input("💰 최대 그린피 금액 (예: 80000): ").strip())
    except:
        print("❌ 숫자가 아닙니다. 제한 없이 진행됩니다.")
        max_price = 0

    for region_name in selected_regions:
        label = f"{region_name} - {','.join(dates)}"
        watch_conditions.append({
            "label": label,
            "dates": dates,
            "hour_range": hour_range,
            "region": region_name,
            "max_price": max_price
        })

    print(f"✅ 일정 추가 완료: {len(selected_regions)}개 지역 등록됨")

def fetch_all_data(date, region_name, hour_range, max_price):
    results = []

    # 골프몬
    code = GOLFMON_REGION_CODE[region_name]
    for t_type in ["1", "2"]:
        items = fetch_region_items(date, code, t_type)
        for _, item in items:
            name = item.get("name", "").strip()
            if any(excluded in name for excluded in EXCLUDED_COURSES):
                continue
            time_raw = item.get("dates", "")
            try:
                hour = int(time_raw.split(" ")[1].split(":")[0])
            except:
                hour = 99
            if hour_range and not (hour_range[0] <= hour <= hour_range[1]):
                continue
            fee_str = item.get("greenFee", "0")
            if not fee_str.isdigit():
                continue  # 전화문의 등 무시
            fee = int(fee_str)
            if max_price and fee > max_price:
                continue
            tee_time = format_korean_time(time_raw)
            price = f"{fee:,}원"
            tag = "양도" if t_type == "1" else "조인"
            results.append(["골프몬", region_name, tag, name, tee_time, price, fee])

    # 골팡
    pang_region = GOLFPANG_REGION_MAP.get(region_name)
    if pang_region:
        pang_items = crawl_golfpang(pang_region, date)
        for row in pang_items:
            name = row[3].strip()
            if any(excluded in name for excluded in EXCLUDED_COURSES):
                continue
            try:
                hour = int(row[0].split(":")[0])
                fee_str = row[5].replace(",", "").replace("원", "").strip()
                if not fee_str.isdigit():
                    continue  # 전화문의 등 무시
                fee = int(fee_str)
            except:
                hour = 99
                fee = 999999
            if hour_range and not (hour_range[0] <= hour <= hour_range[1]):
                continue
            if max_price and fee > max_price:
                continue
            results.append(["골팡", region_name, row[2], name, row[0], row[5], fee])
    return results

def start_watch():
    if not watch_conditions:
        print("⛔ 감시할 일정이 없습니다.")
        return

    print("\n🚨 감시 시작 (1분 간격 자동 감시)")
    seen_tee_times = {}

    # ✅ 최초 실행 시 전체 티타임 모아서 날짜/지역별로 전송
    grouped_by_date_region = defaultdict(lambda: defaultdict(list))
    for cond in watch_conditions:
        region = cond['region']
        for date in cond['dates']:
            all_rows = fetch_all_data(date, region, cond["hour_range"], cond["max_price"])
            for row in all_rows:
                src, reg, typ, name, time_str, price_str, fee = row
                if "전화문의" in price_str:
                    continue
                key = (date, reg, name, time_str, typ)
                seen_tee_times[key] = fee
                grouped_by_date_region[date][region].append(row)

    for date, region_dict in grouped_by_date_region.items():
        if not region_dict:
            continue
        for region, items in region_dict.items():
            if not items:
                continue
            grouped = []
            grouped.append(f"<b>📅 {date} 신규 티타임 모음</b>")
            grouped.append(f"📍 {region}")
            for src, reg, typ, name, time_str, price_str, _ in sorted(items, key=lambda x: x[6]):
                grouped.append(f"• [{src}] {typ} | {name} | {time_str} | {price_str}")
            full_message = "\n".join(grouped).strip()
            send_safe_telegram(full_message)


    # 🔁 이후는 1분마다 신규 추가나 가격 하락만 감지
    try:
        while True:
            new_alerts_by_date_region = defaultdict(lambda: defaultdict(list))
            for cond in watch_conditions:
                region = cond['region']
                for date in cond['dates']:
                    all_rows = fetch_all_data(date, region, cond["hour_range"], cond["max_price"])
                    for row in all_rows:
                        src, reg, typ, name, time_str, price_str, fee = row
                        if "전화문의" in price_str:
                            continue
                        key = (date, reg, name, time_str, typ)

                        if key not in seen_tee_times:
                            seen_tee_times[key] = fee
                            new_alerts_by_date_region[date][region].append(row)

                        elif seen_tee_times[key] > fee:
                            old_fee = seen_tee_times[key]
                            seen_tee_times[key] = fee
                            msg = (
                                f"💰 <b>가격 하락</b> <code>[{src}]</code>\n"
                                f"📅 {date}\n📍 {reg}\n🏌️‍♂️ {name} ({typ})\n⏰ {time_str}\n"
                                f"💸 {old_fee:,}원 → {fee:,}원"
                            )
                            print(f"📉 {date} {reg} {name} {typ} 가격 하락 → {fee:,}원")
                            send_telegram_message(msg)

            for date, region_dict in new_alerts_by_date_region.items():
                grouped = f"<b>📅 {date} 신규 티타임 모음</b>\n"
                for region, items in region_dict.items():
                    grouped += f"\n📍 {region}\n"
                    for src, reg, typ, name, time_str, price_str, _ in sorted(items, key=lambda x: x[6]):
                        grouped += f"• [{src}] {typ} | {name} | {time_str} | {price_str}\n"
                send_safe_telegram(grouped.strip())

            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 감시 중단됨 (Ctrl+C)")


def main():
    print("🎯 골프 티타임 감시 도구")
    while True:
        print("\n📌 메뉴 선택:")
        print("1. 설정된 알람 보기")
        print("2. 알람 추가")
        print("3. 알람 삭제")
        print("4. 감시 시작")
        print("0. 종료")
        cmd = input("입력: ").strip()
        if cmd == "1":
            view_alerts()
        elif cmd == "2":
            add_alert()
        elif cmd == "3":
            delete_alert()
        elif cmd == "4":
            start_watch()
        elif cmd == "0":
            print("👋 종료합니다.")
            break
        else:
            print("❌ 잘못된 입력입니다.")

if __name__ == "__main__":
    main()
