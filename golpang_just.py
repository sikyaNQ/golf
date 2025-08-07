import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time

REGION_MAP = {
    "강북/경춘": 1,
    "경기동부": 2,
    "충청": 4,
    "한강이남": 5,
    "영호남/제주": 6,
    "원주/영동": 8
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.golfpang.com",
    "X-Requested-With": "XMLHttpRequest"
}

def fetch_html(url, data, referer):
    try:
        headers = {**HEADERS, "Referer": referer}
        res = requests.post(url, headers=headers, data=data, timeout=10)
        res.raise_for_status()
        return BeautifulSoup(res.text, "html.parser")
    except:
        return None

def parse_table(soup, region_name, source, rd_date):
    items = []
    if not soup:
        return items

    rows = soup.select("table.type2 tbody tr")
    for row in rows:
        cols = row.select("td")
        if len(cols) < 8:
            continue
        time_str = cols[2].get_text(strip=True)
        course = cols[4].get_text(strip=True)
        price = cols[7].get_text(strip=True)

        match = re.search(r"(\d{1,2}):(\d{2})", time_str)
        if not match:
            continue
        hour, minute = int(match.group(1)), int(match.group(2))
        if "오후" in time_str and hour < 12:
            hour += 12
        if "오전" in time_str and hour == 12:
            hour = 0

        date_obj = datetime.strptime(rd_date, "%Y-%m-%d")
        formatted_date = f"{date_obj.month}월 {date_obj.day}일"
        formatted_time = f"{formatted_date} {hour:02}:{minute:02}"
        sort_key = f"{hour:02}:{minute:02}"

        items.append([sort_key, "골팡", region_name, source, course, formatted_time, price])
    return items

def fetch_all_pages(region_name, sector, source, url, referer, rd_date):
    all_items = []
    page = 1
    while True:
        data = {
            "pageNum": str(page),
            "bkOrder": "",
            "rd_date": rd_date,
            "ampm": "",
            "sector": sector,
            "idx": "",
            "cust_nick": "",
            "clubname": "",
            "sector2": "",
            "sector3": ""
        }
        soup = fetch_html(url, data, referer)
        items = parse_table(soup, region_name, source, rd_date)
        if not items:
            break
        all_items.extend(items)
        page += 1
        time.sleep(0.2)
    return all_items

def crawl_golfpang(region_name: str, rd_date: str):
    sector = REGION_MAP.get(region_name)
    if not sector:
        raise ValueError(f"잘못된 지역명입니다: {region_name}")

    items = []
    items += fetch_all_pages(region_name, sector, "양도",
                             "https://www.golfpang.com/web/round/booking_tblList.do",
                             "https://www.golfpang.com/web/round/booking_list.do",
                             rd_date)
    items += fetch_all_pages(region_name, sector, "조인",
                             "https://www.golfpang.com/web/round/join_tblList.do",
                             "https://www.golfpang.com/web/round/join_list.do",
                             rd_date)

    items.sort(key=lambda x: (x[2], x[0]))
    return items

if __name__ == "__main__":
    today = datetime.today().strftime("%Y-%m-%d")
    result = crawl_golfpang("강북/경춘", today)
    print("출처 | 지역 | 양도/조인 | 골프장 | 시간 | 금액")
    print("-" * 60)
    for item in result:
        print(" | ".join(item[1:]))
