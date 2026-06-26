// Veloce Speedtest Engine
document.addEventListener('DOMContentLoaded', () => {
    // ----------------------------------------------------
    // STATE VARIABLES
    // ----------------------------------------------------
    let isRunning = false;
    let currentPhase = 'idle'; // 'idle', 'ping', 'download', 'upload', 'complete'
    let abortController = null;
    let activeXHR = null;
    
    let pingSamples = [];
    let jitterSum = 0;
    let avgPing = 0;
    let jitter = 0;
    
    let currentDownloadSpeed = 0;
    let finalDownloadSpeed = 0;
    let downloadSpeedSamples = [];
    
    let currentUploadSpeed = 0;
    let finalUploadSpeed = 0;
    let uploadSpeedSamples = [];
    
    let speedChart = null;
    let chartTimeCounter = 0;
    let chartInterval = null;
    
    // Config constants
    const PING_COUNT = 10;
    const TEST_DURATION_MS = 8000; // 8 seconds per phase
    const CLOUDFLARE_DOWN_URL = 'https://speed.cloudflare.com/__down';
    const CLOUDFLARE_UP_URL = 'https://speed.cloudflare.com/__up';
    
    // GAUGE CALCULATION CONSTANTS
    const GAUGE_CIRCUMFERENCE = 534; // 2 * Math.PI * r (r=85 => 534.07)
    
    // ----------------------------------------------------
    // DOM ELEMENTS
    // ----------------------------------------------------
    const btnStart = document.getElementById('btn-start');
    const statusBadge = document.getElementById('status-badge');
    const statusLabel = statusBadge.querySelector('.status-label');
    
    const gaugeDownload = document.getElementById('gauge-download');
    const gaugeUpload = document.getElementById('gauge-upload');
    const gaugePhase = document.getElementById('gauge-phase');
    const gaugeValue = document.getElementById('gauge-value');
    const gaugeUnit = document.getElementById('gauge-unit');
    const radarPulse = document.getElementById('radar-pulse');
    
    const cardDownload = document.getElementById('card-download');
    const cardUpload = document.getElementById('card-upload');
    const cardPing = document.getElementById('card-ping');
    const cardJitter = document.getElementById('card-jitter');
    
    const valDownload = document.getElementById('val-download');
    const valUpload = document.getElementById('val-upload');
    const valPing = document.getElementById('val-ping');
    const valJitter = document.getElementById('val-jitter');
    
    const progressDownload = document.getElementById('progress-download');
    const progressUpload = document.getElementById('progress-upload');
    
    const infoIp = document.getElementById('info-ip');
    const infoIsp = document.getElementById('info-isp');
    const infoLocation = document.getElementById('info-location');
    const infoServer = document.getElementById('info-server');
    
    const cardDiagnosis = document.getElementById('card-diagnosis');
    const diagnosisText = document.getElementById('diagnosis-text');
    const btnShare = document.getElementById('btn-share');
    
    // Initialize Lucide Icons
    lucide.createIcons();
    
    // Initialize Chart
    initChart();
    
    // Load Network Details on Start
    fetchNetworkDetails();
    
    // ----------------------------------------------------
    // EVENT LISTENERS
    // ----------------------------------------------------
    btnStart.addEventListener('click', () => {
        if (isRunning) {
            cancelTest();
        } else {
            startTest();
        }
    });
    
    btnShare.addEventListener('click', () => {
        copyResultsToClipboard();
    });
    
    // ----------------------------------------------------
    // CHART CONFIGURATION
    // ----------------------------------------------------
    function initChart() {
        const ctx = document.getElementById('speed-chart').getContext('2d');
        
        // Custom gradient for datasets
        const downloadGrad = ctx.createLinearGradient(0, 0, 0, 200);
        downloadGrad.addColorStop(0, 'rgba(0, 242, 254, 0.4)');
        downloadGrad.addColorStop(1, 'rgba(0, 242, 254, 0.0)');
        
        const uploadGrad = ctx.createLinearGradient(0, 0, 0, 200);
        uploadGrad.addColorStop(0, 'rgba(243, 85, 136, 0.4)');
        uploadGrad.addColorStop(1, 'rgba(243, 85, 136, 0.0)');

        speedChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Descarga (Mbps)',
                        data: [],
                        borderColor: '#00f2fe',
                        borderWidth: 3,
                        backgroundColor: downloadGrad,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    },
                    {
                        label: 'Subida (Mbps)',
                        data: [],
                        borderColor: '#f35588',
                        borderWidth: 3,
                        backgroundColor: uploadGrad,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false // We will use cards for indicator
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(10, 12, 30, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#9ea2c0',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.03)'
                        },
                        ticks: {
                            color: '#626789',
                            font: { size: 10, family: 'Plus Jakarta Sans' }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.03)'
                        },
                        ticks: {
                            color: '#626789',
                            font: { size: 10, family: 'Plus Jakarta Sans' },
                            callback: function(value) {
                                return value + ' Mbps';
                            }
                        }
                    }
                }
            }
        });
    }
    
    function resetChart() {
        speedChart.data.labels = [];
        speedChart.data.datasets[0].data = [];
        speedChart.data.datasets[1].data = [];
        speedChart.update();
        chartTimeCounter = 0;
    }
    
    function addChartData(downloadVal, uploadVal) {
        chartTimeCounter += 0.5;
        speedChart.data.labels.push(chartTimeCounter.toFixed(1) + 's');
        speedChart.data.datasets[0].data.push(downloadVal);
        speedChart.data.datasets[1].data.push(uploadVal);
        
        // Keep chart size in view
        if (speedChart.data.labels.length > 40) {
            speedChart.data.labels.shift();
            speedChart.data.datasets[0].data.shift();
            speedChart.data.datasets[1].data.shift();
        }
        speedChart.update('none'); // Update without animation for performance
    }
    
    // ----------------------------------------------------
    // GEOLOCATION & NETWORK METADATA
    // ----------------------------------------------------
    async function fetchNetworkDetails() {
        // Method 1: Fetch ipapi.co (detailed geo + ISP name)
        try {
            const response = await fetch('https://ipapi.co/json/');
            if (response.ok) {
                const data = await response.json();
                infoIp.textContent = data.ip || 'No detectada';
                infoIsp.textContent = data.org || 'Proveedor desconocido';
                infoLocation.textContent = `${data.city || ''}, ${data.country_name || ''}`;
                infoServer.textContent = 'Buscando servidor...';
                return;
            }
        } catch (e) {
            console.warn('Fallo al obtener datos de ipapi.co, reintentando con Cloudflare headers.', e);
        }
        
        // Method 2 (Fallback): Extract details from Cloudflare headers
        try {
            const response = await fetch(CLOUDFLARE_DOWN_URL, { method: 'HEAD', cache: 'no-store' });
            infoIp.textContent = response.headers.get('cf-meta-ip') || 'No detectada';
            const asn = response.headers.get('cf-meta-asn') || response.headers.get('asn') || '';
            infoIsp.textContent = asn ? `AS${asn}` : 'Proveedor de Internet';
            
            const city = response.headers.get('cf-meta-city') || response.headers.get('city') || '';
            const country = response.headers.get('cf-meta-country') || response.headers.get('country') || '';
            infoLocation.textContent = (city && country) ? `${city}, ${country}` : 'Desconocida';
            
            const colo = response.headers.get('cf-meta-colo') || response.headers.get('colo') || 'BOG';
            infoServer.textContent = `Cloudflare (${colo})`;
        } catch (e) {
            console.error('Error obteniendo metadatos de conexión:', e);
            infoIp.textContent = 'Error';
            infoIsp.textContent = 'Sin conexión';
            infoLocation.textContent = 'Sin conexión';
            infoServer.textContent = 'Error';
        }
    }
    
    // Update server location details specifically from Cloudflare speedtest headers
    async function updateServerDetails() {
        try {
            const response = await fetch(CLOUDFLARE_DOWN_URL, { method: 'HEAD', cache: 'no-store' });
            const colo = response.headers.get('cf-meta-colo') || response.headers.get('colo') || 'BOG';
            const city = response.headers.get('cf-meta-city') || response.headers.get('city') || '';
            infoServer.textContent = `Cloudflare (${colo})${city ? ' - ' + city : ''}`;
        } catch (e) {
            console.warn('No se pudo actualizar los detalles específicos del servidor Cloudflare:', e);
        }
    }
    
    // ----------------------------------------------------
    // GAUGE & UI UTILITIES
    // ----------------------------------------------------
    function setGaugeOffset(element, percentage) {
        // Constrain percentage between 0 and 100
        const percent = Math.max(0, Math.min(100, percentage));
        // Calculate offset (534 represents full empty, 150 represents full gauge range in this coordinate scale)
        // 534 is the track length. Let's make it cover up to 75% of the circle (270 degrees)
        // Offset = Circumference - (Percent / 100) * (Circumference * 0.75)
        const activeRange = GAUGE_CIRCUMFERENCE * 0.75;
        const offset = GAUGE_CIRCUMFERENCE - (percent / 100) * activeRange;
        element.style.strokeDashoffset = offset;
    }
    
    function resetGauges() {
        setGaugeOffset(gaugeDownload, 0);
        setGaugeOffset(gaugeUpload, 0);
        gaugeValue.textContent = '0.00';
        gaugeUnit.textContent = 'Mbps';
        gaugePhase.textContent = 'Listo';
    }
    
    function setGaugeSpeed(speedMbps, phase) {
        gaugeValue.textContent = speedMbps.toFixed(2);
        
        // Logarithmic scale for gauges: 0 to 500+ Mbps
        // Converts 0-1000 Mbps into a smooth 0-100% dial value
        // Formula: log(speed + 1) / log(1001) * 100
        const normalizedPercentage = (Math.log10(speedMbps + 1) / Math.log10(1001)) * 100;
        
        if (phase === 'download') {
            setGaugeOffset(gaugeDownload, normalizedPercentage);
            setGaugeOffset(gaugeUpload, 0);
            gaugeUnit.textContent = 'Mbps';
            gaugePhase.textContent = 'DESCARGANDO';
            gaugePhase.style.color = 'var(--color-download)';
        } else if (phase === 'upload') {
            setGaugeOffset(gaugeDownload, 0);
            setGaugeOffset(gaugeUpload, normalizedPercentage);
            gaugeUnit.textContent = 'Mbps';
            gaugePhase.textContent = 'SUBIENDO';
            gaugePhase.style.color = 'var(--color-upload)';
        }
    }
    
    function setUIPingPhase(activeSample, totalSamples) {
        gaugePhase.textContent = `PING (${activeSample}/${totalSamples})`;
        gaugePhase.style.color = 'var(--color-ping)';
        gaugeValue.textContent = '---';
        gaugeUnit.textContent = 'ms';
    }
    
    function updateBadgeState(state) {
        statusBadge.className = 'status-indicator-badge';
        if (state === 'idle') {
            statusBadge.classList.add('disconnected');
            statusLabel.textContent = 'Listo';
        } else if (state === 'ping') {
            statusBadge.classList.add('active');
            statusLabel.textContent = 'Ping';
        } else if (state === 'download') {
            statusBadge.classList.add('active');
            statusLabel.textContent = 'Descarga';
        } else if (state === 'upload') {
            statusBadge.classList.add('active-upload');
            statusLabel.textContent = 'Subida';
        } else if (state === 'complete') {
            statusBadge.classList.add('disconnected');
            statusLabel.textContent = 'Completado';
        }
    }
    
    // ----------------------------------------------------
    // SPEEDTEST EXECUTION FLOW
    // ----------------------------------------------------
    async function startTest() {
        if (isRunning) return;
        isRunning = true;
        
        // Reset UI metrics
        valDownload.textContent = '0.00';
        valUpload.textContent = '0.00';
        valPing.textContent = '-';
        valJitter.textContent = '-';
        progressDownload.style.width = '0%';
        progressUpload.style.width = '0%';
        
        // Adjust button
        btnStart.className = 'btn btn-danger btn-lg';
        btnStart.innerHTML = `<i data-lucide="square" class="btn-icon"></i><span>CANCELAR TEST</span>`;
        lucide.createIcons();
        
        cardDiagnosis.classList.add('hidden');
        cardDownload.classList.remove('testing');
        cardUpload.classList.remove('testing');
        cardPing.classList.remove('testing');
        cardJitter.classList.remove('testing');
        
        resetGauges();
        resetChart();
        
        // Update servers and network info again
        await updateServerDetails();
        
        try {
            // PHASE 1: PING & JITTER
            currentPhase = 'ping';
            updateBadgeState('ping');
            cardPing.classList.add('testing');
            cardJitter.classList.add('testing');
            radarPulse.classList.add('pinging');
            
            await runPingPhase();
            
            radarPulse.classList.remove('pinging');
            cardPing.classList.remove('testing');
            cardJitter.classList.remove('testing');
            
            // PHASE 2: DOWNLOAD
            currentPhase = 'download';
            updateBadgeState('download');
            cardDownload.classList.add('testing');
            
            // Setup real-time chart feed
            startChartFeed();
            
            await runDownloadPhase();
            
            cardDownload.classList.remove('testing');
            
            // PHASE 3: UPLOAD
            currentPhase = 'upload';
            updateBadgeState('upload');
            cardUpload.classList.add('testing');
            
            await runUploadPhase();
            
            cardUpload.classList.remove('testing');
            
            // COMPLETE TEST
            currentPhase = 'complete';
            updateBadgeState('complete');
            stopChartFeed();
            
            finishTest();
            
        } catch (error) {
            console.error('Test interrumpido o fallido:', error);
            if (isRunning) {
                // If we didn't cancel manually but it failed
                alert('La prueba falló debido a un error de red. Por favor, verifica tu conexión.');
                cancelTest();
            }
        }
    }
    
    function cancelTest() {
        isRunning = false;
        currentPhase = 'idle';
        updateBadgeState('idle');
        stopChartFeed();
        
        // Abort fetch requests
        if (abortController) {
            abortController.abort();
            abortController = null;
        }
        
        // Abort XHR uploads
        if (activeXHR) {
            activeXHR.abort();
            activeXHR = null;
        }
        
        radarPulse.classList.remove('pinging');
        cardDownload.classList.remove('testing');
        cardUpload.classList.remove('testing');
        cardPing.classList.remove('testing');
        cardJitter.classList.remove('testing');
        
        // Restore button
        btnStart.className = 'btn btn-primary btn-lg';
        btnStart.innerHTML = `<i data-lucide="play" class="btn-icon"></i><span>INICIAR TEST</span>`;
        lucide.createIcons();
        
        resetGauges();
    }
    
    function finishTest() {
        isRunning = false;
        
        // Restore button
        btnStart.className = 'btn btn-primary btn-lg';
        btnStart.innerHTML = `<i data-lucide="play" class="btn-icon"></i><span>REPETIR TEST</span>`;
        lucide.createIcons();
        
        // Set gauge final complete states
        gaugePhase.textContent = 'COMPLETADO';
        gaugePhase.style.color = 'var(--text-secondary)';
        gaugeValue.textContent = finalDownloadSpeed.toFixed(2);
        gaugeUnit.textContent = 'Mbps';
        
        // Update progress bars
        progressDownload.style.width = '100%';
        progressUpload.style.width = '100%';
        
        // Show diagnosis
        displayDiagnosis();
    }
    
    // ----------------------------------------------------
    // PING & JITTER LOGIC
    // ----------------------------------------------------
    async function runPingPhase() {
        pingSamples = [];
        jitterSum = 0;
        
        for (let i = 0; i < PING_COUNT; i++) {
            if (!isRunning || currentPhase !== 'ping') return;
            
            setUIPingPhase(i + 1, PING_COUNT);
            
            const start = performance.now();
            try {
                // Fetch using cache buster to prevent browser cache
                await fetch(`${CLOUDFLARE_DOWN_URL}?t=${start}-${i}`, {
                    method: 'HEAD',
                    cache: 'no-store'
                });
                
                const duration = performance.now() - start;
                pingSamples.push(duration);
                
                // Calculate average ping on the go
                const sum = pingSamples.reduce((a, b) => a + b, 0);
                avgPing = sum / pingSamples.length;
                valPing.textContent = avgPing.toFixed(0);
                
                // Calculate jitter
                if (pingSamples.length > 1) {
                    const latestDiff = Math.abs(pingSamples[pingSamples.length - 1] - pingSamples[pingSamples.length - 2]);
                    jitterSum += latestDiff;
                    jitter = jitterSum / (pingSamples.length - 1);
                    valJitter.textContent = jitter.toFixed(0);
                }
                
            } catch (err) {
                console.warn('Ping sample failed:', err);
                // Continue test with other samples unless cancelled
            }
            
            // Small pause between pings
            await new Promise(resolve => setTimeout(resolve, 80));
        }
        
        if (pingSamples.length === 0) {
            throw new Error('All ping attempts failed.');
        }
    }
    
    // ----------------------------------------------------
    // DOWNLOAD SPEED LOGIC
    // ----------------------------------------------------
    async function runDownloadPhase() {
        downloadSpeedSamples = [];
        abortController = new AbortController();
        
        // Choose size based on ping. Faster connections get larger test files
        // If ping is low (< 50ms), load 25MB. Otherwise, load 10MB to avoid timing out or eating too much bandwidth.
        const testBytes = avgPing < 50 ? 30000000 : 12000000; // 30MB or 12MB
        const url = `${CLOUDFLARE_DOWN_URL}?bytes=${testBytes}&t=${Date.now()}`;
        
        const startTime = performance.now();
        let downloadFinished = false;
        
        // Timeout backup to abort after 8 seconds
        const timeoutId = setTimeout(() => {
            if (!downloadFinished && abortController) {
                abortController.abort();
            }
        }, TEST_DURATION_MS);
        
        try {
            const response = await fetch(url, {
                signal: abortController.signal,
                cache: 'no-store'
            });
            
            if (!response.ok) throw new Error('Response is not ok');
            
            const reader = response.body.getReader();
            let loadedBytes = 0;
            
            while (isRunning && currentPhase === 'download') {
                const { done, value } = await reader.read();
                
                if (done) {
                    downloadFinished = true;
                    break;
                }
                
                loadedBytes += value.byteLength;
                const timeDiff = (performance.now() - startTime) / 1000; // seconds
                
                if (timeDiff > 0.1) { // Throttle calculation frequency slightly
                    // bits / seconds / 1,048,576
                    const speedMbps = (loadedBytes * 8) / timeDiff / 1024 / 1024;
                    currentDownloadSpeed = speedMbps;
                    
                    // Update speedometer UI
                    setGaugeSpeed(currentDownloadSpeed, 'download');
                    valDownload.textContent = currentDownloadSpeed.toFixed(2);
                    
                    // Save samples
                    downloadSpeedSamples.push(currentDownloadSpeed);
                    
                    // Update card progress bar
                    const progressPercentage = Math.min(100, (timeDiff / (TEST_DURATION_MS / 1000)) * 100);
                    progressDownload.style.width = `${progressPercentage}%`;
                }
            }
            
            // Clean reader resources
            if (!done) {
                await reader.cancel();
            }
            
        } catch (err) {
            // If aborted due to timeout, it's a successful run completion!
            if (err.name === 'AbortError') {
                console.log('Fase de descarga completada por límite de tiempo.');
            } else {
                throw err;
            }
        } finally {
            clearTimeout(timeoutId);
            abortController = null;
        }
        
        // Calculate final download speed
        // To get a reliable speed, we take the average of the last 60% of samples (ignoring TCP slow start)
        if (downloadSpeedSamples.length > 0) {
            const sliceStart = Math.floor(downloadSpeedSamples.length * 0.4);
            const stableSamples = downloadSpeedSamples.slice(sliceStart);
            const sum = stableSamples.reduce((a, b) => a + b, 0);
            finalDownloadSpeed = sum / stableSamples.length;
        } else {
            finalDownloadSpeed = currentDownloadSpeed;
        }
        
        valDownload.textContent = finalDownloadSpeed.toFixed(2);
        progressDownload.style.width = '100%';
    }
    
    // ----------------------------------------------------
    // UPLOAD SPEED LOGIC
    // ----------------------------------------------------
    async function runUploadPhase() {
        uploadSpeedSamples = [];
        
        // Generate pre-allocated chunk of random bytes for uploading
        // 5 MB of data
        const chunkSize = 5 * 1024 * 1024;
        const randomBytes = new Uint8Array(chunkSize);
        // Fill array with dummy byte patterns
        for (let i = 0; i < chunkSize; i++) {
            randomBytes[i] = Math.floor(Math.random() * 256);
        }
        const uploadBlob = new Blob([randomBytes], { type: 'application/octet-stream' });
        
        let uploadStartTime = performance.now();
        let totalUploadedBytes = 0;
        let uploadFinished = false;
        
        // Run sequential uploads for 8 seconds
        while (isRunning && currentPhase === 'upload' && !uploadFinished) {
            const timeElapsed = performance.now() - uploadStartTime;
            if (timeElapsed >= TEST_DURATION_MS) {
                break;
            }
            
            await new Promise((resolve, reject) => {
                if (!isRunning || currentPhase !== 'upload') {
                    resolve();
                    return;
                }
                
                activeXHR = new XMLHttpRequest();
                const xhr = activeXHR;
                
                // Add unique timestamp to prevent caching
                xhr.open('POST', `${CLOUDFLARE_UP_URL}?t=${Date.now()}`, true);
                
                let chunkStart = performance.now();
                let lastLoaded = 0;
                
                xhr.upload.onprogress = function(event) {
                    if (!isRunning || currentPhase !== 'upload') {
                        xhr.abort();
                        resolve();
                        return;
                    }
                    
                    if (event.lengthComputable) {
                        const deltaLoaded = event.loaded - lastLoaded;
                        lastLoaded = event.loaded;
                        totalUploadedBytes += deltaLoaded;
                        
                        const totalDurationSeconds = (performance.now() - uploadStartTime) / 1000;
                        
                        if (totalDurationSeconds > 0.1) {
                            const speedMbps = (totalUploadedBytes * 8) / totalDurationSeconds / 1024 / 1024;
                            currentUploadSpeed = speedMbps;
                            
                            setGaugeSpeed(currentUploadSpeed, 'upload');
                            valUpload.textContent = currentUploadSpeed.toFixed(2);
                            uploadSpeedSamples.push(currentUploadSpeed);
                            
                            // Progress bar update
                            const progressPercentage = Math.min(100, (totalDurationSeconds / (TEST_DURATION_MS / 1000)) * 100);
                            progressUpload.style.width = `${progressPercentage}%`;
                        }
                    }
                };
                
                xhr.onload = function() {
                    activeXHR = null;
                    resolve();
                };
                
                xhr.onerror = function() {
                    activeXHR = null;
                    // Log upload error but keep running if time is left
                    resolve();
                };
                
                // Abort when total phase time exceeds limit
                const remainingTime = TEST_DURATION_MS - (performance.now() - uploadStartTime);
                const timer = setTimeout(() => {
                    xhr.abort();
                    uploadFinished = true;
                    resolve();
                }, remainingTime);
                
                xhr.onloadend = () => clearTimeout(timer);
                
                xhr.send(uploadBlob);
            });
        }
        
        activeXHR = null;
        
        // Calculate final upload speed (discarding first 30% of samples for slow start)
        if (uploadSpeedSamples.length > 0) {
            const sliceStart = Math.floor(uploadSpeedSamples.length * 0.3);
            const stableSamples = uploadSpeedSamples.slice(sliceStart);
            const sum = stableSamples.reduce((a, b) => a + b, 0);
            finalUploadSpeed = sum / stableSamples.length;
        } else {
            finalUploadSpeed = currentUploadSpeed;
        }
        
        valUpload.textContent = finalUploadSpeed.toFixed(2);
        progressUpload.style.width = '100%';
    }
    
    // ----------------------------------------------------
    // CHART FEED LOOP
    // ----------------------------------------------------
    function startChartFeed() {
        chartInterval = setInterval(() => {
            if (!isRunning) {
                stopChartFeed();
                return;
            }
            
            let currentDownload = 0;
            let currentUpload = 0;
            
            if (currentPhase === 'download') {
                currentDownload = currentDownloadSpeed;
            } else if (currentPhase === 'upload') {
                currentDownload = finalDownloadSpeed;
                currentUpload = currentUploadSpeed;
            }
            
            addChartData(currentDownload, currentUpload);
        }, 500); // Sample every 500ms
    }
    
    function stopChartFeed() {
        if (chartInterval) {
            clearInterval(chartInterval);
            chartInterval = null;
        }
    }
    
    // ----------------------------------------------------
    // DIAGNOSTIC SUMMARY
    // ----------------------------------------------------
    function displayDiagnosis() {
        cardDiagnosis.classList.remove('hidden');
        
        let qualityText = '';
        
        if (finalDownloadSpeed >= 100 && finalUploadSpeed >= 30 && avgPing <= 20) {
            qualityText = `<strong>¡Conexión Excelente!</strong> Tienes una velocidad de descarga de ${finalDownloadSpeed.toFixed(0)} Mbps y una latencia muy baja (${avgPing.toFixed(0)} ms). Tu conexión es ideal para streaming en 4K/8K de forma simultánea, gaming competitivo de nivel profesional, transmisiones en vivo (streaming) y teletrabajo intensivo sin interrupciones.`;
        } else if (finalDownloadSpeed >= 50 && finalUploadSpeed >= 15 && avgPing <= 45) {
            qualityText = `<strong>¡Conexión Muy Buena!</strong> Tu red ofrece velocidades de descarga sólidas de ${finalDownloadSpeed.toFixed(0)} Mbps y latencia baja. Admite perfectamente streaming en Ultra HD (4K), videollamadas grupales en alta definición y descargas rápidas de archivos de gran tamaño.`;
        } else if (finalDownloadSpeed >= 20 && finalUploadSpeed >= 5 && avgPing <= 80) {
            qualityText = `<strong>Conexión Buena (Estándar).</strong> Tu velocidad de descarga de ${finalDownloadSpeed.toFixed(0)} Mbps es suficiente para el consumo diario de contenido multimedia en HD, navegación web fluida y videoconferencias. Podría experimentar pequeños retrasos si varios dispositivos saturan la red al mismo tiempo.`;
        } else {
            qualityText = `<strong>Conexión Limitada.</strong> Tus velocidades de red (${finalDownloadSpeed.toFixed(1)} Mbps descarga / ${finalUploadSpeed.toFixed(1)} Mbps subida) o tu latencia elevada (${avgPing.toFixed(0)} ms) son básicas. Se recomienda para navegación web sencilla y chat. Podrías experimentar buffering o interrupciones en streaming de video o juegos en línea.`;
        }
        
        diagnosisText.innerHTML = qualityText;
    }
    
    // ----------------------------------------------------
    // COPY TO CLIPBOARD Utility
    // ----------------------------------------------------
    function copyResultsToClipboard() {
        const text = `--- Veloce Test de Velocidad de Red ---
Fecha: ${new Date().toLocaleString()}
Descarga: ${finalDownloadSpeed.toFixed(2)} Mbps
Subida: ${finalUploadSpeed.toFixed(2)} Mbps
Ping: ${avgPing.toFixed(0)} ms
Jitter: ${jitter.toFixed(0)} ms
IP Pública: ${infoIp.textContent}
Proveedor (ISP): ${infoIsp.textContent}
Ubicación: ${infoLocation.textContent}
Servidor: ${infoServer.textContent}
----------------------------------------`;
        
        navigator.clipboard.writeText(text).then(() => {
            const btnText = btnShare.querySelector('span');
            const originalText = btnText.textContent;
            btnText.textContent = '¡Copiado!';
            
            setTimeout(() => {
                btnText.textContent = originalText;
            }, 2000);
        }).catch(err => {
            console.error('Error al copiar resultados:', err);
            alert('No se pudo copiar de manera automática. Copia manualmente los datos de las tarjetas.');
        });
    }
});
