# SECTION 3: MAP & NAVIGATION DATABASE

**Pokémon Red Version — Complete Map Reference**

Coordinate system: (X, Y) where X = column (0 = left), Y = row (0 = top).
All coordinates are tile coordinates on the 2D map grid.
Map IDs use hex notation from the pokered disassembly.

---

## 3.1 — Map ID Quick Reference

| Map ID | Name | Type |
|--------|------|------|
| `0x00` | Pallet Town | Town |
| `0x01` | Viridian City | Town |
| `0x02` | Pewter City | Town |
| `0x03` | Cerulean City | Town |
| `0x04` | Vermilion City | Town |
| `0x05` | Lavender Town | Town |
| `0x06` | Celadon City | City |
| `0x07` | Fuchsia City | Town |
| `0x08` | Cinnabar Island | Town |
| `0x09` | Indigo Plateau | Indoor |
| `0x0A` | Saffron City | City |
| `0x0C` | Route 1 | Overworld |
| `0x0D` | Route 2 | Overworld |
| `0x0E` | Route 3 | Overworld |
| `0x0F` | Route 4 | Overworld |
| `0x10` | Route 5 | Overworld |
| `0x11` | Route 6 | Overworld |
| `0x12` | Route 24 | Overworld |
| `0x13` | Route 25 | Overworld |
| `0x14` | Route 9 | Overworld |
| `0x15` | Route 10 | Overworld |
| `0x16` | Route 11 | Overworld |
| `0x17` | Route 8 | Overworld |
| `0x18` | Route 16 | Overworld |
| `0x19` | Route 17 (Cycling Road) | Overworld |
| `0x1A` | Route 18 | Overworld |
| `0x1B` | Route 19 | Overworld |
| `0x1C` | Route 20 | Overworld |
| `0x21` | Route 21 | Overworld |
| `0x22` | Route 22 | Overworld |
| `0x23` | Route 23 | Overworld |
| `0x24` | Victory Road 2F | Cave |
| `0x25` | Mt. Moon 1F | Cave |
| `0x26` | Mt. Moon B1F | Cave |
| `0x27` | Mt. Moon B2F | Cave |
| `0x28` | Viridian Forest | Forest |
| `0x2D` | SS Anne 1F | Indoor/Ship |
| `0x30` | SS Anne 2F | Indoor/Ship |
| `0x33` | SS Anne B1F | Indoor/Ship |
| `0x36` | Vermilion Dock | Ship Dock |
| `0x41` | Cerulean Cave 1F | Cave |
| `0x42` | Cerulean Cave 2F | Cave |
| `0x43` | Cerulean Cave B1F | Cave |
| `0x60` | Viridian Forest (duplicate map) | Forest |
| `0x61` | Pewter Gym | Gym |
| `0x62` | Cerulean Gym | Gym |
| `0x63` | Vermilion Gym | Gym |
| `0x64` | Celadon Gym | Gym |
| `0x65` | Fuchsia Gym | Gym |
| `0x66` | Saffron Gym | Gym |
| `0x67` | Cinnabar Gym | Gym |
| `0x68` | Viridian Gym | Gym |
| `0x8A` | Player's House 1F | Indoor |
| `0x8B` | Player's House 2F | Indoor |
| `0x8C` | Rival's House | Indoor |
| `0x8D` | Oak's Lab | Indoor |
| `0x9C` | Pokémon Tower 2F | Indoor |
| `0x9D` | Pokémon Tower 3F | Indoor |
| `0x9E` | Pokémon Tower 4F | Indoor |
| `0x9F` | Pokémon Tower 5F | Indoor |
| `0xA0` | Pokémon Tower 6F | Indoor |
| `0xA1` | Pokémon Tower 7F | Indoor |
| `0xC9` | Silph Co. 1F | Indoor |
| ... | Silph Co. 2F–11F | Indoor |
| `0xE4` | Rocket Hideout B1F | Indoor |
| ... | Rocket Hideout B2F–B4F | Indoor |

---

## 3.2 — Pallet Town (Map 0x00)

**Dimensions:** 10×9 tiles (5×4 blocks + borders)

**Walkable area:** X: 3–16, Y: 3–16 (approximate)

### Connections
| Direction | Destination | Warp tile(s) |
|-----------|-------------|-------------|
| North | Route 1 | Step OFF the north edge (Y < 3) |
| South (water, Surf only) | Route 21 | Step into water at Y > 16, X: 8–11 |

### Warp Tiles (Doors entering buildings)
| Warp # | (X,Y) | Destination | Dest Map | Dest Coords |
|--------|-------|-------------|----------|-------------|
| 0 | (5, 5) | Player's House 1F | 0x8A | (4, 4) |
| 1 | (13, 5) | Rival's House | 0x8C | (4, 4) |
| 2 | (9, 9) | Oak's Lab | 0x8D | (4, 4) |

### Key Tiles
| Tile (X,Y) | Type | Description |
|-----------|------|-------------|
| (5, 5) | Door | Player's house entrance (doormat) |
| (13, 5) | Door | Rival's house entrance |
| (9, 9) | Door | Oak's Lab entrance |
| (8, 2) | Sign | "Pallet Town — A Peaceful Haven" |
| (10, 2) | Sign | Other sign |

### NPCs
| (X,Y) | Facing | Description | Dialog Length (advance_dialog calls) | Items/Flags |
|--------|--------|-------------|--------------------------------------|-------------|
| (5, 8) | Down | Mom (appears after Oak event) | ~8 | Story progression |
| (1, 12) | Down | Sign (1 line) | 1 | None |

