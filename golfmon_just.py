import requests
from datetime import datetime
from typing import Optional

# 지역 코드 매핑
region_map = {
    "경기북부": 1,
    "경기동부": 2,
    "경기남부": 3,
    "충청": 4,
    "강원": 5,
    "전라": 6,
    "경상": 7,
    "제주": 8
}

def fetch_region_items(date: str, location_code: int, transfer_type: str):
    url = "https://golfmon.net/action_front.php"
    payload = {
        "cmd": "ApiTransferJoin.getListOfTransferJoin_Location",
        "transferJoinTypeID": transfer_type,
        "location_fk": str(location_code),
        "manager_fk": "0",
        "dates": date,
        "bookingPlazaTimeFilter": "",
        "bookingPlazaOrderFilter": ""
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 8.0.0; SM-G965F)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://m.golfmon.net",
        "Referer": "https://m.golfmon.net/"
    }

    try:
        res = requests.post(url, data=payload, headers=headers)
        if res.status_code != 200:
            return []

        data = res.json()
        items = data.get("entity", [])
        return [(transfer_type, item) for item in items]

    except Exception as e:
        print("❌ 요청 실패:", e)
        return []

def format_korean_time(time_raw: str) -> str:
    try:
        dt = datetime.strptime(time_raw, "%Y-%m-%d %H:%M:%S")
        return f"{dt.month}월 {dt.day}일 {dt.strftime('%H:%M')}"
    except:
        return "??월 ??일 ??:??"

def display_results(results, region_name):
    print(f"\n🎯 {region_name} 지역 총 {len(results)}개 티타임\n")
    print("출처 | 지역 | 양도/조인 | 골프장 | 시간 | 금액")
    print("-" * 60)
    for t_type, item in results:
        name = item.get("name", "Unknown").strip()
        time_raw = item.get("dates", "")
        fee = item.get("greenFee", "0")
        tag = "양도" if t_type == "1" else "조인"
        tee_time = format_korean_time(time_raw)
        price = f"{int(fee):,}원"
        print(f"골프몬 | {region_name} | {tag} | {name} | {tee_time} | {price}")

def run_crawler(input_date: Optional[str] = None, input_region: Optional[str] = "전체"):
    if not input_date:
        input_date = datetime.today().strftime("%Y-%m-%d")

    target_regions = region_map.keys() if input_region == "전체" else [input_region]

    for region_name in target_regions:
        if region_name not in region_map:
            print(f"❌ 잘못된 지역명입니다: {region_name}")
            continue

        code = region_map[region_name]
        results = []
        for transfer_type in ["1", "2"]:
            results += fetch_region_items(input_date, code, transfer_type)

        display_results(results, region_name)

# ✅ 단독 실행 시 오늘 날짜 & 전체 지역
if __name__ == "__main__":
    run_crawler()
