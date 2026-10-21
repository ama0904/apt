/* ==========================================================================
   apetto FitStudio — i18n (繁體中文 / Deutsch)
   Markup opts in with data-i18n="key"; JS strings go through t('key', vars).
   ========================================================================== */

const I18N = {
    zh: {
        'lang.name':            '中文',
        'doc.title':            'apetto FitStudio - 寵物虛擬試衣間',
        'doc.lang':             'zh-TW',

        'header.tagline':       '小汪虛擬試衣間 • 不只可愛，更有帥氣',
        'status.connected':     'AI 引擎已連線 ✅',
        'status.disconnected':  'AI 引擎未連線 (Port 3000)',

        'section1.title':       '選擇或上傳狗狗照片',
        'upload.headline':      '上傳你家狗狗的照片',
        'upload.sell':          '看看牠穿上新衣服有多帥 ✨',
        'upload.main':          '拖曳照片至此，或',
        'upload.browse':        '瀏覽檔案',
        'upload.formats':       '支援 JPG, PNG, WEBP',
        'upload.change':        '🔄 點擊或拖曳以更換圖片',
        'upload.alt':           '狗狗預覽',
        'preset.label':         '還沒有照片？先用示範狗狗試試：',
        'preset.golden':        '黃金獵犬幼犬',
        'preset.labrador':      '棕色拉布拉多',

        'section2.title':       '選擇 apetto 經典服飾',
        'clothes.pink.tag':     '桃粉',
        'clothes.pink.alt':     '桃粉刷毛外套',
        'clothes.yellow.tag':   '螢光黃',
        'clothes.yellow.alt':   '螢光黃雨衣',
        'clothes.blue.tag':     '寶藍',
        'clothes.blue.alt':     '寶藍雨衣',

        'btn.ai.main':          'Real AI 生成',
        'btn.ai.sub':           'AI 自動穿衣',

        'canvas.title':         '準備試衣',
        'canvas.desc':          '請選擇一隻狗狗照片，並為牠挑一件帥氣的衣服吧！',

        'note.title':           'AI 造型師的話',
        'note.writing':         'AI 造型師正在為牠寫推薦…',
        'export.tip':           '這是 AI 生成的試穿結果，可以',
        'export.tip.strong':    '直接下載',
        'export.tip.end':       '保存。',
        'export.button':        '儲存並下載照片',

        'loading.title':        'Real AI 智慧生成中',
        'loading.dogAlt':       '您的狗狗',
        'step1.name':           '準備圖片',
        'step1.sub':            '最佳化處理中...',
        'step2.name':           '連線本機 AI 引擎',
        'step2.sub':            '啟動 AI 引擎...',
        'step3.name':           '傳送狗狗與衣服',
        'step3.sub':            '載入圖片中...',
        'step4.name':           'AI 原生融圖生成',
        'step4.sub':            '約 30–60 秒...',
        'step5.name':           '完成！',
        'step5.sub':            '顯示試穿照片',

        // Progress states pushed from the server
        'srv.prepare':          '📁 準備圖片中...',
        'srv.launch':           '🌐 啟動 AI 引擎...',
        'srv.navigate':         '🌐 導覽至 AI 引擎...',
        'srv.pasteDog':         '🐶 貼上狗狗照片...',
        'srv.pasteClothes':     '👗 貼上衣服圖片...',
        'srv.typePrompt':       '✍️ 輸入生成指令...',
        'srv.sent':             '🚀 指令已送出，等待 AI 回應...',
        'srv.generating':       '✨ 生成中... {sec} 秒',
        'srv.caption':          '✍️ 產生推薦文案...',
        'srv.done':             '🎉 圖片生成完成！',

        'timer.suffix':         ' ({sec} 秒)',
        'done.browser':         '✓ 瀏覽器就緒',
        'done.compress':        '✓ 完成',
        'done.sent':            '✓ 圖片已傳送',
        'done.generated':       '✓ 生成完成',

        'err.pickFirst':        '請先選擇狗狗照片與衣服！',
        'err.busy':             '目前正在為另一位使用者生成圖片，請稍候一分鐘再試。',
        'err.allAccountsExhausted': '所有帳號的額度目前都已用盡，請稍後再試。',
        'err.noImageFromModel': 'AI 沒有生成圖片，只針對照片給了文字說明——通常是照片中不容易辨識出寵物（例如照片太模糊、角度太奇怪，或裡面根本沒有動物）。請換一張清楚的寵物照片再試一次！',
        'err.attachFailed': '照片附加失敗，寵物或衣服照片可能沒有成功送出，請重新整理頁面再試一次。',
        'err.unauthorized':     '存取遭拒（金鑰不符）。\n\n請重新整理頁面再試一次。若仍然失敗，代表伺服器 .env 裡的 FITSTUDIO_API_KEY 與網頁內建的金鑰不一致。',
        'err.timeout':          '【AI 生成逾時】AI 回應超過 5 分鐘，請重試。若 AI 服務很忙，可稍後再試！',
        'err.noImage':          '伺服器未回傳有效圖片，請重試。',
        'err.generic':          'AI 生成失敗: ',
        'err.automation':       '【AI 生成失敗】: '
    },

    de: {
        'lang.name':            'Deutsch',
        'doc.title':            'apetto FitStudio – Virtuelle Anprobe für Hunde',
        'doc.lang':             'de',

        'header.tagline':       'Virtuelle Anprobe für Hunde • Nicht nur süß, sondern richtig schick',
        'status.connected':     'KI-Engine verbunden ✅',
        'status.disconnected':  'KI-Engine nicht verbunden (Port 3000)',

        'section1.title':       'Hundefoto auswählen oder hochladen',
        'upload.headline':      'Lade ein Foto deines Hundes hoch',
        'upload.sell':          'Sieh, wie schick er im neuen Outfit aussieht ✨',
        'upload.main':          'Foto hierher ziehen oder',
        'upload.browse':        'Datei auswählen',
        'upload.formats':       'Unterstützt JPG, PNG, WEBP',
        'upload.change':        '🔄 Klicken oder ziehen zum Ersetzen',
        'upload.alt':           'Hundevorschau',
        'preset.label':         'Noch kein Foto? Probier’s mit einem Beispielhund:',
        'preset.golden':        'Golden-Retriever-Welpe',
        'preset.labrador':      'Brauner Labrador',

        'section2.title':       'apetto Klassiker auswählen',
        'clothes.pink.tag':     'Pink',
        'clothes.pink.alt':     'Pinkfarbener Fleecemantel',
        'clothes.yellow.tag':   'Neongelb',
        'clothes.yellow.alt':   'Neongelbe Regenjacke',
        'clothes.blue.tag':     'Royalblau',
        'clothes.blue.alt':     'Royalblaue Regenjacke',

        'btn.ai.main':          'Real AI Generierung',
        'btn.ai.sub':           'KI zieht den Hund an',

        'canvas.title':         'Bereit zur Anprobe',
        'canvas.desc':          'Wähle ein Hundefoto und such ihm ein schickes Outfit aus!',

        'note.title':           'Notiz der KI-Stylistin',
        'note.writing':         'Die KI-Stylistin schreibt gerade ihre Empfehlung …',
        'export.tip':           'Das ist das KI-generierte Ergebnis – du kannst es',
        'export.tip.strong':    'direkt herunterladen',
        'export.tip.end':       '.',
        'export.button':        'Foto speichern & herunterladen',

        'loading.title':        'Real AI generiert gerade',
        'loading.dogAlt':       'Dein Hund',
        'step1.name':           'Bilder vorbereiten',
        'step1.sub':            'Wird optimiert ...',
        'step2.name':           'KI-Engine verbinden',
        'step2.sub':            'KI-Engine wird gestartet ...',
        'step3.name':           'Hund & Kleidung senden',
        'step3.sub':            'Bilder werden geladen ...',
        'step4.name':           'KI-Bildgenerierung',
        'step4.sub':            'ca. 30–60 Sekunden ...',
        'step5.name':           'Fertig!',
        'step5.sub':            'Ergebnis wird angezeigt',

        'srv.prepare':          '📁 Bilder werden vorbereitet ...',
        'srv.launch':           '🌐 KI-Engine wird gestartet ...',
        'srv.navigate':         '🌐 Verbindung zur KI-Engine ...',
        'srv.pasteDog':         '🐶 Hundefoto wird eingefügt ...',
        'srv.pasteClothes':     '👗 Kleidungsfoto wird eingefügt ...',
        'srv.typePrompt':       '✍️ Anweisung wird eingegeben ...',
        'srv.sent':             '🚀 Gesendet, warte auf die KI ...',
        'srv.generating':       '✨ Generiert ... {sec} s',
        'srv.caption':          '✍️ Empfehlung wird geschrieben ...',
        'srv.done':             '🎉 Bild fertig generiert!',

        'timer.suffix':         ' ({sec} s)',
        'done.browser':         '✓ Browser bereit',
        'done.compress':        '✓ Fertig',
        'done.sent':            '✓ Bilder gesendet',
        'done.generated':       '✓ Generierung fertig',

        'err.pickFirst':        'Bitte zuerst ein Hundefoto und ein Kleidungsstück auswählen!',
        'err.busy':             'Gerade wird für jemand anderen ein Bild generiert. Bitte in einer Minute noch einmal versuchen.',
        'err.allAccountsExhausted': 'Alle Konten haben gerade ihr Kontingent ausgeschöpft. Bitte später erneut versuchen.',
        'err.noImageFromModel': 'Die KI hat kein Bild erzeugt, sondern nur einen Text zum Foto geschrieben — meist weil auf dem Foto kein Tier klar erkennbar war (unscharfes Foto, ungewöhnlicher Winkel, oder gar kein Tier zu sehen). Bitte ein klareres Foto deines Haustiers ausprobieren!',
        'err.attachFailed': 'Das Anhängen der Fotos ist fehlgeschlagen — Haustier- oder Kleidungsfoto wurden eventuell nicht richtig übermittelt. Bitte die Seite neu laden und erneut versuchen.',
        'err.unauthorized':     'Zugriff verweigert (Schlüssel stimmt nicht).\n\nBitte die Seite neu laden und erneut versuchen. Falls es weiterhin fehlschlägt, stimmt FITSTUDIO_API_KEY in der .env des Servers nicht mit dem Schlüssel in der Seite überein.',
        'err.timeout':          '[Zeitüberschreitung] Die KI hat über 5 Minuten nicht geantwortet. Bitte erneut versuchen – vielleicht ist der Dienst gerade ausgelastet.',
        'err.noImage':          'Der Server hat kein gültiges Bild zurückgegeben. Bitte erneut versuchen.',
        'err.generic':          'KI-Generierung fehlgeschlagen: ',
        'err.automation':       '[KI-Generierung fehlgeschlagen]: '
    }
};

