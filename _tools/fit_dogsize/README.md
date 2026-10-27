# 試衣間：狗狗品種／體型判斷（跑在筆電 apetto-server 上）

客人選好照片後，試衣間頁面把照片縮到 384 px，`POST /api/dogsize` 送到試衣間伺服器（和 `/api/stylist` 同一個網址、同一組 API 金鑰與 CORS 設定）。伺服器用影像模型判斷最像的品種和體型（小型／中型／大型），頁面只在很有把握、而且客人選的衣服是另一種體型時，才在「開始試穿」上方顯示提醒；永遠不擋人。網址加 `?dogai=1` 會在照片下方顯示品種與數字（測試模式）。

這個資料夾是要放到筆電 `D:\apetto-server\fit\` 的程式（試衣間伺服器 `server.js` 本身不在這個 repo）：

- `dogsize.mjs`：模型載入、判斷、Express handler。server.js 是 CommonJS，用
  `const { dogSizeHandler, warmup } = await import('./dogsize.mjs')`，再加 `app.post('/api/dogsize', dogSizeHandler)`，
  放在和 `/api/stylist` 一樣的驗證後面。
- `breed_head.json`：品種分類器（第三版新增）：用模型的 768 維影像特徵認 140 種犬種（台灣常見的都有），包含原模型沒有的臘腸狗、柴犬、台灣犬／米克斯；回傳的 `top` 就是它的前三名，`breedSure` 為 false 表示把握不高（可能是米克斯或少見品種）。沒有這個檔時退回 ImageNet 的品種名。
- `size_head.json`：體型分類器的權重。第二版用約 5,300 張標好大小的狗照片訓練，輸入是品種分數加模型的 768 維影像特徵；
  重新訓練只要換這個檔（`features` 欄位說明用哪種輸入）。

模型檔不會自動下載：下載這個資料夾裡的 `dogsize-v2.zip`（約 22 MB，SHA256 0b4c9061…bed5），解壓到 `FIT_MODEL_DIR`（預設 `fit\models`），
變成 `fit\models\dogsize-v2\onnx\model_quantized.onnx`。它是 `facebook/convnext-tiny-224`（ImageNet，Apache-2.0）的 8-bit ONNX
（Xenova 轉換），多加了一個 `pooled` 輸出（768 維影像特徵）；這個修改檔是用 `onnx` 套件在 Python 裡做的，所以不能直接從 Hugging Face 抓。

需求：`@huggingface/transformers`（3.7 以上）和它附帶的 `onnxruntime-node`，CPU 即可。推論限制在 2 個執行緒，一張照片約 0.1～0.3 秒，
一次只處理一張，不會搶 Gemini 試穿的資源。

回傳範例：

```json
{"dog":0.93,"top":[{"zh":"吉娃娃","name":"Chihuahua","p":0.92},…],"breedSure":true,"imagenet":[…],"P":[0.98,0.01,0.01],"guess":"S","ms":90}
```

`guess` 是 `"S"`（小汪斗篷）、`"L"`（大汪雨衣）或 `null`（不確定，不提醒）；`P` 為空代表照片裡看不太到狗。

準確度（第二版，留出的 1,031 張沒訓練過的照片，門檻 0.7）：小型／大型狗給對提醒 78%，大小搞反 1.5%，中型犬或大型犬幼犬誤給提醒 7%。
完全沒看過的品種會差很多（約四成給對、5% 搞反），所以提醒文字一律寫「AI 從照片估計」並附「照樣試穿」。
