# SECTION 7: ADVANCED DATA & GLITCHES

## 7.1 — Mew Glitch (Trainer-Fly Method)

### Overview
This is the most famous and useful glitch in Pokémon Red. It allows obtaining **Mew** (or any Pokémon by manipulating the Special stat).

### Prerequisites
- `Must NOT have defeated:` Jr. Trainer♂ on Route 24 (in tall grass, west of Nugget Bridge)
- `Must NOT have defeated:` Swimmer in Cerulean Gym (first one, on right in water)
- Have an **Abra** (caught on Route 24/25 in Red/Blue, or Route 5 in Yellow)
- Have visited Cerulean City's Pokémon Center at least once (sets Teleport destination)

### Memory-Checkable Precondition Checklist
```
1. Read trainer flag for Jr. Train on Route 24 → must be 0 (undefeated)
2. Read trainer flag for Swimmer in Cerulean Gym → must be 0 (undefeated)
3. Verify Abra in party (species ID from D164 list)
4. Verify player is currently outside Cerulean City (map 0x03)
```

### Steps (Memory-Driven)

**Phase 1: Setup**
1. Fly to Cerulean City (or walk). Confirm map ID = 0x03, center at PC.
2. Save the game (so you can retry).
3. Walk to Route 24 (north of Cerulean), confirm map ID = 0x12.

**Phase 2: Trigger**
1. Walk north on Route 24 until you see the Jr. Trainer in the grass.
   - In memory terms: verify the NPC sprite for Jr. Train appears on screen.
   - He is in tall grass, faces to the right.
2. Stand such that the Jr. Train is ONE tile to the LEFT of the screen edge.
   - Position: He is exactly one tile off screen to his right.
3. Hold START while stepping down (south) into the Jr. Train's line of sight.
   - The `!` exclamation mark appears over the trainer.
   - **BEFORE the battle confirmation text opens**, your menu opens (because you held START).
4. Select Pokémon → Abra → Teleport.
5. Confirm Teleport targeting Cerulean City.
6. You return to Cerulean City. The menu may be stuck (this is expected glitched behavior).

**Phase 3: Exploitation**
1. Walk to Cerulean Gym. The menu bug persists.
2. Battle the Swimmer on the right side of the gym water.
   - **IMPORTANT:** The Swimmer must take at least one step toward you during the battle approach.
   - If the menu doesn't open when the Swimmer sees you, the glitch failed → reload and retry.
   - If the Swimmer sees you AND the menu opens → proceed.
3. Defeat the Swimmer (Lv.16 Horsea + Lv.16 Shellder).

**Phase 4: Encounter Mew**
1. Leave the gym and walk back south to Route 24.
   - Do NOT detour anywhere else.
   - Do NOT open the menu manually.
2. Upon entering Route 24, the menu opens automatically.
3. Press B to close it → A wild Pokémon battle starts.
4. The wild Pokémon is **Mew Lv.7** (species ID 0x15, hex).

**Phase 5: Catch Mew**
1. Mew Lv.7 has: Pound, Transform (only 10 PP each). Catch rate = 45 (same as legendaries).
2. Lower HP, apply sleep if possible, use Ultra Ball.
3. If you KO it, you need to redo the glitch.

### Mew's Level Manipulation
The level of the Mew encounter is determined by the stat stage of the last Pokémon fought. Use Growl (lowers Atk stage) on a sacrificial Pokémon before the encounter to adjust Mew's level. A level 1 Mew can exploit the experience underflow glitch to reach Lv.100.

---

## 7.2 — Old Man Item Duplication

### Overview
Items in the 6th slot of your bag get duplicated by speaking to the Old Man in the tutorial.

### Steps
1. Have exactly 5 items in your bag (D31D = 5).
2. Add the item you want to duplicate (now 6 items).
3. Talk to the Old Man at the northern entrance of Viridian City.
   - Use **default name** "OLD MAN" (not a custom name).
   - The Old Man catching tutorial uses a special script.
