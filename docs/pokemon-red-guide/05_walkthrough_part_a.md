# SECTION 5: COMPLETE WALKTHROUGH — PART A
## New Game through Celadon City

---

> **How to use this walkthrough:** Each step gives you the current map ID, target coordinates (X,Y), direction to press, and what to check in memory. "advance_dialog N times" means press B (or A then B) N times to clear all text boxes. See Section 4 for the safe_move algorithm and Section 3 for map data.

---

## PHASE 1: PALLET TOWN & STARTER

### Step 0: New Game & Naming
- Start ROM / reset. Title screen appears.
- Select "NEW GAME" (press A).
- **Name entry screen:** Default name is selected. To accept a default name without character-by-character input, navigate to the "END" button and press A.
  - For player name "RED": On naming screen, find 'R' (top row, position varies). Press A → find 'E' → A → find 'D' → A → navigate to END → A.
  - For rival name "BLUE": Same process on next screen.
- Through Oak's intro: `advance_dialog` ~15 times until you gain control in your bedroom (Map 0x8B, Player's House 2F).

### Step 1: Player's House 2F → 1F → Outside
**Current:** Map 0x8B, at approximately (7, 0) facing Down.
1. Walk down the stairs (south) to 1F. Map changes to 0x8A.
2. Mom is at approximately (3, 5). Face Down toward her and `interact`.
3. `advance_dialog` ~5 times. (Mom's early dialog — optional but sets events.)
4. Walk south to the exit door at approximately (7, 14). `interact` with doormat.
5. Warp to Pallet Town (0x00) at (5, 6).

### Step 2: Pallet Town → Oak's Lab Event
**Current:** Map 0x00, at (5, 6).
1. Walk north (decrease Y). You'll hit the map edge → enter Route 1 (0x0C).
2. On Route 1, walk north. Prof. Oak stops you.
3. `advance_dialog` through Oak's speech (~8 dialogs). Oak escorts you back south to Pallet Town, then west into his lab.
4. You arrive in Oak's Lab (0x8D). Oak's sprite moves to the table.

### Step 3: Starter Selection (Oak's Lab, Map 0x8D)
**Current:** Map 0x8D. Your character is at approximately (4, 8).

**SAVE the game now** (START → find SAVE option → A → confirm A → advance_dialog through "SAVING..." message).

**The three balls are on the table. Stand south of the desired ball, face Up, press A:**

| Ball | Stand at (X,Y) facing Up | Pokémon | Type |
|------|--------------------------|---------|------|
| Left | (5, 4) | Charmander | Fire |
| **Center** | **(9, 4)** | **Squirtle** | **Water** (recommended) |
| Right | (13, 4) | Bulbasaur | Grass/Poison |

**Sequence:**
1. Walk to (9, 4). Verify D361=9, D362=4.
2. Press A (interact facing Up).
3. advance_dialog through "So! You want the water-type Pokémon, Squirtle?" → "YES/NO" prompt.
4. Default = YES. Press A.
5. advance_dialog through "Here! Take Squirtle!" → naming sequence (press A to accept default or name it).
6. **Verify:** D164 = species ID for Squirtle (0x07). D163 (party count) = 1.

### Step 4: Rival Battle #1 (Oak's Lab)
**Your rival (Gary/Blue) challenges you.**

*If you chose Squirtle: Rival has Bulbasaur Lv.5 (Grass/Poison)*
- Turn 1: Press A (opens battle menu), A (selects FIGHT), A (selects Tackle). Bulbasaur takes neutral damage.
- Continue using Tackle. If HP drops below 8, use Potion from your bag (if obtained in Step 1 PC).
- Bulbasaur's Growl lowers your Attack. Keep attacking. Win in ~3 turns.

**After battle:** advance_dialog through Oak's post-battle speech. Oak gives you the Pokédex and 5 Poké Balls.
- **Memory check:** D707+ flags = Pokédex registered. D31E bag contains Poké Balls (item ID 0x04, quantity 5).

### Step 5: Leave Oak's Lab
1. Walk south to exit warp at approximately (4, 14).
2. Warp to Pallet Town (0x00) at (9, 10).
3. Verify: D35E = 0x00.

---

## PHASE 2: PALLET TOWN → VIRIDIAN CITY

### Step 6: Mom's Running Shoes Event
**Current:** Map 0x00, at (9, 10).
1. Walk north (decrease Y) to your house at (5, 5). 
2. Enter house: interact with doormat at (5, 5). Warp inside to Player's House 1F (0x8A) at (4, 4).
3. Go back outside: Walk south to (7, 14) → interact → warp to Pallet Town (0x00) at (5, 6).
4. Mom appears outside your house. Walk toward her (north from doormat).
5. `interact` with Mom (facing Up toward her sprite). advance_dialog ~8 times.
6. **Memory check:** D70A flag = Running Shoes received.
7. **From now on: Hold B while moving to run at 2× speed.**

### Step 7: Route 1 to Viridian City
**Current:** Map 0x00.
1. **Goal:** Walk north to leave Pallet Town.
2. Walk north (press Up while running, hold B). Pass Y=3, Y=2, Y=1, Y=0.
3. At Y < 0 (off the north edge): Map changes to Route 1 (0x0C). D35E = 0x0C.
4. On Route 1, continue walking north. Stay at approximately X=7.
5. At the north edge of Route 1: Map changes to Viridian City (0x01). D35E = 0x01.

### Step 8: Viridian City — Initial Exploration
**Current:** Map 0x01. Approximate position: (7, 0) — south side.

**SAVE at the Pokémon Center:**
1. Walk to the Pokémon Center door at **(23, 25)** (southwest part of the city, on the building's south wall). The tile (23, 26) is directly below the door — stand there and press UP to enter.
2. Inside: Walk to the nurse (north side). `interact`. advance_dialog through "Welcome to our Pokémon Center!" → "We heal your Pokémon back to perfect health!" → A to confirm "OK?" → advance_dialog "Healing... ..." → done.
3. Walk back south to exit. You'll warp back to **(23, 25)** outside.

**Withdraw money / buy supplies at the Mart:**
1. Walk to the Mart door at **(29, 19)** (southeast part of the city). Stand on that tile and press UP to enter.
2. Talk to the clerk (facing down). advance_dialog through.
3. If you have Oak's Parcel: advance_dialog → clerk gives item and triggers the delivery event.
4. **If you need to deliver Oak's Parcel:** Walk south to Pallet Town (Route 1 south), then west to Oak's Lab, give parcel to Oak.

**Pokémon Fan Club (Bicycle Voucher):**
1. Walk to the north side of Viridian City (Y small). Find the Pokémon Fan Club building.
2. Enter. Walk to the Chairman (facing down, north side of room).
3. `interact` → advance_dialog ~5 times. Chairman gives Bicycle Voucher.
4. **Verify:** Bag contains Bicycle Voucher (item ID 0x43-ish, key item).

---

## PHASE 3: VIRIDIAN FOREST → PEWTER CITY

### Step 9: Route 2 South
**Current:** Map 0x01.
1. Walk east to the Route 2 exit (east side of Viridian City, at approximately X=35, Y=10).
2. Map changes to Route 2 (0x0D). D35E = 0x0D.

### Step 10: Viridian Forest
**Current:** Map 0x0D (Route 2).
1. Find the west entrance to Viridian Forest (walk west through a gap in the cuttable trees). Map changes to Viridian Forest (0x28). D35E = 0x28.

**Navigate Viridian Forest maze:**
1. Walk south along the east wall until you hit the south boundary.
2. Walk west along the south wall, navigating around tree obstacles.
3. Continue northwest through the tree maze.
4. Look for the northwest exit (Pewter City direction).
5. This is a maze. **Key pattern:** Hug the south and west walls. The path serpentines.
6. En route: encounter wild Caterpie/Weedle/Pikachu (rare, ~10%). Catch a Pikachu if possible — Thunder Shock super effective vs. Brock's Onix and future Mt. Moon Zubat (not very effective against Zubat though — actually Electric is neutral vs. Zubat). Still valuable for Water types in general.

### Step 11: Pewter City
**Current:** Exiting Viridian Forest west → Pewter City (0x02). D35E = 0x02.
1. **SAVE at Pokémon Center (17, 15).** Heal.
2. **Grind to Lv. 12+** on Route 3 trainers if needed (exit east side).
3. Buy Potions at the Mart (optional but recommended).

### Step 12: Pewter Gym — Brock Battle

**Map 0x61 (Pewter Gym). Enter at (27, 13).**

**Navigation:**
1. Walk south through the gym.
2. **Jr. Trainer (Bug Catcher)** at approximately (3, 5) blocks the path.
3. Stand facing him (he faces right, so stand to his right or below). `interact`.
4. **Battle: Bug Catcher** — Weedle Lv.10, Caterpie Lv.10. 2 Pokémon, both weak. Any attack wins.
5. advance_dialog 3 times after victory.
6. Walk south to Brock at (3, 2). Brock faces down at (3, 1). Stand at (3, 2) facing Up.
7. `interact` → battle starts.

**BATTLE: BROCK**
```
Geodude Lv.12 — Tackle, Defense Curl  
Onix Lv.14 — Tackle, Screech, Bide
```

*With Squirtle:*
- Turn 1: A, A, A (use Bubble or Water Gun — whichever you have. Lv.5 Squirtle only knows Tackle and Tail Whip. At Lv.12, Squirtle knows Tackle, Tail Whip, Bubble.)
- Use Bubble every turn (2× effective Geodude, 2× effective Onix → Ground/Rock).
- If Onix uses Screech: your Defense drops. Keep HP above 15.
- If Onix uses Bide: it stores damage for 2 turns, then releases 2× stored. Switch to weaker moves or just finish it with Bubble.
- Geodude faints in 1-2 Bubbles. Onix faints in 2-3 Bubbles.

**After victory:**
- `advance_dialog` ~5 times: "I took you for granted!"
- Brock gives BoulderBadge and TM34 (Bide).
- **Verify:** D35E = 0x02 (back in Pewter City). D356 AND 0x01 != 0 → BoulderBadge obtained.
- **Effect:** Attack stat +12.5% in all party Pokémon. HM05 Flash usable outside battle.

---

## PHASE 4: PEWTER CITY → CERULEAN CITY

### Step 13: Route 3
**Current:** Pewter City. Exit east → Route 3 (0x0E).
- Walk east following the path. Trainers will see you from their sight lines.
- Bug Catchers, Lasses. Defeat them for experience.
- Navigate to the Mt. Moon entrance at the far east side.

### Step 14: Mt. Moon

**SAVE before entering Mt. Moon** (heal at Pewter Center first).

**1F (0x25):**
1. Enter cave. Collect the **Potion** (Poké Ball at ~ 5, 1) by walking to the ball and pressing A.
2. Navigate around the central pit.
3. Collect **Moon Stone** at approximately (21, 13), useful for evolving Clefairy/Nidorina/Nidorino.
4. Walk to the north-east exit stairs.

**B1F (0x26):**
1. Larger cave. Navigate carefully.
2. Find **Super Nerd** NPC — talk to him. advance_dialog → receives **TM07 (Horn Drill)**. High-value item but low accuracy OHKO move.
3. Navigate to the south exit.

**B2F (0x27):**
1. Smallest level. Navigate to Route 4 exit (north passage).
2. Wild Pokémon in Mt. Moon: Zubat (common), Geodude, Paras (rare), Clefairy (very rare, ~5%).

### Step 15: Route 4
**Exit Mt. Moon → Route 4 (0x0F).**
1. Walk east through the route to Cerulean City.
2. Collect any items on the ground.

### Step 16: Cerulean City
**Arrive at Cerulean City (0x03).**
**SAVE at Pokémon Center (17, 3). Heal.**

**Immediate task: Rival Battle #2 on Route 22 (west of Viridian City).**

**Route 22 Rival Fight:**
1. Walk west from Cerulean City → Route 5/24? No. Go back through Viridian Forest? No. Go back south through Route 2.
2. Actually: Go WEST from Viridian City (through the tree-blocked path that requires Cut — or go around another way).
3. Easier: From Pewter City area, go south past Viridian Forest to Viridian City, then west to Route 22.
4. Walk west into Route 22. Rival stops you at approximately (5, 3).

**Rival #2:** Pidgey Lv.9, Starter Lv.8.
- Pidgey: Gust. Use Tackle normally.
- Starter (e.g. Bulbasaur if you picked Squirtle): Vine Whip from Ivysaur? No, Bulbasaur Lv.8. Use Bubble.
- Easy win.

**Memory check:** Defeating Rival sets trainer flags for these two Pokémon.

### Step 17: Cerulean City → Bike Shop
1. Return to Cerulean City.
2. Go to the **Bike Shop** at approximately (27, 9).
3. Talk to the owner. You need the **Bicycle Voucher** (from Viridian Fan Club, obtained in Step 8).
4. `interact` → advance_dialog → You receive the **Bicycle**.
5. **Press SELECT** over the Bicycle in your bag to mount it in the overworld. Running speed becomes 3×.

### Step 18: Cerulean City Side Quests
1. **Get TM28 (Dig):** Go to the house just north of the Pokémon Center. There's a Rocket Grunt inside. Defeat/bypass him. Talk to the NPC → receives **TM28 (Dig)**. **Extremely useful Ground-type move** — 100 power, 100% accuracy.
2. Talk to the girl who owns the house — she mentions the Rocket event.

### Step 19: Route 24/25 — Nugget Bridge to Bill's Cottage

1. Exit Cerulean City north → Route 24 (0x12).

**IMPORTANT MEW GLITCH SETUP:** 
- On Route 24, there is a **Jr. Trainer♂ in tall grass, west of Nugget Bridge**. 
- **DO NOT** defeat this trainer if you plan to use the Mew glitch later.
- Avoid stepping into his sight line (he faces right, stands in tall grass).

**Nugget Bridge (Route 24):**
1. Walk north across the bridge. 5 trainer battles and 1 Rocket battle.
2. Each trainer: `advance_dialog` ~3 times after winning.
3. Defeat all trainers on the bridge.

**Rival Battle #3 (Nugget Bridge, on Route 25 side):**
Rival has: Pidgeotto Lv.18, Rattata Lv.15, Abra Lv.15 (only knows Teleport), Bulbasaur Lv.17.
- Abra only knows Teleport — it will flee on its turn. Use this turn to heal or attack another Pokémon.
- Pidgeotto uses Sand-Attack (lowers accuracy). Switch if hit repeatedly.
- Bubble from Squirtle wins this.

**Bill's Sea Cottage (Route 25):**
1. Continue along Route 25 past the Rival to Bill's house.
2. Enter, talk to Bill → advance_dialog through his transformation event.
3. Bill gives **S.S. Ticket** (key item). Required for SS Anne.

---

## PHASE 5: CERULEAN GYM → VERMILION CITY

### Step 20: Cerulean Gym — Misty Battle

**Map 0x62. Enter at (23, 17).**

**Inside the gym:**
1. Walk across platforms. Avoid the Swimmer on the right (you can also fight her if you want).
2. Walk to Misty at approximately (5, 3), surrounded by water platforms.
3. `interact` (facing Up to see her on her platform).

**BATTLE: MISTY**
```
Staryu Lv.18 — Tackle, Water Gun
Starmie Lv.21 — Tackle, Water Gun, Bubblebeam
```

*With Squirtle:*
- Bubble/Bubblebeam is NOT very effective vs. Water types! Water resists Water.
- Use Tackle (neutral). Tail Whip to lower Starmie's Defense.
- Starmie has high Special and Speed. Bubblebeam can lower your Speed.
- **Tip:** If you caught Pikachu in Viridian Forest, use Thunder Shock (2× effective vs. Water).
- If Pikachu: Thunder Shock wins in 2-3 hits.

*With Pikachu:*
- Thunder Shock both: 2× effective. Staryu dies in 1-2 hits. Starmie dies in 2-3.

**After victory:**
- advance_dialog ~3 times. Misty gives CascadeBadge and TM11 (Bubblebeam).
- **Verify:** D356 AND 0x02 != 0 → CascadeBadge obtained.
- **Effect:** Pokémon up to Lv.30 obey (traded). HM01 Cut usable outside battle.

### Step 21: Route 5 → Underground Path → Route 6 → Vermilion City

1. Walk south from Cerulean City → Route 5 (0x10).
2. Navigate south. Enter Underground Path (0x8E) entrance.
3. Navigate Underground Path (simple tunnel) → Exit on Route 6 (0x11) side.
4. Walk south on Route 6 to Vermilion City (0x04).

### Step 22: Vermilion City

**SAVE at Pokémon Center. Get TM28 (Dig) from house if you got it in Cerulean.**

**Key tasks:**
1. **SS Anne access:** Go to the dock at the east side of Vermilion City. Present S.S. Ticket to the guard.
2. Buy Potions at the Mart.

---

### Step 23: SS Anne

**SAVE before boarding. This is a long sequence.**

**1F to 2F to B1F navigation:**
- Navigate right (east), then upstairs (north).
- **Rival Battle #4** occurs on 1F/2F. Rival's team: evolved starter Lv.20, Pidgeotto Lv.19, Kadabra Lv.18, Raticate Lv.16.
- Navigate through cabins. Each trainer must be defeated.
- **Captain's cabin (1F, accessible from back):** Talk to the Captain. advance_dialog through his seasick event.
- The Captain teaches a Pokémon **Cut** directly (this is how you obtain it — no HM item, just a script that teaches Cut to a party Pokémon).

**After the SS Anne event (ship returns):** You're back in Vermilion City.

### Step 24: Vermilion Gym — Lt. Surge Battle

**Map 0x63. Enter at (27, 13) or appropriate warp.**

**Gym puzzle:** Trash can switches. Press interact on trash cans until you find the correct pair that opens the door.

**Memory-driven approach:**
1. Press interact on first trash can. advance_dialog "click!" 
2. Then press interact on each other trash can one by one.
3. When the second correct can is pressed, the door opens (the event flag for the door changes).
4. If no door opens, the first can was wrong. Reset, try another first can.
5. Eventually you reach Lt. Surge's room.

**BATTLE: LT. SURGE**
```
Voltorb Lv.21 — Tackle, Screech, Sonicboom (fixed 20 HP)
Pikachu Lv.18 — Thundershock, Growl, Thunder Wave, Quick Attack
Raichu Lv.24 — Thundershock, Growl, Thunderbolt (high damage)
```

*With Squirtle:* No super effective option. Use physical Tackle or Bubble (neutral vs. Electric).
- Sonicboom deals exactly 20 HP (fixed damage, ignores stats).
- Thor

nder Wave can paralyze. Bring Parlyz Heal or Full Heal.
- If you have Dig (TM28) taught to Squirtle or any Pokémon: Dig is Ground type = IMMUNE to Electric moves and super effective vs. Electric types. This is the best option.

**After victory:**
- ThunderBadge and TM24 (Thunderbolt) obtained.
- **Verify:** D356 AND 0x04 != 0.
- **Effect:** Defense +12.5%. HM02 Fly usable outside battle.

### Step 25: Get HM02 Fly

1. From Vermilion City, walk south → Diglett's Cave exit at Route 2 → Route 2 south → Viridian City.
2. From Viridian City, walk east to Route 2 → Route 16 (north of Celadon area).
3. **Route 16 (0x18):** There's a Cut-able tree blocking a hidden alcove. Cut it.
4. Walk into the hidden alcove. Find the house containing an NPC.
5. Talk to NPC → receives **HM02 Fly**.

---

## PHASE 6: VERMILLION → LAVENDER TOWN → CELADON CITY

### Step 26: Diglett's Cave (Shortcut)

From Vermilion City → Route 11 → Diglett's Cave entrance.
Navigate through Diglett's Cave to the Route 2 exit.
This avoids backtracking through Rock Tunnel.

**Or:** Use Fly → Cerulean City → walk south to Route 9 → Rock Tunnel → Route 10 → Lavender Town.

### Step 27: Rock Tunnel (with Flash)

**Enter Rock Tunnel from Route 9 (east side).**

HM05 Flash (obtained from Oak's Aide in Vermilion after BoulderBadge) illuminates the dark cave.

**Navigation:** Navigate north-west through 1F to the B1F staircase. B1F has **HM04 Strength** — get it from the NPC. B1F continues to Route 10 exit.

### Step 28: Lavender Town

**Map 0x05. SAVE at Pokémon Center.**

**Pokémon Tower event:**
You cannot clear the Pokémon Tower without Silph Scope. For now, note the tower and return after getting Silph Scope from Rocket Hideout (Celadon) → Silph Co.

### Step 29: Celadon City (Map 0x06)

**Walk east from Rock Tunnel → Route 10 → south → Lavender → ... → Fly or walk → Route 5/Underground Path 7-8 → Saffron (blocked initially) → Route 8 → Celadon.**

**Arriving at Celadon City:**
1. **SAVE at Pokémon Center (13, 9).**
2. **Rocket Hideout access:** Go to Game Corner (31, 9). Find the hidden passage behind the inspectors (walk into the right wall of the Game Corner to find the drop to the Hideout).
3. **Or:** Complete Celadon Gym first, then Game Corner.

### Step 30: Celadon Gym — Erika Battle **

*Continued in Part B...*

---