### Important Event: Mom gives Running Shoes
**After Oak event, before leaving Pallet Town north:**
1. Walk OUTSIDE your house (warp back to outside at 5,5).
2. Mom should appear standing at (5, 10) approximately.
3. Face toward Mom (Up), press `interact`.
4. Press `advance_dialog` until done (~8 times through messages).
5. Memory flag `D70A` bit set = Running Shoes obtained. Now pressing B while moving will run at 2× speed.

---

## 3.3 — Oak's Lab (Map 0x8D)

**Dimensions:** 10×9 tiles

### Warp Tiles
| (X,Y) | Destination | Dest Coords |
|--------|-------------|-------------|
| (4, 14) — Exit warp at bottom | Pallet Town | (9, 10) |

### NPCs
| (X,Y) | Description | Dialog | Flags/Items |
|--------|-------------|--------|-------------|
| (4, 1)–(4, 2) | Prof. Oak | Long intro dialog, ~20+ advance_dialog | Triggers rival chain, gives Pokédex, gives Poké Balls |
| (2, 1) | Oak's Aide | 3 advance_dialog | Gives Pokédex when you have 30+ Pokémon |
| (6, 1) | Oak's Aide | 3 advance_dialog | Gives item |

### Poké Balls on Table (Starter Selection)
The table has **3 Poké Ball tiles** on it. Stand on the tile directly south of a ball and press `interact` (facing up) to trigger selection.

| Relative Position | Ball Contents | Recommended for |
|-------------------|--------------|-----------------|
| Left ball (X=4, Y=3 approach from Y=4 facing Up) | **Charmander** (Fire) | Experienced players; struggles early, strong mid/late |
| Center ball (X=8, Y=3 approach) | **Squirtle** (Water) | **Best overall** — Sandshrew at Brock, strong vs. Lt. Surge, Blaine |
| Right ball (X=12, Y=3 approach) | **Bulbasaur** (Grass/Poison) | Easy Brock and Misty; struggles later |

**SAVE before interacting with any ball.** If you interact with the center ball (Squirtle):
1. Walk to (8, 4) facing Up.
2. `interact` → advances dialog ("So! You want [name]?").
3. `advance_dialog` until "YES/NO" appears.
4. YES is the default (top option). Press `interact` to confirm.
5. `advance_dialog` through receiving sequence.
6. Rival appears and challenges you.

### After Starter: Rival Battle #1
Occurs immediately after selection. See Section 6 for battle data.

---

## 3.4 — Route 1 (Map 0x0C)

**Dimensions:** 40×18 tiles (20×9 blocks, each block = 2×2 tiles)
**Connections:** North → Viridian City (offset -5), South → Pallet Town (offset 0)

### Map Layout (Block Map)
Each row below = 1 block row (2 tile rows). `.` = Path, `T` = Tree, `#` = Border, `G` = Grass (wild encounters).

```
Y00-01: # # T T T . T T T # # # # # # . # # T #  <-- N (Viridian)
Y02-03: # # T T . . . . . # # # T T # . . . . #
Y04-05: # # T T . . . . . # # # # T T # . . . #
Y06-07: # # G T T G . . . # # # # # T T . . . #
Y08-09: # # # . . . . T T # # # . . . T T T T #
Y10-11: # # # . . . . . . # # # G G G G . . . #
Y12-13: # # # # T T . . . # # # . . . . . . . #
Y14-15: # # # . . . # . . # # # . . T . . . T #
Y16-17: # # G G G . G G G # # # # # # . # # # #  <-- S (Pallet)
```

### Dual-Path Structure
Route 1 has **two parallel north-south corridors** connected by an S-curve:
- **LEFT corridor:** tile cols 4-17 (west side)
- **RIGHT corridor:** tile cols 24-37 (east side)

### SOUTHBOUND — Fast Path (Viridian City → Pallet Town)
**Strategy:** Stay on the RIGHT corridor (tile cols 30-35), avoid ALL grass.

| Tile Y range | Safe tile X range | Notes |
|---|---|---|
| 0-1 | 30 | Enter from Viridian City |
| 2-3 | 30-37 | Full right corridor open |
| 4-5 | 32-37 | Full right corridor open |
| 6-7 | 32-37 | Full right corridor open |
| 8-9 | 24-29 | Shift left (trees on right) |
| 10-11 | 32-37 | Back to right corridor |
| 12-13 | 24-37 | Full width open |
| 14-15 | 24-27 or 30-35 | Trees at cols 28-29 |
| 16-17 | 30 | Enter Pallet Town |

**Key:** Staying at tile col 30-35 avoids ALL grass patches. No wild encounters.

### NORTHBOUND — Slower Path (Pallet Town → Viridian City)
**Strategy:** Navigate the S-curve. Start left, shift right around grass.

| Tile Y range | Path tile X range | Notes |
|---|---|---|
| 16-17 | 10 | Enter from Pallet Town |
| 14-15 | 6-11 | Stay left |
| 12-13 | 12-17 | Stay left |
| 10-11 | 6-17 | Wide path, stay left |
| 8-9 | 6-13 | Stay left |
| 6-7 | 12-17 | Shift right (grass on left) |
| 4-5 | 8-17 | Stay in left corridor |
| 2-3 | 8-17 | Stay in left corridor |
| 0-1 | 10 or 30 | Two exits; col 30 → Viridian City |

**Key:** Grass at Y6-7 (cols 4-11) and Y10-11 (cols 8-15) forces the S-curve.