4. After the tutorial, all items from slot 6 onward are duplicated.

### Memory Verification
```
Before: D31D = item count, D31E+10 and D31E+11 = 6th item
After: D31D = higher count. Verify duplicated items present.
```
**Note:** Too many items (above 20) can cause bugs. Don't exceed the 20-item bag limit.

---

## 7.3 — Experience Underflow (Level 100 from Low-Level Pokémon)

A Pokémon with very low experience (near 0) that gains experience from a high-level defeat can "underflow" and jump to level 100. This works because the experience counter is stored in 3 bytes — if it goes below 0, it wraps around to 16,777,215 (0xFFFFFF), which corresponds to level 100.

Used in conjunction with: Catching a low-level Mew (Lv.1-7) from the Mew glitch, then defeating a high-exp-yield trainer or Pokémon.

---

## 7.4 — Stat Modification Glitch

Using X Attack, X Defend, X Speed, X Special in battle can cause stat stages to overflow and corrupt memory if used repeatedly. In Gen 1, this is the basis for many speedruns but can also cause game crashes.

**Practical application:** Use 6 X Accuracy boosts, then use OHKO moves (Horn Drill) for guaranteed hits. The stat overflow can cause graphical glitches but the OHKO check still works.

---

## 7.5 — Infinite TM/HM Glitches

In Gen 1, HMs can be used unlimited times (as items). TMs are single-use items. There is no infinite TM glitch without external devices.

---

## 7.6 — 151 Pokémon Reference (Red Version Obtainable)

### Starters
| # | Species | Type | Location |
|---|---------|------|----------|
| 001 | Bulbasaur | Grass/Poison | Oak's Lab (gift) |
| 004 | Charmander | Fire | Oak's Lab (gift) |
| 007 | Squirtle | Water | Oak's Lab (gift) |

### Wild Encounter Tables (key encounters only)

| Route/Floor | Pokémon | Level Range |
|-------------|---------|-------------|
| Viridian Forest | Pikachu | 3–5 (rare, 10%) |
| Mt. Moon B2F | Clefairy | 8–10 (rare, 5%) |
| Route 22 | Pidgey, Rattata | 2–5 |
| Route 6 | Oddish, Bellsprout, Pidgey | 12–15 |
| Route 12–15 | Various (Pidgey,Oddish,Venonat, etc.) | 20–28 |
| Route 16–18 | Spearow, Doduo, etc. | 18–24 |
| Safari Zone | Chansey (2–5%), Kangaskhan, Tauros, Scyther, Pinsir | 22–31 |
| Seafoam Islands | Seel, Horsea, Krabby, etc. | 25–35 |
| Pokémon Mansion | Grimer, Growlithe, Ponyta, Magmar | 30–40 |
| Victory Road | Machoke, Graveler, Onix, Marowak | 38–48 |
| Cerulean Cave | Golbat, Machoke, Magneton, Ditto, etc. | 50–60 |
| Cerulean Cave | Mewtwo | 70 |

### Legendary Birds
| # | Species | Type | Location |
|---|---------|------|----------|
| 144 | Articuno | Ice/Flying | Seafoam Islands B4F (Lv.50) |
| 145 | Zapdos | Electric/Flying | Power Plant (Lv.50) |
| 146 | Moltres | Fire/Flying | Victory Road (Lv.50) |

### Mythical
| # | Species | Type | Location |
|---|---------|------|----------|
| 150 | Mewtwo | Psychic | Cerulean Cave B1F (Lv.70) |
| 151 | Mew | Psychic | Mew glitch only (Event unavailable in Red) |

### Trade Evolutions (Must Trade to Another Game to Evolve)
| Base | Evolution | Trade |
|------|-----------|-------|
| Kadabra (064) | Alakazam | Trade |
| Machoke (67) | Machamp | Trade |
| Graveler (75) | Golem | Trade |
| Haunter (93) | Gengar | Trade |

