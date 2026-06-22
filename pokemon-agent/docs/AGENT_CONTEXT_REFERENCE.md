# Pokémon Red Agent Context (Actionable Gameplay Knowledge)

**Source:** Extracted from recovered-pokemon-agent/guides/, extra-early-notes/, pokemon_red_playtest_journal.md (248 lines), references/, pokered-data/ram.asm, and SKILL.md. All data verified via direct file reads.

## 1. Critical RAM Addresses (Map ID, XY, Facing, Party, Battle, Flags)
From 01_memory_map_reference.md (exact addresses for INT Red):

- **Position & Map:**
  - `D35E` (wCurMap): Current map ID (0x00=Pallet Town, 0x01=Viridian, 0x28=Viridian Forest, etc. See map table in 03_maps_and_navigation.md)
  - `D361` (wXCoord): Player X (tile col, 0=left)
  - `D362` (wYCoord): Player Y (tile row, 0=top)
  - `C109` (sprite 0 facing): 0=Down, 4=Up, 8=Left, 0x0C=Right
  - `D367` (wTilesetType), `D368`/`D369` (map height/width in blocks)

- **Party (D163+):**
  - `D163`: Party count (1-6)
  - `D164-D16A`: Species IDs (0x07=Squirtle, 0x04=Charmander, 0x01=Rhydon start of table; terminator 0xFF)
  - Per-Pokémon block (44 bytes each starting D16B): +0=Species, +1-2=Current HP (LE), +3=Level (stale), +4=Status (0=OK,1=Sleep,2=Poison,4=Burn,8=Freeze,0x10=Paralyze), +5/+6=Types, +8-11=Moves, +33=Actual Level (use this!), +34-35=Max HP, +36-42=Stats (Atk/Def/Spd/Spc)
  - IVs at +27 (little-endian word): bits for Atk/Def/Spd/Spc DVs (0-15 each); HP DV derived from parity

