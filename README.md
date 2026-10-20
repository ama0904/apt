# apetto 網站鏡像 + 商品後台

這個 repo 存放 https://www.apetto.com.tw/ 的靜態鏡像，以及一個可以新增、下架、刪除商品的後台。
推送到 `main` 之後，GitHub Actions 會依 `_data/products.json` 重新產生商品相關頁面並部署到 GitHub Pages。

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

## 檔案結構

```
www.apetto.com.tw/          靜態網站（Pages 的發布根目錄）
  _data/products.json       商品資料（後台唯一會改的資料檔）
  _data/uploads/            後台上傳的圖片
  _templates/               產生頁面用的原始模板（請勿手動修改）
  _ext/                     從 CDN 抓回的 CSS / JS / 圖片
  _raw_html/                原站未改寫的 HTML 備份（不會部署）
_tools/site_builder.py      依 products.json 重新產生首頁、分類頁、商品頁、搜尋頁、sitemap
_tools/admin.html           後台頁面（部署時複製到網站根目錄）
_tools/mirror.py            當初爬取整站用的爬蟲
_tools/verify.py            檢查站內連結是否都指到存在的檔案
.github/workflows/deploy.yml  建置與部署流程
```

## 本機重新產生（可選）

```
pip install beautifulsoup4 lxml
python _tools/site_builder.py build
```
