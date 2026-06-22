# Pokémon Agent Project Guide & Index

**Created:** 2026-06-06
**Last updated:** 2026-06-22
**Purpose:** Comprehensive reference for project structure, components, usage, extension, and current modifications. For use by agents working on the project.

## 1. Project Structure

```
/home/toast/projects/pokemon-agent-fork/    ← This package (emulation + API + dashboard)
├── pokemon_agent/                    # Main Python package
│   ├── __init__.py
│   ├── cli.py                        # Entry point: `pokemon-agent` CLI (serve, info, play)
│   ├── server.py                     # FastAPI server (REST + WS + dashboard)
│   ├── emulator.py                   # PyBoy wrapper (headless)
│   ├── collision.py                  # RAM-derived walkability grid (10x9)
│   ├── overlay.py                    # A1..J9 grid + walkability overlay on screenshots
│   ├── pathfinding.py                # A* navigation on collision grid
│   ├── autopilot.py                  # ⚠️ ARCHIVED — Hermes autopilot driver (not active)
│   ├── sessions.py                   # Game session management
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── reader.py                 # Abstract memory reader
│   │   ├── red.py                    # Pokémon Red/Blue RAM parser (addresses from pret/pokered)
│   │   └── firered.py                # FireRed parser (Phase 2, partial)
│   ├── state/
│   │   ├── __init__.py
│   │   └── builder.py                # Structured JSON state from reader (party, map, battle, etc.)
│   └── dashboard/
│       ├── __init__.py
│       ├── mount.py                  # FastAPI static + WS mount for /dashboard
│       ├── history.py                # JSONL event logger for Field Log
│       └── static/
│           ├── index.html            # Dashboard UI (react-like, WS client)
│           ├── style.css             # Dark cyberpunk theme
│           └── app.js                # Live updates, grid toggle, controls, streaming token console
├── skill/
│   └── SKILL.md                      # ⚠️ ARCHIVED — Hermes `pokemon-player` skill definition
├── AGENT_CONTEXT.md                  # Agent gameplay knowledge (RAM, navigation, battle)
├── README.md                         # User-facing docs (API, quickstart, architecture)
├── pyproject.toml                    # Package config (v0.1.0, extras: pyboy, dashboard, autopilot)
├── .gitignore
└── .venv/                            # Local virtualenv (python 3.11)

/home/toast/projects/pokemon-standalone-agent/  ← Agent logic (LLM, memory, nav, battle)
├── src/
│   ├── main_loop.py                  # Agent loop (nav, battle, dialog, critique)
│   ├── agents.py                     # NavigationAgent, BattleAgent, GuideAgent, CritiqueAgent
│   ├── llm/
│   │   ├── client.py                 # LLM client with vision fallback
│   │   ├── agents.py                 # Agent prompt builders
│   │   └── prompts.py                # Prompt templates (nav, battle, dialog, guide)
│   └── memory/
│       ├── store.py                  # PokemonMemory class (warps, items, battle logs, dialog facts, map knowledge)
│       └── retrieval.py              # RAG retrieval (keyword + recency scoring)
├── memory/                           # Persisted JSON memory stores
│   ├── warps.json                    # Discovered warp connections
│   ├── items.json                    # Found items
│   ├── battle_logs.json              # Battle history
│   ├── dialog_facts.json             # NPC dialog knowledge
│   ├── map_knowledge.json            # Per-map tile/exploration data
│   └── opponent_models.json          # Trainer/Pokémon models
├── guide.json                        # Objectives, hints, completion conditions
├── config.yaml                       # LLM provider, models, vision fallback
└── README.md
```

**Notes on structure:**
- This package (`pokemon-agent-fork`) is the **emulation + API + dashboard layer**.
- Agent logic lives in the sibling `pokemon-standalone-agent` project.
- Data persisted under `~/.pokemon-agent/games/<session>/` (saves, objectives, stats).
- Git repo with recent commits focused on navigation hardening, memory wiring, streaming, and dialog handling.

## 2. Key Components

