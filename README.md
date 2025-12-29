# ホットペッパービューティー NEW OPEN 美容室監視システム

全国のホットペッパービューティー「NEW OPEN」特集を15分間隔で監視し、新規掲載美容室を検知したらChatworkに通知します。

## 監視対象

### エリア（9地域）
- 北海道、東北、関東、北信越、東海、関西、中国、四国、九州・沖縄

### ジャンル
- 美容室のみ

## 通知内容

新規店舗が検知されると、以下の情報がChatworkに通知されます：
- 店舗名
- 📞 電話番号（即架電用）
- 🔗 店舗ページURL

---

## セットアップ手順

### 1. GitHubリポジトリ作成

```bash
git init
git add .
git commit -m "初期コミット"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/hotpepper-monitor.git
git push -u origin main
```

### 2. GitHub Secretsを設定

リポジトリの Settings → Secrets and variables → Actions で以下を追加：

| Secret名 | 値 |
|----------|-----|
| `CHATWORK_API_TOKEN` | ChatworkのAPIトークン |
| `CHATWORK_ROOM_ID` | 通知先のルームID |

### 3. GitHub Actionsを有効化

リポジトリの Actions タブで「I understand my workflows, go ahead and enable them」をクリック

### 4. 初回実行

Actions → 「ホットペッパー新規店舗監視」→ 「Run workflow」で手動実行

---

## ローカルでテスト

```bash
# 依存インストール
pip install -r requirements.txt

# 実行
python main.py
```

---

## 通知サンプル

```
🆕 ホットペッパー NEW OPEN 美容室
検出時刻: 2025/01/15 10:30
新規店舗数: 3件

━━━ 関東 ━━━
【hair salon TOKYO 渋谷店】
📞 03-1234-5678
🔗 https://beauty.hotpepper.jp/slnH000123456/

【Beauty OSAKA なんば店】
📞 06-9876-5432
🔗 https://beauty.hotpepper.jp/slnH000123457/
```

---

## カスタマイズ

### 監視間隔を変更
`.github/workflows/monitor.yml` の cron を編集：

```yaml
schedule:
  - cron: '*/30 * * * *'  # 30分間隔
  - cron: '0 * * * *'     # 1時間間隔
```

### 特定エリアのみ監視
`main.py` の `AREAS` を編集：

```python
AREAS = {
    "svcSA": "関東",
    "svcSB": "関西",
    # 他は削除
}
```

---

## 注意事項

- GitHub Actions無料枠: 月2,000分
- 15分間隔だと月約2,880回 × 約3分/回 = 約144時間（無料枠超過の可能性）
- **推奨: 30分〜1時間間隔に変更するか、有料プランを検討**

---

## ファイル構成

```
hotpepper-monitor/
├── main.py                    # メインスクリプト
├── requirements.txt           # 依存パッケージ
├── known_salons.json          # 既知店舗データ（自動生成）
├── README.md
└── .github/
    └── workflows/
        └── monitor.yml        # GitHub Actions設定
```
