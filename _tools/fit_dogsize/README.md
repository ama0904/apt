# 試衣間：狗狗品種／體型判斷（跑在筆電 apetto-server 上）

客人選好照片後，試衣間頁面把照片縮到 384 px，`POST /api/dogsize` 送到試衣間伺服器（和 `/api/stylist` 同一個網址、同一組 API 金鑰與 CORS 設定）。伺服器用影像模型判斷最像的品種和體型（小型／中型／大型），頁面只在很有把握、而且客人選的衣服是另一種體型時，才在「開始試穿」上方顯示提醒；永遠不擋人。網址加 `?dogai=1` 會在照片下方顯示品種與數字（測試模式）。

這個資料夾是要放到筆電 `D:\apetto-server\fit\` 的程式（試衣間伺服器 `server.js` 本身不在這個 repo）：

- `dogsize.mjs`：模型載入、判斷、Express handler。`import { dogSizeHandler } from './dogsize.mjs'` 後加一條
  `app.post('/api/dogsize', express.json({ limit: '1mb' }), dogSizeHandler)`，放在和 `/api/stylist` 一樣的驗證後面。
- `size_head.json`：體型分類器的權重（用約 2,300 張標好大小的狗照片訓練；重新訓練只要換這個檔）。

需求：`npm i @huggingface/transformers@3.7.2`（會帶 onnxruntime-node，CPU 即可，不用 GPU）。第一次啟動會從 Hugging Face 下載
`Xenova/convnext-tiny-224` 的 8-bit ONNX 模型（約 28 MB，Apache-2.0）到 `FIT_MODEL_DIR`（預設 `fit\models`），之後都從硬碟載入。
一張照片約 0.1～0.3 秒；一次只處理一張，不會搶 Gemini 試穿的資源。

回傳範例：

```json
{"dog":0.93,"top":[{"id":151,"name":"Chihuahua","zh":"吉娃娃","p":0.82},…],"P":[0.98,0.01,0.01],"guess":"S","ms":140}
```

`guess` 是 `"S"`（小汪斗篷）、`"L"`（大汪雨衣）或 `null`（不確定，不提醒）；`P` 為空代表照片裡看不太到狗。
