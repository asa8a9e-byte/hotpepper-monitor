#!/usr/bin/env python3
"""
ホットペッパービューティー NEW OPEN 美容室監視システム
- 全国の「NEW OPEN」特集ページを全ページ監視
- 新規店舗を検知したら電話番号を取得してChatworkに通知
- Google スプレッドシートに全店舗を蓄積
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from datetime import datetime
from typing import Dict, List, Set, Optional

import gspread
from google.oauth2.service_account import Credentials

# ============================================
# 設定
# ============================================

CHATWORK_API_TOKEN = os.environ.get("CHATWORK_API_TOKEN", "07a5b6d533a6ef46e8f1e29ed1f97691")
CHATWORK_ROOM_ID = os.environ.get("CHATWORK_ROOM_ID", "418568359")

# Google Sheets設定
CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "/Users/yuta/Desktop/snappy-density-451702-c0-04b85779ba38.json")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1qe1WK1IAJPD-8fxE-4E9maWzVGjw5xAhO94vWUyJY2s")
SHEET_NAME = "NEW"

# データ保存先
DATA_FILE = "known_salons.json"

# リクエスト設定
REQUEST_DELAY = 1.5  # リクエスト間隔（秒）
MAX_PAGES = 50  # 1カテゴリあたり最大ページ数（安全装置）
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 監視対象エリア（全国9地域）
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

# NEW OPEN特集のパス
NEW_OPEN_PATH = "spkSP13_spdL035/"


# ============================================
# HTTP通信
# ============================================

def fetch_page(url: str) -> Optional[str]:
    """ページを取得"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            return None  # 404は最終ページ超過の可能性
        print(f"[ERROR] HTTP {response.status_code}: {url}")
        return None
    except Exception as e:
        print(f"[ERROR] {url}: {e}")
        return None


# ============================================
# スクレイピング
# ============================================

def get_new_open_url(genre_prefix: str, area_code: str, page: int = 1) -> str:
    """NEW OPEN特集ページのURLを生成"""
    base = "https://beauty.hotpepper.jp"
    if page == 1:
        return f"{base}/{genre_prefix}{area_code}/{NEW_OPEN_PATH}"
    else:
        return f"{base}/{genre_prefix}{area_code}/{NEW_OPEN_PATH}PN{page}.html"


def extract_salons(html: str) -> List[Dict]:
    """HTMLから店舗情報を抽出"""
    soup = BeautifulSoup(html, "html.parser")
    salons = []
    seen_ids = set()
    
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
                a_tag = h3.find("a")
                if a_tag:
                    salon_name = a_tag.get_text(strip=True)
                else:
                    salon_name = h3.get_text(strip=True)
        
        if not salon_name:
            salon_name = link.get_text(strip=True)[:60]
        
        # 店舗名のクリーニング
        salon_name = re.sub(r'\s+', ' ', salon_name).strip()[:60]
        
        salons.append({
            "id": salon_id,
            "name": salon_name,
            "url": f"https://beauty.hotpepper.jp/{salon_id}/",
            "tel_url": f"https://beauty.hotpepper.jp/{salon_id}/tel/"
        })
    
    return salons


def get_total_pages(html: str) -> int:
    """総ページ数を取得"""
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.find(string=re.compile(r'\d+/\d+ページ'))
    if page_text:
        match = re.search(r'(\d+)/(\d+)ページ', page_text)
        if match:
            return int(match.group(2))
    return 1


def has_next_page(html: str, current_page: int) -> bool:
    """次のページがあるかチェック"""
    soup = BeautifulSoup(html, "html.parser")
    next_page = current_page + 1
    next_link = soup.find("a", href=re.compile(rf"PN{next_page}\.html"))
    return next_link is not None


def get_phone_number(tel_url: str) -> str:
    """電話番号ページから電話番号を取得"""
    html = fetch_page(tel_url)
    if not html:
        return ""
    
    soup = BeautifulSoup(html, "html.parser")
    
    # パターン1: <td class="fs16 b">045-594-9284</td>
    td = soup.find("td", class_=re.compile(r"fs16|b"))
    if td:
        phone = td.get_text(strip=True)
        if re.match(r'[\d\-]+', phone):
            return phone
    
    # パターン2: telリンク
    tel_link = soup.find("a", href=re.compile(r"tel:"))
    if tel_link:
        phone = tel_link.get("href", "").replace("tel:", "")
        return phone
    
    # パターン3: テキストから電話番号を抽出
    text = soup.get_text()
    phone_match = re.search(r'(\d{2,4}[-‐ー]\d{2,4}[-‐ー]\d{3,4})', text)
    if phone_match:
        return phone_match.group(1)
    
    return ""