### Evolution by Level (Key Examples)
| Pokémon | Evolution | Level |
|---------|-----------|-------|
| Bulbasaur | Ivysaur | Lv.16 |
| Ivysaur | Venusaur | Lv.32 |
| Charmander | Charmeleon | Lv.16 |
| Charmeleon | Charizard | Lv.36 |
| Squirtle | Wartortle | Lv.16 |
| Wartortle | Blastoise | Lv.36 |
| Caterpie | Metapod | Lv.7 |
| Metapod | Butterfree | Lv.10 |
| Weedle | Kakuna | Lv.7 |
| Kakuna | Beedrill | Lv.10 |
| Pidgey | Pidgeotto | Lv.18 |
| Pidgeotto | Pidgeot | Lv.36 |
| Rattata | Raticate | Lv.20 |
| Spearow | Fearow | Lv.20 |
| Ekans | Arbok | Lv.22 |
| Pikachu | Raichu | Thunder Stone |
| Nidoran♀ | Nidorina | Lv.16 |
| Nidorina | Nidoqueen | Moon Stone |
| Nidoran♂ | Nidorino | Lv.16 |
| Nidorino | Nidoking | Moon Stone |
| Clefairy | Clefable | Moon Stone |
| Vulpix | Ninetales | Fire Stone |
| Jigglypuff | Wigglytuff | Water Stone |
| Oddish | Gloom | Lv.21 |
| Gloom | Vileplume | Leaf Stone |
| Paras | Parasect | Lv.24 |
| Venonat | Venomoth | Lv.31 |
| Diglett | Dugtrio | Lv.26 |
| Meowth | Persian | Lv.28 |
| Psyduck | Golduck | Lv.33 |
| Mankey | Primeape | Lv.28 |
| Growlithe | Arcanine | Fire Stone |
| Poliwag | Poliwhirl | Lv.25 |
| Poliwhirl | Poliwrath OR Politoed | Water Stone OR Trade w/ King's Rock* |
| Abra | Kadabra | Lv.16 |
| Machop | Machoke | Lv.28 |
| Bellsprout | Weepinbell | Lv.21 |
| Weepinbell | Victreebel | Leaf Stone |
| Tentacool | Tentacruel | Lv.30 |
| Geodude | Graveler | Lv.25 |
| Ponyta | Rapidash | Lv.40 |
| Slowpoke | Slowbro | Lv.37 |
| Magnemite | Magneton | Lv.30 |
| Doduo | Dodrio | Lv.31 |
| Seel | Dewgong | Lv.34 |
| Grimer | Muk | Lv.38 |
| Shellder | Cloyster | Water Stone |
| Gastly | Haunter | Lv.25 |
| Drowzee | Hypno | Lv.26 |
| Krabby | Kingler | Lv.28 |
| Voltorb | Electrode | Lv.30 |
| Exeggcute | Exeggutor | Leaf Stone |
| Cubone | Marowak | Lv.28 |
| Koffing | Weezing | Lv.35 |
| Rhyhorn | Rhydon | Lv.42 |
| Horsea | Seadra | Lv.32 |
| Goldeen | Seaking | Lv.33 |
| Staryu | Starmee | Water Stone |
| Magikarp | Gyarados | Lv.20 |
| Eevee | Vaporeon/Jolteon/Flareon | Water/Thunder/Fire Stone |
| Omanyte | Omastar | Lv.40 |
| Kabuto | Kabutops | Lv.40 |

*(Politoed not in Gen 1)*

---

## 7.7 — TM Location Quick Reference

