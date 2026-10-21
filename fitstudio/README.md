# apetto FitStudio — 寵物虛擬試衣間

這是 apetto FitStudio 的前端快照，從原本獨立跑的本機專案複製過來，供嵌入 apetto 官網使用。

## 運作方式

這組靜態檔案（`index.html` / `app.js` / `style.css` / `i18n.js` / `assets_data.js`）本身不含任何
AI 邏輯——實際呼叫 Gemini、操作瀏覽器產生合成圖的伺服器，繼續跑在原作者自己的電腦上，
透過 Tailscale Funnel 對外開放：

```
https://tablet-uaj7iieq.tail188668.ts.net
```

`app.js` 開頭的 `API_BASE` 常數就是指向這個網址；如果那台機器換了對外網址（重灌 Tailscale、
換成別的 tunnel 服務等），只要更新這一個常數即可。

**這台機器不是 24 小時穩定上線的伺服器**——是一般家用電腦，會重開機、會斷線。串接前記得看
一下 API 規格文件裡「目前狀態」那段的說明，並確認前端有妥善處理 `/api/health` 打不通時的
降級顯示（例如「試衣間暫停服務，請稍後再來」）。

## 檔案說明

- `index.html` / `style.css` — 頁面結構與樣式，含繁中/德文雙語支援
- `app.js` — 主要邏輯：拖曳上傳、與伺服器溝通、結果顯示、下載/分享
- `i18n.js` — 文案字典（zh/de），所有使用者可見文字都走這裡
- `assets_data.js` — 範例狗狗照片、三款示範衣服的 base64 圖片資料

`app.js` 裡 `callGroqMultimodalPrompt` / `callOllamaMultimodalPrompt` / `callOpenRouterMultimodalPrompt` /
`callPlaywrightMultimodalPrompt` 這幾個函式是開發過程中嘗試過的其他方案，現在沒有被呼叫，
是死碼，可以直接刪除。

完整 API 規格另外以訊息方式提供。
