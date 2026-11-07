# 三億健身房管理系統

以 Flask + PostgreSQL 開發的健身房資料庫應用系統，架構沿用課程範例（MVC、Flask-Login、`api/sql.py` 集中管理 SQL）。

## 功能

**會員（前台）**
- 預約課程：查看未開始課程、剩餘名額、搜尋課程／教練／教室，一鍵預約
- 我的預約：預約紀錄與狀態，課程開始前可取消，取消後可重新預約
- 合約與退款：購買方案、查看合約狀態與可退餘額、線上申請退款、查看審核結果
- 個人資料：修改基本資料、新增／刪除聯絡電話、查看負責教練

**管理者（後台）**
- 資料分析：系統總覽、每月收款與退款、方案淨收款、課程預約率與出席率、教練負責會員與授課數
- 會員管理：查詢（姓名、email、電話）、新增（可同時建立登入帳號）、編輯、刪除、電話管理
- 教練管理：新增、編輯、刪除、指定直屬主管、分派／解除負責會員
- 課程管理：新增、編輯、刪除、點名（出席／缺席）
- 方案管理：新增、編輯、刪除、銷售統計
- 合約管理：所有合約與狀態、7 天內到期提醒、替會員新增合約
- 退款審核：依狀態篩選、核准／駁回

**資料庫規則**
- 課程額滿由觸發器 `trg_booking_capacity` 擋下
- 預約時課程日期必須在會員合約有效期間內
- 退款金額不能超過可退餘額（審核中＋已核准都會佔用額度）
- 有合約的會員、有課程的教練、已售出的方案不能刪除（外鍵 RESTRICT）

## 測試帳號

| 身分 | 帳號 | 密碼 |
|---|---|---|
| 管理者 | admin | admin1234 |
| 會員（徐毓廷） | m001 | 1234 |
| 會員（M002～M008） | m002～m008 | 1234 |

## 專案結構

```
app.py                  程式進入點
api/sql.py              所有 SQL（對應 db/03_feature_queries.sql）
api/api.py              登入、註冊、登出、權限檢查
api/forms.py            共用表單與中文代碼對照
member/                 會員前台（views + templates）
backstage/              管理者後台（views + templates）
templates/              共用版面、首頁、登入、註冊、共用表單
static/                 CSS、網站圖示
db/                     資料庫 SQL 檔（01～05）
```

## 安裝與執行

```bash
pip install -r requirements.txt
```

把 `.env.example` 複製成 `.env`，填入資料庫連線資訊（`DB_SCHEMA=gym`）。

### 資料庫

全新資料庫依序執行 `db/` 裡的：
`01_schema.sql` → `02_demo_data.sql` → `04_schema_fix.sql` → `05_accounts.sql`
（`03_feature_queries.sql` 是功能 SQL 測試，最後會 ROLLBACK，不影響資料。）

### 啟動

```bash
python app.py
```

打開 http://127.0.0.1:5000

## 部署（Render）

1. 把專案上傳到 GitHub（`.env` 已在 `.gitignore`，不會被上傳）
2. Render → New → Web Service → 選這個 repo
3. Build Command：`pip install -r requirements.txt`
4. Start Command：`gunicorn app:app`
5. Environment 加入 `.env` 裡的每一個變數
