/* ============================================================
   FRIENDY FAZBEAR — INTERACTIVE CONSOLE JS
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
    initToasts();
    initPasswordToggles();
    initCopyRoomCode();
    initSettingsControls();
    initProfilePreview();
    initArenaCanvas();
});

/* 1. Dismissible Toast Stack */
function initToasts() {
    document.querySelectorAll('.toast').forEach((toast, idx) => {
        const closeBtn = toast.querySelector('.toast-close');
        const dismiss = () => {
            toast.classList.add('leaving');
            setTimeout(() => toast.remove(), 260);
        };
        if (closeBtn) closeBtn.addEventListener('click', dismiss);
        setTimeout(dismiss, 4500 + idx * 600);
    });
}

/* 2. Password Visibility Toggles */
function initPasswordToggles() {
    document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-toggle-password');
            const input = document.getElementById(targetId);
            if (!input) return;
            const showing = input.type === 'text';
            input.type = showing ? 'password' : 'text';
            btn.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
            btn.classList.toggle('is-visible', !showing);
        });
    });
}

/* 3. Copy Lobby Room Code */
function initCopyRoomCode() {
    const btn = document.getElementById('copyRoomCodeBtn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
        const code = btn.getAttribute('data-code') || '';
        try {
            await navigator.clipboard.writeText(code);
        } catch {
            const tmp = document.createElement('input');
            tmp.value = code;
            document.body.appendChild(tmp);
            tmp.select();
            document.execCommand('copy');
            tmp.remove();
        }
        const label = btn.querySelector('span');
        if (label) {
            const prev = label.textContent;
            label.textContent = 'Copied!';
            setTimeout(() => { label.textContent = prev; }, 1600);
        }
    });
}

/* 4. Settings: Live Sliders + Live Theme Preview */
function initSettingsControls() {
    document.querySelectorAll('.arcade-range').forEach((slider) => {
        const update = () => {
            const val = Number(slider.value);
            const target = document.getElementById(slider.dataset.output);
            if (target) target.textContent = `${val}%`;
            slider.style.background = `linear-gradient(90deg, var(--accent) 0%, var(--accent) ${val}%, rgba(255,255,255,0.1) ${val}%)`;
        };
        slider.addEventListener('input', update);
        update();
    });

    const resetBtn = document.getElementById('resetAudioBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            const defaults = { master_volume: 80, sfx_volume: 85, music_volume: 70 };
            Object.entries(defaults).forEach(([name, val]) => {
                const el = document.querySelector(`input[name="${name}"]`);
                if (el) {
                    el.value = val;
                    el.dispatchEvent(new Event('input'));
                }
            });
        });
    }

    document.querySelectorAll('input[name="theme"]').forEach((radio) => {
        radio.addEventListener('change', () => {
            if (radio.checked) {
                document.documentElement.setAttribute('data-theme', radio.value);
            }
        });
    });
}

/* 5. Profile Live Card Preview */
function initProfilePreview() {
    const avatarBadge = document.getElementById('profileAvatarPreview');
    const namePreview = document.getElementById('profileNamePreview');
    const bioPreview = document.getElementById('profileBioPreview');

    const initials = {
        freddy: 'FF',
        bonnie: 'BB',
        chica: 'CC',
        foxy: 'FX',
        golden_freddy: 'GF',
        puppet: 'TP',
    };

    if (avatarBadge) {
        document.querySelectorAll('input[name="avatar"]').forEach((radio) => {
            radio.addEventListener('change', () => {
                if (!radio.checked) return;
                avatarBadge.className = `av av-lg av-${radio.value}`;
                avatarBadge.textContent = initials[radio.value] || 'FF';
            });
        });
    }

    const nameInput = document.querySelector('input[name="display_name"]');
    if (nameInput && namePreview) {
        nameInput.addEventListener('input', () => {
            namePreview.textContent = nameInput.value.trim() || namePreview.dataset.fallback || 'Player';
        });
    }

    const bioInput = document.querySelector('textarea[name="bio"]');
    if (bioInput && bioPreview) {
        bioInput.addEventListener('input', () => {
            bioPreview.textContent = bioInput.value.trim() || 'Ready to play!';
        });
    }
}