### Core Runtime
- **emulator.py**: Abstract `Emulator` base + PyBoy implementation. Handles `press()`, `tick()`, `get_screen()`, `save_state()`, `load_state()`, memory peek. Headless by design (no X11).
- **memory/reader.py + red.py**: `PokemonRedReader` parses RAM addresses (D35E=map, D361/D362=XY, D163+=party, D057=battle, etc.). Returns dicts for state builder. FireRed partial.
- **state/builder.py**: `build_game_state(reader)` → clean JSON with `player`, `party`, `bag`, `battle`, `dialog`, `flags`, `collision` (10x9 grid from collision.py), `metadata`.
- **collision.py**: Builds walkability grid (`@` player, `.` walkable, `#` blocked) from tileset + map data.
- **overlay.py**: Draws labelled A1-J9 grid + tint on screenshots for agent vision.
- **pathfinding.py**: A* on the collision grid for navigation helpers.

### Server & API (server.py)
- FastAPI app with CORS, startup hook that loads ROM + emulator + reader.
- Global state: `_emulator`, `_reader`, `_objectives`, control state (`running`/`paused`/`stopped`).
- Sessions support via `sessions.py` (new/load games bind Hermes session + save-states).
- WebSocket `/ws` for real-time events.
- Dashboard mounted at `/dashboard` (if extra installed).

### CLI & Drivers (cli.py, autopilot.py, pokemon_agent.py)
- **cli.py**: `serve`, `info`, `play`.
- **autopilot.py**: `HermesDriver` class. Polls `/control`, runs wake sequence, stuck detection, auto-save. Invokes `hermes chat --resume <id> -s pokemon-player --image <grid> -q "<state>"`. Hermes then POSTs `/action`, `/event`, `/objectives`.
- **pokemon_agent.py** (root): Standalone Ollama loop (OpenAI client to localhost:11434). Uses custom system prompt with Red's House specifics, dialog rules, stuck recovery. Logs to /tmp. Recently updated (see §5).

### Dashboard
- Editorial "Field Log" UI: reasoning stream, live screenshot/grid toggle, party, objectives, telemetry (stuck meter, counters), milestones.
- Pushes via `POST /event` (type: reasoning/decision/key_moment/alert).
- Controls: START/PAUSE/STOP via `/control`.

### Other
- **sessions.py**: Manages game sessions, Hermes binding, save-state scoping.
- Tests cover movement, collision, facing, server, imports, species mapping, timing.

## 3. How to Run Server and Agent

### Prerequisites
- ROM file (user-provided, e.g. `pokemon_red.gb`).
- `pyboy` installed.
- For dashboard: `pokemon-agent[dashboard]`.

**Install (in project):**
```bash
cd /home/toast/projects/pokemon-agent-fork
source .venv/bin/activate
pip install -e ".[pyboy,dashboard]"
```

### Run Server
```bash
pokemon-agent serve --rom /path/to/pokemon_red.gb --port 8765 --data-dir ~/.pokemon-agent
```

Output banner shows API at `http://localhost:8765`, dashboard at `/dashboard`, WS at `/ws`.

**Key endpoints** (see README or server.py for full):
- `GET /state` — full JSON state + collision grid.
- `GET /screenshot`, `/screenshot/grid`, `/screenshot/base64`
- `GET /map/ascii`, `/minimap`
- `POST /action` — `{"actions": ["walk_up", "press_a", ...]}`
- `POST /event` — push narration to dashboard.
- `GET/POST /objectives`
- `GET/POST /control` — autopilot state (archived).
- `/games/new`, `/games/{id}/load`, `/games/current`
- `/save`, `/load`, `/saves`
- `GET /health`

### Run the Agent

The agent runs from the sibling `pokemon-standalone-agent` project. See that project's README for details.

> **Note:** The `pokemon-agent play` CLI command (Hermes autopilot driver) is **archived** and not the active workflow.

## 4. How to Extend Endpoints

All endpoints live in `pokemon_agent/server.py`.

