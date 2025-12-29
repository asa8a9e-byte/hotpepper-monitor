#!/usr/bin/env python3
"""
ホットペッパービューティー NEW OPEN店舗 電話番号取得テスト
- 20店舗だけ取得してChatworkに通知
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

CHATWORK_API_TOKEN = "07a5b6d533a6ef46e8f1e29ed1f97691"
CHATWORK_ROOM_ID = "418568359"

REQUEST_DELAY = 1.0  # リクエスト間隔（秒）
MAX_SALONS = 20  # テスト用に20店舗のみ
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 関東の美容室のみ
TEST_URL = "https://beauty.hotpepper.jp/svcSA/spkSP13_spdL035/"


# ============================================
# スクレイピング
# ============================================

def fetch_page(url: str) -> str | None:
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"[ERROR] {url}: {e}")
        return None


def extract_salons_from_list(html: str, max_count: int) -> List[Dict]:
    """一覧ページから店舗情報を抽出"""
    soup = BeautifulSoup(html, "html.parser")
    salons = []
    seen_ids = set()
    
    for link in soup.find_all("a", href=True):
        if len(salons) >= max_count:
            break
            
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
                a_tag = h3.find("a")
                if a_tag:
                    salon_name = a_tag.get_text(strip=True)
                else:
                    salon_name = h3.get_text(strip=True)
        
        if not salon_name:
            salon_name = link.get_text(strip=True)[:60]
        
        salon_name = re.sub(r'\s+', ' ', salon_name).strip()[:60]
        
        salons.append({
            "id": salon_id,
            "name": salon_name,
            "url": f"https://beauty.hotpepper.jp/{salon_id}/",
            "tel_url": f"https://beauty.hotpepper.jp/{salon_id}/tel/",
            "phone": ""
        })
    
    return salons


def get_phone_number(tel_url: str) -> str:
    """電話番号ページから電話番号を取得"""
    html = fetch_page(tel_url)
    if not html:
        return ""
    
    soup = BeautifulSoup(html, "html.parser")
    
    # <td class="fs16 b">045-594-9284</td> を探す
    td = soup.find("td", class_=re.compile(r"fs16|b"))
    if td:
        phone = td.get_text(strip=True)
        # 電話番号っぽいかチェック
        if re.match(r'[\d\-]+', phone):
            return phone
    
    # 別パターン: telリンク
    tel_link = soup.find("a", href=re.compile(r"tel:"))
    if tel_link:
        phone = tel_link.get("href", "").replace("tel:", "")
        return phone
    
    # テキストから電話番号を抽出
    text = soup.get_text()
    phone_match = re.search(r'(\d{2,4}[-‐ー]\d{2,4}[-‐ー]\d{3,4})', text)
    if phone_match:
        return phone_match.group(1)
    
    return ""


def send_chatwork(message: str) -> bool:
    """Chatworkにメッセージ送信"""
    url = f"https://api.chatwork.com/v2/rooms/{CHATWORK_ROOM_ID}/messages"
    headers = {"X-ChatWorkToken": CHATWORK_API_TOKEN}
    data = {"body": message}
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=30)
        response.raise_for_status()
        print("[OK] Chatwork送信成功")
        return True
    except Exception as e:
        print(f"[ERROR] Chatwork送信失敗: {e}")
        return False


def format_message(salons: List[Dict]) -> str:
    """Chatwork用メッセージを整形"""
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    
    lines = [
        "[info][title]🆕 ホットペッパー NEW OPEN 美容室[/title]",
        f"取得時刻: {now}",
        f"店舗数: {len(salons)}件",
        "",
    ]
    
    for i, salon in enumerate(salons, 1):
        phone = salon["phone"] if salon["phone"] else "取得できず"
        lines.append(f"【{i}】{salon['name']}")
        lines.append(f"📞 {phone}")
        lines.append(f"🔗 {salon['url']}")
        lines.append("")
    
    lines.append("[/info]")
    
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("ホットペッパー NEW OPEN 電話番号取得テスト")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"取得店舗数: {MAX_SALONS}件")
    print("=" * 60)
    
    # 1. 一覧ページから店舗取得
    print("\n[1] 一覧ページ取得中...")
    html = fetch_page(TEST_URL)
    if not html:
        print("一覧ページの取得に失敗しました")
        return
    
    salons = extract_salons_from_list(html, MAX_SALONS)
    print(f"  → {len(salons)}店舗を検出")
    
    # 2. 各店舗の電話番号を取得
    print("\n[2] 電話番号取得中...")
    for i, salon in enumerate(salons):
        print(f"  {i+1}/{len(salons)}: {salon['name'][:30]}...", end=" ")
        phone = get_phone_number(salon["tel_url"])
        salon["phone"] = phone
        print(f"→ {phone if phone else 'なし'}")
        time.sleep(REQUEST_DELAY)
    
    # 3. CSV出力
    print("\n[3] CSV出力...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"newopen_test_{timestamp}.csv"
    
    with open(filename, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["店舗ID", "店舗名", "電話番号", "URL"])
        for salon in salons:
            writer.writerow([
                salon["id"],
                salon["name"],
                salon["phone"],
                salon["url"]
            ])
    print(f"  → {filename}")
    
    # 4. Chatwork送信
    print("\n[4] Chatwork送信...")
    message = format_message(salons)
    print("\n--- 送信内容 ---")
    print(message)
    print("--- ここまで ---\n")
    
    send_chatwork(message)
    
    # 5. サマリー
    print("\n" + "=" * 60)
    print("完了！")
    phone_count = len([s for s in salons if s["phone"]])
    print(f"電話番号取得: {phone_count}/{len(salons)}件")
    print("=" * 60)


if __name__ == "__main__":
    main()
