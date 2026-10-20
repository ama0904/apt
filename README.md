# apetto 網站鏡像 + 商品後台

這個 repo 存放 apetto（https://www.apetto.com.tw/）的商品資料與圖片，並用自己的版型（`_tools/theme.py`）產生整個網站，
加上一個可以新增、下架、刪除商品的後台。推送到 `main` 之後，GitHub Actions 會依 `_data/products.json` 重新產生所有頁面並部署到 GitHub Pages。

| 項目 | 網址 |
|---|---|
| 前台 | https://ama0904.github.io/apt/ |
| 後台 | https://ama0904.github.io/apt/admin.html |

## 後台怎麼用

1. 打開後台網址，輸入後台密碼。密碼用來解開 `admin_secret.json` 裡加密的 GitHub token（PBKDF2 60 萬次 + AES-256-GCM），解開後 token 存在你瀏覽器的 localStorage。右上角「改用 token 登入」可以直接貼 token。
   - 更換密碼或 token：`python _tools/set_admin_password.py <token> <密碼>`，然後 commit 推送。
   - 密碼越長越安全；這個檔案是公開的，三個字元的密碼只能擋住隨手亂試的人。token 建議用只有這個 repo Contents 讀寫（加 Actions 讀取）權限的 fine-grained token。
2. 「新增商品」：填名稱、價格、分類、首頁區塊、介紹文字，上傳主圖（可再加多張圖）。瀏覽器會自動裁出列表方塊圖與縮圖，然後連同 `products.json` 一次 commit 進 repo。
3. 「下架」會把商品從前台所有頁面拿掉但保留資料，「刪除」則連資料與上傳圖片一起移除。
4. 每次儲存後 Actions 會重新產生網站，大約 1 到 2 分鐘後前台更新。後台上方會顯示部署狀態。
5. 後台右上角可切換介面語言（中文 / Deutsch）。德文模式下，分類與區塊名稱會沿用前台的翻譯表；新字串的德文寫在 `admin.html` 的 `DE` 表。

## 版型

- 版型與所有頁面（首頁、分類、商品、搜尋、暢銷、關於我們、購物流程（原服務條款）、最新消息（消息與公告合併）、404）都由 `_tools/theme.py` 產生，樣式在 `assets/theme.css`、`assets/theme.js`（建置時寫出）。原站的 OpenCart 版型、jQuery 與追蹤碼都不再使用。
- 首頁區塊：主視覺、三大系列、暢銷商品、品牌故事、機能細節、推薦商品、全系列。暢銷 / 推薦由後台「首頁顯示區塊」勾選，全系列自動列出所有上架商品。
- 中文商品頁有「立即購買」：連到後台填的「購買連結」（例如蝦皮），沒填就連到原官網商品頁；也可在 `products.json` 的 `settings.shop_url` 設整站預設。外語版只有商品介紹，沒有購買按鈕。
- 首頁橫幅的字不在圖片裡，是 HTML 文字，所以會跟著語言切換；兩張去字的底圖（`*.clean.jpg`）用相鄰的樹林區塊修補。

## 多語版本

每個頁面有中文、英文、日文、德文四個版本：`index.html` / `index.en.html` / `index.ja.html` / `index.de.html`，其他頁面同樣以 `.en` / `.ja` / `.de` 結尾。頁首有語言切換（手機版在標題列下方一整排），同語言內的連結互相串接，並帶 hreflang 標記。
版型本身的字串（按鈕、區塊標題）翻譯寫在 `_tools/theme.py` 的 `UI`；商品與頁面內容的翻譯在 `i18n.json`。
翻譯對照表在 `www.apetto.com.tw/_data/i18n.json`（中文原文 → 各語言），建置時逐字串替換；含數字的樣板字串用 `{n}` 佔位；不在表裡的字串維持中文。
後台新增商品時可填英 / 日 / 德文名稱。商品介紹若是新寫的中文，需要把對應句子加進 `i18n.json` 才會翻譯。

### 外語版內容與預覽

- 外語版只做商品介紹：沒有購買按鈕，商品頁改顯示「請至台灣官方商店購買」。
- 後台編輯商品時，「外語版內容」可為英、日、德各別填寫名稱、簡介、重點說明、商品介紹。有填的欄位會直接取代該語言頁面的內容，沒填的照翻譯表處理。
- 「預覽」按鈕會用前台現有的商品頁套上表單內容，四種語言都能切換查看，確認後再按「儲存並發布」。

### 搜尋、圖片與追蹤碼

- 搜尋是純前端：頁首搜尋框會導到該語言的 `search.*.html?q=關鍵字`，在瀏覽器裡篩選商品，也能用中文名稱搜到外語頁面的商品。
- `_tools/optimize_images.py` 為大圖產生最大 1600px 的 WebP（`*.opt.webp`），建置時自動換用。部署流程每次都會跑，後台新上傳的圖也會處理。
- `_tools/crop_images.py` 把每張商品圖（主圖與圖庫）裁成統一比例：`*.sq.webp`（1:1，列表卡片與縮圖）、`*.w43.webp`（4:3，商品頁主圖），裁切位置自動抓畫面細節最多的區域（狗與衣服），對照表在 `_data/image_crops.json`。部署流程每次都會跑。
- 原站的 Google Analytics、Microsoft Clarity、Facebook 追蹤碼在建置時移除；要加自己的追蹤碼，加在 `_tools/site_builder.py` 的 `strip_trackers` 之後即可。

### 圖片裡的文字

圖片不再寫死文字。含中文的圖分兩種處理，設定都在 `www.apetto.com.tw/_data/image_text.json`：

- **尺寸示意圖**：保留一張去掉文字的底圖（`*.clean.png`，由 `_tools/clean_images.py` 用 OpenCV 修補產生），文字改成 HTML 疊在圖上，位置與字級以圖片寬度百分比記錄，依語言顯示翻譯。
- **尺寸表**：整張圖換成真正的 HTML 表格，內容在 `image_text.json` 的 `charts`。

重新掃描或調整位置：`_tools/ocr/ocr.ps1`（Windows 內建 OCR）找出文字框，`_tools/make_image_text.py` 產生設定，`_tools/clean_images.py` 產生底圖，再 `site_builder.py build`。

## 檔案結構

```
www.apetto.com.tw/          靜態網站（Pages 的發布根目錄）
  _data/products.json       商品資料（後台唯一會改的資料檔）
  _data/uploads/            後台上傳的圖片
  _templates/info/          關於我們、購物流程、消息、公告的原始內容（建置時抽出正文）
  _ext/                     從原站 CDN 抓回的圖片
  _raw_html/                原站未改寫的 HTML 備份（不會部署）
  assets/                   版型 CSS / JS（建置時產生）
_tools/theme.py             版型：所有頁面的 HTML 與樣式
_tools/site_builder.py      資料、翻譯、圖片文字、搜尋等共用邏輯；`build` 會呼叫 theme.py
_tools/admin.html           後台頁面（部署時複製到網站根目錄）
_tools/mirror.py            當初爬取整站用的爬蟲
_tools/verify.py            檢查站內連結是否都指到存在的檔案
_tools/crop_images.py       商品圖統一裁切（1:1 與 4:3）
_tools/repair_banners.py    重做兩張首頁橫幅的去字底圖
_tools/prune_assets.py      列出 / 刪除 _ext 裡沒人用到的檔案
_tools/selftest.py          新增假商品、建置、檢查輸出、還原
.github/workflows/deploy.yml  建置與部署流程
```

## 本機重新產生（可選）

```
pip install beautifulsoup4 lxml
python _tools/site_builder.py build
```
