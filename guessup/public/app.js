/**
 * FormiGuessUp - Complete Game Logic
 */
(function () {
    'use strict';

    const STORAGE_KEY = 'formiguessup_history';
    const GAME_DURATION = 60;
    const ACCENT_COLORS = ['#a855f7','#ec4899','#06b6d4','#f97316','#10b981','#6366f1','#f43f5e','#eab308','#14b8a6','#8b5cf6'];

    // DOM
    const $ = (s) => document.querySelector(s);
    const screens = {
        home: $('#homeScreen'),
        loading: $('#loadingScreen'),
        orientation: $('#orientationScreen'),
        game: $('#gameScreen'),
        results: $('#resultsScreen')
    };
    const themeInput = $('#themeInput');
    const clearInputBtn = $('#clearInput');
    const btnPlay = $('#btnPlay');
    const historyList = $('#historyList');
    const historyEmpty = $('#historyEmpty');
    const clearHistoryBtn = $('#clearHistory');
    const bgParticles = $('#bgParticles');
    const appContainer = $('#appContainer');

    // State
    let history = loadHistory();
    let gameWords = [];
    let remainingWords = [];
    let correctWords = [];
    let wrongWords = [];
    let currentWord = '';
    let currentTheme = '';
    let gameTimerId = null;
    let selectedDuration = 60;
    let timeLeft = selectedDuration;
    let currentScreen = 'home';
    let tiltState = 'neutral';
    const TILT_THRESHOLD = 40;
    const NEUTRAL_THRESHOLD = 20;

    // ============================
    // Screen Management
    // ============================
    function showScreen(name) {
        Object.values(screens).forEach(s => s.classList.remove('active'));
        screens[name].classList.add('active');
        currentScreen = name;

        // Adjust container for game screen
        if (name === 'game') {
            appContainer.style.maxWidth = '100%';
            appContainer.style.padding = '0';
        } else {
            appContainer.style.maxWidth = '480px';
            appContainer.style.padding = '0 20px';
        }
    }

    // ============================
    // Particles
    // ============================
    function createParticles() {
        const colors = ['rgba(168,85,247,0.3)','rgba(236,72,153,0.3)','rgba(6,182,212,0.3)','rgba(249,115,22,0.2)'];
        const count = window.innerWidth < 500 ? 12 : 20;
        for (let i = 0; i < count; i++) {
            const p = document.createElement('div');
            p.classList.add('particle');
            const size = Math.random() * 6 + 2;
            const color = colors[Math.floor(Math.random() * colors.length)];
            p.style.cssText = `width:${size}px;height:${size}px;background:${color};left:${Math.random()*100}%;animation-duration:${Math.random()*15+10}s;animation-delay:${Math.random()*10}s;box-shadow:0 0 ${size*2}px ${color};`;
            bgParticles.appendChild(p);
        }
    }

    // ============================
    // History
    // ============================
    function loadHistory() {
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []; } catch { return []; }
    }
    function saveHistory() { localStorage.setItem(STORAGE_KEY, JSON.stringify(history)); }

    function addToHistory(theme) {
        const entry = { id: Date.now(), theme: theme.trim(), timestamp: new Date().toISOString(), color: ACCENT_COLORS[Math.floor(Math.random() * ACCENT_COLORS.length)] };
        if (history.length > 0 && history[0].theme.toLowerCase() === entry.theme.toLowerCase()) return;
        history.unshift(entry);
        if (history.length > 30) history = history.slice(0, 30);
        saveHistory();
        renderHistory();
    }

    function formatTime(iso) {
        const diff = Math.floor((Date.now() - new Date(iso)) / 60000);
        if (diff < 1) return "À l'instant";
        if (diff < 60) return `Il y a ${diff}min`;
        if (diff < 1440) return `Il y a ${Math.floor(diff/60)}h`;
        if (diff < 10080) return `Il y a ${Math.floor(diff/1440)}j`;
        return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
    }

    function escapeHtml(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    function renderHistory() {
        historyList.innerHTML = '';
        if (history.length === 0) { historyEmpty.classList.add('visible'); clearHistoryBtn.classList.remove('visible'); return; }
        historyEmpty.classList.remove('visible');
        clearHistoryBtn.classList.add('visible');
        history.forEach((entry, i) => {
            const item = document.createElement('div');
            item.classList.add('history-item');
            item.style.animationDelay = `${i * 0.05}s`;
            item.innerHTML = `<span class="history-item__color" style="background:${entry.color};box-shadow:0 0 8px ${entry.color};"></span><span class="history-item__name">${escapeHtml(entry.theme)}</span><span class="history-item__time">${formatTime(entry.timestamp)}</span><span class="history-item__replay">▶</span>`;
            item.addEventListener('click', () => { themeInput.value = entry.theme; toggleClearButton(); themeInput.focus(); });
            historyList.appendChild(item);
        });
    }

    function toggleClearButton() { clearInputBtn.classList.toggle('visible', themeInput.value.trim().length > 0); }

    // ============================
    // Play Flow
    // ============================
    async function handlePlay() {
        const theme = themeInput.value.trim();
        if (!theme) {
            btnPlay.classList.add('shake');
            const w = themeInput.closest('.input-wrapper');
            w.style.borderColor = '#f43f5e';
            setTimeout(() => { w.style.borderColor = ''; }, 1000);
            setTimeout(() => { btnPlay.classList.remove('shake'); }, 500);
            return;
        }

        currentTheme = theme;
        addToHistory(theme);

        // Show loading screen
        showScreen('loading');
        $('#loadingTheme').textContent = `Thème : ${theme}`;
        const fill = $('#loadingBarFill');
        fill.style.width = '0%';

        // Animate loading bar
        let progress = 0;
        const loadInterval = setInterval(() => {
            progress += Math.random() * 8 + 2;
            if (progress > 90) progress = 90;
            fill.style.width = progress + '%';
        }, 300);

        try {
            // Request permission for orientation if needed (iOS)
            if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
                const permissionState = await DeviceOrientationEvent.requestPermission();
                if (permissionState !== 'granted') {
                    alert("La permission d'accéder au gyroscope est nécessaire pour jouer.");
                    showScreen('home');
                    return;
                }
            }

            const res = await fetch('/api/generate-words', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ theme })
            });

            clearInterval(loadInterval);

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || 'Erreur serveur');
            }

            const data = await res.json();
            fill.style.width = '100%';
            gameWords = data.words;

            // Short delay to show 100%
            await new Promise(r => setTimeout(r, 500));

            // Go to orientation check
            showOrientationScreen();

        } catch (err) {
            clearInterval(loadInterval);
            console.error('Play error:', err);
            alert('Erreur : ' + err.message);
            showScreen('home');
        }
    }

    // ============================
    // Orientation Management
    // ============================
    function isLandscape() {
        return window.innerWidth > window.innerHeight;
    }

    function showOrientationScreen() {
        if (isLandscape()) {
            startGame();
        } else {
            showScreen('orientation');
        }
    }

    function onOrientationChange() {
        if (currentScreen === 'orientation' && isLandscape()) {
            startGame();
        }
        // During game, if user rotates back to portrait, we don't stop the game
        // but we could show a warning (for now we let it continue)
    }

    function handleDeviceOrientation(e) {
        if (currentScreen !== 'game') return;

        // More robust angle detection for landscape "nodding"
        let angle = 0;
        const orientation = window.orientation || (screen.orientation && screen.orientation.angle) || 0;

        // We target the rotation around the phone's long axis
        if (orientation === 90) {
            angle = e.gamma;
        } else if (orientation === -90 || orientation === 270) {
            angle = -e.gamma;
        } else {
            angle = e.beta;
        }

        // Normalize: 0 is vertical (on forehead), positive is UP, negative is DOWN
        // Typically angle is around 90 or -90 when vertical
        let normalized = 0;
        if (angle > 0) normalized = angle - 90;
        else normalized = angle + 90;

        // State machine
        if (tiltState === 'neutral') {
            if (normalized > TILT_THRESHOLD) {
                tiltState = 'correct';
                markCorrect();
            } else if (normalized < -TILT_THRESHOLD) {
                tiltState = 'wrong';
                markWrong();
            }
        } else {
            if (Math.abs(normalized) < NEUTRAL_THRESHOLD) {
                tiltState = 'neutral';
            }
        }
    }

    window.addEventListener('resize', onOrientationChange);
    if (screen.orientation) {
        screen.orientation.addEventListener('change', onOrientationChange);
    }
    window.addEventListener('orientationchange', onOrientationChange);

    // ============================
    // Game Logic
    // ============================
    function shuffleArray(arr) {
        const a = [...arr];
        for (let i = a.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [a[i], a[j]] = [a[j], a[i]];
        }
        return a;
    }

    function startGame() {
        showScreen('game');
        remainingWords = shuffleArray(gameWords);
        correctWords = [];
        wrongWords = [];
        timeLeft = selectedDuration;

        showNextWord();
        updateGameUI();
        startTimer();
        requestWakeLock();
        
        // Reset tilt state
        tiltState = 'neutral';
        window.addEventListener('deviceorientation', handleDeviceOrientation);
    }

    function showNextWord() {
        if (remainingWords.length === 0) {
            // No more words - end early
            endGame();
            return;
        }
        currentWord = remainingWords.pop();
        const wordEl = $('#gameWord');
        wordEl.textContent = currentWord;
        wordEl.className = 'game-word';
        // Re-trigger animation
        void wordEl.offsetWidth;
        wordEl.style.animation = 'none';
        void wordEl.offsetWidth;
        wordEl.style.animation = '';
    }

    function markCorrect() {
        correctWords.push(currentWord);
        const wordEl = $('#gameWord');
        wordEl.classList.add('flash-correct');
        updateGameUI();
        setTimeout(() => showNextWord(), 150);
    }

    function markWrong() {
        wrongWords.push(currentWord);
        const wordEl = $('#gameWord');
        wordEl.classList.add('flash-wrong');
        updateGameUI();
        setTimeout(() => showNextWord(), 150);
    }

    function updateGameUI() {
        $('#gameScore').textContent = correctWords.length;
        $('#gameTimer').textContent = timeLeft;
        const total = remainingWords.length;
        $('#gameRemaining').textContent = `${total} restant${total > 1 ? 's' : ''}`;

        // Timer styling
        const timerEl = $('#gameTimer');
        timerEl.classList.remove('warning', 'danger');
        if (timeLeft <= 5) timerEl.classList.add('danger');
        else if (timeLeft <= 15) timerEl.classList.add('warning');

        // Timer bar
        const pct = (timeLeft / selectedDuration) * 100;
        $('#gameTimerFill').style.width = pct + '%';
    }

    function startTimer() {
        if (gameTimerId) clearInterval(gameTimerId);
        gameTimerId = setInterval(() => {
            timeLeft--;
            updateGameUI();
            if (timeLeft <= 0) {
                endGame();
            }
        }, 1000);
    }

    function endGame() {
        try {
            if (gameTimerId) { clearInterval(gameTimerId); gameTimerId = null; }
            // The current word that wasn't answered goes to wrong
            if (currentWord && !correctWords.includes(currentWord) && !wrongWords.includes(currentWord)) {
                wrongWords.push(currentWord);
            }
            releaseWakeLock();
            window.removeEventListener('deviceorientation', handleDeviceOrientation);
            showResults();
        } catch (err) {
            console.error('End game error:', err);
            showResults(); // Try to show results anyway
        }
    }

    function showResults() {
        try {
            showScreen('results');

            const score = correctWords.length;
            $('#resultsScoreValue').textContent = score;
            $('#resultsTheme').textContent = `Thème : ${currentTheme}`;
            $('#statCorrect').textContent = correctWords.length;
            $('#statWrong').textContent = wrongWords.length;

            // Animate score counter
            animateCounter($('#resultsScoreValue'), score);

            // Build results table
            const table = $('#resultsTable');
            table.innerHTML = '';

            // Show correct words first, then wrong
            correctWords.forEach((w, i) => {
                const row = document.createElement('div');
                row.classList.add('result-row', 'result-row--correct');
                row.style.animationDelay = `${i * 0.05}s`;
                row.innerHTML = `<span class="result-row__icon">✅</span><span class="result-row__word">${escapeHtml(w)}</span>`;
                table.appendChild(row);
            });

            wrongWords.forEach((w, i) => {
                const row = document.createElement('div');
                row.classList.add('result-row', 'result-row--wrong');
                row.style.animationDelay = `${(correctWords.length + i) * 0.05}s`;
                row.innerHTML = `<span class="result-row__icon">❌</span><span class="result-row__word">${escapeHtml(w)}</span>`;
                table.appendChild(row);
            });
        } catch (err) {
            console.error('Show results error:', err);
        }
    }

    function animateCounter(el, target) {
        let current = 0;
        const step = Math.max(1, Math.floor(target / 20));
        const interval = setInterval(() => {
            current += step;
            if (current >= target) { current = target; clearInterval(interval); }
            el.textContent = current;
        }, 40);
    }

    // ============================
    // Event Listeners
    // ============================
    themeInput.addEventListener('input', toggleClearButton);
    clearInputBtn.addEventListener('click', () => { themeInput.value = ''; toggleClearButton(); themeInput.focus(); });
    btnPlay.addEventListener('click', handlePlay);
    themeInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') handlePlay(); });

    // Duration selection
    const durationBtns = document.querySelectorAll('.duration-btn');
    durationBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            durationBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedDuration = parseInt(btn.dataset.value);
            localStorage.setItem('formiguessup_duration', selectedDuration);
        });
    });

    // Load saved duration
    const savedDuration = localStorage.getItem('formiguessup_duration');
    if (savedDuration) {
        selectedDuration = parseInt(savedDuration);
        durationBtns.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.value == savedDuration);
        });
    }

    clearHistoryBtn.addEventListener('click', () => {
        const items = historyList.querySelectorAll('.history-item');
        items.forEach((item, i) => { item.style.transition = `opacity 0.2s ${i*0.03}s, transform 0.2s ${i*0.03}s`; item.style.opacity = '0'; item.style.transform = 'translateX(20px)'; });
        setTimeout(() => { history = []; saveHistory(); renderHistory(); }, items.length * 30 + 200);
    });

    // Game buttons removed in favor of gyroscope

    // Results buttons
    $('#btnReplay').addEventListener('click', () => {
        if (gameWords && gameWords.length > 0) {
            // Just restart with existing gameWords
            showOrientationScreen();
        } else {
            // Fallback if list lost
            handlePlay();
        }
    });
    
    $('#btnHome').addEventListener('click', () => {
        showScreen('home');
        // Reset input for a fresh start
        themeInput.value = '';
        toggleClearButton();
    });

    // Prevent sleep during game via wake lock if supported
    let wakeLock = null;
    async function requestWakeLock() {
        try {
            if ('wakeLock' in navigator) {
                wakeLock = await navigator.wakeLock.request('screen');
            }
        } catch {}
    }
    function releaseWakeLock() {
        if (wakeLock) { try { wakeLock.release(); } catch(e) {} wakeLock = null; }
    }

    // ============================
    // Init
    // ============================
    createParticles();
    renderHistory();
    toggleClearButton();
})();
