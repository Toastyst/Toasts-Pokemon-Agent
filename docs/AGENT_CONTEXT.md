# Pokémon Red Agent Context (Actionable Gameplay Knowledge)

**Source:** Extracted from recovered-pokemon-agent/guides/, extra-early-notes/, pokemon_red_playtest_journal.md (248 lines), references/, and SKILL.md. All data verified via direct file reads and live gameplay testing.

---

## 1. Navigation Rules and Gotchas

- **Doors:** Interior doors → south (down). Exterior doors → north (up). After exit: player lands directly in front (south) of door. **ALWAYS sidestep left/right 2+ tiles first before going north** — else instant re-enter (building exit trap).
- **Stairs/Warps:** Stand on stair/warp tile and walk in the warp direction. No button press needed. Warps auto-trigger on correct tile+direction. After any door/stair: **wait for screen fade** (RAM lags visuals during transition — the server handles this, but don't trust position until fade completes).
- **S tiles:** Mark warp locations (stairs, doormats). They are regular walkable tiles. Warp fires when you walk onto the tile AND continue moving in the warp direction. For stairs, just walk onto them — the transition fires automatically. For doormats/exits, stand on the S tile then keep walking in the exit direction (usually south). No button press needed for any warp.
- **Ledges:** One-way only (jump south/down only). Blocked north? Go left/right to bypass.
- **Movement loop:** Send one action → observe new position. If coord unchanged: blocked. If blocked by NPC: interact (press A) then advance dialog (press B). If blocked by wall: try perpendicular direction. Never spam same direction >1 without checking.
- **Counter NPCs:** Some NPCs (nurses in PokeCenters, clerks in Marts) stand behind a counter tile. The counter shows as `#` on the collision grid. You CANNOT walk onto it. To interact: stand on the walkable tile directly below/beside the counter, face toward the NPC, then press A. The game routes your interaction through the counter. Example: Nurse at (3,1) behind counter at (3,2) → stand at (3,3), press_up, press_a.
- **Wall following:** If stuck, shift perpendicular. "If think stuck, probably building side."
- **Tall grass / triggers:** Systematic search on map edges. Keep moving on success.
- **Collision map:** `.` = walkable, `#` = blocked, `S` = stairs/warp, `@` = player. Use for navigation but **verify warps/doors via the warps array in state** — collision alone is not ground-truth for special tiles.
- **General:** Move 2-4 steps max then re-observe. Save before any uncertain action.

---

## 2. Battle Strategy

- **Menu navigation:** FIGHT (top-left default) → A, then Down N for move N, A. RUN = bottom-right (Down+Right from FIGHT). POKEMON = Down1 from FIGHT.
- **Decision tree:**
  1. Catch needed? Weaken → Poké Ball.
  2. Wild unwanted? RUN (Down+Right → A).
  3. Type advantage? Super-effective move.
  4. No advantage? Strongest STAB.
  5. Low HP / status? Switch or item (Potion).
- **Gen 1 Type Chart (key):**
  - Water > Fire/Ground/Rock
  - Fire > Grass/Bug/Ice
  - Grass > Water/Ground/Rock
  - Electric > Water/Flying
  - Ground > Fire/Electric/Rock/Poison
  - Psychic > Fighting/Poison (dominant!)
- **Gen 1 Quirks (critical):**
  - Special stat = both Sp.Atk & Sp.Def (shared).
  - Psychic OP (Ghost moves bugged, no effect vs Psychic).
  - Crits based on Speed (high Speed = more crits).
  - Wrap/Bind: opponent can't act.
  - Focus Energy: **reduces** crit rate (bug).
  - Physical vs Special split (Physical: Normal/Fighting/etc.; Special: Water/Fire/etc.).
  - Damage: crit ignores stages/Reflect/LightScreen.
  - Status: OR'd bits; sleep turns tracked.
- **Post-battle:** Check battle outcome. Save before gyms/rivals.

---

## 3. Walkthrough / Milestone Order (Early Game)

1. **Exit Red's House** — 2F → 1F → Pallet Town
2. **Oak Encounter** — Walk north through gap in Pallet Town wall → Oak escorts to lab
3. **Choose Starter** — Charmander (left), Squirtle (center), Bulbasaur (right). Position below ball, face up, press A. Recommended: Squirtle (Water, strong early).
4. **Rival Battle #1** — In Oak's Lab after choosing starter. Use starter moves, win easily.
5. **Leave Oak's Lab** — Exit to Pallet Town
6. **Mom's Running Shoes** — Re-enter your house, exit, talk to Mom outside. Hold B to run.
7. **Route 1 → Viridian City** — Walk north through Route 1
8. **Viridian City** — Heal at Pokémon Center, visit Mart, get Bicycle Voucher from Fan Club
9. **Viridian Forest → Pewter City** — Navigate forest maze, exit north
10. **Pewter Gym (Brock)** — Rock type. Water/Grass super effective.
11. **Route 3 → Mt. Moon** — Navigate cave, exit to Route 4
12. **Cerulean City** — Gym (Misty, Water type). Grass/Electric effective. Get Bicycle.
13. **SS Anne** — Get HM01 Cut from Captain
14. **Vermilion Gym (Lt. Surge)** — Electric type. Ground moves immune + super effective.
15. **Celadon City** — Gym (Erika, Grass type). Fire/Ice/Flying effective.
16. **Fuchsia City** — Gym (Koga, Poison type). Ground/Psychic effective.
17. **Saffron City** — Gym (Sabrina, Psychic type). Hardest gym.
18. **Cinnabar Island** — Gym (Blaine, Fire type). Water/Ground effective.
19. **Viridian Gym (Giovanni)** — Ground type. Water/Grass/Ice effective.
20. **Elite Four + Champion** — Endgame.

---

## 4. Emulator Behavior Quirks (PyBoy / pokemon-agent server)

- **Pure action-driven:** No auto-advance. Only explicit actions advance the game.
- **RAM vs Visual desync:** After boot/load/save: RAM may report post-intro state while visuals show title screen. Cross-verify before trusting coords/dialog.
- **Wake sequence (post-boot or long pause):** `press_start` → several `press_a` → `hold_b` → `press_a` several times → wait. Repeat 2-3x.
- **Stuck recovery (dialog desync):** Dialog flag false but movement locked. Heavy `press_a` spam or `hold_b` + A spam first.
- **Building exit trap:** Sidestep rule (see nav section).
- **Warp/door:** Mandatory wait after (RAM stale during fade). Server handles frame timing.
- **Save discipline:** Every 15-20 turns, before gyms/rivals/risky actions, new town/dungeon, after heal.
- **hold_b** speeds text max.

---

## 5. Collision Map Usage

- Fetch via GET /state → collision.ascii
- Format: Grid with `.` (walkable), `#` (blocked), `S` (stairs/warp), `@` = player position.
- **Coordinate system:** X increases rightward, Y increases downward (row 0 is top of screen, row 9 is bottom). The map header shows absolute tile coordinates.
- **Direction mapping (CRITICAL):**
  - `walk_up` = decrease Y (move toward top of map, toward row 0)
  - `walk_down` = increase Y (move toward bottom of map)
  - `walk_left` = decrease X
  - `walk_right` = increase X
- **Usage:** Primary for navigation. Far superior to heuristics.
- **Gotchas:** Not ground-truth for special tiles (doors/stairs/warps/ledges) — cross-ref the `warps` array in state. 2x scale can confuse on object sizes.
- **Procedure for warps:** Read collision for walkables → candidate path → verify exact warp tile via warps array → confirm new map after move.
- Always: Move short segments, re-fetch collision + state.
- **When moving toward a target:** Subtract your (X,Y) from target (X,Y) to get dx/dy. Positive dx → `walk_right`, negative dx → `walk_left`. Positive dy → `walk_down`, negative dy → `walk_up`. Use the path hint in the prompt which already computes this for you.

---

## 6. Starter Selection Details

All three balls are on the table in Oak's Lab. **Pokeball items block movement** — you cannot walk onto their tile. Stand on the tile SOUTH of the desired ball (y+1), face Up, press A.

**CRITICAL:** Items/pokeballs are NOT walkable. Walk to the tile adjacent to the ball, then press A. Do NOT try to walk onto the ball's tile.

Actual sprite positions (from server state):
- Bulbasaur: (6, 3) — stand at (6, 4), face Up, press A
- Charmander: (7, 3) — stand at (7, 4), face Up, press A
- Squirtle: (8, 3) — stand at (8, 4), face Up, press A

**Selection sequence:**
1. Walk to the tile SOUTH of your chosen ball (y = ball_y + 1)
2. Face Up (press_up without moving is fine, or just be facing up)
3. Press A → "So! You want the [type]-type Pokémon, [name]?"
4. Press A to confirm YES (default cursor is on YES)
5. Press B through remaining dialog ("Here! Take [name]!" etc.)
6. Nickname screen: press B to skip, or press_start to confirm default
7. **Verify:** Party count = 1

---

**Rule:** Never trust state alone after boot/warp/dialog — always cross-verify. Save before any uncertain action. Move 2-4 tiles max per loop.