def scan_category(genre_prefix: str, area_code: str, genre_name: str, area_name: str) -> List[Dict]:
    """1カテゴリの全ページをスキャン"""
    all_salons = []
    seen_ids = set()
    page = 1
    total_pages = 1
    
    while page <= min(MAX_PAGES, total_pages + 1):
        url = get_new_open_url(genre_prefix, area_code, page)
        
        html = fetch_page(url)
        if not html:
            break
        
        if page == 1:
            total_pages = get_total_pages(html)
            print(f"[SCAN] {genre_name} - {area_name}: {total_pages}ページ")
        
        salons = extract_salons(html)
        new_count = 0
        
        for salon in salons:
            if salon["id"] not in seen_ids:
                salon["genre"] = genre_name
                salon["area"] = area_name
                all_salons.append(salon)
                seen_ids.add(salon["id"])
                new_count += 1
        
        if page > 1:
            print(f"  Page {page}/{total_pages}: +{new_count}件")
        
        if page >= total_pages:
            break
        if not has_next_page(html, page):
            break
            
        page += 1
        time.sleep(REQUEST_DELAY)
    
    print(f"  → 合計: {len(all_salons)}件")
    return all_salons


def scan_all_categories() -> Dict[str, List[Dict]]:
    """全エリア・全ジャンルをスキャン"""
    all_salons = {}
    
    for genre_key, genre_info in GENRES.items():
        for area_code, area_name in AREAS.items():
            key = f"{genre_key}_{area_code}"
            
            salons = scan_category(
                genre_info["prefix"], 
                area_code, 
                genre_info["name"], 
                area_name
            )
            all_salons[key] = salons
            
            time.sleep(REQUEST_DELAY)
    
    return all_salons


# ============================================
# データ管理
# ============================================

