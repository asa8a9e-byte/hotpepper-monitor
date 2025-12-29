#!/usr/bin/env python3
"""
ホットペッパービューティー NEW OPEN店舗 CSV出力テスト
- 全国の「NEW OPEN/NEW FACE」特集ページを全ページスキャン
- 結果をCSVファイルに出力
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
import re
from datetime import datetime
from typing import Dict, List

# ============================================
# 設定
# ============================================

REQUEST_DELAY = 1.5  # リクエスト間隔（秒）
MAX_PAGES = 50  # 1カテゴリあたり最大ページ数
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 監視対象エリア
AREAS = {
    "svcSA": "関東",
    "svcSB": "関西", 
    "svcSC": "東海",
    "svcSD": "北海道",
    "svcSE": "東北",
    "svcSF": "北信越",
    "svcSG": "九州・沖縄",
    "svcSH": "中国",
    "svcSI": "四国",
}

# 監視対象ジャンル（美容室のみ）
GENRES = {
    "hair": {"prefix": "", "name": "美容室"},
}

NEW_OPEN_PATH = "spkSP13_spdL035/"


# ============================================
# スクレイピング
# ============================================

def get_new_open_url(genre_prefix: str, area_code: str, page: int = 1) -> str:
    base = "https://beauty.hotpepper.jp"
    if page == 1:
        return f"{base}/{genre_prefix}{area_code}/{NEW_OPEN_PATH}"
    else:
        return f"{base}/{genre_prefix}{area_code}/{NEW_OPEN_PATH}PN{page}.html"


def fetch_page(url: str) -> str | None:
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"[ERROR] {url}: {e}")
        return None


def extract_salons(html: str) -> List[Dict]:
    """HTMLから店舗情報を抽出"""
    soup = BeautifulSoup(html, "html.parser")
    salons = []
    seen_ids = set()
    
    # 店舗リンクを探す
    for link in soup.find_all("a", href=True):
        href = link["href"]
        match = re.search(r'/(slnH\d+)/', href)
        if not match:
            continue
            
        salon_id = match.group(1)
        if salon_id in seen_ids:
            continue
        seen_ids.add(salon_id)
        
        # 店舗名を取得
        salon_name = ""
        parent = link.find_parent(["li", "div"])
        if parent:
            h3 = parent.find("h3")
            if h3:
                # リンクテキストから店舗名を取得
                a_tag = h3.find("a")
                if a_tag:
                    salon_name = a_tag.get_text(strip=True)
                else:
                    salon_name = h3.get_text(strip=True)
        
        # 店舗名が取れなかった場合
        if not salon_name:
            salon_name = link.get_text(strip=True)[:80]
        
        # 店舗名のクリーニング
        salon_name = re.sub(r'\s+', ' ', salon_name).strip()
        if len(salon_name) > 80:
            salon_name = salon_name[:80]
        
        salons.append({
            "id": salon_id,
            "name": salon_name,
            "url": f"https://beauty.hotpepper.jp/{salon_id}/"
        })
    
    return salons


def get_total_pages(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.find(string=re.compile(r'\d+/\d+ページ'))
    if page_text:
        match = re.search(r'(\d+)/(\d+)ページ', page_text)
        if match:
            return int(match.group(2))
    return 1


def has_next_page(html: str, current_page: int) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    next_page = current_page + 1
    next_link = soup.find("a", href=re.compile(rf"PN{next_page}\.html"))
    return next_link is not None


def scan_category(genre_key: str, genre_info: dict, area_code: str, area_name: str) -> List[Dict]:
    """1カテゴリの全ページをスキャン"""
    all_salons = []
    seen_ids = set()
    page = 1
    total_pages = 1
    
    print(f"\n[{genre_info['name']}] {area_name}")
    
    while page <= min(MAX_PAGES, total_pages + 1):
        url = get_new_open_url(genre_info["prefix"], area_code, page)
        
        html = fetch_page(url)
        if not html:
            break
        
        if page == 1:
            total_pages = get_total_pages(html)
            print(f"  URL: {url}")
            print(f"  総ページ数: {total_pages}")
        
        salons = extract_salons(html)
        new_count = 0
        
        for salon in salons:
            if salon["id"] not in seen_ids:
                salon["genre"] = genre_info["name"]
                salon["area"] = area_name
                salon["genre_key"] = genre_key
                salon["area_code"] = area_code
                all_salons.append(salon)
                seen_ids.add(salon["id"])
                new_count += 1
        
        print(f"  Page {page}/{total_pages}: {new_count}件取得")
        
        if page >= total_pages:
            break
        if not has_next_page(html, page):
            break
            
        page += 1
        time.sleep(REQUEST_DELAY)
    
    print(f"  → 合計: {len(all_salons)}件")
    return all_salons


def main():
    print("=" * 60)
    print("ホットペッパービューティー NEW OPEN店舗 CSV出力テスト")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    all_salons = []
    
    for genre_key, genre_info in GENRES.items():
        for area_code, area_name in AREAS.items():
            salons = scan_category(genre_key, genre_info, area_code, area_name)
            all_salons.extend(salons)
            time.sleep(REQUEST_DELAY)
    
    # CSV出力
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"hotpepper_newopen_{timestamp}.csv"
    
    with open(filename, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["店舗ID", "店舗名", "ジャンル", "エリア", "URL"])
        
        for salon in all_salons:
            writer.writerow([
                salon["id"],
                salon["name"],
                salon["genre"],
                salon["area"],
                salon["url"]
            ])
    
    print("\n" + "=" * 60)
    print(f"完了！")
    print(f"総店舗数: {len(all_salons)}件")
    print(f"出力ファイル: {filename}")
    print("=" * 60)
    
    # サマリー表示
    print("\n【ジャンル別集計】")
    for genre_key, genre_info in GENRES.items():
        count = len([s for s in all_salons if s["genre_key"] == genre_key])
        print(f"  {genre_info['name']}: {count}件")
    
    print("\n【エリア別集計】")
    for area_code, area_name in AREAS.items():
        count = len([s for s in all_salons if s["area_code"] == area_code])
        print(f"  {area_name}: {count}件")


if __name__ == "__main__":
    main()