const I18N_STORE_KEY = 'fitstudio_lang';

function getLang() {
    const saved = localStorage.getItem(I18N_STORE_KEY);
    if (saved && I18N[saved]) return saved;
    // Fall back to the browser's preference, then Chinese
    return (navigator.language || '').toLowerCase().startsWith('de') ? 'de' : 'zh';
}

function setLang(lang) {
    if (!I18N[lang]) return;
    localStorage.setItem(I18N_STORE_KEY, lang);
    applyI18n();
    document.dispatchEvent(new CustomEvent('langchange', { detail: { lang } }));
}

/** Translate a key; {placeholders} are filled from `vars`. */
function t(key, vars) {
    const lang = getLang();
    let s = (I18N[lang] && I18N[lang][key]) || (I18N.zh && I18N.zh[key]) || key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.split('{' + k + '}').join(v);
    return s;
}

/** Rewrite every element carrying data-i18n / data-i18n-alt in the current language. */
function applyI18n() {
    const lang = getLang();
    document.documentElement.lang = t('doc.lang');
    document.title = t('doc.title');

    document.querySelectorAll('[data-i18n]').forEach(el => {
        el.textContent = t(el.getAttribute('data-i18n'));
    });
    document.querySelectorAll('[data-i18n-alt]').forEach(el => {
        el.alt = t(el.getAttribute('data-i18n-alt'));
    });

    // Segmented switch: both languages visible, current one marked
    document.querySelectorAll('.lang-opt').forEach(btn => {
        const isActive = btn.dataset.lang === lang;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-pressed', String(isActive));
    });
}

document.addEventListener('DOMContentLoaded', () => {
    applyI18n();
    document.querySelectorAll('.lang-opt').forEach(btn => {
        btn.addEventListener('click', () => setLang(btn.dataset.lang));
    });
});