| TM | Move | Location | How to Obtain |
|----|------|----------|---------------|
| TM01 | Mega Punch | Mt. Moon 1F | On ground |
| TM02 | Razor Wind | Rocket Hideout B2F | On ground |
| TM03 | Swords Dance | Silph Co. 5F | On ground |
| TM04 | Whirlwind | Route 4 | Hidden item |
| TM05 | Mega Kick | Victory Road 2F | On ground |
| TM06 | Toxic | Fuchsia Gym | Prize from Koga |
| TM07 | Horn Drill | Mt. Moon B1F | NPC gift |
| TM08 | Body Slam | SS Anne 2/3F | Cabin floor |
| TM09 | Take Down | Silph Co. 10F | On ground |
| TM10 | Double-Edge | Rocket Hideout B3F | On ground |
| TM11 | BubbleBeam | Cerulean Gym | Prize from Misty |
| TM12 | Water Gun | Mt. Moon 1F | Super Nerd event |
| TM13 | Ice Beam | Celadon Dept Store Rooftop | Gift (give vending drink) |
| TM14 | Blizzard | Pokémon Mansion B1F | On ground |
| TM15 | Hyper Beam | Celadon Game Corner | 5500 Coins |
| TM16 | Pay Day | Route 12 | On ground |
| TM17 | Submission | Victory Road 1F | On ground |
| TM18 | Counter | Celadon Dept Store 3F | NPC |
| TM19 | Seismic Toss | Route 25 | Mr. Fuji/Sea Cottage |
| TM20 | Rage | Route 15 | On ground |
| TM21 | Mega Drain | Celadon Gym | Prize from Erika |
| TM22 | SolarBeam | Pokémon Mansion 1F | On ground |
| TM23 | Dragon Rage | Celadon Game Corner | 3300 Coins |
| TM24 | Thunderbolt | Vermilion Gym | Prize from Lt. Surge |
| TM25 | Thunder | Power Plant | Hidden |
| TM26 | Earthquake | Silph Co. 7F | On ground |
| TM27 | Fissure | Viridian Gym | Prize from Giovanni |
| TM28 | Dig | Cerulean City | House event (Rocket) |
| TM29 | Psychic | Saffron City | Mr. Psychic's house |
| TM30 | Teleport | Route 24 | Not found (traded) |
| TM31 | Mimic | Silph Co. | NPC event (copycat) |
| TM32 | Double Team | Celadon Game Corner | 1000 Coins |
| TM33 | Reflect | Celadon Dept Mart | Route 1 |
| TM34 | Bide | Pewter Gym | Prize from Brock |
| TM35 | Metronome | Cerulean Cave 1F or NPC | NPC gift (copycat's daughter) |
| TM36 | Selfdestruct | Celadon Game Corner | 3300 Coins |
| TM37 | Egg Bomb | Celadon Game Corner | 5500 Coins |
| TM38 | Fire Blast | Cinnabar Gym | Prize from Blaine |
| TM39 | Swift | Rock Tunnel 1F | NPC gift |
| TM40 | Skull Bash | Cerulean Cave | Ground item |
| TM41 | Softboiled | Celadon City event | Copycat event trade |
| TM42 | Dream Eater | Viridian City | Requires event |
| TM43 | Sky Attack | Victory Road 2F | Ground item |
| TM44 | Rest | Lapras event / Silph Co. 11F | |
| TM45 | Thunder Wave | Pewter City Mart | Sold for ₽2000 |
| TM46 | Psywave | Saffron Gym | Prize from Sabrina |
| TM47 | Explosion | Celadon Game Corner | 5500 Coins |
| TM48 | Rock Slide | Victory Road 3F | Ground item |
| TM49 | Tri Attack | Celadon Game Corner | 5500 Coins |
| TM50 | Substitute | Celadon Game Corner | 3300 Coins |

---

## 7.8 — Complete HM Reference

| HM | Move | Location | Requires |
|----|------|----------|----------|
| HM01 | Cut | SS Anne (Captain teaches) | CascadeBadge + need story progress in SS Anne |
| HM02 | Fly | Route 16 (hidden house) | ThunderBadge for field use |
| HM03 | Surf | Fuchsia City (Warden's house, after returning Gold Teeth from Safari Zone) | SoulBadge for field use |
| HM04 | Strength | Rock Tunnel B1F (NPC gift) | RainbowBadge for field use + need to find the right tile |
| HM05 | Flash | Oak's Lab (Oak's Aide in Vermilion City before Surge) or Route 2 | BoulderBadge for field use |

---

*Continue to Section 9: Appendices*