### Grass Patches (Wild Encounters)
| Location | Tile cols | Encounters |
|---|---|---|
| Y0-1 (north) | 12-19 | Pidgey 50%, Rattata 50% (Lv2-5) |
| Y6-7 | 4-11 | Pidgey 50%, Rattata 50% (Lv2-5) |
| Y10-11 | 8-15 | Pidgey 50%, Rattata 50% (Lv2-5) |
| Y16-17 (south) | 4-7, 12-15 | Pidgey 50%, Rattata 50% (Lv2-5) |

### NPCs
| (X,Y) | Description | Notes |
|--------|-------------|-------|
| (5, 24) | Youngster (connected coords) | In Pallet Town space, not on Route 1 proper |
| (15, 13) | Youngster (connected coords) | On Route 1 or near boundary |

### Items
- **Potion:** Given by Viridian Poké Mart employee standing in the clearing (after delivering Oak's Parcel)
- No hidden items on Route 1

### Sign
- **Route 1 Sign** at connected coords (9, 27) — in Pallet Town space
- Reads: "ROUTE 1 - PALLET TOWN / VIRIDIAN CITY"

---

## 3.5 — Viridian City (Map 0x01)

**Dimensions:** 20×18 tiles

**Coordinate note:** This guide uses the game's internal coordinate system where (0,0) is the top-left of the connected map grid. The Viridian City map connects to Route 1 (south), Route 2 (east/north), and Route 22 (west), and coordinates may exceed the base 20×18 dimensions due to the connected map grid. Door entrance tiles (warp_events) are the tiles you stand on and press a direction to enter a building. Warp destination coordinates are where you appear when exiting a building or using Fly/Teleport.

### Warp Tiles (Door Entrances — from pokered disassembly)
| Warp # | (X,Y) | Destination | Interior Exit → Overworld |
|--------|-------|-------------|--------------------------|
| 1 | (23, 25) | Viridian Pokecenter | (3,7)/(4,7) interior → warp #1 at (23, 25) |
**⬆ To enter:** Stand on the warp tile and press UP. Tile (23, 26) is directly south of the PC door — approach from there.
| 2 | (29, 19) | Viridian Mart | (3,7)/(4,7) interior → warp #2 at (29, 19) |
| 3 | (21, 15) | School House | (2,7)/(3,7) interior → warp #3 at (21, 15) |
| 4 | (21, 9) | Nickname House | (2,7)/(3,7) interior → warp #4 at (21, 9) |
| 5 | (32, 7) | Viridian Gym | (16,17)/(17,17) interior → warp #5 at (32, 7) |

**NOTE:** The old guide had incorrect coordinates (e.g. PC at 17,17 which is the main city sign, Mart at 23,11). The above are the correct door entrance tiles from the pokered ROM disassembly. To enter a building, stand on the exact tile and press UP (for south-facing doors).

### Signs (bg_events — read with interact)
| (X,Y) | Sign Text |
|--------|-----------|
| (17, 17) | Main city sign ("Viridian City — The Eternally Green Paradise") |
| (24, 25) | Pokecenter sign |
| (30, 19) | Mart sign |
| (19, 1) | Trainer Tips sign |
| (21, 29) | Trainer Tips sign |
| (27, 7) | Gym sign |

### Connections
| Direction | Destination |
|-----------|-------------|
| South | Route 1 |
| East | Route 2 |
| West | Route 22 (fenced, need Cut or go through) |
| North | Route 2 (gatehouse) |

### Items
- **Hidden item:** Potion at (7, 15) — examine empty tile with `interact`
- **Oak's Parcel:** Given by Mart clerk after talking to Oak
- **Bicycle Voucher:** Given by Pokémon Fan Club Chairman (see below)

### Key NPCs
| (X,Y) | Description | Dialog | Items/Flags |
|--------|-------------|--------|-------------|
| (8, 15) | Old Man (item finder) | 4 dialog | Gives Itemfinder after 30 Pokémon registered |
| (17, 11) | NPC blocking gym initially | 2 dialog | Moves after 7 badges |

### Pokémon Fan Club (North Viridian City)
- Building at approximately (13, 5).
- **Chairman** is at (9, 3) inside, facing down.
- `interact` → advance_dialog through his Pikachu speech (~5 calls).
- He gives **Bicycle Voucher** (key item). You need this to get the Bike from the Cerulean Bike Shop.

### Viridian City Gym (Map 0x68) — Giovanni
**Locked until you have 7 badges.** Once unlocked:
- Leader **Giovanni** at approximately (10, 2), facing down, 1-tile trigger.
- Invisibility trick: trainers are positioned to guide correct path.
- Strength puzzles and arrow tiles must be navigated. See Section 5 walkthrough for full tile path.

---

## 3.6 — Route 2 (Map 0x0D)

**Dimensions:** Large vertical+horizontal route with tree mazes.

### Connections
| Direction | Destination | Notes |
|-----------|-------------|-------|
| South | Viridian City (navigate eastern road north to south) |
| North | Pewter City (navigate to north exit) |
| West | Viridian Forest (enter from east via tree gap) |

### Important Tiles
- The path goes through a maze of Cut-able trees on the west side.
- **HM01 cut not needed to pass Route 2** — the path goes around trees.

### Items
- None essential to routine navigation.

### NPCs
- Bug Catcher trainers on Route 2. Each has approximately 3–4 advance_dialog upon defeat.

---

## 3.7 — Viridian Forest (Map 0x28)

**Dimensions:** Multiple connected sub-maps.

**This is the first mandatory forest maze.** You MUST pass through it to reach Pewter City.

### Layout Key
- The forest is filled with tall grass and trees forming a maze path.
- **Cut-able trees:** At least one tree must be Cut (HM01) to access full forest.
- **Essential path without Cut:** A narrow path exists along the south and east edges.

### Connections
| Direction | Destination |
|-----------|-------------|
| West/Pewter | Pewter City |
| East/Viridian | Route 2 |

### Items
| Tile | Item | How |
|------|------|-----|
| (3, 5) approx | Antidote | Hidden - examine tile |
| (15, 2) approx | Potion | Hidden - examine tile |
| (8, 10) approx | Poké Ball | On ground |

### Important NPCs
- **Bug Catcher** at (5, 8) etc. — typically 4 advance_dialog.
- Requires Cascade Badge for Cut to access full west side.

### Key Wild Encounters
| Pokémon | Level | Rate | Notes |
|---------|-------|------|-------|
| Caterpie | 3–5 | 40% | Evolve to Butterfree at Lv.7 — early Sleep Powder |
| Weedle | 3–5 | 40% | |
| Pikachu | 3–5 | 10% | Rare but valuable. Use Quick Attack vs. Brock |

**Route through forest (no Cut needed):**
1. Enter from east (Route 2 edge).
2. Walk south to the bottom of the map (follow south wall).
3. Navigate west under the tree obstacles.
4. Exit west into Pewter City area.

---

## 3.8 — Pewter City (Map 0x02)

**Dimensions:** 20×18 tiles

### Warp Tiles
| (X,Y) | Destination | Map | Notes |
|--------|-------------|-----|-------|
| (17, 15) | Pokémon Center | Indoor | |
| (14, 11) | Mart | Indoor | |
| (27, 13) | Pewter Gym | 0x61 | |
| (3, 13) | Museum (1F) | Indoor | |
| (3, 11) | Museum (2F) | Indoor | Entrance from 1F |

### Key Items
- **Old Amber:** Museum 2F, interact with scientist after viewing exhibits. He revives it into Aerodactyl at Cinnabar Lab.
- **Helix Fossil / Dome Fossil:** Not in Red — only Old Amber here.
- **TM45 (Thunder Wave):** Sold in Mart for ₽2000 (optional).

### Pewter Gym (Map 0x61) — Brock
**Layout:** Simple straight path with one trainer before Brock.

| Trainer | Position | Team | Dialog |
|---------|----------|------|--------|
| Jr. Trainer (Bug Catcher) | (3, 5) | Lv.10 Weedle, Lv.10 Caterpie | 3 advance_dialog after defeat |

**Brock:** Position (3, 1), facing down. Trigger = step onto (3, 2) facing up and press `interact`. He has:
- Geodude Lv.12: Tackle, Defense Curl
- Onix Lv.14: Tackle, Screech, Bide

**Strategy:** Water moves are 2× effective. FIGHT type moves are 2× effective. Normal moves work too (Screech from Onix actually helps you by lowering Defense). See Section 6 for detailed battle plan.

**After defeat:** BoulderBadge obtained → Attack +12.5%, HM05 Flash usable outside battle.

---

## 3.9 — Route 3 (Map 0x0E)

**Dimensions:** 35×9 (long horizontal route)

### Key NPCs (Trainer Posings)
All along the route with 1–3 tile sight lines:
- **Bug Catcher** at approximately (4, 3) — faces right, 3-tile sight.
- **Lass** at (8, 2) — faces down, 2-tile sight.
- Multiple trainers throughout.

### Wild Encounters
| Pokémon | Level | Rate |
|---------|-------|------|
| Pidgey | 6–8 | 35% |
| Spearow | 5–8 | 35% |
| Nidoran♀ | 4–6 | 15% |
| Nidoran♂ | 4–6 | 15% |

### Connections
| Direction | Destination |
|-----------|-------------|
| West | Pewter City (exit west) |
| East | Mt. Moon entrance |

---

## 3.10 — Mt. Moon (Maps 0x25, 0x26, 0x27)

### Mt. Moon 1F (Map 0x25)

**Entrance:** From Route 3 at approximately X=20, Y=3 on the east side of Mt. Moon.

**Layout:** Cave with a central pit/staircase area. Navigate UP-and-around.

**Items on 1F:**
| Tile | Item | Type |
|------|------|------|
| (5, 1) | Poké Ball (Potion) | Ground item |
| (28, 14) | Poké Ball (Poké Ball) | Ground item |
| (21, 13) | Moon Stone | Ground item |
| (15, 2) | Ether | Hidden |

**Exit to B1F:** Multiple stair warp tiles lead down. The main exit is at approximately (3, 5).

### Mt. Moon B1F (Map 0x26)

Larger cave map. NPC trainers patrol here.
**Super** NPCs: Includes a **Super Nerd** who gives **TM06 (Horn Drill)** — rare item.

**Exit to B2F:** Navigate to south-east warp.

### Mt. Moon B2F (Map 0x27)

Smallest level. Contains the **Fossil choice** (though Old Amber is in the museum in Red version). Exit back to Route 4 via north-east passage.

### Wild Encounters
| Pokémon | Level | Rate |
|---------|-------|------|
| Zubat | 6–11 | 60% |
| Geodude | 8–10 | 20% |
| Paras | 8–10 | 15% |
| Clefairy | 8–10 | 5% | Very rare but valuable (evolves to Clefable with Moon Stone) |

---

## 3.11 — Route 4 (Map 0x0F)

**Items:**
- Hidden Great Ball at eastern section.
- TM (various) can be found on the ground.

**Navigation:** Walk east through the single-path route. No grass encounters in some areas.

---

## 3.12 — Cerulean City (Map 0x03)

**Dimensions:** 20×18 tiles

### Warp Tiles
| (X,Y) | Destination |
|--------|-------------|
| (17, 3) | Pokémon Center |
| (27, 9) | Bike Shop (get Bicycle after exchanging voucher) |
| (23, 17) | Cerulean Gym (0x62) |
| (13, 9) | House with Rocket (post-Giovanni) |

### Key Events
1. **Rival Battle #3 on Nugget Bridge (Route 25)** — before reaching Cerulean.
2. **Team Rocket in the city** (the house at approximately (13, 9) has a Rocket guarding something).
3. **Stolen TM:** After defeating Rocket in the house, speak to the NPC for **TM28 (Dig)**.

### Cerulean City Bike Shop
- Located at (27, 9) area.
- Speak to the shop owner, use **Bicycle Voucher** from Viridian Fan Club.
- Receive **Bicycle** (key item). Press SELECT to mount/dismount (in overworld, hold SELECT near bike icon).

### Cerulean Gym (Map 0x62) — Misty

**Layout:** Single pool area with trainers on platforms. Walk across platforms through shallow water (Surf not needed in gym).

**Trainers:**
- Swimmer (girl on right) — Horsea Lv.16, Shellder Lv.16.

**Misty:** At (5, 3), behind the water pool, on a small platform. Approach from south.
- Staryu Lv.18: Tackle, Water Gun
- Starmie Lv.21: Tackle, Water Gun, Bubblebeam

**Strategy:** Electric moves (Pikachu) are 2× effective. Starmie is Water/Psychic — Grass moves from Bulbasaur work too.

**After defeat:** CascadeBadge → traded Pokémon up to Lv.30 obey, HM01 Cut usable outside battle.

---

## 3.13 — Route 24 & Route 25 (Maps 0x12, 0x13)

### Route 24
Nugget Bridge — 6+ trainers on the bridge (5 Jr. Trainers + 1 Rocket + Rival).

**Items:**
- TM on the ground: Rare Candy (requires Cut to reach).

### Route 25 (Bill's Sea Cottage)
- Path continues past Nugget bridge to Bill's house.
- Trainer Youngster (D) has Slowpoke — important for Mew glitch setup.

### Items
- **TM43 (Whirlwind)** hidden at (15, 12) on Route 25.
- **TM19 (Seismic Toss)** — Bill gives this in his house dialogue sequence.
- **Elixer** and **Ether** hidden on Route 25.

---

## 3.14 — Route 5 & Route 6 (Maps 0x10, 0x11)

### Route 5
Connects Cerulean City (south) to Underground Path 5-6 entrance and onward to Saffron City.

### Underground Path (Route 5-6)
Connecting tunnel between Route 5 and Route 6. Simple straight path.

**Hidden items:**
- Full Restore
- X Special

### Route 6
Connects to Underground Path and Vermilion City (south exit).

---

## 3.15 — Vermilion City (Map 0x04)

### Key Features
- **SS Anne** docked at the east side. Ticket required (obtained from Bill).
- **Pokémon Fan Club** — already visited if you got Bicycle Voucher.
- **Vermilion Gym (Map 0x63)** — Lt. Surge.

### SS Anne (Multiple Maps)

**Entry:** Present S.S. Ticket to guard at dock. Guard at approximately (18, 10).

**Key items and locations within SS Anne:**
| Floor/Area | Item | Location |
|-----------|------|----------|
| 1F | None initially | |
| 2F | TM (Body Slam TM08) | Cabin areas |
| B1F | Hyper Potion | Hidden |
| Kitchen | Max Ether | Hidden |
| Captain's cabin | HM01 Cut | Obtain by talking to Captain (requires event) |
| Multiple cabins | Trainer battles, rival battle | |

### Rival Battle #4 (SS Anne 1F or 2F)
Happens on 1F/2F in a hallway.

### Obtaining HM01 Cut
In the Captain's cabin (1F, accessible through back of ship), the Captain is seasick. Use `interact` and advance_dialog through all text. Captain teaches a Pokémon Cut directly (not via HM item — in Gen 1 you cut the "Cut tree" door in the path to get Cut taught).

### Vermilion Gym (Map 0x63) — Lt. Surge

**Puzzle:** The gym has trash can switches. You must find the correct switch pair (randomized on each playthrough). **Memory-driven approach:** try each switch. If the door doesn't open, reset the other switch. Interactive method: check if the gym internal event flag bits change after each switch press.

**Lt. Surge:** At (9, 3), behind locked doors.
- Voltorb Lv.21: Tackle, Screech, Sonicboom
- Pikachu Lv.18: Thundershock, Growl, Thunder Wave, Quick Attack
- Raichu Lv.24: Thundershock, Growl, Thunderbolt

**Strategy:** All Electric types → Ground moves (Dig) or just overpower with a strong non-Electric type. Pokémon immune to Electric: Pokemon with Ground type.

**After defeat:** ThunderBadge → Defense +12.5%, HM02 Fly usable outside battle.

---

## 3.16 — Route 11 & Diglett's Cave

### Route 11
Long horizontal route with gatehouse (connects to Lavender Town).

### Diglett's Cave (Map 0x5C)
Two-level cave. Full of wild Diglett and Dugtrio.

**Wild encounters:** Diglett (15–22, 95%), Dugtrio (15–24, 5%).

**Exit:** Two exits — one to Route 11, one to Route 2.

---

## 3.17 — Route 9 & Route 10

### Route 9
Connects to Rock Tunnel entrance and Cerulean outskirts.

### Route 10
Contains the entrance to Rock Tunnel (north) and connects to Lavender Town (north) and Power Plant (south, water-side).

---

## 3.18 — Rock Tunnel (Maps 0x46/0x47)

**Two floors (1F and B1F).**

HM05 Flash is recommended (dark cave — without Flash, the screen is too dark to navigate in a vision-limited context) BUT you can navigate using walls and coordinates.

**B1F Warp Tiles:** Multiple warps connect between 1F and B1F.

**HM04 Strength** is found on B1F but you need to navigate to obtain it first.

**Essential items:**
- **HM04 Strength:** B1F — interact with NPC. Allows pushing boulder puzzles.
- **TM (varies):** On ground.

**Key Wild Pokémon:**
| Pokémon | Level | Rate |
|---------|-------|------|
| Zubat | 15–18 | 55% |
| Geodude | 16–18 | 25% |
| Machop | 15–17 | 15% |
| Onix | 15–17 | 5% | Great catch — strong at gyms |

**Navigation requires knowing the coordinate path carefully.**

---

## 3.19 — Lavender Town (Map 0x05)

### Key Buildings
1. **Pokémon Center** — (17, 9) area.
2. **Mr. Fuji's House** — (13, 11). After rescuing Pokémon Tower, Mr. Fuji gives **Poké Flute**.
3. **Pokémon Tower** — (5, 5). Multi-floor ghost tower.

### Key Events
- **Rival Battle #5** in Pokémon Tower 2F.
- **Ghost Marowak** (cannot see, need Silph Scope from Celadon).
- **Mr. Fuji rescue event** — after obtaining Silph Scope and resolving ghost event in Tower, Mr. Fuji gives you **Poké Flute** (key item — wakes Snorlax).
- **Silph Scope** obtained from Giovanni's hideout in Celadon (Rocket Hideout B4F).

---

## 3.20 — Pokémon Tower (Maps 0x9C–0xA1)

**Floors 2F–7F.** Static ghost encounters need Silph Scope to see and battle.

| Floor | Wild Pokémon | Notes |
|-------|-------------|-------|
| 2F–3F | Gastly (13–20) | Ghost-type |
| 4F–5F | Haunter (18–22) | Ghost-type |
| 6F | Marowak Ghost | Cannot defeat without Silph Scope (forced event battle) |

**Items:**
- Elixer (hidden)
- Various ground items

**Strategy without Silph Scope:**
You cannot identify wild Ghost types — all you can see is "GHOST." You still cannot SEE them without Silph Scope. Once Silph Scope is obtained, you can identify.

**Ghost Marowak:** Use Silph Scope on the ghost at (5, 10) on 6F → triggers story battle. Defeat or catch Marowak ghost → story progress → Mr. Fuji freed.

---

## 3.21 — Celadon City (Map 0x06)

**Of all maps, Celadon has the most buildings:**

| Building | Warp (X,Y) | Key Content |
|----------|-------------|-------------|
| Pokémon Center | (13, 9) | |
| Celadon Dept Store 1F | (25, 5) | TMs, Rare Candy, X items |
| Celadon Dept Store Roof | — | Vending machines for Fresh Water, Soda Pop, Lemonade (give to guards) |
| Celadon Gym (0x64) | (17, 17) | Erika |
| Game Corner | (31, 9) | Pokémon prizes, Rocket Hideout access |
| Rocket Hideout elevator | (game corner basement) | |
| Prize Corner | (dept store roof area) | Prize Pokémon |
| Hotel | (27, 17) | |

### Celadon Dept Store (7 floors)
| Floor | Key Items |
|-------|-----------|
| 1F | Reception |
| 2F | Revive, Great Ball, Super Potion, Antidote, etc. |
| 3F | Posters (viewing), TM18 (Counter) |
| 4F | Various TMs |
| 5F | Rare Candy, PP Up, X items |
| 6F | Elevator |
| Roof | Vending machines |

### Celadon Gym (Map 0x64) — Erika

**Puzzle:** Invisible walls blocking paths (some walls are passable). Navigate coordinate by coordinate.

**Erika:** Located at approximately (4, 1) on the far side.
- Victreebel Lv.29: Razor Leaf, Wrap, Poisonpowder, Sleep Powder
- Tangela Lv.24: Constrict, Bind
- Vileplume Lv.29: Petal Dance, Poisonpowder, Mega Drain, Sleep Powder

**Strategy:** Fire moves (Flamethrower, Fire Blast) are 2× effective. Ice moves also 2×. Psychic also strong.

---

## 3.22 — Rocket Hideout (Multiple Maps)

Accessed via Game Corner — inspectors wall at (4, 17) in Game Corner has a hidden passage to Hideout.

**Elevator system:** Floors B1F–B4F.

| Floor | Key Items |
|-------|-----------|
| B1F | Warp tiles (teleporters), navigational puzzle |
| B2F | Nugget, Super Potion, PP Up (hidden) |
| B3F | More trainers |
| B4F | **Lift Key** (key item) — gives access to elevator to Giovanni's office → **Silph Scope** from Giovanni |

### Navigation Strategy
Each B1F teleporter warp pad teleports you randomly or in a fixed pattern. **Save before each warp.**

---

## 3.23 — Saffron City (Map 0x0A)

### Key Buildings
| Building | Warp (X,Y) | Content |
|----------|-------------|---------|
| Pokémon Center | (17, 9) | |
| Silph Co. 1F | (3, 3) | 11-floor building — main story progression |
| Saffron Gym (0x66) | (9, 17) | Sabrina (Psychic) |
| Fighting Dojo | (21, 17) | Trade for Hitmonlee/Hitmonchan |
| Mr. Psychic's House | (29, 5) | TM29 (Psychic) |

### Silph Co. (Multiple Maps, 1F–11F)

This is the **most complex building** in the game. 11 floors with:

**Key Items throughout:**
| Floor | Item |
|-------|------|
| 1F | Security Card (Card Key) from NPC |
| 3F | Elixer, Max Potion (hidden) |
| 5F | TM (Earthquake TM26) |
| 7F | Card Key doors open |
| 9F | Multiple items |
| 10F | TM (Take Down TM09) |
| 11F | **Master Ball** — ground item in Giovanni's office |

**Floor-to-floor access:** Elevators, warp tiles, and staircases. 7 floors open after obtaining Card Key.

**Event:** Rival Battle on 5F (approximately).

**Boss Giovanni:** 11F. After defeating him, obtain Master Ball and story progresses to Silph Scope if not yet obtained.

### Saffron Gym (Map 0x66) — Sabrina

**Layout:** Warp tiles (teleporters) throughout. Each warp teleports you to a new room.
Navigate by memorizing warp tile coordinate patterns.

**Sabrina** at the end:
- Kadabra Lv.38: Disable, Psybeam, Recover, Psychic
- Mr. Mime Lv.37: Confusion, Barrier, Light Screen, Doubleslap
- Venomoth Lv.38: Poisonpowder, Leech Life, Stun Spore, Psybeam
- Alakazam Lv.43: Psybeam, Recover, Psywave, Reflect

**Strategy:** Bug moves (weak in Gen 1 against Psychic). Physical sweepers work best. Alakazam is fast and strong. Focus fire.

**After defeat:** MarshBadge → traded Pokémon up to Lv.70 obey. No HM.

---

## 3.24 — Fuchsia City (Map 0x07)

### Key Buildings
| Building | Warp (X,Y) | Content |
|----------|-------------|---------|
| Pokémon Center | (17, 11) | |
| Safari Zone Gate | (11, 17) | Safari Zone entrance |
| Warden's House | (17, 9) | Gold Teeth (after Safari) |
| Fuchsia Gym (0x65) | (3, 17) | Koga |

### Safari Zone (Multiple Maps)

**Entrance fee:** ₽500. Given 30 Safari Balls. Must leave after 500 steps (step counter at memory address).

**Key wild Pokémon:**
- Chansey (rare — high catch rate item)
- Kangaskhan
- Tauros
- Scyther / Pinsir
- Eevee (prize corner of Dept Store in some versions)

**HM03 Surf** is obtained from the Warden after finding the **Gold Teeth** in Safari Zone Area 3 (hidden item tile).

**Hidden in Safari Zone: Gold Teeth** (give to Warden for HM03 Surf — critical move for water navigation).

### Fuchsia Gym (Map 0x65) — Koga

**Invisible wall maze.** Trainers guide direction. Coordinate memorization required.

**Koga:** Hidden behind walls.
- Koffing Lv.37: Tackle, Smog, Sludge, Smokescreen
- Muk Lv.39: Disable, Poison Gas, Minimize, Sludge
- Koffing Lv.37: (duplicate)
- Weezing Lv.43: Smog, Sludge, Toxic, Selfdestruct

**Strategy:** Psychic moves (Psychic) are 2× effective. Earth moves work. Toxic from Weezing is very dangerous.

**After defeat:** SoulBadge → Speed +12.5%, HM03 Surf usable outside battle.

---

## 3.25 — Cinnabar Island (Map 0x08)

### Pokémon Mansion (Multi-floor)

**4 floors + B1F.** Wild Pokémon include: Growlithe/Vulpix, Ponyta, Grimer/Muk, Magmar, Ditto.

**Key Items:**
- Moon Stone (hidden)
- Max Revive, Rare Candy (hidden)
- **Secret Key** (key item) — from a statue/door switch. Opens Cinnabar Gym.

### Cinnabar Gym (Map 0x67) — Blaine

**Quiz gym:** Answer questions correctly to progress. Each question is a YES/NO.
- Questions and answers are randomized per game.

**Blaine:**
- Growlithe Lv.42: Ember, Leer, Take Down, Agility
- Ponyta Lv.40: Tail Whip, Stomp, Growl, Fire Spin
- Rapidash Lv.42: Tail Whip, Stomp, Growl, Fire Spin
- Arcanine Lv.47: Roar, Ember, Ember, Take Down

**Strategy:** Water moves are 2× effective. Rock moves also 2×. Earth moves.
**After defeat:** VolcanoBadge → Special +12.5%. No HM.

---

## 3.26 — Pokémon League — Indigo Plateau (Map 0x09)

### Pokémon Center — LAST HEAL before Elite Four
**Before entering the building fully, stock up on:**
- Full Restore (buy at Mart if affordable) × 10+
- Revive × 5+
- Full Heal × 5+
- Elixer × 10+

**No access to Mart or Pokémon Center once inside the Elite Four sequence.**

### Elite Four Building (Lorelei's Room onward)
Each member is in a unique room connected by single paths. You heal between members.

**Important: If you use Dig or Teleport to leave, you must restart the Elite Four from the beginning.**

---

## 3.27 — Victory Road (Maps 0x11, 0x4A, 0x4B approx)

**Three floors of cave before Indigo Plateau.**

**Navigational challenges:**
- Strength boulder puzzles (push boulders into holes to unblock paths)
- Hidden items
- Multiple trainer battles (one nearly invisible — "invisible trainer" requires boulder to be in correct position)

**Items:**
- Ultra Ball (hidden)
- Full Restore (hidden)

**Wild Pokémon:** Machoke, Machop, Geodude, Graveler, Onix, Marowak (high level), etc.

**Key: Strength is required.** Push boulders onto specific holes to create paths across floor gaps.

---

## 3.28 — Victory Road — Strength Puzzle Walkthrough

**Floor 1:** Boulder at (7, 9) → push Right to (13, 9) → proceed north.

**Floor 2:** Boulder at (16, 3) → push Down to (16, 12) → proceed west.

**Floor 3:** Multiple boulders. Coordinates vary. Push all three boulders into holes to reach exit at east/west.

---

## 3.29 — Other Maps (Brief Reference)

### Seafoam Islands
Multi-floor water cave with currents (push player downstream).

**Legendary Pokémon:**
- **Articuno** — Seafoam Islands B4F. Level 50. Very powerful Ice-type.

### Power Plant
Water-side cave across from Route 10. Contains:
- **Zapdos** Lv.50 (legendary Electric bird) — find on ground.
- TM (Thunder TM25) hidden.
- Voltorb "items" (disguised Pokémon — auto-trigger battle on pickup).

### Cerulean Cave (Post-game)
**Mewtwo** Lv.70 here. Most powerful wild Pokémon. Requires Surf and multiple warps to navigate.

---

## 3.30 — Quick Warp Destination Reference

| Source Map | Warp (X,Y) | Destination |
|-----------|-------------|-------------|
| Pallet Town (0x00) | (5, 5) | Player's House 1F → (4, 4) |
| Player's House 1F | (7, 0) | Player's House 2F → (7, 0) |
| Player's House 2F | (7, 0) | Player's House 1F → (7, 0) |
| Rival's House | (4, 14) | Pallet Town → (13, 10) |
| Oak's Lab | (4, 14) | Pallet Town → (9, 10) |
| Viridian Mart | (3, 7)/(4, 7) interior | Viridian City → (29, 19) [warp #2] |
| Viridian PC | (3, 7)/(4, 7) interior | Viridian City → (23, 25) [warp #1] |
| Pewter Gym | (4, 14) | Pewter City → (27, 14) |
| ... | ... | ... |

*(Full warp table for all 252+ maps is beyond a single-page summary. Each map above has its key warps documented.)*

---

## 3.31 — Hidden Item Complete Reference

| Map | Hidden Tile | Item |
|-----|------------|------|
| Viridian City | (7, 15) | Potion |
| Viridian Forest | (3, 5) approx | Antidote |
| Viridian Forest | (15, 2) approx | Potion |
| Mt. Moon | (15, 2) | Ether |
| Mt. Moon | (21, 13) | Moon Stone |
| Route 4 | (6, 18) | Great Ball |
| Cerulean City | (23, 17) | Rare Candy |
| Route 25 | (14, 2) | Elixer |
| Route 25 | (20, 4) | Ether |
| Underground Path 5-6 | (3, 3) | Full Restore |
| Underground Path 5-6 | (6, 4) | X Special |
| SS Anne | (30, 9) | Hyper Potion |
| SS Anne | (15, 6) | Great Ball |
| Route 11 | (7, 16) | Escape Rope |
| Route 12 | (2, 50) | Hyper Potion |
| Route 9 | (20, 2) | Ether |
| Route 10 | (12, 16) | Super Potion |
| Route 10 | (25, 23) | Max Ether |
| Underground Path 7-8 | (4, 3) | Elixer |
| Underground Path 7-8 | (7, 4) | Nugget |
| Celadon City | (9, 3) | PP Up |
| Rocket Hideout B2F | (2, 5) | PP Up |
| Rocket Hideout B2F | (4, 15) | Nugget |
| Rocket Hideout B2F | (5, 7) | Super Potion |
| Pokémon Tower | (16, 10) | Elixer |
| Route 13 | (12, 14) | Calcium |
| Route 13 | (22, 10) | PP Up |
| Route 17 | (9, 14) | Rare Candy |
| Route 17 | (12, 11) | Full Restore |
| Route 17 | (15, 4) | PP Up |
| Route 17 | (29, 12) | Max Revive |
| Route 17 | (40, 8) | Max Elixer |
| Safari Zone | (5, 22) | Revive |
| Vermilion City | (22, 14) | Max Ether |
| Power Plant | (18, 16) | Max Elixer |
| Power Plant | (24, 12) | PP Up |
| Silph Co. | (12, 3) | Elixer |
| Silph Co. | (5, 5) | Max Potion |
| Saffron City | (10, 3) | Nugget |
| Seafoam Islands | (25, 8) | Ultra Ball |
| Seafoam Islands | (32, 6) | Max Elixer |
| Seafoam Islands | (15, 12) | Nugget |
| Pokémon Mansion | (14, 28) | Moon Stone |
| Pokémon Mansion | (5, 1) | Max Revive |
| Pokémon Mansion | (22, 2) | Rare Candy |
| Route 23 | (3, 34) | Max Ether |
| Route 23 | (21, 20) | Ultra Ball |
| Route 23 | (29, 18) | Full Restore |
| Victory Road | (23, 7) | Ultra Ball |
| Victory Road | (13, 4) | Full Restore |

---

*Continue to Section 4: Systematic Navigation Procedure*


