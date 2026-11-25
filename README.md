# Friendy Fazbear — Multiplayer Arcade Console

**Friendy Fazbear** is a full-stack Django multiplayer arcade lobby and Canvas 2D mini-game hub inspired by couch co-op party consoles. Players can host 4-player rooms with unique 4-digit PIN codes, pair local or remote controllers, compete across 4 playable HTML5 Canvas 2D mini-games with synthesized Web Audio SFX & chiptune music, manage a mutual Crew roster, customize console themes, and climb global and crew leaderboards.

---

## Key Features

- **Authentication & Player Identity**
  - Sign in with username or email, register with automatic `#FAZ-XX` gamer tag provisioning, password visibility toggles, and CSRF-protected sign-out.
  - Customizable Player Profile with 6 character avatars, live preview card, favorite game selector, and per-game Personal Bests.
- **Multiplayer Lobby & Controller Pairing**
  - Automatic 4-digit Room Code generator with one-click copy code, shareable pairing URL (`/join/<code>/`), local couch co-op pad pairing, host kick controls, Ready/Standby toggles, and live JSON polling (`/api/room/<code>/`).
  - Supports authenticated players and guest mobile/device controllers while enforcing the host's `Public`, `Friends Only`, or `Private` lobby privacy setting.
- **4 Playable Canvas 2D Arcade Mini-Games**
  1. **Fazbear Frenzy** — Top-down 360° survival tag (collect Faz-Tokens while dodging stalking hunters).
  2. **Pizza Dash Sprint** — High-speed 4-lane runner & catcher (catch pizza slices & VIP slices, dodge burnt pans).
  3. **Laser Havoc Arena** — 360° chrome deflector shield brawler (reflect incoming lasers before they hit the core).
  4. **Night Guard Duel** — 4-sector security camera blast-door reflex game (click sectors or press keys `1`–`4`).
  - Built-in Web Audio API SFX synthesizer, optional retro chiptune music loop, Pause/Resume (`P`/`Esc`), per-game top scores, and automatic rank placement.
- **Social Crew & Leaderboards**
  - Two-way Crew friend requests (send invite by username or `#FAZ` tag, Accept/Decline incoming invites, Cancel pending invites, remove mutual friends).
  - Global and Crew-filtered leaderboards tracking wins, match count, and cumulative score.
- **Console Settings & Live Themes**
  - Audio mixer (`Master`, `SFX`, `Music`) wired directly into the Arena Web Audio engine.
  - 4 live-switching console themes: **Fazbear Dark**, **Neon Cyberpunk**, **Retro 80s Arcade**, and **Midnight Emerald**.
- **Database & Admin**
  - Uses local SQLite by default and automatically switches to Supabase PostgreSQL when `DATABASE_URL` is configured in `.env`.
  - Full Django Admin registration for all 8 core models.

---

## Local Setup

```bash
cd friendy-fazbear

# 1. Create and activate a virtual environment
python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
# source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply database migrations
python manage.py migrate

# 4. (Optional) Create an admin superuser
python manage.py createsuperuser

# 5. Start the development server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your browser.

---

## Supabase / PostgreSQL Configuration (Optional)

Copy `.env.example` to `.env` inside `friendy-fazbear/` and set your database credentials:

```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_PUBLISHABLE_KEY=your-publishable-key
DATABASE_URL=postgresql://postgres.your-project-ref:YOUR-PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres
```

Then run `python manage.py migrate`.

---

## Running Automated Tests

```bash
cd friendy-fazbear
python manage.py test -v 2
```
