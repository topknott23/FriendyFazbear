/* ============================================================
   FRIENDY FAZBEAR — INTERACTIVE CONSOLE JS
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
    initToasts();
    initPasswordToggles();
    initCopyButtons();
    initSettingsControls();
    initProfilePreview();
    initNotificationPolling();
    initLobbyPolling();
    initArenaPartySync();
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
            btn.textContent = showing ? 'Show' : 'Hide';
            btn.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
            btn.classList.toggle('is-visible', !showing);
        });
    });
}

/* 3. Copy Lobby Room Code & Pair Link */
async function copyText(value) {
    try {
        await navigator.clipboard.writeText(value);
    } catch {
        const tmp = document.createElement('input');
        tmp.value = value;
        document.body.appendChild(tmp);
        tmp.select();
        document.execCommand('copy');
        tmp.remove();
    }
}

function initCopyButtons() {
    const codeBtn = document.getElementById('copyRoomCodeBtn');
    if (codeBtn) {
        codeBtn.addEventListener('click', async () => {
            await copyText(codeBtn.getAttribute('data-code') || '');
            const label = codeBtn.querySelector('span');
            if (label) {
                const prev = label.textContent;
                label.textContent = 'Copied!';
                setTimeout(() => { label.textContent = prev; }, 1600);
            }
        });
    }

    const linkBtn = document.getElementById('copyJoinLinkBtn');
    if (linkBtn) {
        linkBtn.addEventListener('click', async () => {
            await copyText(linkBtn.getAttribute('data-url') || '');
            const label = linkBtn.querySelector('span');
            if (label) {
                const prev = label.textContent;
                label.textContent = 'Link Copied!';
                setTimeout(() => { label.textContent = prev; }, 1600);
            }
        });
    }
}

/* 4. Settings: Live Sliders + Live Theme Preview */
function initSettingsControls() {
    document.querySelectorAll('.arcade-range').forEach((slider) => {
        const update = () => {
            const val = Number(slider.value);
            const target = document.getElementById(slider.dataset.output);
            if (target) target.textContent = `${val}%`;
            slider.style.background = `linear-gradient(90deg, var(--accent) 0%, var(--accent) ${val}%, rgba(255,255,255,0.12) ${val}%)`;
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

/* 6. Live Crew Notification Badge Polling */
function initNotificationPolling() {
    const nav = document.querySelector('[data-notif-poll]');
    const badge = document.getElementById('crewNotifBadge');
    if (!nav || !badge) return;

    const url = nav.getAttribute('data-notif-poll');

    async function pollNotifications() {
        if (document.hidden) return;
        try {
            const res = await fetch(url, { headers: { Accept: 'application/json' } });
            if (!res.ok) return;
            const data = await res.json();
            const count = Number(data.crew_notifications || 0);
            badge.textContent = count > 99 ? '99+' : String(count);
            badge.classList.toggle('hidden', count <= 0);
            badge.setAttribute('aria-label', `${count} pending crew notifications`);
        } catch {
            // Ignore transient polling errors
        }
    }

    setInterval(pollNotifications, 5000);
}

/* 7. Live Lobby Controller Polling + Auto-Launch When Host Picks a Game */
function initLobbyPolling() {
    const lobbySection = document.querySelector('[data-room-poll]');
    const badge = document.getElementById('slotCountBadge');
    if (!lobbySection || !badge) return;

    const pollUrl = lobbySection.getAttribute('data-room-poll');
    const isHost = lobbySection.getAttribute('data-is-host') === '1';
    let lastSignature = '';

    async function pollRoom() {
        if (document.hidden) return;
        try {
            const res = await fetch(pollUrl, { headers: { Accept: 'application/json' } });
            if (!res.ok) return;
            const data = await res.json();

            // Non-host crew members automatically follow when the host launches a game!
            if (!isHost && data.status === 'in_game' && data.arena_url) {
                window.location.href = data.arena_url;
                return;
            }
            if (!isHost && data.status === 'closed') {
                window.location.reload();
                return;
            }

            badge.textContent = `${data.player_count} / ${data.max_players} Slots`;
            const sig = JSON.stringify(data.slots.map((s) => [s.slot_number, s.occupied, s.player_alias, s.is_ready]));
            if (lastSignature && sig !== lastSignature) {
                window.location.reload();
            }
            lastSignature = sig;
        } catch {
            // Silently ignore transient network blips
        }
    }

    pollRoom();
    setInterval(pollRoom, 2500);
}

/* 8. Live Arena Party Sync (Auto-Switch Game, 3s Synced Countdown & Live Standings) */
function initArenaPartySync() {
    const root = document.getElementById('arenaSyncRoot');
    if (!root) return;

    const pollUrl = root.getAttribute('data-arena-poll');
    const isParty = root.getAttribute('data-is-party') === '1';
    const isHost = root.getAttribute('data-is-host') === '1';
    const currentGame = root.getAttribute('data-current-game') || '';
    const currentMatchId = root.getAttribute('data-match-id') || '';
    const currentMatchStatus = root.getAttribute('data-match-status') || '';
    const mySubmitted = root.getAttribute('data-my-submitted') === '1';
    const currentScoreCount = Number(root.getAttribute('data-score-count') || 0);

    function isRoundOrCountdownActive() {
        if (typeof window.fazbearIsActive === 'function') {
            return window.fazbearIsActive();
        }
        const overlay = document.getElementById('canvasOverlay');
        return overlay && overlay.classList.contains('hidden');
    }

    async function pollArenaRoom() {
        if (document.hidden) return;
        try {
            const res = await fetch(pollUrl, { headers: { Accept: 'application/json' } });
            if (!res.ok) return;
            const data = await res.json();

            // Non-host syncs immediately when Host switches games, returns to lobby, or starts a new round
            if (!isHost) {
                if (data.status === 'waiting' || data.status === 'closed') {
                    window.location.href = data.lobby_url || '/';
                    return;
                }
                if (data.current_game_id && data.current_game_id !== currentGame && data.arena_url) {
                    window.location.href = data.arena_url;
                    return;
                }
                if (data.active_match_id && String(data.active_match_id) !== String(currentMatchId)) {
                    window.location.reload();
                    return;
                }
            }

            // Synchronized 3-2-1-GO! Start when Host presses Start Party Round
            if (
                isParty &&
                !mySubmitted &&
                data.active_match_status === 'ongoing' &&
                data.round_start_at &&
                data.starts_in_ms !== null &&
                data.starts_in_ms !== undefined &&
                typeof window.fazbearTriggerSyncedCountdown === 'function'
            ) {
                window.fazbearTriggerSyncedCountdown(String(data.active_match_id), Number(data.starts_in_ms));
            }

            // Refresh live Party Match Standings when a teammate submits a score or match finishes
            // (never interrupt mid-countdown or mid-gameplay!)
            if (!isRoundOrCountdownActive() && data.player_count > 1) {
                const newCount = Array.isArray(data.match_scores) ? data.match_scores.length : 0;
                const statusChanged = data.active_match_status && data.active_match_status !== currentMatchStatus;
                if (newCount !== currentScoreCount || statusChanged) {
                    window.location.reload();
                }
            }
        } catch {
            // Ignore transient polling errors
        }
    }

    // Poll faster (800ms) in Party Mode so crew members catch the host's 3-2-1 countdown almost instantly
    const intervalMs = isParty ? 800 : 2500;
    pollArenaRoom();
    setInterval(pollArenaRoom, intervalMs);
}
