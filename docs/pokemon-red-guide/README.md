# Pokémon Red Gen 1 Technical Guide
# Vision-Limited / Memory-Driven Complete Reference

**Version 1.0 — Compiled for Pokémon Red Version (International)**

---

## About This Guide

This guide is designed for players who have **limited or no reliable visual output** from the game screen. Instead, the player can:

- **Read memory state:** map ID, tile coordinates (X,Y), party data, bag items, badges, event flags, battle data
- **Press buttons:** directional inputs, A, B, START, SELECT
- **Use higher-level actions:** interact, advance_dialog

Every instruction in this guide is executable using **only memory reads and button presses**, with no reliance on screen appearance.

---

## File Structure

| File | Section | Content |
|------|---------|---------|
| `01_memory_map_reference.md` | §1 | Complete memory addresses for map, party, items, badges, Pokédex, battle state, RNG |
| `02_core_mechanics.md` | §2 | Damage formula, capture formula, type chart, EVs/IVs, status conditions, experience formulas |
| `03_maps_and_navigation.md` | §3 | Map IDs, warp tiles, NPC coordinates, hidden items, trainer positions for ALL maps |
| `04_navigation_procedure.md` | §4 | Safe-move loop algorithm, wall following, warp verification, menu navigation, troubleshooting |
| `05_walkthrough_part_a.md` | §5A | Step-by-step walkthrough: New Game through Celadon City |
| `05_complete_walkthrough.md` | §5B | Step-by-step walkthrough: Viridian Gym through Hall of Fame |
| `06_battle_system.md` | §6 | Battle menu navigation, decision trees, gym leader & Elite Four strategies |
| `07_advanced_data.md` | §7 | Mew glitch (memory-driven steps), item duplication, evolution data, TM/HM locations |
| `09_appendices.md` | §9 | Quick reference: type chart, badge effects, key items, experience tables, button sequences, glossary |

*(Section 8 — Dialog Flow Database — is integrated into Section 3 map entries for each NPC.)*

---

## How to Use This Guide

### If You're Starting a New Game:
1. Begin with **Section 5A** (Walkthrough Part A).
2. Reference **Section 3** for map navigation details when moving between locations.
3. Reference **Section 6** when entering battles.

### If You Need to Navigate a Specific Map:
1. Look up the map in **Section 3** by name or Map ID.
2. Use the warp tile coordinates to find doors/exits.
3. Use **Section 4** (Navigation Procedure) for the safe-move loop algorithm.

### If You Need Battle Strategies:
1. **Section 6** contains decision trees readable from memory (HP values, types).
2. Gym Leader and Elite Four teams with full counters are documented.

### If You Encounter a Glitch or Edge Case:
1. **Section 7** documents practical glitches (Mew glitch with memory-verifiable steps).
2. **Section 4** has troubleshooting for navigation failures.

---

## Key Quick Reference

### Memory Addresses (Most Used)
```
D35E  = Current map ID
D361  = Player X coordinate  
D362  = Player Y coordinate
D163  = Party count
D164  = Species ID list start (6 bytes + 0xFF terminator)
D16B  = First Pokémon data block (44 bytes per Pokémon)
D31D  = Bag item count
D31E  = Bag item list start
D347  = Money byte 1 (MSB)
D356  = Badge bitfield
D2F7  = Pokédex "own" flags start
D0DD  = Enemy current HP (trainer, low byte)
CD1A  = Player Attack stage modifier
```

### Badge Effects
```
Bit 0 (0x01) = BoulderBadge: Attack +12.5%, HM05 Flash
Bit 1 (0x02) = CascadeBadge: Obedience Lv.30, HM01 Cut
Bit 2 (0x04) = ThunderBadge: Defense +12.5%, HM02 Fly
Bit 3 (0x08) = RainbowBadge: Obedience Lv.50, HM04 Strength
Bit 4 (0x10) = SoulBadge: Speed +12.5%, HM03 Surf
Bit 5 (0x20) = MarshBadge: Obedience Lv.70
Bit 6 (0x40) = VolcanoBadge: Special +12.5%
Bit 7 (0x80) = EarthBadge: Obedience Lv.101
```

### Universal Safe-Move Algorithm
```
1. Read current (X,Y) from D361,D362
2. Press direction key once
3. Wait 30 frames
4. Read new (X,Y)
5. If changed → continue
6. If unchanged → NPC blocking (interact + advance_dialog) or wall (try different direction)
7. If map ID changed → warp triggered successfully
```

### Battle Menu Quick Select
```
Use Move N:     A, A, (Down × N-1), A
Switch Pokémon: A, Down, A, (scroll to slot), A
Use Item:       A, Down, Down, A, (scroll to item), A, (target)
Run (wild only):A, Down, Down, Down, A
```

---

## Technical Notes

### Memory Address Conventions
- All addresses are **hexadecimal** unless otherwise noted.
- Byte ordering is **little-endian** for 2-byte values (e.g., HP) unless noted.
- Map IDs use the **pokered disassembly** convention (e.g., PALLET_TOWN = 0x00).

### Coordinate System
- (X, Y) where X = column (0 = left edge), Y = row (0 = top edge).
- The player occupies a single tile. Moving Down increases Y by 1.
- Blocks (stored at D363/D364) are 2×2 tile groups: block_X = floor(tile_X / 2).

### Version Differences
This guide is written for the **international (English) Pokémon Red** ROM.
- Japanese version has some shifted addresses (typically 0x19 earlier for item/SRAM areas).
- Pokémon Blue has identical mechanics but different encounter tables for some species (e.g., Vulpix vs. Growlithe).

### Known Gen 1 Bugs Documented
1. **Focus Energy bug:** Lowers crit rate instead of raising it (Section 2.3)
2. **Great Ball bug:** No better than Poké Ball (Section 2.4)
3. **Hyper Beam recharge:** Skips recharge if it KOs (Section 2.9)
4. **Freeze bug:** No automatic thaw chance (Section 2.7)
5. **Stat boost text:** ThunderBadge and SoulBadge have swapped descriptions (Section 9, Appendix B)
6. **Wrap on switch:** Ends immediately when the trapped Pokémon switches out (Section 2.9)
7. **OHKO formula:** Accuracy = (Attacker_LV - Defender_LV + 30)% (Section 2.6)

---

## Credits & Sources

This guide was compiled using data from:
- **pret/pokered** disassembly (https://github.com/pret/pokered)
- **Data Crystal ROM map** (https://datacrystal.tcrf.net)
- **Bulbapedia** technical reference
- **Serebii.net** trainer team data
- **Psypokes.com** gym leader data
- **GameFAQs** zerokid mechanics guide v2.9.1
- **Crystal_'s RBY battle mechanics research** (damage formula)
- Direct memory analysis from emulator observation

---

*Guide compiled by OWL for Toastyst.*
*For autonomous agent use with the Pokémon Red MCP tools.*
*Total guide: ~200KB across 9 files.*
*Last updated: June 2026.*