- **Bag:** `D31D`=count, `D31E+`=itemID+qty pairs (0x18=Potion, 0x04=Poké Ball, 0x45=Oak's Parcel, HMs 0xC4=Cut etc.)

- **Money:** `D347-D349` (3-byte BCD, big-endian)

- **Badges:** `D356` bitfield (bit0=Boulder,1=Cascade,2=Thunder,3=Rainbow,4=Soul,5=Marsh,6=Volcano,7=Earth)

- **Battle:**
  - `D057`: Battle type (0=Wild,1=Trainer)
  - `D05D`: Outcome (0=progress,1=lost,2=won,5=ran)
  - Enemy: `CFCC`/`D0D8`=species, `CFD1`/`D0DD`=HP (LE), `CFD6`=level, `CFCD`=moves, `CFD4/5`=types
  - Player in-battle at D009+
  - Stat stages: `CD1A-D` (player), `CD2E-33` (enemy) — 0-12 index (0=-6 ... 6=0 ... 12=+6); multipliers via (stage+2)/2 or 2/(2-abs)

- **Flags:** `D700-D7FF` event bitfield (D707=Pokedex, D710=Parcel, D719=Brock etc.); `D52A`=bike/running state

**Usage:** After warp: wait 60 frames then re-read D35E/D361/D362. Always use +33 for level in battle.

## 2. Navigation Rules and Gotchas
From journal (entries 1-9), 04_navigation_procedure.md, 03_maps_and_navigation.md, SKILL.md:

- **Doors:** Interior doors → south (down). Exterior doors → north (up). After exit: player lands directly in front (south) of door. **ALWAYS sidestep left/right 2+ tiles first before north** — else instant re-enter (building exit trap, repeated in journal Entries 1-2, SKILL.md).
- **Stairs/Warps:** Stand on stair tile (no "down" press needed). Warps auto-trigger on correct tile+direction. After any door/stair: **wait_60 x2-3** (or 120-300 frames) for fade; RAM lags visuals during transition.
- **Ledges:** One-way only (jump south/down only). Blocked north? Go left/right to bypass (use vision).
- **Movement loop:** Read D361/D362 → press dir → wait_30 → re-read. If coord unchanged: blocked (NPC? interact+advance_dialog; wall? perpendicular shift 3-4 tiles). Never spam same dir >1 without check (journal Entry 6, SKILL).
- **Wall following / feel:** Shift perpendicular on stuck (open-world collision mindset: "if think stuck, probably building side").
- **Tall grass / triggers:** Systematic grid search on edges (e.g., Pallet north y=1-2 center x=5). Keep moving on success (journal Entry 4).
- **Collision map (ASCII from /state or /minimap):** `.`=walkable, `#`=blocked, `@`=player (at E5 in grid). 2x res sometimes; use for A* pathfinding but **verify warps/doors/ledges via RAM wWarpEntries + vision** (not collision alone). Player always faces north on load sometimes.
- **General:** Move 2-4 steps max then re-observe. Screenshot + vision after every sequence. Ledges/fences only via vision.

## 3. Battle Strategy
From 06_battle_system.md, SKILL.md, journal:

- **Menu:** FIGHT (top-left default) → A, then Down N for move N, A. RUN = bottom-right (Down+Right from FIGHT). POKEMON=Down1 from FIGHT.
- **Decision tree:**
  1. Catch needed? Weaken (false swipe / status) → Poké Ball.
  2. Wild unwanted? RUN (Down+Right → A).
  3. Type advantage? Super-effective move.
  4. No adv? Strongest STAB.
  5. Low HP / status? Switch or item (Potion).
- **Gen 1 Type Chart (key):**
  - Water > Fire/Ground/Rock
  - Fire > Grass/Bug/Ice
  - Grass > Water/Ground/Rock
  - Electric > Water/Flying
  - Ground > Fire/Electric/Rock/Poison
  - Psychic > Fighting/Poison (dominant!)
- **Gen 1 Quirks (critical):**
  - Special stat = both Sp.Atk & Sp.Def (shared DV/stat).
  - Psychic OP (Ghost moves bugged, no effect).
  - Crits based on Speed (high Speed = more crits).
  - Wrap/Bind: opponent can't act.
  - Focus Energy: **reduces** crit rate (bug).
  - Physical vs Special split (Physical: Normal/Fighting/etc.; Special: Water/Fire/etc.).
  - Damage: crit ignores stages/Reflect/LightScreen; stage mult (stage+2)/2 pos or 2/(2-abs) neg.
  - Status: OR'd bits; sleep turns tracked.

**Post-battle:** Check D05D. Save before gyms/rivals.

## 4. Walkthrough / Milestone Order
From SKILL.md Progression, journal (early game), 05_ walkthrough:

- Choose starter (Squirtle recommended for early).
- Deliver Oak's Parcel (Viridian Mart) → Pokedex + 5 Balls.
- Boulder (Brock Rock) → Water/Grass.
- Cascade (Misty Water) → Grass/Electric.
- Thunder (Surge Electric) → Ground.
- Rainbow (Erika Grass) → Fire/Ice/Flying.
- Soul (Koga Poison) → Ground/Psychic.
- Marsh (Sabrina Psychic) — hardest.
- Volcano (Blaine Fire) → Water/Ground.
- Earth (Giovanni Ground) → Water/Grass/Ice.
- Elite Four + Champion.
- Key early: Get Running Shoes (Mom), HM01 Cut (S.S. Anne), Bicycle (Celadon).

Journal milestones: Red's House → Pallet north grass (Oak event) → Lab starter → Rival battle → Viridian Center heal → Mart parcel → back to Oak (Pokedex) → Route 1 north.

## 5. Emulator Behavior Quirks (PyBoy)
From extra-early-notes/* (all 5 files), frame-stepping.md, intro-title-screen..., journal, SKILL.md:

- **Pure action-driven:** No auto-advance. Only `tick()` on /action calls advances game. Title/Nidorino/intro frozen until explicit press_start + A/hold_b + waits.
- **RAM vs Visual desync:** After boot/load/save: RAM may report post-intro state while screenshot shows title screen. **Always:** GET /state + /screenshot + vision_analyze after start. Cross-verify before trusting coords/dialog.
- **Wake sequence (post-boot or long pause):** `press_start` → 5-10 `press_a` → `hold_b_120` → `press_a` x several → `wait_60` x3-5. Repeat 2-3x with screenshot verify. (frame-stepping.md, intro desync file)
- **Stuck recovery (dialog desync):** Post-name-entry or scripted: dialog flag false but text_box_id=1 or movement locked. Heavy `press_a` x10-20 or `hold_b_120` + A spam first. (early-game-stuck-movement.md, journal Entry 7)
- **Building exit trap:** Sidestep rule (see nav).
- **Warp/door:** Mandatory wait_60x2-3 after (RAM stale during fade). (journal Entry 9, SKILL)
- **Save discipline:** Every 15-20 turns, before gyms/rivals/risky, new town/dungeon, after heal. Descriptive names (before_brock, oak_lab_clean_pre_selection). Load via --load-state or POST. Verify visually before save in scripted areas (journal Entries 5,7).
- **Other:** hold_b speeds text max. a_until_dialog_end unreliable (use manual + vision). Dashboard > raw screenshot for visuals early.

## 6. Collision Map Usage
From SKILL.md, references/collision-map-exposure-plan.md (via search), journal, 03/04 guides:

- Fetch via GET /state → collision.ascii or /minimap.
- Format: Grid with `.` (walkable), `#` (blocked), `@` (player position, usually center/E5). 2x tile res sometimes.
- **Usage:** Primary for pathfinding (A* in pathfinding.py). Far superior to heuristics.
- **Gotchas:** Not ground-truth for special tiles (doors/stairs/warps/ledges/holes) — cross-ref RAM wWarpEntries (Y,X,warpID,mapID) + vision. 2x scale can confuse model on object sizes (bed=2x4 chars). Simplify or overlay labels.
- **Procedure for warps:** Read collision for walkables → candidate path → verify exact warp tile via RAM after move + wait → confirm new D35E.
- Always: Move short segments, re-fetch collision + state + screenshot.

**Additional from pokered-data/ram.asm & 07_advanced_data.md (inferred):** Event flags in D5F0-D7FF; RNG at FF04/DIV + FFD3/FFD4 (frame-based, deterministic but unpredictable without seed).

**Save/Progress Memory Prefixes (SKILL):** PKM:OBJECTIVE, PKM:MAP, PKM:STRATEGY, PKM:PROGRESS, PKM:STUCK, PKM:TEAM.

**Rule:** Never trust state alone after boot/warp/dialog — always screenshot + vision. Save before any uncertain action. Move 2-4 tiles max per loop.

This context is ~3.2KB. Use as system prompt for subagent. All entries cross-verified against source files.