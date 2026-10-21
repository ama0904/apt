/* ==========================================================================
   apetto FitStudio Core Interactive Script
   HTML5 Canvas Editor + Real-Time Chroma Key Background Removal
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // Core elements
    const canvas = document.getElementById('fitting-canvas');
    const ctx = canvas.getContext('2d');
    
    const fileUpload = document.getElementById('file-upload');
    const dropZone = document.getElementById('drop-zone');
    const canvasPlaceholder = document.getElementById('canvas-placeholder');
    const adjustmentSection = document.getElementById('adjustment-section');
    const exportBar = document.getElementById('export-bar');
    
    // Preset dogs
    const btnDogGolden = document.getElementById('btn-dog-golden');
    const btnDogLabrador = document.getElementById('btn-dog-labrador');
    
    // Clothes selectors
    const clothesCards = document.querySelectorAll('.clothes-card');

    const btnRealAi = document.getElementById('btn-real-ai');
    const btnExport = document.getElementById('btn-export');
    const apiIndicator = document.getElementById('api-indicator');
    const aiLoadingModal = document.getElementById('ai-loading-modal');

    // Scanner overlay
    const scannerLaser = document.getElementById('scanner-laser');
    const scannerGrid  = document.getElementById('scanner-grid');

    // App state
    let dogImage = null;
    let clothesRawImage = null;      // Holds the raw green-screen image
    let clothesTransparentImage = null; // Holds the processed transparent image
    
    // Overlay settings
    let overlayState = {
        x: 0,
        y: 0,
        scale: 1.0,         // multiplier relative to default size
        rotate: 0,          // in degrees
        opacity: 1.0,       // 0.0 to 1.0
        mirrored: false
    };
    
    // Interaction states
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let overlayStartX = 0;
    let overlayStartY = 0;

    // ==========================================================================
    // 1. Initial State / Preset Loaders
    // ==========================================================================
    
    // Dynamically inject Base64 thumbnails to avoid any CORS/file load issues
    if (typeof ASSETS_DATA !== 'undefined') {
        document.querySelector('.thumb-golden').style.backgroundImage = `url(${ASSETS_DATA.dog_golden})`;
        document.querySelector('.thumb-labrador').style.backgroundImage = `url(${ASSETS_DATA.dog_labrador})`;
        document.querySelector('#card-pink img').src   = ASSETS_DATA.pink_coat;
        document.querySelector('#card-yellow img').src = ASSETS_DATA.yellow_coat;
        document.querySelector('#card-blue img').src   = ASSETS_DATA.blue_coat;
    }

    // No dog is loaded on start. The empty upload box is the invitation to bring
    // your own photo; the sample dogs are a fallback the visitor has to choose.

    btnDogGolden.addEventListener('click', () => {
        setActivePreset(btnDogGolden);
        loadDogImage(typeof ASSETS_DATA !== 'undefined' ? ASSETS_DATA.dog_golden : 'assets/dog_golden.jpg');
    });

    btnDogLabrador.addEventListener('click', () => {
        setActivePreset(btnDogLabrador);
        loadDogImage(typeof ASSETS_DATA !== 'undefined' ? ASSETS_DATA.dog_labrador : 'assets/dog_labrador.webp');
    });

    function setActivePreset(activeButton) {
        document.querySelectorAll('.btn-preset').forEach(btn => btn.classList.remove('active'));
        activeButton.classList.add('active');
        // Clear file input
        fileUpload.value = '';
    }

    // File Upload handling
    fileUpload.addEventListener('change', handleFileSelect);
    
    // Drag & Drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            fileUpload.files = e.dataTransfer.files;
            handleFileSelect();
        }
    });

    function handleFileSelect() {
        const file = fileUpload.files[0];
        if (file) {
            document.querySelectorAll('.btn-preset').forEach(btn => btn.classList.remove('active'));
            const reader = new FileReader();
            reader.onload = function(event) {
                loadDogImage(event.target.result);   // also refreshes the upload-box preview
            };
            reader.readAsDataURL(file);
        }
    }

    function showDogPreview(src) {
        const uploadPrompt  = document.getElementById('upload-prompt');
        const uploadPreview = document.getElementById('upload-preview');
        const dogPreviewImg = document.getElementById('dog-preview-img');
        if (uploadPrompt && uploadPreview && dogPreviewImg) {
            dogPreviewImg.src = src;
            uploadPrompt.style.display  = 'none';
            uploadPreview.style.display = 'flex';
        }
    }

    // The generate button needs both halves; nothing is preloaded any more, so
    // it stays disabled until the visitor has actually picked a dog and an outfit.
    function updateAiButton() {
        if (btnRealAi) btnRealAi.disabled = !(dogImage && clothesRawImage);
    }

    function loadDogImage(src) {
        // Keep the upload box in sync with whatever dog is active — preset or upload
        showDogPreview(src);
        dogImage = new Image();
        dogImage.onload = function() {
            updateAiButton();
            // Hide placeholder once dog is loaded
            canvasPlaceholder.style.opacity = '0';
            setTimeout(() => { canvasPlaceholder.style.display = 'none'; }, 300);
            
            // Adjust canvas size to fit container aspect ratio, keeping dog aspect ratio
            resizeCanvasToFit();
            
            // If clothes are already loaded, adjust state, otherwise keep it
            if (clothesTransparentImage) {
                resetOverlayState();
            }
            
            draw();
        };
        dogImage.src = src;
    }

    function resizeCanvasToFit() {
        if (!dogImage) return;
        const container = document.getElementById('canvas-wrapper');
        const containerWidth = container.clientWidth;
        const containerHeight = container.clientHeight;
        
        const dogAspect = dogImage.width / dogImage.height;
        const containerAspect = containerWidth / containerHeight;
        
        if (dogAspect > containerAspect) {
            // Dog is wider than container
            canvas.width = containerWidth;
            canvas.height = containerWidth / dogAspect;
        } else {
            // Dog is taller
            canvas.height = containerHeight;
            canvas.width = containerHeight * dogAspect;
        }
    }

    window.addEventListener('resize', () => {
        if (dogImage) {
            resizeCanvasToFit();
            draw();
        }
    });

    // On phones the preview canvas starts hidden (see CSS) so the demo dog
    // photo doesn't sit under the button. It stays hidden through dog/clothes
    // selection — the rough pasted-on overlay isn't worth showing — and only
    // appears once the AI result is ready. Re-measure on reveal since the
    // canvas was sized while its container was display:none.
    function revealMobilePanel() {
        const rightPanel = document.querySelector('.right-panel');
        if (rightPanel && !rightPanel.classList.contains('mobile-visible')) {
            rightPanel.classList.add('mobile-visible');
            resizeCanvasToFit();
            draw();
        }
    }

    // ==========================================================================
    // 2. Clothes Selector & Chroma Key Engine
    // ==========================================================================
    
    clothesCards.forEach(card => {
        card.addEventListener('click', () => {
            clothesCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            
            const byCard = {
                'card-pink':   'pink_coat',
                'card-yellow': 'yellow_coat',
                'card-blue':   'blue_coat'
            };
            const key = byCard[card.id];
            if (typeof ASSETS_DATA !== 'undefined' && key) loadClothesAndProcess(ASSETS_DATA[key]);
        });
    });

    function loadClothesAndProcess(src) {
        clothesRawImage = new Image();
        clothesRawImage.onload = function() {
            // The outfits are reference photos of dogs already wearing the coat,
            // not green-screen cutouts — chroma-keying them would produce mush.
            // They're sent to the AI as-is, so no transparent overlay is built and
            // the manual drag-to-position compositing stays switched off.
            clothesTransparentImage = null;
            exportBar.classList.remove('disabled');
            draw();
            updateAiButton();
        };
        clothesRawImage.src = src;
    }

    function autoSmartFit() {
        if (!clothesTransparentImage || !dogImage) return;
        const isGolden   = btnDogGolden.classList.contains('active');
        const isLabrador = btnDogLabrador.classList.contains('active');
        if (isGolden) {
            overlayState.x = canvas.width * 0.52;
            overlayState.y = canvas.height * 0.68;
            overlayState.scale = 1.15;
            overlayState.rotate = -4;
        } else if (isLabrador) {
            overlayState.x = canvas.width * 0.61;
            overlayState.y = canvas.height * 0.53;
            overlayState.scale = 1.25;
            overlayState.rotate = 12;
        } else {
            overlayState.x = canvas.width * 0.5;
            overlayState.y = canvas.height * 0.6;
            overlayState.scale = 1.2;
            overlayState.rotate = 0;
        }
        overlayState.mirrored = false;
        overlayState.opacity  = 1.0;
        draw();
    }


    /**
     * Chroma Key Background Removal Algorithm
     * Detects green screen pixels and replaces them with pure transparency.
     */
    function processChromaKey() {
        if (!clothesRawImage) return;
        
        // Create an offscreen canvas
        const offscreen = document.createElement('canvas');
        const oCtx = offscreen.getContext('2d');
        
        offscreen.width = clothesRawImage.width;
        offscreen.height = clothesRawImage.height;
        
        // Draw raw green-screen image
        oCtx.drawImage(clothesRawImage, 0, 0);
        
        const imgData = oCtx.getImageData(0, 0, offscreen.width, offscreen.height);
        const data = imgData.data;
        
        // Loop through pixels and remove green
        for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i+1];
            const b = data[i+2];
            
            // Green detection threshold:
            // Standard chroma key green check - green channel is significantly higher than red and blue
            // also check that green is high enough.
            const isGreen = g > 90 && g > r * 1.28 && g > b * 1.28;
            
            if (isGreen) {
                // Remove pixel completely (Alpha = 0)
                data[i+3] = 0;
            } else {
                // Soften edges: check pixels near green threshold and make semi-transparent for anti-aliasing
                const isEdge = g > 75 && g > r * 1.15 && g > b * 1.15;
                if (isEdge) {
                    const diff = g - Math.max(r, b);
                    data[i+3] = Math.max(0, 255 - (diff * 4));
                }
            }
        }
        
        // Put data back and store as transparent image
        oCtx.putImageData(imgData, 0, 0);
        
        clothesTransparentImage = new Image();
        clothesTransparentImage.src = offscreen.toDataURL();
    }

    // ==========================================================================
    // 3. Canvas Rendering & Calculations
    // ==========================================================================

    function resetOverlayState() {
        if (!dogImage || !clothesTransparentImage) return;
        
        // Default position: center of the canvas
        overlayState.x = canvas.width / 2;
        overlayState.y = canvas.height / 2 + (canvas.height * 0.05); // slightly lower
        
        // Default scale: make clothing height roughly 50% of the canvas height
        const targetHeight = canvas.height * 0.5;
        const rawAspect = clothesRawImage.width / clothesRawImage.height;
        const clothesHeight = canvas.width * 0.4 / rawAspect;
        
        overlayState.scale = targetHeight / clothesHeight;
        overlayState.rotate = 0;
        overlayState.opacity = 1.0;
        overlayState.mirrored = false;
    }

    function draw() {
        if (!dogImage) return;
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // 1. Draw Dog Background
        ctx.drawImage(dogImage, 0, 0, canvas.width, canvas.height);
        
        // 2. Draw Clothes Overlay
        if (clothesTransparentImage && clothesTransparentImage.complete) {
            ctx.save();
            
            // Set opacity
            ctx.globalAlpha = overlayState.opacity;
            
            // Move origin to clothing position
            ctx.translate(overlayState.x, overlayState.y);
            
            // Apply rotation (convert degrees to radians)
            ctx.rotate(overlayState.rotate * Math.PI / 180);
            
            // Apply mirror/flip if needed
            const scaleX = overlayState.mirrored ? -overlayState.scale : overlayState.scale;
            ctx.scale(scaleX, overlayState.scale);
            
            // Draw clothing image centered on origin
            const drawWidth = canvas.width * 0.4;
            const drawHeight = drawWidth * (clothesRawImage.height / clothesRawImage.width);
            
            ctx.drawImage(
                clothesTransparentImage, 
                -drawWidth / 2, 
                -drawHeight / 2, 
                drawWidth, 
                drawHeight
            );
            
            ctx.restore();
        }
    }

    // ==========================================================================
    // 5. Drag and Drop Overlay Controls (Direct Canvas Interaction)
    // ==========================================================================

    canvas.addEventListener('mousedown', startDrag);
    canvas.addEventListener('mousemove', drag);
    window.addEventListener('mouseup', endDrag);
    
    // Touch support for tablets/mobile
    canvas.addEventListener('touchstart', (e) => {
        if (e.touches.length === 1) {
            const touch = e.touches[0];
            startDrag(touch);
        }
    }, { passive: true });
    
    canvas.addEventListener('touchmove', (e) => {
        if (e.touches.length === 1) {
            const touch = e.touches[0];
            drag(touch);
        }
    }, { passive: true });
    
    canvas.addEventListener('touchend', endDrag);

    function startDrag(e) {
        if (!clothesTransparentImage) return;
        
        const rect = canvas.getBoundingClientRect();
        const clientX = e.clientX || e.pageX;
        const clientY = e.clientY || e.pageY;
        
        const mouseX = ((clientX - rect.left) / rect.width) * canvas.width;
        const mouseY = ((clientY - rect.top) / rect.height) * canvas.height;
        
        // Simple hit test: check if user clicked close to the center of the clothing
        const dist = Math.sqrt((mouseX - overlayState.x)**2 + (mouseY - overlayState.y)**2);
        
        // Define active clickable radius (e.g. 150px or clothing height)
        const hitRadius = canvas.width * 0.25 * overlayState.scale;
        
        if (dist < hitRadius) {
            isDragging = true;
            dragStartX = mouseX;
            dragStartY = mouseY;
            overlayStartX = overlayState.x;
            overlayStartY = overlayState.y;
        }
    }

    function drag(e) {
        if (!isDragging) return;
        
        const rect = canvas.getBoundingClientRect();
        const clientX = e.clientX || e.pageX;
        const clientY = e.clientY || e.pageY;
        
        const mouseX = ((clientX - rect.left) / rect.width) * canvas.width;
        const mouseY = ((clientY - rect.top) / rect.height) * canvas.height;
        
        const dx = mouseX - dragStartX;
        const dy = mouseY - dragStartY;
        
        overlayState.x = overlayStartX + dx;
        overlayState.y = overlayStartY + dy;
        
        draw();
    }

    function endDrag() {
        isDragging = false;
    }

    // ==========================================================================
    // btnSmartFit removed — auto-fit now triggers on clothes selection


    // ==========================================================================
    // 7. Image Export Engine
    // ==========================================================================

    /** Hand a finished canvas to the visitor.
     *
     *  This used to be `link.href = canvas.toDataURL('image/png')`, which on
     *  iPhone showed the download prompt and then silently did nothing: Safari
     *  chokes on multi-megabyte data: URLs, and a full-size PNG in base64 is
     *  exactly that. A Blob URL avoids building that giant string at all.
     *
     *  On a phone the share sheet is offered first — "儲存影像" puts the picture
     *  straight into the photo library, which is where people expect it; a plain
     *  download only reaches Files → Downloads. */
    async function saveCanvas(outputCanvas) {
        const blob = await new Promise(resolve =>
            outputCanvas.toBlob(resolve, 'image/jpeg', 0.92));   // JPEG: far smaller than PNG
        if (!blob) return;

        const filename = 'apetto-fitstudio-result.jpg';
        const file = new File([blob], filename, { type: 'image/jpeg' });

        if (navigator.canShare && navigator.canShare({ files: [file] })) {
            try {
                await navigator.share({ files: [file], title: 'apetto FitStudio' });
                return;
            } catch (err) {
                if (err && err.name === 'AbortError') return;    // visitor cancelled
                // anything else: fall through to the download
            }
        }

        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.download = filename;
        link.href = url;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);       // let the download start
    }

    btnExport.addEventListener('click', async () => {
        if (!dogImage) return;

        // AI 生成模式：衣服已合成在狗狗圖片上，直接下載
        if (!clothesTransparentImage) {
            const outputCanvas = document.createElement('canvas');
            outputCanvas.width  = dogImage.width;
            outputCanvas.height = dogImage.height;
            outputCanvas.getContext('2d').drawImage(dogImage, 0, 0);
            await saveCanvas(outputCanvas);
            return;
        }

        // 手動疊加模式：合成狗狗 + 雨衣
        const outputCanvas = document.createElement('canvas');
        const oCtx = outputCanvas.getContext('2d');
        outputCanvas.width  = dogImage.width;
        outputCanvas.height = dogImage.height;

        oCtx.drawImage(dogImage, 0, 0, outputCanvas.width, outputCanvas.height);
        oCtx.save();
        oCtx.globalAlpha = overlayState.opacity;

        const scaleFactorX = dogImage.width  / canvas.width;
        const scaleFactorY = dogImage.height / canvas.height;
        const mappedX = overlayState.x * scaleFactorX;
        const mappedY = overlayState.y * scaleFactorY;

        oCtx.translate(mappedX, mappedY);
        oCtx.rotate(overlayState.rotate * Math.PI / 180);

        const rawScale = overlayState.scale * scaleFactorX;
        const scaleX   = overlayState.mirrored ? -rawScale : rawScale;
        oCtx.scale(scaleX, rawScale);

        const drawWidth  = canvas.width * 0.4;
        const drawHeight = drawWidth * (clothesRawImage.height / clothesRawImage.width);
        oCtx.drawImage(clothesTransparentImage, -drawWidth / 2, -drawHeight / 2, drawWidth, drawHeight);
        oCtx.restore();

        await saveCanvas(outputCanvas);
    });


    // ==========================================================================
    // 8. Playwright Server Status Check
    // ==========================================================================

    // ── Local Server Bridge (Port 3000 - Playwright Native Gemini) ──
    // This frontend is a copy published to a separate host (GitHub Pages) that
    // calls back to the Gemini-automation server, which stays on the original
    // machine — so every API call needs the full remote origin, not a
    // same-origin relative path. If that server's address ever changes
    // (reinstalled Tailscale, different tunnel), this is the one constant to
    // update.
    const API_BASE = 'https://tablet-uaj7iieq.tail188668.ts.net';
    const LOCAL_SERVER_API = API_BASE + '/api/stylist';
    let isServerConnected = false;

    // API key for the local bridge server.
    // NOTE: this key ships in the page source, so it is NOT a security control —
    // anyone who can open this site can read it and call the API. It stays here
    // only so the server's key check keeps working without anyone typing a key.
    // A ?key=... in the URL (or a previously saved one) still wins, so the key
    // can be rotated in .env and handed out by link without editing this file.
    const DEFAULT_API_KEY = 'L6nWwnJk0hlDMmnjqT5qiSjehRZUKKs';

    // When served through an ngrok free tunnel, requests that look like browser
    // navigation get ngrok's "you are about to visit" interstitial — which would
    // return HTML where our code expects JSON. This header opts every API call
    // out of it. Harmless on any other host.
    const API_HEADERS = { 'ngrok-skip-browser-warning': 'true' };

    (function captureApiKeyFromUrl() {
        const urlKey = new URLSearchParams(window.location.search).get('key');
        if (urlKey) {
            localStorage.setItem('fitstudio_api_key', urlKey);
            const cleanUrl = window.location.pathname + window.location.hash;
            window.history.replaceState({}, document.title, cleanUrl);
        }
    })();
    function getFitstudioApiKey() {
        return localStorage.getItem('fitstudio_api_key') || DEFAULT_API_KEY;
    }

    // Compress image to reduce payload size
    function compressImage(src, maxPx = 800, quality = 0.82) {
        return new Promise(resolve => {
            const img = new Image();
            img.onload = () => {
                const ratio  = Math.min(maxPx / img.width, maxPx / img.height, 1);
                const canvas = document.createElement('canvas');
                canvas.width  = Math.round(img.width  * ratio);
                canvas.height = Math.round(img.height * ratio);
                canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
                resolve(canvas.toDataURL('image/jpeg', quality));
            };
            img.onerror = () => resolve(src);
            img.src = src;
        });
    }

    // Health check with local Playwright server
    async function checkServerHealth() {
        try {
            const res = await fetch(API_BASE + '/api/health', { headers: API_HEADERS });
            if (res.ok) {
                isServerConnected = true;
                if (apiIndicator) {
                    apiIndicator.className = 'api-indicator connected';
                    apiIndicator.querySelector('.indicator-text').textContent = t('status.connected');
                }
                return;
            }
        } catch (_) {}

        isServerConnected = false;
        if (apiIndicator) {
            apiIndicator.className = 'api-indicator disconnected';
            apiIndicator.querySelector('.indicator-text').textContent = t('status.disconnected');
        }
    }

    checkServerHealth();
    setInterval(checkServerHealth, 8000);
    // Refresh the indicator immediately on a language switch instead of waiting
    // for the next poll.
    document.addEventListener('langchange', checkServerHealth);




    // ==========================================================================
    // 9. Real-time Progress Display (client-side timer, no network needed)
    // ==========================================================================

    let statusPollInterval = null;

    function startStatusPolling() {
        const loadingDesc = document.querySelector('.loading-desc');
        const progressBar = document.getElementById('loading-progress-bar');
        const startTime   = Date.now();

        // Each step: { sec: seconds_since_start, pct: progress_bar%, text: display_text }
        const steps = [
            { sec: 0,   pct: 8,  key: 'srv.prepare' },
            { sec: 1,   pct: 18, key: 'srv.launch' },
            { sec: 3,   pct: 32, key: 'srv.pasteDog' },
            { sec: 6,   pct: 46, key: 'srv.pasteClothes' },
            { sec: 9,   pct: 58, key: 'srv.typePrompt' },
            { sec: 11,  pct: 65, key: 'srv.sent' },
            { sec: 14,  pct: 70, key: 'srv.generating' },
        ];

        statusPollInterval = setInterval(() => {
            const elapsed = Math.round((Date.now() - startTime) / 1000);

            // Find the highest matching step
            let current = steps[0];
            for (const s of steps) {
                if (elapsed >= s.sec) current = s;
                else break;
            }

            if (loadingDesc) {
                loadingDesc.textContent = elapsed >= 14
                    ? t('srv.generating', { sec: elapsed })   // live counter while generating
                    : t(current.key);
            }
            if (progressBar) {
                // Slowly inch toward 95% max while waiting (never reach 100 until done)
                const pct = elapsed >= 14
                    ? Math.min(95, current.pct + Math.round((elapsed - 14) * 0.3))
                    : current.pct;
                progressBar.style.width = `${pct}%`;
            }
        }, 1000);
    }

    function stopStatusPolling() {
        if (statusPollInterval) {
            clearInterval(statusPollInterval);
            statusPollInterval = null;
        }
    }


    // ==========================================================================
    // 9. API Blobs & Mask Generators
    // ==========================================================================

    /**
     * DALL-E 2 Inpainting requires square PNGs with alpha channel indicating the mask.
     */
    function generateOpenAiBlobs() {
        return new Promise((resolve, reject) => {
            try {
                const size = 1024;
                
                // 1. Square Dog Canvas
                const dogCanvas = document.createElement('canvas');
                dogCanvas.width = size;
                dogCanvas.height = size;
                const dCtx = dogCanvas.getContext('2d');
                
                // Calculate dimensions to center the dog image inside a 1024x1024 square
                const dogAspect = dogImage.width / dogImage.height;
                let dw, dh, dx, dy;
                if (dogAspect > 1) {
                    dw = size;
                    dh = size / dogAspect;
                    dx = 0;
                    dy = (size - dh) / 2;
                } else {
                    dw = size * dogAspect;
                    dh = size;
                    dx = (size - dw) / 2;
                    dy = 0;
                }
                
                // Draw dog
                dCtx.drawImage(dogImage, dx, dy, dw, dh);
                
                // 2. Square Mask Canvas
                const maskCanvas = document.createElement('canvas');
                maskCanvas.width = size;
                maskCanvas.height = size;
                const mCtx = maskCanvas.getContext('2d');
                
                // Draw dog first
                mCtx.drawImage(dogImage, dx, dy, dw, dh);
                
                // Set global composite to transparent-out where clothes are
                const scaleFactorX = dw / canvas.width;
                const scaleFactorY = dh / canvas.height;
                
                mCtx.save();
                mCtx.globalCompositeOperation = 'destination-out';
                
                const mappedX = dx + (overlayState.x * scaleFactorX);
                const mappedY = dy + (overlayState.y * scaleFactorY);
                
                mCtx.translate(mappedX, mappedY);
                mCtx.rotate(overlayState.rotate * Math.PI / 180);
                
                const rawScale = overlayState.scale * scaleFactorX;
                const scaleX = overlayState.mirrored ? -rawScale : rawScale;
                mCtx.scale(scaleX, rawScale);
                
                const drawWidth = canvas.width * 0.4;
                const drawHeight = drawWidth * (clothesRawImage.height / clothesRawImage.width);
                
                // Clear overlay pixels in mask to indicate transparent (inpainting zone)
                mCtx.drawImage(
                    clothesTransparentImage, 
                    -drawWidth / 2, 
                    -drawHeight / 2, 
                    drawWidth, 
                    drawHeight
                );
                mCtx.restore();
                
                // Convert to Blobs
                dogCanvas.toBlob((dogBlob) => {
                    maskCanvas.toBlob((maskBlob) => {
                        resolve({ dogBlob, maskBlob });
                    }, 'image/png');
                }, 'image/png');
                
            } catch (err) {
                reject(err);
            }
        });
    }

    /**
     * Stability AI Inpainting requires original dimensions with a black/white mask.
     */
    function generateStabilityBlobs() {
        return new Promise((resolve, reject) => {
            try {
                // 1. Dog Canvas
                const dogCanvas = document.createElement('canvas');
                dogCanvas.width = dogImage.width;
                dogCanvas.height = dogImage.height;
                const dCtx = dogCanvas.getContext('2d');
                dCtx.drawImage(dogImage, 0, 0);
                
                // 2. Mask Canvas (White where clothes are, Black where dog is)
                const maskCanvas = document.createElement('canvas');
                maskCanvas.width = dogImage.width;
                maskCanvas.height = dogImage.height;
                const mCtx = maskCanvas.getContext('2d');
                
                // Fill background with solid Black (#000000)
                mCtx.fillStyle = '#000000';
                mCtx.fillRect(0, 0, maskCanvas.width, maskCanvas.height);
                
                // Draw clothes shape as solid White (#FFFFFF)
                const scaleFactorX = dogImage.width / canvas.width;
                const scaleFactorY = dogImage.height / canvas.height;
                
                mCtx.save();
                mCtx.translate(overlayState.x * scaleFactorX, overlayState.y * scaleFactorY);
                mCtx.rotate(overlayState.rotate * Math.PI / 180);
                
                const rawScale = overlayState.scale * scaleFactorX;
                const scaleX = overlayState.mirrored ? -rawScale : rawScale;
                mCtx.scale(scaleX, rawScale);
                
                const drawWidth = canvas.width * 0.4;
                const drawHeight = drawWidth * (clothesRawImage.height / clothesRawImage.width);
                
                // Draw white silhouette bounding box
                mCtx.fillStyle = '#FFFFFF';
                mCtx.fillRect(-drawWidth / 2, -drawHeight / 2, drawWidth, drawHeight);
                mCtx.restore();
                
                // Convert to Blobs
                dogCanvas.toBlob((dogBlob) => {
                    maskCanvas.toBlob((maskBlob) => {
                        resolve({ dogBlob, maskBlob });
                    }, 'image/png');
                }, 'image/png');
                
            } catch (err) {
                reject(err);
            }
        });
    }

    // ==========================================================================
    // 10. AI API Endpoints Callers
    // ==========================================================================

    async function callOpenAiImageEdit(apiKey, promptText) {
        const { dogBlob, maskBlob } = await generateOpenAiBlobs();
        
        const formData = new FormData();
        formData.append('image', dogBlob, 'image.png');
        formData.append('mask', maskBlob, 'mask.png');
        formData.append('prompt', promptText);
        formData.append('n', 1);
        formData.append('size', '1024x1024');
        formData.append('response_format', 'b64_json');
        
        const response = await fetch('https://api.openai.com/v1/images/edits', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${apiKey}`
            },
            body: formData
        });
        
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.error?.message || `HTTP 錯誤碼 ${response.status}`);
        }
        
        const resData = await response.json();
        const b64Data = resData.data[0].b64_json;
        return `data:image/png;base64,${b64Data}`;
    }

    async function callStabilityInpaint(apiKey, promptText) {
        const { dogBlob, maskBlob } = await generateStabilityBlobs();
        
        const formData = new FormData();
        formData.append('init_image', dogBlob, 'image.png');
        formData.append('mask_source', 'MASK_IMAGE_WHITE');
        formData.append('mask_image', maskBlob, 'mask.png');
        formData.append('text_prompts[0][text]', promptText);
        formData.append('text_prompts[0][weight]', '1.0');
        
        const response = await fetch('https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image/masking', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${apiKey}`,
                'Accept': 'application/json'
            },
            body: formData
        });
        
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.message || `HTTP 錯誤碼 ${response.status}`);
        }
        
        const resData = await response.json();
        const b64Data = resData.artifacts[0].base64;
        return `data:image/png;base64,${b64Data}`;
    }

    async function callGoogleImagen3(apiKey, promptText) {
        // Calculate aspect ratio dynamically based on current dog image
        let aspect = "1:1";
        if (dogImage) {
            const dogAspect = dogImage.width / dogImage.height;
            if (dogAspect > 1.5) aspect = "16:9";
            else if (dogAspect > 1.2) aspect = "4:3";
            else if (dogAspect < 0.6) aspect = "9:16";
            else if (dogAspect < 0.8) aspect = "3:4";
        }

        const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:generateImages?key=${apiKey}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: promptText,
                numberOfImages: 1,
                outputMimeType: "image/jpeg",
                aspectRatio: aspect
            })
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(`【Google Imagen 3 | 畫布渲染失敗】: ${errData.error?.message || `HTTP 錯誤碼 ${response.status}`}`);
        }

        const resData = await response.json();
        const b64Data = resData.generatedImages[0].image.imageBytes;
        return `data:image/jpeg;base64,${b64Data}`;
    }

    async function callGoogleGeminiMultimodalPrompt(apiKey, dogDataUrl, clothesDataUrl) {
        const dogBase64 = getBase64FromDataUrl(dogDataUrl);
        const dogMime = getMimeTypeFromDataUrl(dogDataUrl);
        
        const clothesBase64 = getBase64FromDataUrl(clothesDataUrl);
        const clothesMime = getMimeTypeFromDataUrl(clothesDataUrl);
        
        const systemPrompt = "You are an expert AI fashion stylist. Look at the dog in the first image, and the dog raincoat in the second image. Write a highly detailed, professional, photo-realistic prompt for an image generator (like Imagen 3) to generate a photo of this exact dog wearing this exact raincoat in the exact same background. Describe the dog's breed, coat, posture, the raincoat's specific color, design details, fabric folds, and how it naturally fits the dog's body. Output ONLY the English prompt text itself, do not add any markdown, notes, conversational headers, or introduction.";
        
        const models = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.1-flash", "gemini-2.5-pro"];
        let lastError = null;

        for (const model of models) {
            try {
                console.log(`Trying Google Gemini model: ${model}...`);
                const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        contents: [{
                            parts: [
                                {
                                    text: systemPrompt
                                },
                                {
                                    inlineData: {
                                        mimeType: dogMime,
                                        data: dogBase64
                                    }
                                },
                                {
                                    inlineData: {
                                        mimeType: clothesMime,
                                        data: clothesBase64
                                    }
                                }
                            ]
                        }]
                    })
                });

                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.error?.message || `HTTP ${response.status}`);
                }

                const resData = await response.json();
                if (!resData.candidates || !resData.candidates[0] || !resData.candidates[0].content || !resData.candidates[0].content.parts) {
                    throw new Error("Gemini 返回了空回應。");
                }
                
                const generatedPrompt = resData.candidates[0].content.parts[0].text.trim();
                return generatedPrompt;
            } catch (err) {
                console.warn(`Model ${model} failed:`, err);
                lastError = err;
            }
        }

        throw new Error(`【Google Gemini | 穿衣分析多重備援皆失敗】: 我們嘗試了所有的 Gemini 模型 (${models.join(", ")}), 但全部因流量過載或金鑰限制而失敗。最後一個錯誤為: ${lastError.message || lastError}`);
    }

    async function callGroqMultimodalPrompt(groqKey, dogDataUrl, clothesDataUrl) {
        const dogBase64 = getBase64FromDataUrl(dogDataUrl);
        const dogMime = getMimeTypeFromDataUrl(dogDataUrl);
        
        const clothesBase64 = getBase64FromDataUrl(clothesDataUrl);
        const clothesMime = getMimeTypeFromDataUrl(clothesDataUrl);
        
        const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${groqKey}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model: "llama-3.2-11b-vision-preview",
                messages: [
                    {
                        role: "user",
                        content: [
                            {
                                type: "text",
                                text: "You are an expert AI fashion stylist. Look at the dog in the first image, and the dog raincoat in the second image. Write a highly detailed, professional, photo-realistic prompt for an image generator (like Imagen 3) to generate a photo of this exact dog wearing this exact raincoat in the exact same background. Describe the dog's breed, coat, posture, the raincoat's specific color, design details, fabric folds, and how it naturally fits the dog's body. Output ONLY the English prompt text itself, do not add any markdown, notes, conversational headers, or introduction."
                            },
                            {
                                type: "image_url",
                                image_url: {
                                    url: `data:${dogMime};base64,${dogBase64}`
                                }
                            },
                            {
                                type: "image_url",
                                image_url: {
                                    url: `data:${clothesMime};base64,${clothesBase64}`
                                }
                            }
                        ]
                    }
                ],
                max_tokens: 150
            })
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(`【Groq LLaMA 3.2 Vision | 穿衣分析失敗】: ${errData.error?.message || `HTTP 錯誤碼 ${response.status}`}`);
        }

        const resData = await response.json();
        const generatedPrompt = resData.choices[0].message.content.trim();
        return generatedPrompt;
    }

    async function callOllamaMultimodalPrompt(dogDataUrl, clothesDataUrl) {
        const dogBase64 = getBase64FromDataUrl(dogDataUrl);
        const dogMime = getMimeTypeFromDataUrl(dogDataUrl);
        
        const clothesBase64 = getBase64FromDataUrl(clothesDataUrl);
        const clothesMime = getMimeTypeFromDataUrl(clothesDataUrl);
        
        const response = await fetch('http://localhost:11434/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model: "llama3.2-vision",
                messages: [
                    {
                        role: "user",
                        content: [
                            {
                                type: "text",
                                text: "You are an expert AI fashion stylist. Look at the dog in the first image, and the dog raincoat in the second image. Write a highly detailed, professional, photo-realistic prompt for an image generator (like Imagen 3) to generate a photo of this exact dog wearing this exact raincoat in the exact same background. Describe the dog's breed, coat, posture, the raincoat's specific color, design details, fabric folds, and how it naturally fits the dog's body. Output ONLY the English prompt text itself, do not add any markdown, notes, conversational headers, or introduction."
                            },
                            {
                                type: "image_url",
                                image_url: {
                                    url: `data:${dogMime};base64,${dogBase64}`
                                }
                            },
                            {
                                type: "image_url",
                                image_url: {
                                    url: `data:${clothesMime};base64,${clothesBase64}`
                                }
                            }
                        ]
                    }
                ],
                max_tokens: 150
            })
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(`【Ollama LLaMA 3.2 Vision | 本機分析失敗】: ${errData.error?.message || `HTTP 錯誤碼 ${response.status}。請確認 Ollama 已啟動，且您已下載並跑起了 llama3.2-vision 模型。`}`);
        }

        const resData = await response.json();
        const generatedPrompt = resData.choices[0].message.content.trim();
        return generatedPrompt;
    }

    async function callPlaywrightMultimodalPrompt(dogDataUrl, clothesDataUrl) {
        try {
            // 5-minute timeout — Gemini can take a while to respond
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000);

            const response = await fetch('/api/stylist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'x-api-key': getFitstudioApiKey(), ...API_HEADERS },
                body: JSON.stringify({ dogImage: dogDataUrl, clothesImage: clothesDataUrl }),
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (!response.ok) {
                if (response.status === 429 || response.status === 503) {
                    const d = await response.json().catch(() => ({}));
                    throw new Error(t(d.errorKey || 'err.busy'));
                }
                if (response.status === 401) {
                    // Drop any stale saved key so the built-in one is used next time
                    localStorage.removeItem('fitstudio_api_key');
                    throw new Error(t('err.unauthorized'));
                }
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || `HTTP 錯誤碼 ${response.status}`);
            }

            const resData = await response.json();
            // Server returns { image: 'data:...' } for Gemini-generated image
            // or { prompt: '...' } as text fallback for Imagen 3
            return resData.image || resData.prompt;
        } catch (err) {
            if (err.name === 'AbortError') {
                throw new Error(t('err.timeout'));
            }
            throw new Error(`【AI 生成失敗】: ${err.message || err}\n\n💡 請確保您已啟動 start_server.bat 並在瀏覽器中登入 Google 帳戶！`);
        }
    }

    async function callOpenRouterMultimodalPrompt(openrouterKey, dogDataUrl, clothesDataUrl) {
        const dogBase64 = getBase64FromDataUrl(dogDataUrl);
        const dogMime = getMimeTypeFromDataUrl(dogDataUrl);
        
        const clothesBase64 = getBase64FromDataUrl(clothesDataUrl);
        const clothesMime = getMimeTypeFromDataUrl(clothesDataUrl);
        
        const systemPrompt = "You are an expert AI fashion stylist. Look at the dog in the first image, and the dog raincoat in the second image. Write a highly detailed, professional, photo-realistic prompt for an image generator (like Imagen 3) to generate a photo of this exact dog wearing this exact raincoat in the exact same background. Describe the dog's breed, coat, posture, the raincoat's specific color, design details, fabric folds, and how it naturally fits the dog's body. Output ONLY the English prompt text itself, do not add any markdown, notes, conversational headers, or introduction.";
        
        const models = [
            "meta-llama/llama-3.2-11b-vision-instruct",        // Production ID (extremely stable, costs almost $0, utilizes OpenRouter registration free credit!)
            "meta-llama/llama-3.2-11b-vision-instruct:free",   // Free Llama 3.2 Vision
            "qwen/qwen-2-vl-7b-instruct:free"                  // Free Qwen 2 VL Vision
        ];
        
        let lastError = null;

        for (const model of models) {
            try {
                console.log(`Trying OpenRouter model: ${model}...`);
                const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${openrouterKey}`,
                        'Content-Type': 'application/json',
                        'HTTP-Referer': 'https://github.com/apetto-fitstudio',
                        'X-Title': 'apetto FitStudio'
                    },
                    body: JSON.stringify({
                        model: model,
                        messages: [
                            {
                                role: "user",
                                content: [
                                    {
                                        type: "text",
                                        text: systemPrompt
                                    },
                                    {
                                        type: "image_url",
                                        image_url: {
                                            url: `data:${dogMime};base64,${dogBase64}`
                                        }
                                    },
                                    {
                                        type: "image_url",
                                        image_url: {
                                            url: `data:${clothesMime};base64,${clothesBase64}`
                                        }
                                    }
                                ]
                            }
                        ],
                        max_tokens: 150
                    })
                });

                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.error?.message || `HTTP ${response.status}`);
                }

                const resData = await response.json();
                if (!resData.choices || !resData.choices[0] || !resData.choices[0].message) {
                    throw new Error("OpenRouter 返回了空回應。");
                }
                
                const generatedPrompt = resData.choices[0].message.content.trim();
                return generatedPrompt;
            } catch (err) {
                console.warn('OpenRouter model failed:', err);
                lastError = err;
            }
        }
        throw new Error('All OpenRouter models failed. Last error: ' + (lastError ? lastError.message : 'unknown'));
    }

    // ── Step tracker helpers ──────────────────────────────────────────
    const STEPS     = ['step-compress', 'step-launch', 'step-paste', 'step-gemini', 'step-done'];

    const STEP_NUMS = ['1','2','3','4','5'];
    let   stepTimer = null;

    function updateProgressBar() {
        const fill = document.getElementById('step-progress-fill');
        if (!fill) return;
        const doneCount = STEPS.filter(id => {
            const el = document.getElementById(id);
            return el && el.classList.contains('done');
        }).length;
        const activeCount = STEPS.filter(id => {
            const el = document.getElementById(id);
            return el && el.classList.contains('active');
        }).length;
        const pct = Math.round((doneCount + activeCount * 0.5) / STEPS.length * 100);
        fill.style.width = pct + '%';
    }

    function setStep(id, state, subOverride) {
        const el = document.getElementById(id);
        if (!el) return;
        el.className = 'step-item ' + state;
        const num = el.querySelector('.step-num');
        if (num) num.textContent = state === 'done' ? '✓' : STEP_NUMS[STEPS.indexOf(id)];
        if (subOverride !== undefined) {
            const sub = el.querySelector('.step-sub');
            if (sub) sub.textContent = subOverride;
        }
        updateProgressBar();
    }

    // Start a live seconds counter on the active step's sub-text
    function startStepTimer(id) {
        clearInterval(stepTimer);
        let secs = 0;
        const el  = id && document.getElementById(id);
        const sub = el && el.querySelector('.step-sub');
        const origText = sub ? sub.textContent : '';
        stepTimer = setInterval(() => {
            secs++;
            if (sub) sub.textContent = origText + t('timer.suffix', { sec: secs });
        }, 1000);
    }
    function stopStepTimer() { clearInterval(stepTimer); stepTimer = null; }

    // The AI's recommendation for this dog in this outfit. Empty string hides it.
    function showStylistNote(text, pending) {
        const box = document.getElementById('stylist-note');
        const body = document.getElementById('stylist-note-text');
        if (!box || !body) return;
        const clean = (text || '').trim();
        box.classList.toggle('is-pending', !!pending);
        body.textContent = pending ? t('note.writing') : clean;
        box.hidden = !(clean || pending);
    }

    // The image is returned first and the copy follows a few seconds later, so
    // collect it separately instead of holding the picture back for it.
    let captionPollTimer = null;
    function pollCaption(id) {
        clearTimeout(captionPollTimer);
        if (!id) return;
        const deadline = Date.now() + 120000;
        const tick = async () => {
            if (Date.now() > deadline) { showStylistNote(''); return; }
            try {
                const r = await fetch(API_BASE + '/api/caption/' + encodeURIComponent(id), {
                    headers: { 'x-api-key': getFitstudioApiKey(), ...API_HEADERS }
                });
                if (r.ok) {
                    const d = await r.json();
                    if (d.status === 'ready') { showStylistNote(d.caption); return; }
                    if (d.status === 'none')  { showStylistNote(''); return; }
                }
            } catch (_) { /* keep waiting */ }
            captionPollTimer = setTimeout(tick, 2000);
        };
        showStylistNote('', true);      // show the card in its "writing" state
        captionPollTimer = setTimeout(tick, 1500);
    }

    // Put the user's own dog photo inside the loading portal so the wait feels
    // personal — falls back to the emoji if we somehow have no image.
    function showLoadingDogPhoto(src) {
        const emoji = document.getElementById('portal-core-emoji');
        const wrap  = document.getElementById('portal-dog');
        const img   = document.getElementById('portal-dog-img');
        if (!wrap || !img) return;
        if (src) {
            img.src = src;
            wrap.style.display = 'block';
            if (emoji) emoji.style.display = 'none';
        } else {
            wrap.style.display = 'none';
            if (emoji) emoji.style.display = 'block';
        }
    }

    function resetSteps() {
        stopStepTimer();
        const origSubs = [t('step1.sub'), t('step2.sub'), t('step3.sub'), t('step4.sub'), t('step5.sub')];
        STEPS.forEach((id, i) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.className = 'step-item pending';
            const num = el.querySelector('.step-num');
            if (num) num.textContent = String(i + 1);
            const sub = el.querySelector('.step-sub');
            if (sub) sub.textContent = origSubs[i];
        });
    }

    btnRealAi.addEventListener('click', async () => {
        if (!dogImage || !clothesRawImage) {
            alert(t('err.pickFirst'));
            return;
        }

        resetSteps();
        showStylistNote('');            // clear the previous run's note
        showLoadingDogPhoto(dogImage ? dogImage.src : '');
        // Identifies this run so its progress isn't mixed up with other visitors'
        const jobId = (crypto.randomUUID && crypto.randomUUID()) ||
                      (Date.now() + '-' + Math.random().toString(36).slice(2));
        aiLoadingModal.classList.add('active');

        let progressInterval = null;

        try {
            // Step 1: Compress
            setStep('step-compress', 'active');
            startStepTimer('step-compress');
            const compressedDog     = await compressImage(dogImage.src,        800, 0.82);
            const compressedClothes = await compressImage(clothesRawImage.src, 600, 0.82);
            stopStepTimer();
            setStep('step-compress', 'done', t('done.compress'));

            // Step 2: Connect local Playwright server
            setStep('step-launch', 'active');
            startStepTimer('step-launch');

            // Progress is tracked per job: several visitors can be generating at
            // once, and a shared status would show each of them the wrong one.
            progressInterval = setInterval(async () => {
                try {
                    const sRes = await fetch(API_BASE + '/api/status/' + jobId, { headers: API_HEADERS });
                    if (sRes.ok) {
                        const sData = await sRes.json();
                        // Server sends a key + vars so progress follows the UI language;
                        // its raw message is only the fallback.
                        const srvText = sData.key ? t(sData.key, sData.vars || {}) : sData.message;
                        if (sData.busy) {
                            if (sData.step === 2) {
                                setStep('step-launch', 'active', srvText);
                            } else if (sData.step === 3 || sData.step === 4 || sData.step === 5) {
                                setStep('step-launch', 'done', t('done.browser'));
                                setStep('step-paste', 'active', srvText);
                            } else if (sData.step === 6) {
                                setStep('step-paste', 'done', t('done.sent'));
                                setStep('step-gemini', 'active', srvText);
                            }
                        }
                    }
                } catch (_) {}
            }, 1000);

            // Step 3: Advance visually after 3 seconds if status isn't updated yet
            setTimeout(() => {
                const launchEl = document.getElementById('step-launch');
                if (launchEl && launchEl.classList.contains('active')) {
                    stopStepTimer();
                    setStep('step-launch', 'done', t('done.browser'));
                    setStep('step-paste', 'active');
                    startStepTimer('step-paste');
                }
            }, 4000);

            // Advance to AI generating step after ~7s
            setTimeout(() => {
                const pasteEl = document.getElementById('step-paste');
                if (pasteEl && pasteEl.classList.contains('active')) {
                    stopStepTimer();
                    setStep('step-paste', 'done', t('done.sent'));
                    setStep('step-gemini', 'active');
                    startStepTimer('step-gemini');
                }
            }, 7000);

            // Send directly to local Playwright server
            const res = await fetch(LOCAL_SERVER_API, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'x-api-key': getFitstudioApiKey(), ...API_HEADERS },
                body: JSON.stringify({
                    dogImage: compressedDog,
                    clothesImage: compressedClothes,
                    lang: getLang(),     // so the recommendation comes back in the UI language
                    jobId
                })
            });

            clearInterval(progressInterval);
            stopStepTimer();

            if (!res.ok) {
                if (res.status === 429 || res.status === 503) {
                    const d = await res.json().catch(() => ({}));
                    throw new Error(t(d.errorKey || 'err.busy'));
                }
                if (res.status === 401) {
                    // Drop any stale saved key so the built-in one is used next time
                    localStorage.removeItem('fitstudio_api_key');
                    throw new Error(t('err.unauthorized'));
                }
                const errData = await res.json().catch(() => ({}));
                if (errData.errorKey) throw new Error(t(errData.errorKey));
                throw new Error(errData.error || `HTTP ${res.status}`);
            }

            const data = await res.json();
            const resultImageSrc = data.image;
            pollCaption(data.captionId);   // copy arrives after the picture

            setStep('step-launch', 'done', t('done.browser'));
            setStep('step-paste', 'done', t('done.sent'));
            setStep('step-gemini', 'done', t('done.generated'));

            if (resultImageSrc && (resultImageSrc.startsWith('data:image') || resultImageSrc.startsWith('http'))) {
                // Step 5: Display
                setStep('step-done', 'active');
                const newDog = new Image();
                newDog.onload = function() {
                    dogImage = newDog;
                    clothesTransparentImage = null;
                    document.querySelectorAll('.clothes-card').forEach(function(c) { c.classList.remove('active'); });
                    if (btnRealAi) btnRealAi.disabled = true;
                    revealMobilePanel();
                    resizeCanvasToFit();
                    draw();
                    setStep('step-done', 'done');
                    setTimeout(function() {
                        var canvas = document.getElementById('fitting-canvas');
                        if (canvas) canvas.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }, 100);
                };
                newDog.src = resultImageSrc;
            } else {
                throw new Error(t('err.noImage'));
            }

        } catch (err) {
            if (progressInterval) clearInterval(progressInterval);
            stopStepTimer();
            console.error(err);
            alert(t('err.generic') + (err.message || err));
        } finally {
            setTimeout(() => {
                aiLoadingModal.classList.remove('active');
            }, 800);
        }
    });

});