def load_known_salons() -> Dict[str, Set[str]]:
    """既知の店舗IDを読み込み"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {k: set(v) for k, v in data.items()}
    return {}


def save_known_salons(salons: Dict[str, Set[str]]):
    """既知の店舗IDを保存"""
    data = {k: list(v) for k, v in salons.items()}
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_new_salons(current: Dict[str, List[Dict]], known: Dict[str, Set[str]]) -> List[Dict]:
    """新規店舗を検出"""
    new_salons = []

    for key, salons in current.items():
        known_ids = known.get(key, set())

        for salon in salons:
            if salon["id"] not in known_ids:
                new_salons.append(salon)

    return new_salons


def update_known_salons(current: Dict[str, List[Dict]], known: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    """既知リストを更新"""
    for key, salons in current.items():
        if key not in known:
            known[key] = set()
        for salon in salons:
            known[key].add(salon["id"])
    return known


# ============================================
# Google Sheets連携
# ============================================

def get_sheets_client():
    """Google Sheets APIクライアントを取得"""
    # 環境変数から認証情報を取得（GitHub Actions用）
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")

    if creds_json:
        # 環境変数からJSON文字列で認証
        import json
        creds_dict = json.loads(creds_json)
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    elif os.path.exists(CREDENTIALS_FILE):
        # ローカルファイルから認証
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    else:
        print("[WARN] Google認証情報が見つかりません。スプシ連携をスキップします。")
        return None

    return gspread.authorize(credentials)


def get_existing_salon_ids(worksheet) -> Set[str]:
    """スプレッドシートから既存の店舗IDを取得"""
    try:
        all_values = worksheet.get_all_values()
        if len(all_values) <= 1:  # ヘッダーのみ
            return set()
        # A列（店舗ID）を取得
        return {row[0] for row in all_values[1:] if row[0]}
    except Exception as e:
        print(f"[ERROR] 既存店舗ID取得失敗: {e}")
        return set()


def append_salons_to_sheet(new_salons: List[Dict]) -> bool:
    """新規店舗をスプレッドシートに追加"""
    if not new_salons:
        return True

    client = get_sheets_client()
    if not client:
        return False

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)

        # シートを取得または作成
        try:
            worksheet = spreadsheet.worksheet(SHEET_NAME)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=10)
            # ヘッダーを追加
            headers = ["店舗ID", "店舗名", "電話番号", "URL", "エリア", "ジャンル", "検出日時", "ステータス"]
            worksheet.append_row(headers)
            print(f"[INFO] シート '{SHEET_NAME}' を新規作成しました")

        # ヘッダーがなければ追加
        first_row = worksheet.row_values(1)
        if not first_row or first_row[0] != "店舗ID":
            headers = ["店舗ID", "店舗名", "電話番号", "URL", "エリア", "ジャンル", "検出日時", "ステータス"]
            worksheet.insert_row(headers, 1)

        # 新規店舗を追加
        now = datetime.now().strftime("%Y/%m/%d %H:%M")
        rows_to_add = []

        for salon in new_salons:
            row = [
                salon["id"],
                salon.get("name", ""),
                salon.get("phone", ""),
                salon.get("url", ""),
                salon.get("area", ""),
                salon.get("genre", ""),
                now,
                "🆕 NEW"  # 新規追加マーク
            ]
            rows_to_add.append(row)

        # バッチで追加（効率化）
        if rows_to_add:
            worksheet.append_rows(rows_to_add)
            print(f"[OK] スプレッドシートに {len(rows_to_add)} 件追加しました")

        return True

    except Exception as e:
        print(f"[ERROR] スプレッドシート更新失敗: {e}")
        return False


# ============================================
# Chatwork通知
# ============================================

def send_chatwork(message: str) -> bool:
    """Chatworkにメッセージを送信"""
    url = f"https://api.chatwork.com/v2/rooms/{CHATWORK_ROOM_ID}/messages"
    headers = {"X-ChatWorkToken": CHATWORK_API_TOKEN}
    data = {"body": message}
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=30)
        response.raise_for_status()
        print("[OK] Chatwork通知送信完了")
        return True
    except Exception as e:
        print(f"[ERROR] Chatwork送信失敗: {e}")
        return False


def format_notification(new_salons: List[Dict]) -> str:
    """通知メッセージを整形（電話番号付き）"""
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    
    lines = [
        "[info][title]🆕 ホットペッパー NEW OPEN 美容室[/title]",
        f"検出時刻: {now}",
        f"新規店舗数: {len(new_salons)}件",
        "",
    ]
    
    # エリア別にグループ化
    by_area = {}
    for salon in new_salons:
        area = salon.get("area", "不明")
        if area not in by_area:
            by_area[area] = []
        by_area[area].append(salon)
    
    for area, salons in by_area.items():
        lines.append(f"━━━ {area} ━━━")
        for salon in salons[:15]:  # 各エリア最大15件
            name = salon["name"][:40] if salon["name"] else "（店舗名取得中）"
            phone = salon.get("phone", "")
            phone_str = f"📞 {phone}" if phone else "📞 取得できず"
            lines.append(f"【{name}】")
            lines.append(phone_str)
            lines.append(f"🔗 {salon['url']}")
            lines.append("")
        if len(salons) > 15:
            lines.append(f"...他{len(salons) - 15}件")
            lines.append("")
    
    lines.append("[/info]")
    
    return "\n".join(lines)


# ============================================
# メイン処理
# ============================================

def main():
    print("=" * 60)
    print("ホットペッパービューティー NEW OPEN 美容室監視")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 既知の店舗を読み込み
    known_salons = load_known_salons()
    is_first_run = len(known_salons) == 0
    
    if is_first_run:
        print("[INFO] 初回実行 - 現在の店舗リストを取得します")
    
    # 全ページをスキャン
    current_salons = scan_all_categories()
    
    # 新規店舗を検出
    new_salons = find_new_salons(current_salons, known_salons)
    
    print("-" * 60)
    print(f"新規店舗: {len(new_salons)}件")
    
    # 新規店舗の電話番号を取得してスプシに追加
    if new_salons:
        print("\n[電話番号取得中...]")
        for i, salon in enumerate(new_salons):
            print(f"  {i+1}/{len(new_salons)}: {salon['name'][:30]}...", end=" ")
            phone = get_phone_number(salon["tel_url"])
            salon["phone"] = phone
            print(f"→ {phone if phone else 'なし'}")
            time.sleep(REQUEST_DELAY)

        # スプレッドシートに追加（初回も含む）
        print("\n[スプレッドシート更新中...]")
        append_salons_to_sheet(new_salons)

        # Chatwork通知（初回は送信しない）
        if not is_first_run:
            message = format_notification(new_salons)
            print("\n[通知内容]")
            print(message)
            send_chatwork(message)
        else:
            # 初回実行完了通知
            total = sum(len(s) for s in current_salons.values())
            msg = f"[info][title]✅ 監視システム起動完了[/title]現在の掲載店舗数: {total}件\nスプレッドシートに全店舗を追加しました。\n次回以降、新規店舗を検出したら通知します。[/info]"
            send_chatwork(msg)
    else:
        print("[INFO] 新規店舗なし")
    
    # 既知リストを更新・保存
    known_salons = update_known_salons(current_salons, known_salons)
    save_known_salons(known_salons)
    
    print("\n[DONE] 完了")


if __name__ == "__main__":
    main()
