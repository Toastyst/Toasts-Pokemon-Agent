# SECTION 6: BATTLE SYSTEM GUIDE (Memory-Driven)

## 6.1 — Reading Battle State

### Before Battle Starts
When a battle starts (triggered by stepping into a trainer's sight line, walking in tall grass, or story event):
1. Read `D057` → Battle type: `0`=Wild, `1`=Trainer, `2`=Old Man, `3`=Safari, `4`=Forced
2. Read enemy species from `D0D8` (trainer) or `CFCC` (wild)
3. Read enemy level from `D0DD` or `CFD6`
4. Read enemy current HP from `D0DD`/`CFD1` (2 bytes, little-endian)
5. Read enemy moves from `CFCD` (4 bytes)

### During Battle — Turn Structure
Each turn, the battle system:
1. Calculates move order (speed-based, unless priority involved)
2. Executes faster Pokémon's move
3. Executes slower Pokémon's move
4. Applies end-of-turn effects (poison, burn, Leech Seed, Toxic counter increase)
5. Checks for faints

### Between-Turn Check
```
1. Read enemy current HP (D0DD or DFD1)
2. If enemy HP == 0: battle won → apply experience, return to overworld
3. Read all party members' current HP
4. Check status conditions
5. Decide next action
```

---

## 6.2 — Move Selection by Button Presses

### Battle Menu Layout
```
+------------+
| FIGHT      |  (Index 0 — default)
| POKEMON    |  (Index 1)
| ITEM        |  (Index 2)
| RUN         |  (Index 3)
+------------+
```

### Selecting a Move (after pressing A on FIGHT)
Moves are displayed as:
```
+------------+
| Move1      |  (Index 0 — default)
| Move2      |  (Index 1)
| Move3      |  (Index 2)
| Move4      |  (Index 3)
+------------+
```

**Button sequence to select move N (0-indexed):**
```
A           (open FIGHT menu, which displays moves)
press Down N times   (move cursor to move N)
A           (select the move)
```
The battle automatically processes the move.

### Example — Use 3rd move on your active Pokémon:
```
Read current HP to assess situation
Press A          (opens battle menu, cursor on FIGHT)
Press A          (select FIGHT, opens move list)
Press Down twice (move cursor from move 1 to move 3)  
Press A          (select move 3)
Wait for turn to resolve
```

### Switching Pokémon
```
Press A         (opens battle menu)
Press Down once (moves cursor from FIGHT to POKEMON)
Press A          (select POKEMON, opens party list)
Press Down N times  (move cursor to slot N+1)
Press A          (select that Pokémon as switch target)
```

### Using an Item in Battle
```
Press A          (opens battle menu)
Press Down twice (moves cursor to ITEM)
Press A          (opens bag item list)
Scroll to desired item with Down presses
Press A           (select item)
Select target Pokémon with Down/A
```

**Healing Item Quick Reference (position in bag depends on what you carry):**
- Items appear in the same order as your bag list. Know the index.
- If Potion is your first bag item: A, Down, A, A (on first Pokémon's slot)
- If you carry the items in consistent order, you can always select by index.

### Running from Battle
```
Press A           (opens battle menu)
Press Down three times  (moves cursor to RUN)
Press A           (attempt to run)
```
**Run success rate:** Based on your active Pokémon's Speed vs. the enemy's Speed.
- If your Speed > enemy Speed: almost always escapes
- Trainer battles: **CANNOT RUN** unless you used a Smoke Ball or there's a special event
- In trainer battles, the RUN option appears but will fail with "No! There's no running from a TRAINER battle!"

---

## 6.3 — Decision Tree for Memory-Driven Battle

```
FUNCTION decide_battle_action():
    
    my_HP = read_active_Pokemon_current_HP()
    my_max_HP = read_active_Pokemon_max_HP()
    enemy_HP = read_enemy_current_HP()
    enemy_species = read_enemy_species()
    my_moves = read_active_Pokemon_moves()
    
    // PRIORITY 1: Check if any party member needs reviving
    // (Do this between battles, not during)
    
    // PRIORITY 2: Is enemy about to faint?
    // Estimate damage: if enemy_HP is low, use strongest available move
    
    // PRIORITY 3: Is my Pokémon in danger?
    IF my_HP < my_max_HP * 0.25:
        // Below 25% HP — high risk
        // Option A: Heal with recovery item or move
        // Option B: Switch to a tankier Pokémon
        IF has_recovery_item():
            use_recovery_item()
        ELSE IF has_Pokemon_of_type_that_resists(enemy):
            switch_to_resistant_Pokemon()
        ELSE:
            use_strongest_attack()     // Try to finish before fainting
    
    // PRIORITY 4: Is there a super effective matchup?
    FOR each move in my_moves:
        effectiveness = type_matchup(move.type, enemy_type1) * type_matchup(move.type, enemy_type2)
        IF effectiveness >= 2.0:    // Super effective OR better
            use_that_move()
            RETURN
    
    // PRIORITY 5: Use highest-damage neutral STAB move
    best_move = find_move_with_highest_power_that_matches_my_type()
    use_that_move()
    
    // PRIORITY 6: Status moves
    // If all else fails or to set up: Toxic, Sleep, Paralysis, etc.
```

---

## 6.4 — Gym Leader & Elite Team Quick Strategies

All teams from Section 1 reference, plus battle details here.

---

### BROCK (Pewter Gym)

**Team:** Geodude Lv.12, Onix Lv.14

| Your Starter | Best Strategy |
|-------------|---------------|
| Bulbasaur | Vine Whip (2× vs. both). Tackle otherwise. Easy win. |
| Charmender | Use nearby Pikachu (Thunder Shock, 2× vs. Onix). Or use Dig (TM) if taught. Growl to lower Attack. |
| Squirtle | Water Gun / Bubble are 2× effective. Easy win. |

**Battle flow:** Use super effective move. If using Charmander, prioritize Pikachu. If the Onix uses Screech, it helps you (lower Defense). Onix's Bide can store damage — hit with weak moves until ready.

---

### MISTY (Cerulean Gym)

**Team:** Staryu Lv.18, Starmie Lv.21

| Your Starter | Best Strategy |
|-------------|---------------|
| Bulbasaur | Vine Whip (2× vs. both). Razor Leaf by Lv.25+. Easy. |
| Charmender | Use Pikachu (Thunder Shock/Thunderbolt if taught TM). Super effective. |
| Squirtle | Bubble won't be effective (water vs. water). Use Pikachu if available, or grind levels. Usestatus moves. |

**Starmie** has high Special and Speed. Bubblebeam may lower your Speed. Keep HP high.

---

### LT. SURGE (Vermilion Gym)

**Team:** Voltorb Lv.21, Pikachu Lv.18, Raichu Lv.24

| Your Starter | Best Strategy |
|-------------|---------------|
| Bulbasaur | Neutral damage. Use Vine Whip or normal moves. |
| Squirtle | Neutral damage. Bubble not effective. Use physical moves or Ground type if available. |
| Any | If you have Dig (TM from Cerulean house it) taught to any Pokémon, Ground moves are immune to Electric. Alternatively, just overpower with levels and neutral/fighting moves. |

**Raichu** has Thunderbolt (high damage). Keep your HP above 40%. Use physical Fighting moves (Karate Chop) for super effective vs. Raichu (Normal component makes it not very effective).

---

### ERIKA (Celadon Gym)

**Team:** Victreebel Lv.29, Tangela Lv.24, Vileplume Lv.29

| Your Starter | Best Strategy |
|-------------|---------------|
| Charazard | Flamethrower (4× vs. Victreebel, 2× vs. all Grass). Sweep. |
| Blastoise | Surf/Bubblebeam not effective. Use Ice Beam (TM13) for 2× on all. Or use physical Normal moves. |
| Venusaur | Razor Leaf (2× Grass vs. Grass). Or Fire TM if available. |

**Victreebel:** Wrap can trap you. Try to kill quickly. Sleep Powder can incapacitate your active Pokémon.

---

### KOGA (Fuchsia Gym)

**Team:** Koffing Lv.37, Muk Lv.39, Koffing Lv.37, Weezing Lv.43

| Strategy |
|----------|
| Psychic moves (2× effective). Earth moves (2× effective). |

**Toxic from Weezing:** Very dangerous — Toxic damage increases each turn. Heal with Full Heal if your Pokémon gets hit with Toxic. Use Psychic (Alakazam, Mewtwo, or TM attacks) to sweep.

---

### SABRINA (Saffron Gym)

**Team:** Kadabra Lv.38, Mr. Mime Lv.37, Venomoth Lv.38, Alakazam Lv.43

| Strategy |
|----------|
| Bug moves (not very effective in Gen 1). Physical Fighting moves. Ghost moves. |

**In Gen 1, Psychic-types have NO weakness from Ghost** (bug). Only Bug is super effective, but most Bug/Poison Pokémon take neutral from Psychic.

**Best approach:** Use strong physical attackers (High Attack, high-level Normal-type moves), or level advantage. Alakazam is very fast and hits hard. Lower its accuracy with Sand-Attack or use status (Toxic/Paralysis) if possible.

---

### BLAINE (Cinnabar Gym)

**Team:** Growlithe Lv.42, Ponyta Lv.40, Rapidash Lv.42, Arcanine Lv.47

| Strategy |
|----------|
| Water moves (2× effective). Rock moves (2× effective). Ground moves (2× effective). |

Arcanine is fast and powerful (Take Down recoil). Use Surf/Hydro Pump from Blastoise or Ice Beam (not as effective vs. Fire).

---

### GIOVANNI (Viridian Gym)

**Team:** Rhyhorn Lv.45, Dugtrio Lv.42, Nidoqueen Lv.44, Nidoking Lv.45, Rhydon Lv.50

| Strategy |
|----------|
| Water moves (4× vs. Rhyhorn/Rhydon). Ice moves. |

Giovanni's team is Ground/Rock heavy. Grass moves from Venusaur are 4× effective vs. Rhydon/Rhyhorn. Surf/Bubblebeam from Blastoise works. Nidoqueen/Nidoking are Ground/Poison — Surf (4×) or Psychic (2×) / Ice (2×).

---

### ELITE FOUR — LORELEI

**Team:** Dewgong Lv.54, Cloyster Lv.53, Slowbro Lv.54, Jynx Lv.56, Lapras Lv.56

| Strategy |
|----------|
| Electric (2× vs. all Water types). Thunderbolt is king here. |

- Lapras uses Blizzard → threatens Grass types.
- Slowbro uses Amnesia (boosts Special massively) — kill it before it sets up.
- Dewgong uses Rest (full heal) — finish it off before it wakes up.
- Cloyster has massive Defense → use Special moves, not physical.

**Recommended:** Zapdos (Thunderbolt), any Electric type, strong Electric TMs.

---

### ELITE FOUR — BRUNO

**Team:** Onix Lv.53, Hitmonchan Lv.55, Hitmonlee Lv.55, Onix Lv.56, Machamp Lv.58

| Strategy |
|----------|
| Psychic (2× effective vs. Fighting). Flying moves (2×). |

- Onix: weak to Water and Grass.
- Machamp: has Focus Energy bug (reduces crit rate) and Fissure (OHKO). Kill quickly or miss the OHKO.
- Hitmonlee's Jump Kick/Hi Jump Kick: If you're in the air (Fly), it will miss and Hitmonlee takes massive crash damage!

**Recommended:** Gengar (immune to Fighting/Normal moves in Gen 1, retaliates with Psychic).

---

### ELITE FOUR — AGATHA

**Team:** Gengar Lv.56, Golbat Lv.56, Haunter Lv.55, Arbok Lv.58, Gengar Lv.60

| Strategy |
|----------|
| Psychic (2× vs. Poison, immune to Ghost in Gen 1). Ground moves (immune to Electric, super effective vs Poison/Ground). |

- Gengar: Confuse Ray, Night Shades, Hypnosis, Dream Eater combo is dangerous.
- Use Psychic to sweep — Psychic types are immune to Ghost moves in Gen 1.
- Arcan be status-heavy (poison). Bring Full Heals.

**Recommended:** Alakazam (Psychic sweep), strong Psychic types, Earthquake from Dugtrio or Nidoking.

---

### ELITE FOUR — LANCE

**Team:** Gyarados Lv.58, Dragonair Lv.56, Dragonair Lv.56, Aerodactyl Lv.60, Dragonite Lv.62

| Strategy |
|----------|
| Electric (4× vs. Gyarados, 2× water). Ice vs. Dragon (2×). |

- Gyarados: 4× weak to Electric. Thunderbolt from any Electric type.
- Dragonites: Hyper Beam + Barrier setup. Ice Beam (4× vs. Dragon/Flying) if you have it.
- Dragonair: Dragon Rage (fixed 40 damage) is annoying but sets consistent chip damage.

**Recommended:** Lapras with Thunderbolt + Ice Beam. Any Electric type (Zapdos, Electabuzz) for Gyarados. Ice Beam on a Water type for Dragons.

---

### CHAMPION — BLUE (Rival Final)

**Team (if player chose Squirtle, rival has Bulbasaur/Venusaur):**

| Pokémon | Level | Moves |
|---------|-------|-------|
| Pidgeot | Lv.60 | Wing Attack, Mirror Move, Sky Attack, Whirlwind |
| Alakazam | Lv.57 | Psybeam, Psychic, Reflect, Recover |
| Rhydon | Lv.59 | Leer, Tail Whip, Fury Attack, Horn Drill |
| Arcanine | Lv.57 | Roar, Ember, Take Down, Agility* |
| Exeggutor | Lv.59 | Stomp, Barrage, Hypnosis |
| Venusaur | Lv.63 | Razor Leaf, Whip, Poisonpowder, SolarBeam |

(*Arcanine moves may vary based on starter choice)

**Strategy:**
- Exeggutor: Psychic or Bug moves. Only Normal moves otherwise (Psychic immune to Grass STAB? No, Grass hits Psychic ×2). Use Psychic → Bug moves (Venomoth).
- Gyarados/Electric: Zapdos if not wasted on Lorelei.
- Rhydon: Grass or Water moves (4× for both Grass+Ground).
- Alakazam: Physical moves or quick KO.
- Venusaur: Psychic (2×), Fire (2×), Ice (2×).
- **Arcanine's Hyper Beam:** Big damage, but if it KOs, no recharge. If it doesn't KO, it recharges next turn → free turn.

**Healing between champions:** There IS a heal point between the last Elite Four member and the Champion. Use it.

---

## 6.5 — Safari Zone Battle Differences

In Safari Zone battles, instead of FIGHT menu:
```
+-----------+
| BALL      |  (Throw Safari Ball — equivalent to "catch")
| BAIT      |  (Makes catching harder but less likely to flee)
| ROCK      |  (Makes catching easier but more likely to flee)  
| RUN       |  (Flee)
+-----------+
```

Battle flow: Wild Pokémon can flee after any turn. Your goal is to weaken and catch before running out of Safari Balls (30 given).

---

## 6.6 — Day Care and Leveling

To level up efficiently without battle:
1. Leave a Pokémon at the Day Care on Route 4.
2. The Pokémon gains 1 XP per step taken.
3. This is VERY slow for high-level Pokémon but useful for low-level ones.

---

## 6.7 — Quick Type Matchup Reference for Major Battles

| Opponent | Super Effective | Not Very Effective |
|----------|----------------|-------------------|
| Brock (Rock/Ground) | Water, Grass, Fighting, Ice | Normal, Fire, Electric, Poison, Flying |
| Misty (Water) | Electric, Grass | Water, Fire, Ice |
| Surge (Electric) | Ground | Electric, Flying, Dragon |
| Erika (Grass) | Fire, Ice, Flying, Bug, Psychic | Water, Electric, Rock, Ground |
| Koga (Poison) | Psychic, Ground | Grass, Fighting, Bug, Poison |
| Sabrina (Psychic) | Bug | Fighting, Psychic, Normal* |
| Blaine (Fire) | Water, Rock, Ground | Fire, Grass, Ice, Bug, Dragon |
| Giovanni (Ground/Rock) | Water, Grass, Ice | Normal, Fire, Electric, Poison, Flying, Bug |
| Lorelei (Ice/Water) | Electric, Grass, Fighting, Rock | Fire |
| Bruno (Fighting/Rock) | Psychic, Grass, Water, Flying | Normal, Rock, Fire, Electric |
| Agatha (Ghost/Poison) | Psychic, Ghost, Ground | Normal*, Fighting*, Grass, Poison |
| Lance (Dragon/Flying/Water) | Electric, Ice, Rock, Dragon | Grass, Electric, Fire, Water, Fighting, Bug, Ground* |
| Champion (Mixed) | Depends on team composition | — |

*In Gen 1, Ghost is immune to Normal and Fighting types. Psychic is immune to Ghost moves.*

---

*Continue to Section 7: Advanced Data & Glitches*