**Pattern to add a new endpoint:**
1. Define Pydantic model if needed (e.g. `class FooRequest(BaseModel): ...`).
2. Add route after existing ones (around line 500+):
   ```python
   @app.get("/new/endpoint")
   async def new_endpoint(param: str = "default"):
       _ensure_emulator()
       # use _emulator, _reader, _objectives, etc.
       return {"result": ...}
   ```
   Or POST:
   ```python
   @app.post("/new/endpoint")
   async def new_endpoint(req: FooRequest):
       ...
       # Broadcast if needed: await _broadcast_event(...)
   ```
3. For WebSocket or dashboard updates, use existing `_broadcast_event` or history logger.
4. Update `configure()` if new config needed.
5. Test with `test_server.py` or manual curl.
6. Document in README.md API table and this guide.
7. For new game-specific logic, extend `memory/red.py` or `state/builder.py` first.

**Example extension ideas:**
- `/minimap/enhanced` with pathfinding overlay.
- `/battle/analyze` using type chart from state.
- New control for speed multiplier.

**Important:** Server uses global singletons; keep thread-safe with `_run_sync` for emulator calls. Startup is in `@app.on_event("startup")`.

## 5. Reference for Current Modifications

**Last updated:** 2026-06-22

### Active Components
- `server.py` — FastAPI server with sound_emulated=False (fixes buffer overrun spam), raised FD limit (65536) for agent subprocess.
- `emulator.py` — PyBoy wrapper, headless.
- `collision.py` — RAM walkability grid with `@` (player), `.` (walkable), `#` (blocked), `D` (doormat/warp tile).
- `state/builder.py` — Structured JSON state (party, map, battle, dialog, collision).
- `dashboard/` — Field Log UI with streaming token console, grid toggle, objectives, telemetry.

### Agent Logic (in pokemon-standalone-agent)
- `src/main_loop.py` — Agent loop with A* path suggestions, oscillation detection, visited tiles tracking, building exit nudges, dialog summary, battle button sequences, streaming token output.
- `src/agents.py` — NavigationAgent (with rolling 4-turn history), BattleAgent (hardcoded B-press sequences), GuideAgent (with memory context), CritiqueAgent (with party health + exact map names).
- `src/llm/client.py` — LLM client with vision fallback, context-managed HTTP sessions (no FD leaks).
- `src/memory/store.py` — PokemonMemory with warps, items, battle logs, dialog facts, map knowledge, opponent models.
- `src/memory/retrieval.py` — Lightweight RAG (keyword + recency scoring).
- `config.yaml` — Primary model, model list, vision fallback models.
- `guide.json` — Objectives with hints, exact map names for completion matching.

### Recent Changes (June 2022)
- **P0 Memory wiring:** `record_warp()` on map transitions, `update_map_knowledge()` for explored tiles, `end_battle()` populates opponent models, Guide agent gets memory context, battle agent gets battle history summary.
- **Navigation hardening:** A* path shown in prompt, ping-pong oscillation detection, visited tiles per map, building exit nudges.
- **Streaming console:** Live LLM tokens pushed to dashboard (nav=blue, battle=red, dialog-vision=gold).
- **Vision fallback:** Config-driven fallback to vision-capable models on 404/429 errors.
- **Sound fix:** `sound_emulated=False` + logger suppression eliminates buffer overrun spam.
- **FD leak fix:** All `requests.post()` calls wrapped in `with` context managers; FD limit raised to 65536.
- **Battle sequences:** Hardcoded B,B at battle start; move-specific A/DOWN/B combos with waits.

### Archived Components
- `autopilot.py` — Hermes autopilot driver (not active, retained for reference).
- `skill/SKILL.md` — Hermes `pokemon-player` skill (archived).
- `pokemon_agent.py` (root) — Standalone Ollama loop (removed from active use).
- `AGENT_CONTEXT_REFERENCE.md` — Duplicate of AGENT_CONTEXT.md (can be removed).

### Recommendations for Further Work
- P1: Objective-level summaries, persist visited tiles into MapKnowledge, strengthen RAG retrieval.
- P1: Clean up archived components (autopilot.py, skill/SKILL.md, AGENT_CONTEXT_REFERENCE.md).
- P1: Graph-based spatial memory (NetPlay room partitioning, TME DAG).
- P2: Early-exit verifiers (OpenHands patterns, SPR tracking).
- P2: Expand FireRed reader.