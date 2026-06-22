# SECTION 9: APPENDICES

---

## Appendix A: Type Chart (Gen 1 Attack Effectiveness)

Super Effective = 2× | Not Very Effective = 0.5× | Immune = 0×

```
         NOR FIR WAT GRA ELE ICE FIG POI GRO FLY PSY BUG ROC GHO DRA
Normal    1   1   1   1   1   1   1   1   1   1   1   1  0.5  0   1
Fire      1  0.5 0.5   2   1   2   1   1   1   1   1   2  0.5  1  0.5
Water     1   2  0.5 0.5   1   1   1   1   2   1   1   1   2   1  0.5
Grass     1  0.5   2  0.5   1   1   1  0.5   2  0.5   1  0.5   2   1  0.5
Electric  1   1   2  0.5 0.5   1   1   1   0   2   1   1   1   1  0.5
Ice       1   1  0.5   2   1  0.5   1   1   2   2   1   1   1   1   2
Fighting  2   1   1   1   1   2   1  0.5   1  0.5 0.5  0.5   2   0   1
Poison    1   1   1   2   1   1   1  0.5 0.5   1   1   2  0.5 0.5   1
Ground    1   2   1  0.5   2   1   1   2   1   0   1  0.5   2   1   1
Flying    1   1   1   2  0.5   1   2   1   1   1   1   2  0.5   1   1
Psychic   1   1   1   1   1   1   2   2   1   1  0.5   1   1   1   1
Bug       1  0.5   1   2   1   1  0.5   2   1  0.5   2   1   1  0.5   1
Rock      1   2   1   1   1   2  0.5   1  0.5   2   1   2   1   1   1
Ghost     0   1   1   1   1   1   1   1   1   1   0   1   1   2   1
Dragon    1   1   1   1   1   1   1   1   1   1   1   1   1   1   1   2

Key Gen 1 anomalies:
- Ghost is immune to Normal AND Fighting (most physical attackers can't touch GHOST types)
- Psychic is immune to Ghost (this was BUGGED in Gen 1 only)
- Ground is immune to Electric
- Dragon and Rock interact uniquely with specific types
```

---

## Appendix B: Badge Effect Table

| # | Badge | Gym Leader | Stat Boost | Max Obedience Level | Field HM Unlocked |
|---|-------|-----------|------------|--------------------|--------------------|
| 1 | BoulderBadge | Brock | Attack +12.5% | 10 (no change) | HM05 Flash |
| 2 | CascadeBadge | Misty | — | 30 | HM01 Cut |
| 3 | ThunderBadge | Lt. Surge | Defense +12.5%* | 30 (no change) | HM02 Fly |
| 4 | RainbowBadge | Erika | — | 50 | HM04 Strength |
| 5 | SoulBadge | Koga | Speed +12.5%* | 50 (no change) | HM03 Surf |
| 6 | MarshBadge | Sabrina | — | 70 | — |
| 7 | VolcanoBadge | Blaine | Special +12.5% | 70 (no change) | — |
| 8 | EarthBadge | Giovanni | — | 101 | — |

*Common mislabeling in game text: ThunderBadge text says Speed boost; SoulBadge text says Defense boost. Actual effects are reversed (see table).*

> Badges are stored at memory address D356 as a bitfield. Read badge flags directly to confirm obedience threshold.

---

## Appendix C: Key Item Location Quick Reference

| Item | Location | How |
|------|----------|-----|
| **Old Amber** | Pewter Museum 2F | Give to scientist → Aerodactyl at Cinnabar Lab |
| **S.S. Ticket** | Bill's Sea Cottage (Route 25) | Bill gives after event |
| **Bicycle Voucher** | Viridian Fan Club | Chairman gives after speech |
| **Bicycle** | Cerulean Bike Shop | Exchange voucher |
| **Oak's Parcel** | Viridian Mart | Mart clerk gives after Oak event |
| **HM01 Cut** | SS Anne | Captain teaches |
| **HM02 Fly** | Route 16 house | Hidden house in tall grass |
| **HM03 Surf** | Fuchsia City (Warden) | Get Gold Teeth from Safari Zone → give to Warden |
| **HM04 Strength** | Rock Tunnel B1F | NPC gift |
| **HM05 Flash** | Oak's Lab (aide) | Aide after BoulderBadge |
| **Silph Scope** | Rocket Hideout B4F | From Giovanni after defeat |
| **Poké Flute** | Mr. Fuji's House (Lavender) | Mr. Fuji gives after Pokémon Tower event |
| **Gold Teeth** | Safari Zone Area 3 | Hidden item |
| **Card Key** | Silph Co. 1F | NPC |
| **Lift Key** | Rocket Hideout B4F | Ground item |
| **Exp. All** | Route 15 house | Rocker in house gives |
| **Running Shoes** | Mom (Pallet Town) | Event after Oak, before leaving |
| **Coin Case** | Celadon Game Corner | NPC |
| **Master Ball** | Silph Co. 11F | Giovanni's office |

---

## Appendix D: Experience Group Thresholds

