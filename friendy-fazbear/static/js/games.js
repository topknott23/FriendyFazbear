/* ==========================================================================
   FRIENDY FAZBEAR — 4-IN-1 PLAYABLE CANVAS 2D ARCADE ENGINE
   Games:
     1. fazbear_frenzy   — Top-Down 360° Survival Tag
     2. pizza_dash       — High-Speed Arcade Sprint & Catcher
     3. laser_havoc      — 360° Core Reflector Shield Brawler
     4. night_guard_duel — 4-Sector Security Cam Blast-Door Reflex
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('arenaCanvas');
    if (!canvas) return;
    initFazbearArcade(canvas);
});

function initFazbearArcade(canvas) {
    const ctx = canvas.getContext('2d');
    const W = 800;
    const H = 450;
    canvas.width = W;
    canvas.height = H;

    const gameId = canvas.dataset.game || 'fazbear_frenzy';
    const masterVol = Math.max(0, Math.min(100, Number(canvas.dataset.masterVol ?? 80))) / 100;
    const sfxVol = Math.max(0, Math.min(100, Number(canvas.dataset.sfxVol ?? 85))) / 100;

    // UI Elements
    const overlay = document.getElementById('canvasOverlay');
    const overlayBadge = document.getElementById('overlayBadge');
    const overlayTitle = document.getElementById('overlayTitle');
    const overlaySub = document.getElementById('overlaySub');
    const startBtn = document.getElementById('startArcadeBtn');
    const saveOverlayBtn = document.getElementById('saveOverlayBtn');

    const hudScore = document.getElementById('hudScore');
    const hudTimer = document.getElementById('hudTimer');
    const hudCombo = document.getElementById('hudCombo');
    const hudHp = document.getElementById('hudHp');

    const scoreInput = document.getElementById('scoreInput');
    const durationInput = document.getElementById('durationInput');
    const scoreForm = document.getElementById('arenaScoreForm');

    // Web Audio Synthesizer (zero external files, respects user volume settings)
    let audioCtx = null;
    function beep(freq, duration = 0.09, type = 'sine', gainScale = 0.25) {
        const vol = masterVol * sfxVol * gainScale;
        if (vol <= 0.005) return;
        try {
            if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            if (audioCtx.state === 'suspended') audioCtx.resume();
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = type;
            osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
            gain.gain.setValueAtTime(vol, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start();
            osc.stop(audioCtx.currentTime + duration);
        } catch {}
    }

    const sfx = {
        pickup: (combo = 1) => beep(520 + Math.min(combo, 8) * 55, 0.1, 'triangle', 0.24),
        bonus: () => { beep(660, 0.08, 'triangle', 0.25); setTimeout(() => beep(880, 0.12, 'triangle', 0.25), 70); },
        hit: () => beep(140, 0.2, 'sawtooth', 0.3),
        deflect: (combo = 1) => beep(380 + Math.min(combo, 8) * 60, 0.09, 'square', 0.18),
        door: () => beep(220, 0.08, 'square', 0.2),
        win: () => {
            [523, 659, 784, 1046].forEach((f, i) => setTimeout(() => beep(f, 0.14, 'triangle', 0.24), i * 85));
        },
    };

    const GAME_META = {
        fazbear_frenzy: {
            duration: 30,
            controls: 'Move with Mouse, Touch, or WASD / Arrows. Collect glowing Faz-Tokens and evade the stalking hunters!',
        },
        pizza_dash: {
            duration: 30,
            controls: 'Glide left/right (Mouse, Touch, or A/D / Arrows) across lanes to catch Pizza Slices and dodge Burnt Pans!',
        },
        laser_havoc: {
            duration: 30,
            controls: 'Aim your chrome shield around the core with Mouse/Touch (or Left/Right keys) to deflect incoming lasers!',
        },
        night_guard_duel: {
            duration: 30,
            controls: 'Click any alerted camera sector (or press keys 1, 2, 3, 4) to slam the blast door before breach!',
        },
    };
    const meta = GAME_META[gameId] || GAME_META.fazbear_frenzy;

    // Shared Game State
    let running = false;
    let score = 0;
    let combo = 1;
    let hp = 3;
    let timeLeft = meta.duration;
    let elapsed = 0;
    let lastTs = 0;
    let shake = 0;

    let particles = [];
    let popups = [];
    const keys = {};
    const pointer = { x: W / 2, y: H / 2, active: false };

    // Per-mode entities
    let state = {};

    function spawnParticles(x, y, color = '#ffffff', count = 12) {
        for (let i = 0; i < count; i++) {
            const a = (Math.PI * 2 * i) / count + Math.random() * 0.4;
            const spd = 70 + Math.random() * 190;
            particles.push({
                x, y,
                vx: Math.cos(a) * spd,
                vy: Math.sin(a) * spd,
                life: 0.4 + Math.random() * 0.25,
                maxLife: 0.65,
                color,
                size: 2 + Math.random() * 3,
            });
        }
    }

    function addPopup(x, y, text, color = '#ffffff') {
        popups.push({ x, y, text, color, life: 0.75, maxLife: 0.75 });
    }

    function updateHud() {
        if (hudScore) hudScore.textContent = Math.round(score).toLocaleString();
        if (hudTimer) hudTimer.textContent = `${Math.max(0, timeLeft).toFixed(1)}s`;
        if (hudCombo) hudCombo.textContent = `x${combo}`;
        if (hudHp) hudHp.textContent = '●'.repeat(Math.max(0, hp)) + '○'.repeat(Math.max(0, 3 - hp));
        if (scoreInput) scoreInput.value = Math.max(0, Math.round(score));
        if (durationInput) durationInput.value = Math.max(1, Math.round(elapsed));
    }

    function drawGridBackground(scrollY = 0) {
        ctx.fillStyle = '#070709';
        ctx.fillRect(0, 0, W, H);
        ctx.strokeStyle = 'rgba(255,255,255,0.045)';
        ctx.lineWidth = 1;
        for (let x = 0; x <= W; x += 40) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, H);
            ctx.stroke();
        }
        const offset = scrollY % 40;
        for (let y = offset; y <= H; y += 40) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(W, y);
            ctx.stroke();
        }
    }

    function drawParticlesAndPopups(dt) {
        for (let i = particles.length - 1; i >= 0; i--) {
            const p = particles[i];
            p.x += p.vx * dt;
            p.y += p.vy * dt;
            p.life -= dt;
            if (p.life <= 0) { particles.splice(i, 1); continue; }
            ctx.globalAlpha = Math.max(0, p.life / p.maxLife);
            ctx.fillStyle = p.color;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.globalAlpha = 1;

        ctx.font = '700 14px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        for (let i = popups.length - 1; i >= 0; i--) {
            const pop = popups[i];
            pop.y -= 36 * dt;
            pop.life -= dt;
            if (pop.life <= 0) { popups.splice(i, 1); continue; }
            ctx.globalAlpha = Math.max(0, pop.life / pop.maxLife);
            ctx.fillStyle = pop.color;
            ctx.fillText(pop.text, pop.x, pop.y);
        }
        ctx.globalAlpha = 1;
    }

    // =========================================================================
    // MODE 1: FAZBEAR FRENZY (Top-Down 360° Survival Tag)
    // =========================================================================
    function initFrenzy() {
        state = {
            px: W / 2, py: H / 2, pr: 15, invuln: 0,
            hunters: [
                { x: 90, y: 90, r: 16, spd: 115 },
                { x: W - 90, y: H - 90, r: 16, spd: 130 },
            ],
            tokens: [],
            spawnT: 0,
            hunterSpawnT: 9,
        };
        for (let i = 0; i < 3; i++) spawnFrenzyToken();
    }

    function spawnFrenzyToken() {
        state.tokens.push({
            x: 50 + Math.random() * (W - 100),
            y: 50 + Math.random() * (H - 100),
            r: 11,
            pulse: Math.random() * Math.PI * 2,
        });
    }

    function tickFrenzy(dt) {
        drawGridBackground(0);
        const speed = 320;
        if (keys['ArrowLeft'] || keys['KeyA']) state.px -= speed * dt;
        if (keys['ArrowRight'] || keys['KeyD']) state.px += speed * dt;
        if (keys['ArrowUp'] || keys['KeyW']) state.py -= speed * dt;
        if (keys['ArrowDown'] || keys['KeyS']) state.py += speed * dt;
        if (pointer.active) {
            state.px += (pointer.x - state.px) * Math.min(1, dt * 11);
            state.py += (pointer.y - state.py) * Math.min(1, dt * 11);
        }
        state.px = Math.max(24, Math.min(W - 24, state.px));
        state.py = Math.max(24, Math.min(H - 24, state.py));
        if (state.invuln > 0) state.invuln -= dt;

        // Spawn extra hunter mid-round for tension
        state.hunterSpawnT -= dt;
        if (state.hunterSpawnT <= 0 && state.hunters.length < 4) {
            state.hunterSpawnT = 10;
            const corner = state.hunters.length % 2 === 0 ? { x: 40, y: H - 40 } : { x: W - 40, y: 40 };
            state.hunters.push({ x: corner.x, y: corner.y, r: 16, spd: 125 + state.hunters.length * 14 });
            addPopup(corner.x, corner.y - 20, 'HUNTER INBOUND!', '#f43f5e');
        }

        // Tokens
        state.spawnT -= dt;
        if (state.spawnT <= 0 && state.tokens.length < 4) {
            spawnFrenzyToken();
            state.spawnT = 1.4;
        }
        for (let i = state.tokens.length - 1; i >= 0; i--) {
            const t = state.tokens[i];
            t.pulse += dt * 5;
            if (Math.hypot(t.x - state.px, t.y - state.py) < t.r + state.pr) {
                const pts = 100 * combo;
                score += pts;
                combo = Math.min(8, combo + 1);
                sfx.pickup(combo);
                spawnParticles(t.x, t.y, '#ffffff', 14);
                addPopup(t.x, t.y - 10, `+${pts}`, '#ffffff');
                state.tokens.splice(i, 1);
                continue;
            }
            ctx.save();
            ctx.shadowBlur = 18;
            ctx.shadowColor = '#ffffff';
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(t.x, t.y, t.r + Math.sin(t.pulse) * 2, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        }

        // Hunters
        for (const h of state.hunters) {
            const ang = Math.atan2(state.py - h.y, state.px - h.x);
            h.x += Math.cos(ang) * h.spd * dt;
            h.y += Math.sin(ang) * h.spd * dt;

            if (state.invuln <= 0 && Math.hypot(h.x - state.px, h.y - state.py) < h.r + state.pr - 2) {
                hp -= 1;
                combo = 1;
                state.invuln = 1.25;
                shake = 12;
                sfx.hit();
                spawnParticles(state.px, state.py, '#f43f5e', 20);
                addPopup(state.px, state.py - 18, 'TAGGED!', '#f43f5e');
                // Push hunter back
                h.x -= Math.cos(ang) * 90;
                h.y -= Math.sin(ang) * 90;
            }

            ctx.save();
            ctx.translate(h.x, h.y);
            ctx.rotate(ang);
            ctx.shadowBlur = 16;
            ctx.shadowColor = '#f43f5e';
            ctx.fillStyle = '#18181b';
            ctx.strokeStyle = '#f43f5e';
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.arc(0, 0, h.r, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
            // Glowing eyes
            ctx.fillStyle = '#f43f5e';
            ctx.fillRect(5, -5, 4, 3);
            ctx.fillRect(5, 2, 4, 3);
            ctx.restore();
        }

        // Player
        if (state.invuln <= 0 || Math.floor(state.invuln * 16) % 2 === 0) {
            ctx.save();
            ctx.shadowBlur = 20;
            ctx.shadowColor = '#ffffff';
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(state.px, state.py, state.pr, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#09090b';
            ctx.beginPath();
            ctx.arc(state.px, state.py, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        }
    }

    // =========================================================================
    // MODE 2: PIZZA DASH SPRINT (High-Speed Lane Racer & Catcher)
    // =========================================================================
    function initPizzaDash() {
        state = {
            px: W / 2, py: H - 62, pr: 20, invuln: 0,
            scroll: 0,
            items: [],
            spawnT: 0,
        };
    }

    function tickPizzaDash(dt) {
        const speedMult = 1 + (elapsed / meta.duration) * 0.7;
        state.scroll += 260 * speedMult * dt;
        drawGridBackground(state.scroll);

        // Draw 4 subtle highway lanes
        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
        ctx.setLineDash([14, 14]);
        for (let i = 1; i < 4; i++) {
            const lx = (W / 4) * i;
            ctx.beginPath();
            ctx.moveTo(lx, 0);
            ctx.lineTo(lx, H);
            ctx.stroke();
        }
        ctx.setLineDash([]);

        if (keys['ArrowLeft'] || keys['KeyA']) state.px -= 470 * dt;
        if (keys['ArrowRight'] || keys['KeyD']) state.px += 470 * dt;
        if (pointer.active) state.px += (pointer.x - state.px) * Math.min(1, dt * 14);
        state.px = Math.max(36, Math.min(W - 36, state.px));
        if (state.invuln > 0) state.invuln -= dt;

        state.spawnT -= dt;
        if (state.spawnT <= 0) {
            const lane = Math.floor(Math.random() * 4);
            const x = (W / 4) * lane + W / 8;
            const roll = Math.random();
            const kind = roll < 0.30 ? 'hazard' : roll > 0.88 ? 'golden' : 'slice';
            state.items.push({ x, y: -24, r: kind === 'hazard' ? 18 : 15, kind, vy: (220 + Math.random() * 70) * speedMult });
            state.spawnT = Math.max(0.24, 0.48 - elapsed * 0.007);
        }

        for (let i = state.items.length - 1; i >= 0; i--) {
            const it = state.items[i];
            it.y += it.vy * dt;
            if (Math.hypot(it.x - state.px, it.y - state.py) < it.r + state.pr) {
                if (it.kind === 'hazard') {
                    if (state.invuln <= 0) {
                        hp -= 1;
                        combo = 1;
                        state.invuln = 1.0;
                        shake = 12;
                        sfx.hit();
                        spawnParticles(it.x, it.y, '#f43f5e', 16);
                        addPopup(it.x, it.y - 12, 'BURNT!', '#f43f5e');
                    }
                } else if (it.kind === 'golden') {
                    const pts = 250 * combo;
                    score += pts;
                    combo = Math.min(8, combo + 1);
                    sfx.bonus();
                    spawnParticles(it.x, it.y, '#ffffff', 18);
                    addPopup(it.x, it.y - 12, `VIP +${pts}`, '#ffffff');
                } else {
                    const pts = 75 * combo;
                    score += pts;
                    combo = Math.min(8, combo + 1);
                    sfx.pickup(combo);
                    spawnParticles(it.x, it.y, '#e4e4e7', 10);
                    addPopup(it.x, it.y - 12, `+${pts}`, '#e4e4e7');
                }
                state.items.splice(i, 1);
                continue;
            }
            if (it.y > H + 30) {
                if (it.kind === 'slice') combo = 1;
                state.items.splice(i, 1);
                continue;
            }

            ctx.save();
            ctx.translate(it.x, it.y);
            if (it.kind === 'hazard') {
                ctx.fillStyle = '#18181b';
                ctx.strokeStyle = '#f43f5e';
                ctx.lineWidth = 2.5;
                ctx.fillRect(-16, -12, 32, 24);
                ctx.strokeRect(-16, -12, 32, 24);
                ctx.fillStyle = '#f43f5e';
                ctx.font = '700 12px "JetBrains Mono", monospace';
                ctx.textAlign = 'center';
                ctx.fillText('X', 0, 4);
            } else {
                // Draw stylized Pizza Slice triangle
                ctx.shadowBlur = it.kind === 'golden' ? 22 : 12;
                ctx.shadowColor = '#ffffff';
                ctx.fillStyle = it.kind === 'golden' ? '#ffffff' : '#d4d4d8';
                ctx.beginPath();
                ctx.moveTo(0, -16);
                ctx.lineTo(14, 13);
                ctx.lineTo(-14, 13);
                ctx.closePath();
                ctx.fill();
                ctx.fillStyle = '#09090b';
                ctx.beginPath();
                ctx.arc(0, 2, 3, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.restore();
        }

        // Player Tray / Runner
        if (state.invuln <= 0 || Math.floor(state.invuln * 16) % 2 === 0) {
            ctx.save();
            ctx.shadowBlur = 18;
            ctx.shadowColor = '#ffffff';
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.roundRect(state.px - 28, state.py - 10, 56, 20, 10);
            ctx.fill();
            ctx.restore();
        }
    }

    // =========================================================================
    // MODE 3: LASER HAVOC ARENA (360° Chrome Shield Deflector)
    // =========================================================================
    function initLaserHavoc() {
        state = {
            cx: W / 2, cy: H / 2,
            angle: -Math.PI / 2,
            shieldDist: 54,
            shieldArc: 1.05,
            bolts: [],
            spawnT: 0.4,
        };
    }

    function tickLaserHavoc(dt) {
        drawGridBackground(0);
        if (keys['ArrowLeft'] || keys['KeyA']) state.angle -= 4.4 * dt;
        if (keys['ArrowRight'] || keys['KeyD']) state.angle += 4.4 * dt;
        if (pointer.active) {
            state.angle = Math.atan2(pointer.y - state.cy, pointer.x - state.cx);
        }

        // Spawn lasers from edges toward center
        state.spawnT -= dt;
        if (state.spawnT <= 0) {
            const a = Math.random() * Math.PI * 2;
            const dist = Math.max(W, H) * 0.56;
            const spd = 165 + elapsed * 4.5 + Math.random() * 55;
            state.bolts.push({
                x: state.cx + Math.cos(a) * dist,
                y: state.cy + Math.sin(a) * dist,
                vx: -Math.cos(a) * spd,
                vy: -Math.sin(a) * spd,
                angle: a,
                reflected: false,
            });
            state.spawnT = Math.max(0.32, 0.78 - elapsed * 0.015);
        }

        // Subtle radar rings
        ctx.strokeStyle = 'rgba(255,255,255,0.06)';
        ctx.lineWidth = 1;
        [54, 120, 200].forEach((r) => {
            ctx.beginPath();
            ctx.arc(state.cx, state.cy, r, 0, Math.PI * 2);
            ctx.stroke();
        });

        // Update bolts
        for (let i = state.bolts.length - 1; i >= 0; i--) {
            const b = state.bolts[i];
            b.x += b.vx * dt;
            b.y += b.vy * dt;

            const dist = Math.hypot(b.x - state.cx, b.y - state.cy);
            if (!b.reflected && dist <= state.shieldDist + 8 && dist >= state.shieldDist - 12) {
                const boltAngle = Math.atan2(b.y - state.cy, b.x - state.cx);
                let diff = Math.abs(boltAngle - state.angle);
                if (diff > Math.PI) diff = Math.PI * 2 - diff;
                if (diff <= state.shieldArc / 2 + 0.14) {
                    b.reflected = true;
                    b.vx *= -1.9;
                    b.vy *= -1.9;
                    const pts = 120 * combo;
                    score += pts;
                    combo = Math.min(8, combo + 1);
                    sfx.deflect(combo);
                    spawnParticles(b.x, b.y, '#ffffff', 14);
                    addPopup(b.x, b.y - 10, `DEFLECT +${pts}`, '#ffffff');
                }
            } else if (!b.reflected && dist < 24) {
                hp -= 1;
                combo = 1;
                shake = 14;
                sfx.hit();
                spawnParticles(state.cx, state.cy, '#f43f5e', 20);
                addPopup(state.cx, state.cy - 24, 'CORE HIT!', '#f43f5e');
                state.bolts.splice(i, 1);
                continue;
            }

            if (b.x < -50 || b.x > W + 50 || b.y < -50 || b.y > H + 50) {
                state.bolts.splice(i, 1);
                continue;
            }

            ctx.save();
            ctx.strokeStyle = b.reflected ? '#ffffff' : '#f43f5e';
            ctx.shadowBlur = 16;
            ctx.shadowColor = b.reflected ? '#ffffff' : '#f43f5e';
            ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.moveTo(b.x, b.y);
            ctx.lineTo(b.x - b.vx * 0.06, b.y - b.vy * 0.06);
            ctx.stroke();
            ctx.restore();
        }

        // Center Core
        ctx.save();
        ctx.fillStyle = '#18181b';
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(state.cx, state.cy, 22, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.restore();

        // Chrome Deflector Shield Arc
        ctx.save();
        ctx.strokeStyle = '#ffffff';
        ctx.shadowBlur = 20;
        ctx.shadowColor = '#ffffff';
        ctx.lineWidth = 7;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.arc(state.cx, state.cy, state.shieldDist, state.angle - state.shieldArc / 2, state.angle + state.shieldArc / 2);
        ctx.stroke();
        ctx.restore();
    }

    // =========================================================================
    // MODE 4: NIGHT GUARD DUEL (4-Sector Security Cam Blast-Door Reflex)
    // =========================================================================
    function initNightGuard() {
        const pad = 18;
        const cw = (W - pad * 3) / 2;
        const ch = (H - pad * 3) / 2;
        state = {
            cams: [
                { id: 1, name: 'CAM-01 // STAGE', x: pad, y: pad, w: cw, h: ch, threat: 0, maxThreat: 2.0, flash: 0 },
                { id: 2, name: 'CAM-02 // HALL', x: pad * 2 + cw, y: pad, w: cw, h: ch, threat: 0, maxThreat: 2.0, flash: 0 },
                { id: 3, name: 'CAM-03 // VENT', x: pad, y: pad * 2 + ch, w: cw, h: ch, threat: 0, maxThreat: 2.0, flash: 0 },
                { id: 4, name: 'CAM-04 // DOOR', x: pad * 2 + cw, y: pad * 2 + ch, w: cw, h: ch, threat: 0, maxThreat: 2.0, flash: 0 },
            ],
            spawnT: 0.4,
        };
    }

    function triggerCamSector(idx) {
        if (!running || gameId !== 'night_guard_duel') return;
        const cam = state.cams[idx];
        if (!cam) return;
        cam.flash = 0.25;
        sfx.door();
        if (cam.threat > 0) {
            const speedBonus = Math.round((cam.threat / cam.maxThreat) * 100);
            const pts = (120 + speedBonus) * combo;
            score += pts;
            combo = Math.min(8, combo + 1);
            cam.threat = 0;
            sfx.pickup(combo);
            spawnParticles(cam.x + cam.w / 2, cam.y + cam.h / 2, '#ffffff', 16);
            addPopup(cam.x + cam.w / 2, cam.y + cam.h / 2, `SECURED +${pts}`, '#ffffff');
        } else {
            combo = 1;
            addPopup(cam.x + cam.w / 2, cam.y + cam.h / 2, 'CLEAR', '#71717a');
        }
    }

    function tickNightGuard(dt) {
        drawGridBackground(0);
        state.spawnT -= dt;
        if (state.spawnT <= 0) {
            const free = state.cams.filter((c) => c.threat <= 0);
            if (free.length > 0) {
                const chosen = free[Math.floor(Math.random() * free.length)];
                const dur = Math.max(1.05, 2.0 - elapsed * 0.028);
                chosen.maxThreat = dur;
                chosen.threat = dur;
            }
            state.spawnT = Math.max(0.55, 1.15 - elapsed * 0.02);
        }

        for (const cam of state.cams) {
            if (cam.flash > 0) cam.flash -= dt;
            if (cam.threat > 0) {
                cam.threat -= dt;
                if (cam.threat <= 0) {
                    cam.threat = 0;
                    hp -= 1;
                    combo = 1;
                    shake = 14;
                    sfx.hit();
                    spawnParticles(cam.x + cam.w / 2, cam.y + cam.h / 2, '#f43f5e', 18);
                    addPopup(cam.x + cam.w / 2, cam.y + cam.h / 2, 'BREACH!', '#f43f5e');
                }
            }

            ctx.save();
            ctx.fillStyle = cam.flash > 0 ? 'rgba(255,255,255,0.16)' : cam.threat > 0 ? 'rgba(244,63,94,0.12)' : 'rgba(18,18,22,0.9)';
            ctx.strokeStyle = cam.threat > 0 ? '#f43f5e' : 'rgba(255,255,255,0.22)';
            ctx.lineWidth = cam.threat > 0 ? 2.5 : 1;
            ctx.beginPath();
            ctx.roundRect(cam.x, cam.y, cam.w, cam.h, 12);
            ctx.fill();
            ctx.stroke();

            // Header label + key hint
            ctx.fillStyle = '#a1a1aa';
            ctx.font = '700 12px "JetBrains Mono", monospace';
            ctx.textAlign = 'left';
            ctx.fillText(cam.name, cam.x + 14, cam.y + 24);
            ctx.textAlign = 'right';
            ctx.fillStyle = '#ffffff';
            ctx.fillText(`[KEY ${cam.id}]`, cam.x + cam.w - 14, cam.y + 24);

            if (cam.threat > 0) {
                const ratio = cam.threat / cam.maxThreat;
                const cx = cam.x + cam.w / 2;
                const cy = cam.y + cam.h / 2 + 10;
                ctx.strokeStyle = '#f43f5e';
                ctx.lineWidth = 4;
                ctx.beginPath();
                ctx.arc(cx, cy, 34, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * ratio);
                ctx.stroke();
                ctx.fillStyle = '#ffffff';
                ctx.font = '800 13px "JetBrains Mono", monospace';
                ctx.textAlign = 'center';
                ctx.fillText('CLICK / SLAM', cx, cy + 5);
            } else {
                ctx.fillStyle = 'rgba(255,255,255,0.25)';
                ctx.font = '600 12px "JetBrains Mono", monospace';
                ctx.textAlign = 'center';
                ctx.fillText('SECTOR CLEAR', cam.x + cam.w / 2, cam.y + cam.h / 2 + 12);
            }
            ctx.restore();
        }
    }

    // =========================================================================
    // MAIN LOOP & LIFECYCLE
    // =========================================================================
    function startGame() {
        score = 0;
        combo = 1;
        hp = 3;
        timeLeft = meta.duration;
        elapsed = 0;
        shake = 0;
        particles = [];
        popups = [];

        if (gameId === 'fazbear_frenzy') initFrenzy();
        else if (gameId === 'pizza_dash') initPizzaDash();
        else if (gameId === 'laser_havoc') initLaserHavoc();
        else initNightGuard();

        running = true;
        lastTs = performance.now();
        if (overlay) overlay.classList.add('hidden');
        if (saveOverlayBtn) saveOverlayBtn.style.display = 'none';
        updateHud();
        requestAnimationFrame(loop);
    }

    function finishGame(survived) {
        running = false;
        if (survived) {
            const bonus = hp * 150;
            score += bonus;
            sfx.win();
        }
        const finalScore = Math.max(0, Math.round(score));
        updateHud();

        if (overlayBadge) overlayBadge.textContent = survived ? 'ROUND CLEARED' : 'SIGNAL LOST';
        if (overlayTitle) overlayTitle.textContent = `FINAL SCORE: ${finalScore.toLocaleString()} PTS`;
        if (overlaySub) {
            overlaySub.textContent = survived
                ? `Survived ${Math.round(elapsed)}s with ${hp} shield${hp === 1 ? '' : 's'} left! Save your score to Supabase or play again.`
                : `Lasted ${Math.round(elapsed)}s before losing all shields. Save your score or try another run!`;
        }
        if (startBtn) startBtn.textContent = 'Play Again';
        if (saveOverlayBtn) saveOverlayBtn.style.display = 'inline-flex';
        if (overlay) overlay.classList.remove('hidden');
    }

    function loop(ts) {
        if (!running) return;
        const dt = Math.min(0.05, (ts - lastTs) / 1000 || 0.016);
        lastTs = ts;

        timeLeft -= dt;
        elapsed += dt;

        ctx.save();
        if (shake > 0) {
            ctx.translate((Math.random() - 0.5) * shake, (Math.random() - 0.5) * shake);
            shake = Math.max(0, shake - dt * 36);
        }

        if (gameId === 'fazbear_frenzy') tickFrenzy(dt);
        else if (gameId === 'pizza_dash') tickPizzaDash(dt);
        else if (gameId === 'laser_havoc') tickLaserHavoc(dt);
        else tickNightGuard(dt);

        drawParticlesAndPopups(dt);
        ctx.restore();

        updateHud();

        if (hp <= 0) {
            finishGame(false);
            return;
        }
        if (timeLeft <= 0) {
            timeLeft = 0;
            finishGame(true);
            return;
        }

        requestAnimationFrame(loop);
    }

    // Input Handling
    function updatePointer(e) {
        const rect = canvas.getBoundingClientRect();
        pointer.x = ((e.clientX - rect.left) / rect.width) * W;
        pointer.y = ((e.clientY - rect.top) / rect.height) * H;
        pointer.active = true;
    }

    canvas.addEventListener('pointermove', updatePointer);
    canvas.addEventListener('pointerdown', (e) => {
        updatePointer(e);
        if (running && gameId === 'night_guard_duel' && state.cams) {
            state.cams.forEach((cam, idx) => {
                if (pointer.x >= cam.x && pointer.x <= cam.x + cam.w && pointer.y >= cam.y && pointer.y <= cam.y + cam.h) {
                    triggerCamSector(idx);
                }
            });
        }
    });
    canvas.addEventListener('pointerleave', () => { pointer.active = false; });

    window.addEventListener('keydown', (e) => {
        keys[e.code] = true;
        if (running && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(e.code)) {
            e.preventDefault();
        }
        if (running && gameId === 'night_guard_duel') {
            if (e.key === '1') triggerCamSector(0);
            if (e.key === '2') triggerCamSector(1);
            if (e.key === '3') triggerCamSector(2);
            if (e.key === '4') triggerCamSector(3);
        }
    });
    window.addEventListener('keyup', (e) => { keys[e.code] = false; });

    if (startBtn) startBtn.addEventListener('click', startGame);
    if (saveOverlayBtn && scoreForm) {
        saveOverlayBtn.addEventListener('click', () => scoreForm.submit());
    }

    // Initial idle render + dynamic instructions
    if (overlaySub) overlaySub.textContent = meta.controls;
    drawGridBackground(0);
    updateHud();
}