/* 6. Interactive Canvas 2D Arcade Mini-Game on Arena Page */
function initArenaCanvas() {
    const canvas = document.getElementById('arenaCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const overlay = document.getElementById('canvasOverlay');
    const overlayTitle = document.getElementById('overlayTitle');
    const overlaySub = document.getElementById('overlaySub');
    const startBtn = document.getElementById('startArcadeBtn');
    const hudScore = document.getElementById('hudScore');
    const hudTimer = document.getElementById('hudTimer');
    const hudCombo = document.getElementById('hudCombo');
    const scoreInput = document.getElementById('scoreInput');
    const gameId = canvas.dataset.game || 'fazbear_frenzy';

    const themes = {
        fazbear_frenzy: { primary: '#ffffff', hazard: '#71717a', bg: '#070709', label: 'Collect Chrome Tokens' },
        pizza_dash: { primary: '#e4e4e7', hazard: '#52525b', bg: '#08080a', label: 'Catch Silver Slices' },
        laser_havoc: { primary: '#f4f4f5', hazard: '#71717a', bg: '#060709', label: 'Absorb Energy Orbs' },
        night_guard_duel: { primary: '#d4d4d8', hazard: '#52525b', bg: '#050507', label: 'Charge Power Cells' },
    };
    const palette = themes[gameId] || themes.fazbear_frenzy;

    let W = 800;
    let H = 450;
    canvas.width = W;
    canvas.height = H;

    let running = false;
    let score = 0;
    let combo = 1;
    let timeLeft = 20;
    let lastTs = 0;
    let spawnTimer = 0;
    let keys = {};

    const player = { x: W / 2, y: H - 56, r: 18, vx: 0 };
    let items = [];
    let particles = [];

    function spawnBurst(x, y, color, count = 12) {
        for (let i = 0; i < count; i++) {
            const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4;
            const speed = 90 + Math.random() * 170;
            particles.push({
                x, y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                life: 0.45 + Math.random() * 0.25,
                maxLife: 0.7,
                color,
                size: 2.5 + Math.random() * 3,
            });
        }
    }

    function spawnItem() {
        const isHazard = Math.random() < 0.28;
        items.push({
            x: 34 + Math.random() * (W - 68),
            y: -18,
            r: isHazard ? 13 : 14,
            vy: (isHazard ? 210 : 165) + Math.random() * 115 + (20 - timeLeft) * 4,
            hazard: isHazard,
            spin: Math.random() * Math.PI * 2,
        });
    }

    function drawBackground() {
        ctx.fillStyle = palette.bg;
        ctx.fillRect(0, 0, W, H);

        ctx.strokeStyle = 'rgba(255,255,255,0.045)';
        ctx.lineWidth = 1;
        for (let x = 0; x < W; x += 40) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, H);
            ctx.stroke();
        }
        for (let y = 0; y < H; y += 40) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(W, y);
            ctx.stroke();
        }
    }

    function renderIdle() {
        drawBackground();
        ctx.save();
        ctx.shadowBlur = 24;
        ctx.shadowColor = palette.primary;
        ctx.fillStyle = palette.primary;
        ctx.beginPath();
        ctx.arc(player.x, player.y, player.r, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }

    function endRound() {
        running = false;
        const finalScore = Math.max(100, Math.round(score));
        if (scoreInput) {
            scoreInput.value = finalScore;
            scoreInput.focus();
        }
        if (overlayTitle) overlayTitle.textContent = `Round Complete — ${finalScore.toLocaleString()} pts`;
        if (overlaySub) overlaySub.textContent = 'Your score is synced below. Hit "Complete Match & Record Score" to save it to the leaderboard, or play again!';
        if (startBtn) startBtn.textContent = 'Play Another Round';
        if (overlay) overlay.classList.remove('hidden');
    }

    function tick(ts) {
        if (!running) return;
        const dt = Math.min(0.05, (ts - lastTs) / 1000 || 0.016);
        lastTs = ts;

        timeLeft -= dt;
        if (timeLeft <= 0) {
            timeLeft = 0;
            if (hudTimer) hudTimer.textContent = '0.0s';
            endRound();
            return;
        }

        // Keyboard movement
        const speed = 460;
        if (keys['ArrowLeft'] || keys['KeyA']) player.x -= speed * dt;
        if (keys['ArrowRight'] || keys['KeyD']) player.x += speed * dt;
        if (keys['ArrowUp'] || keys['KeyW']) player.y -= speed * 0.7 * dt;
        if (keys['ArrowDown'] || keys['KeyS']) player.y += speed * 0.7 * dt;
        player.x = Math.max(player.r + 8, Math.min(W - player.r - 8, player.x));
        player.y = Math.max(H * 0.45, Math.min(H - player.r - 12, player.y));

        spawnTimer -= dt;
        if (spawnTimer <= 0) {
            spawnItem();
            spawnTimer = Math.max(0.22, 0.44 - (20 - timeLeft) * 0.009);
        }

        drawBackground();

        // Update & draw items
        for (let i = items.length - 1; i >= 0; i--) {
            const it = items[i];
            it.y += it.vy * dt;
            it.spin += dt * 3;

            const dx = it.x - player.x;
            const dy = it.y - player.y;
            const dist = Math.hypot(dx, dy);

            if (dist < it.r + player.r) {
                if (it.hazard) {
                    combo = 1;
                    score = Math.max(0, score - 60);
                    spawnBurst(it.x, it.y, palette.hazard, 16);
                } else {
                    score += 50 * combo;
                    combo = Math.min(8, combo + 1);
                    spawnBurst(it.x, it.y, palette.primary, 12);
                }
                items.splice(i, 1);
                continue;
            }

            if (it.y > H + 30) {
                if (!it.hazard) combo = 1;
                items.splice(i, 1);
                continue;
            }

            ctx.save();
            ctx.translate(it.x, it.y);
            ctx.rotate(it.spin);
            if (it.hazard) {
                ctx.shadowBlur = 16;
                ctx.shadowColor = palette.hazard;
                ctx.fillStyle = palette.hazard;
                ctx.fillRect(-it.r * 0.85, -it.r * 0.85, it.r * 1.7, it.r * 1.7);
            } else {
                ctx.shadowBlur = 18;
                ctx.shadowColor = palette.primary;
                ctx.fillStyle = palette.primary;
                ctx.beginPath();
                ctx.arc(0, 0, it.r, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = '#fff';
                ctx.beginPath();
                ctx.arc(-4, -4, 3.5, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.restore();
        }

        // Particles
        for (let i = particles.length - 1; i >= 0; i--) {
            const p = particles[i];
            p.x += p.vx * dt;
            p.y += p.vy * dt;
            p.life -= dt;
            if (p.life <= 0) {
                particles.splice(i, 1);
                continue;
            }
            ctx.globalAlpha = Math.max(0, p.life / p.maxLife);
            ctx.fillStyle = p.color;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fill();
            ctx.globalAlpha = 1;
        }

        // Player ship / Fazbear core
        ctx.save();
        ctx.shadowBlur = 24;
        ctx.shadowColor = palette.primary;
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(player.x, player.y, player.r, 0, Math.PI * 2);
        ctx.fill();
        ctx.lineWidth = 4;
        ctx.strokeStyle = palette.primary;
        ctx.stroke();
        ctx.restore();

        if (hudScore) hudScore.textContent = Math.round(score).toLocaleString();
        if (hudTimer) hudTimer.textContent = `${timeLeft.toFixed(1)}s`;
        if (hudCombo) hudCombo.textContent = `x${combo}`;
        if (scoreInput) scoreInput.value = Math.max(100, Math.round(score));

        requestAnimationFrame(tick);
    }

    function movePointer(clientX, clientY) {
        if (!running) return;
        const rect = canvas.getBoundingClientRect();
        const nx = ((clientX - rect.left) / rect.width) * W;
        const ny = ((clientY - rect.top) / rect.height) * H;
        player.x = Math.max(player.r + 8, Math.min(W - player.r - 8, nx));
        player.y = Math.max(H * 0.45, Math.min(H - player.r - 12, ny));
    }

    canvas.addEventListener('pointermove', (e) => movePointer(e.clientX, e.clientY));
    canvas.addEventListener('pointerdown', (e) => movePointer(e.clientX, e.clientY));
    window.addEventListener('keydown', (e) => { keys[e.code] = true; });
    window.addEventListener('keyup', (e) => { keys[e.code] = false; });

    if (startBtn) {
        startBtn.addEventListener('click', () => {
            score = 0;
            combo = 1;
            timeLeft = 20;
            items = [];
            particles = [];
            player.x = W / 2;
            player.y = H - 56;
            running = true;
            lastTs = performance.now();
            if (overlay) overlay.classList.add('hidden');
            requestAnimationFrame(tick);
        });
    }

    renderIdle();
}