| Level | Fast (N³×4/5) | Medium Fast (N³) | Medium Slow (1.2N³-15N²+100N-140) | Slow (N³×1.25) |
|-------|----------------|-------------------|------------------------------------|--------------------|
| 10 | 800 | 1,000 | 1,000 | 1,250 |
| 20 | 6,400 | 8,000 | 7,400 | 10,000 |
| 30 | 21,600 | 27,000 | 24,300 | 33,750 |
| 40 | 51,200 | 64,000 | 58,400 | 80,000 |
| 50 | 100,000 | 125,000 | 115,000 | 156,250 |
| 60 | 172,800 | 216,000 | 201,600 | 270,000 |
| 70 | 274,400 | 343,000 | 324,800 | 428,750 |
| 80 | 409,600 | 512,000 | 492,800 | 640,000 |
| 90 | 583,200 | 729,000 | 713,700 | 911,250 |
| 100 | 800,000 | 1,000,000 | 996,000 | 1,250,000 |

Common Fast exp group Pokémon: Rattata line, Pidgey line, Caterpie line, Weedle line, Spearow line, Ekans line, Clefairy line, Jigglypuff line.

Common Medium Slow exp group Pokémon: Starter lines, Machop line, Gastly line, Abra line, Pikachu line, Dratini line, Lapras.

Common Slow exp group Pokémon: Mewtwo, Snorlax, Chansey, Lapras (some), Dragonite line.

---

## Appendix E: Memory Address Quick Reference Card

```
QUICK REFERENCE — Read these addresses for critical info:
════════════════════════════════════════════════════
D35E    → Current map ID
D361    → Player X coordinate
D362    → Player Y coordinate
C109    → Player facing direction (0=D,4=U,8=L,C=R)
D163    → Party count
D16B+1  → Slot 1 current HP (low byte), +2 (high byte)
D16B+33 → Slot 1 actual level
D0D1+33 → Enemy current HP during battle (verify specific addr)
D0DD    → Enemy current HP (trainer battles, low byte)
D31D    → Bag item count
D31E    → Bag item list start
D347-9  → Money (3 bytes BCD, big-endian)
D356    → Badge bitfield
D2F7    → Pokédex "own" flags (19 bytes, bitfield)
D355    → Options
════════════════════════════════════════════════════
```

---

## Appendix F: Button Sequence Quick Reference

### Universal Actions
| Action | Buttons |
|--------|---------|
| Open main menu | START |
| Close menu / Cancel | B |
| Confirm / Talk | A |
| Run (if Running Shoes held) | Hold B + direction |
| Mount/dismount Bike | SELECT |

### In-Battle Action Shortcuts
| Action | Sequence |
|--------|----------|
| Use Move 1 | A, A |
| Use Move 2 | A, Down, A |
| Use Move 3 | A, Down, Down, A |
| Use Move 4 | A, Down, Down, Down, A |
| Switch to slot 2 | A, Down, A, (cursor to slot 2), A |
| Use Item (nth in bag) | A, Down, Down, A, (scroll to item), A, (select target) |
| Run (wild only) | A, Down, Down, Down, A |

### Overworld Action Shortcuts
| Action | Sequence |
|--------|----------|
| Save | START → Down×N to SAVE → A → A → advance_dialog until done |
| Use Repel | START → Down to ITEM → A → find Repel → A → A |
| Heal at Pokémon Center | Talk to nurse → advance_dialog through menu → A to confirm |
| Check PC | Interact with PC → advance_dialog OPTIONS → select WITHDRAW or DEPOSIT |

---

## Appendix G: Glossary

| Term | Meaning |
|------|---------|
| DV | Deterministic Value (Gen 1 term for IV), range 0–15 per stat |
| EV | Effort Value (stat experience), range 0–65535 per stat |
| STAB | Same-Type Attack Bonus, +50% damage if move type matches attacker |
| OHKO | One-Hit KO move (Horn Drill, Fissure, Guillotine, Sheer Cold) |
| Advance Dialog | Press B to advance one text box (equivalent to pressing A then B on each text box in sequence) |
| Warp | Map transition triggered by entering specific tiles |
| Sprite | Visual character/entity on screen (not directly readable in vision-limited mode) but the sprite data is readable in memory (C1x0 block) |
| Block | 2×2 tile group used for map coordinate compression |
| Repel | Item that prevents encounters with Pokémon below your lead's level for 256 steps |
| Safari Zone | Special encounter zone with unique battle mechanics and step counter |
| Poké Doll | Key item used to escape from Ghost Marowak battle in Pokémon Tower |

---

*End of Guide*

*Complete guide is distributed across files:
- `01_memory_map_reference.md` — Memory addresses and data structures
- `02_core_mechanics.md` — Formulas, type chart, mechanics
- `03_maps_and_navigation.md` — Map database with coordinates
- `04_navigation_procedure.md` — Safe move loop and algorithms
- `05_complete_walkthrough.md` (referenced — see Section 3 + 6 for key data)
- `06_battle_system.md` — Battle strategies and decision trees
- `07_advanced_data.md` — Glitches, TM locations, Pokémon data
- `08_dialog_flow_database.md` (integrated into map section)
- `09_appendices.md` — Quick reference tables

*Total guide size: ~200KB of technical reference data*
*Compiled for vision-limited / memory-driven play*
*Version: 1.0 — Pokémon Red Version (INT)*
