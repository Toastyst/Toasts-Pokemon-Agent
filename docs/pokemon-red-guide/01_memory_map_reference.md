# SECTION 1: COMPLETE MEMORY MAP REFERENCE

**Pokémon Red Version (INT) — Game Boy RAM Map**

All addresses below are for the **international (non-Japanese)** version of Pokémon Red.
Values are in hexadecimal unless noted. "WRAM" = Work RAM (C000–DFFF), "HRAM" = High RAM (FF80–FFFE).

---

## 1.1 — Player Position & Map

| Address | Label | Size | Description |
|---------|-------|------|-------------|
| `D35E` | `wCurMap` | 1 byte | **Current map ID.** Compare against the Map ID table (Section 3) to identify location. If a warp occurs, read this after `wait_frames(60)` to confirm the new value. |
| `D361` | `wXCoord` | 1 byte | **Player X coordinate** (tile column, 0-indexed, left = 0). Increases rightward. Valid range depends on map. |
| `D362` | `wYCoord` | 1 byte | **Player Y coordinate** (tile row, 0-indexed, top = 0). Increases downward. Valid range depends on map. |
| `D363` | `wXBlock` | 1 byte | Player X position in "blocks" (2×2 tile groups). Usually equals `wXCoord / 2`. |
| `D364` | `wYBlock` | 1 byte | Player Y position in "blocks". Usually equals `wYCoord / 2`. |
| `C109` | `wSpriteStateData1 + 9` (sprite 0) | 1 byte | **Facing direction.** Values: `0`=Down, `4`=Up, `8`=Left, `12` (0x0C)=Right. Add to sprite base offset `C100` + 0x10×sprite_num for other sprites. |
| `D367` | `wTilesetType` | 1 byte | Current tileset ID (determines gfx loaded: overworld, cave, indoors, etc.). |
| `D368` | `wCurMapHeight` | 1 byte | Current map height in 2×2 blocks. |
| `D369` | `wCurMapWidth` | 1 byte | Current map width in 2×2 blocks. |

**Usage — "Am I at the right tile?":**
```
read D361 → X, read D362 → Y
If X == target_X and Y == target_Y: position confirmed
```

**Usage — "Did the warp trigger?":**
```
After stepping onto a warp tile, wait 60 frames, then read D35E.
If D35E != original_map_id: warp succeeded → read new D361/D362 for position.
If D35E == original_map_id after 120 frames: warp did not trigger → wrong tile or direction.
```

---

## 1.2 — Party Data

### Party Structure

| Address | Size | Description |
|---------|------|-------------|
| `D163` | 1 byte | **Party count** (1–6). Number of Pokémon currently in the active party. |

### Pokémon Species List (D164–D16A)
Starting at `D164`, 6 bytes containing the species ID of each party Pokémon, followed by a terminator byte `0xFF`.

```
D164: Species ID of slot 1
D165: Species ID of slot 2
...
D169: Species ID of slot 6 (or 0xFF if fewer than 6)
D16A: 0xFF terminator byte
```

**Key Species IDs (hex):** `0x01`=Rhydon, `0x04`=Charmander, `0x07`=Squirtle, `0x19`=Rattata, `0x1C`=Pikachu, `0x25`=Nidoran♀, `0x2D`=Zubat, `0x30`=Oddish, `0x39`=Growlithe, `0x3B`=Abra, `0x3C`=Drowzee, `0x41`=Machop, `0x49`=Tentacool, `0x4C`=Geodude, `0x50`=Slowpoke, `0x52`=Magnemite, `0x54`=Doduo, `0x55`=Seel, `0x58`=Gastly, `0x5A`=Onix, `0x5B`=Krabby, `0x5F`=Voltorb, `0x60`=Exeggcute, `0x61`=Cubone, `0x63`=Hitmonlee, `0x64`=Hitmonchan, `0x66`=Koffing, `0x67`=Rhyhorn, `0x69`=Horsea, `0x6D`=Staryu, `0x70`=Scyther, `0x73`=Tangela, `0x75`=Goldeen, `0x76`=Starmie, `0x78`=Mr. Mime, `0x79`=Jynx, `0x7D`=Electabuzz, `0x7E`=Magmar, `0x7F`=Pinsir, `0x80`=Tauros, `0x83`=Gyarados, `0x85`=Lapras, `0x88`=Eevee, `0x8A`=Porygon, `0x8E`=Aerodactyl, `0x92`=Articuno, `0x93`=Zapdos, `0x94`=Moltres, `0x97`=Mewtwo, `0x98`=Mew, ... (full internal index needed per encounter tables).

*(A complete 256-entry species ID table is in Appendix A.)*

### Per-Pokémon Data Block

Starting at `D16B`, each Pokémon occupies **44 bytes** in this order:

| Offset from start of block | Size | Field | Description |
|---|---|---|---|
| `+0` | 1 byte | Species ID | Internal index (same as species list above) |
| `+1` | 2 bytes | Current HP | Little-endian. If this reaches 0, Pokémon has fainted. |
| `+3` | 1 byte | **"Level in party" byte** | The Pokémon's level as stored outside of battle. During battle, "box level" is used instead. For status/display checks in menus, use this byte. |
| `+4` | 1 byte | Status condition | `0`=Healthy, `1`=Sleep, `2`=Poison, `4`=Burn, `8`=Freeze, `10` (0x10)=Paralysis. These values are OR'd together if multiple. |
| `+5` | 1 byte | Type 1 | Type ID (see Type Chart table in Section 2). |
| `+6` | 1 byte | Type 2 | Type ID, or same as Type 1 for single-type Pokémon. |
| `+7` | 1 byte | Catch rate / held item | In Gen 1, in-party Pokémon use this byte as the held item value (usually 0). For wild catches, this is the catch rate. |
| `+8` | 4 bytes | Moves | 4 bytes, each a move ID. 0 = no move in that slot. |
| `+12` | 2 bytes | Trainer ID | OT's ID for caught Pokémon; 0 for traded. Used in obedience checks. |
| `+14` | 3 bytes | Experience points | 3 bytes, big-endian (MSB first). Exp value determines the "level byte" via lookup tables. |
| `+17` | 2 bytes | HP EV | Little-endian. Accumulated HP effort values. |
| `+19` | 2 bytes | Attack EV | Little-endian. |
| `+21` | 2 bytes | Defense EV | Little-endian. |
| `+23` | 2 bytes | Speed EV | Little-endian. |
| `+25` | 2 bytes | Special EV | Little-endian. Both Sp.Atk and Sp.Def share this value in Gen 1. |
| `+27` | 2 bytes | IVs (DVs) | Little-endian 2-byte field. Bits: `AAAA DDSS SSSS AAAA` — Atk DV = high nibble of byte 1, Def DV = low nibble of byte 1, Spd DV = high nibble of byte 2, Spc DV = low nibble of byte 2. Each DV ranges `0–15`. |
| `+29` | 4 bytes | PP | 1 byte per move. Remaining PP for moves 1–4. |
| `+33` | 1 byte | **Actual level (used in menus/battle)** | This is the true level used by the engine. The `+3` byte above may be stale after level-up while `+33` is always current. **ALWAYS use `+33` for battle decisions.** |
| `+34` | 2 bytes | Max HP | Little-endian, computed from Base Stats, IVs, EVs, and Level. |
| `+36` | 2 bytes | Attack | Little-endian, computed stat. |
| `+38` | 2 bytes | Defense | |
| `+40` | 2 bytes | Speed | |
| `+42` | 2 bytes | Special | |

**Example — Reading current HP of first Pokémon:**
```
base = D16B
HP_address = base + 1
low_byte = read(HP_address)
high_byte = read(HP_address + 1)
current_HP = high_byte * 256 + low_byte
```

**Example — Check if second Pokémon is fainted:**
```
base = D16B + 44
HP_address = base + 1
low_byte = read(HP_address)
high_byte = read(HP_address + 1)
current_HP = high_byte * 256 + low_byte
If current_HP == 0: fainted.
```

---

## 1.3 — Bag Items

| Address | Description |
|---------|-------------|
| `D31D` | **Total item count** in bag (1 byte, max 20). |
| `D31E` | Start of item list. Each item is 2 bytes: byte 1 = **item ID**, byte 2 = **quantity** (1–99). Up to 20 entries (40 bytes total). List ends with `0xFF` terminator byte. |

**Key Item IDs (hex):**
`0x01`=Master Ball, `0x02`=Ultra Ball, `0x03`=Great Ball, `0x04`=Poké Ball, `0x05`=Town Map, `0x06`=Bicycle, `0x07`=Safari Ball?, `0x0C`=Moon Stone, `0x0F`=Antidote, `0x10`=Burn Heal, `0x11`=Ice Heal, `0x12`=Awakening, `0x13`=Parlyz Heal, `0x14`=Full Restore, `0x15`=Max Potion, `0x16`=Hyper Potion, `0x17`=Super Potion, `0x18`=Potion, `0x19`=Boulderbadge?, `0x1C`=Escape Rope, `0x1D`=Repel, `0x1E`=Old Amber, `0x1F`=Fire Stone, `0x20`=Thunderstone, `0x21`=Water Stone, `0x26`=HP Up, `0x27`=Protein, `0x28`=Iron, `0x29`=Carbos, `0x2A`=Calcium, `0x2B`=Rare Candy, `0x2D`=X Accuracy, `0x2E`=Leaf Stone, `0x2F`=Metal Coat?, `0x30`=Nugget, `0x31`=Poké Doll, `0x32`=Full Heal, `0x33`=Revive, `0x34`=Max Revive, `0x35`=Guard Spec., `0x36`=Super Repel, `0x37`=Max Repel, `0x38`=Dire Hit, `0x3A`=Fresh Water, `0x3B`=Soda Pop, `0x3C`=Lemonade, `0x3D`=S.S. Ticket, `0x3E`=Gold Teeth, `0x3F`=X Attack, `0x40`=X Defend, `0x41`=X Speed, `0x42`=X Special, `0x44`=Coin Case, `0x45`=Oak's Parcel, `0x46`=Itemfinder, `0x47`=Silph Scope, `0x48`=Poké Flute, `0x49`=Lift Key, `0x4A`=Exp. All, `0x4B`=Old Rod, `0x4C`=Good Rod, `0x4D`=Super Rod, `0x4F`=PP Up, `0x50`=Ether, `0x51`=Max Ether, `0x52`=Elixer, `0x53`=Max Elixer, ... *(see Appendix B for full item ID table)*.

**HM IDs:** `0xC4`=HM01 (Cut), `0xC5`=HM02 (Fly), `0xC6`=HM03 (Surf), `0xC7`=HM04 (Strength), `0xC8`=HM05 (Flash).
**TM IDs:** `0xC9`–`0xFC` (TMs 01–50).

*(Note: TM/HM items in the bag are the single-use TMs or reusable HMs as items. After teaching, HM items remain.)*

**Example — Count Potion quantity:**
```
count = read(D31D)
For i = 0 to count-1:
    addr = D31E + i*2
    item_id = read(addr)
    qty = read(addr + 1)
    If item_id == 0x18: Potion qty = qty
```

---

## 1.4 — Money

| Address | Description |
|---------|-------------|
| `D347`–`D349` | **Money** (3 bytes, big-endian, decimal-coded BCD). Maximum: 999,999. |

**Example:** If D347=`0x01`, D344=`0x23`, D349=`0x45` → Money = ₽12,345.

---

## 1.5 — Badges

| Address | Description |
|---------|-------------|
| `D356` | **Badge bitfield** (1 byte). Bits correspond to badges: |

| Bit | Badge | Hex value |
|-----|-------|-----------|
| 0 | BoulderBadge (Brock) | `0x01` |
| 1 | CascadeBadge (Misty) | `0x02` |
| 2 | ThunderBadge (Surge) | `0x04` |
| 3 | RainbowBadge (Erika) | `0x08` |
| 4 | SoulBadge (Koga) | `0x10` |
| 5 | MarshBadge (Sabrina) | `0x20` |
| 6 | VolcanoBadge (Blaine) | `0x40` |
| 7 | EarthBadge (Giovanni) | `0x80` |

**Example — Check if you have the Thunder Badge:**
```
read D356 → badges
If (badges AND 0x04) != 0: ThunderBadge obtained.
```

---

## 1.6 — Pokédex

| Address | Description |
|---------|-------------|
| `D2F7`–`D309` | **"Own" flags** — 19 bytes (bitfield for Pokémon 1–152, 8 per byte). Byte 0 bit 0 = Pokédex #001, etc. If bit is set, player owns that species. |
| `D30B`–`D31D` | **"Seen" flags** — same format. If bit is set, player has seen that species. |

**Example — Count owned Pokémon:**
```
total = 0
For addr = D2F7 to D309:
    byte = read(addr)
    For bit = 0 to 7:
        If (byte AND (1 << bit)) != 0: total += 1
```

---

## 1.7 — Player Identity

| Address | Description |
|---------|-------------|
| `D158`–`D162` | Player name (7 bytes, terminator-padded). |
| `D34A`–`D351` | Rival name (8 bytes, `BLUE`/`GREEN`/custom). |
| `D359`–`D35A` | Player Trainer ID (2 bytes, little-endian). Used in obedience and Pokémon OT matching. |
| `D355` | **Options** bitfield. Bit 0-1: text speed (`0`=Slow, `1`=Mid, `2`=Fast). Bit 4-5: battle style (`0`=Set, `1`=Shift). Bit 7: battle scene on/off. |

---

## 1.8 — Battle State Data

### Battle Type & Status

| Address | Description |
|---------|-------------|
| `D057` | **Battle type.** `0`=Wild, `1`=Trainer battle, `2`=Old Man (tutorial), `3`=Safari Zone, `4`=Forced battle (Ghost Marowak). |
| `D05D` | Battle outcome. `0`=In progress / won so far (no KOs of all player mons yet), `1`=Player lost, `2`=Player won, `5`=Player ran, etc. Check after battle to determine win/loss. |
| `D05E` | Critical hit / OHKO flag. `1`=Critical, `2`=OHKO. Use to track what happened. |
| `D05F` | The move that made the critical hit (move ID). |
| `D015` | In-battle turn number. |
| `CCD5` | Number of turns (alternative location). |

### Player In-Battle Data Block (starting at D009)

| Offset from D009 | Size | Description |
|---|---|---|
| `+0` | 1 byte | Active player Pokémon's species ID (in-battle version of slot 1). |
| `+1` | 2 bytes | Active player Pokémon's current HP (little-endian). |
| `+3` | 1 byte | Active player Pokémon's move count. |
| `+4` | 4 bytes | Active player Pokémon's 4 moves (move IDs). |
| `+8`–`+12` | – | Additional move data. |
| `+28` | 1 byte | Active player Pokémon max HP (low byte). |
| `+29` | 1 byte | Active player Pokémon max HP (high byte). |

*(The full in-battle structure mirrors the party structure but is cached separately once battle starts.)*

### Enemy In-Battle Data Block (starting at CFCC for wild, D0D8 for trainer for some fields)

| Address | Size | Description |
|---------|------|-------------|
| `CFCC` / `D0D8` | 1 byte | Enemy Pokémon species ID. |
| `CFD1` / `D0DD` | 2 bytes | Enemy current HP (little-endian). Critical for judging whether to attack or heal. |
| `CFE4` | 2 bytes | Enemy max HP. |
| `CFD6` | 1 byte | Enemy level. |
| `CFD7` | 2 bytes | Enemy Attack stat. |
| `CFD9` | 2 bytes | Enemy Defense stat. |
| `CFDB` | 2 bytes | Enemy Speed stat. |
| `CFDD` | 2 bytes | Enemy Special stat. |
| `CFD4` | 1 byte | Enemy Type 1. |
| `CFD5` | 1 byte | Enemy Type 2. |
| `CFCD` | 4 bytes | Enemy moves (4 bytes, move IDs). |
| `CFE3` | 1 byte | Enemy status condition. Same encoding as party status byte. |
| `CFCF` | 1 byte | Enemy status turn counter (for sleep duration, confusion turns). |

### Stat Modifiers

| Address | Description |
|---------|-------------|
| `CD1A` | Player Attack stage modifier (-6 to +6, stored as index 0–12 internally). |
| `CD1B` | Player Defense stage modifier. |
| `CD1C` | Player Speed stage modifier. |
| `CD1D` | Player Special stage modifier. |
| `CD1E` | Player Accuracy stage modifier. |
| `CD1F` | Player Evasion stage modifier. |
| `CD2E` | Enemy Attack stage modifier. |
| `CD2F` | Enemy Defense stage modifier. |
| `CD30` | Enemy Speed stage modifier. |
| `CD31` | Enemy Special stage modifier. |
| `CD32` | Enemy Accuracy stage modifier. |
| `CD33` | Enemy Evasion stage modifier. |

**Stage modifier table (stored value → multiplier):**
```
Stage: -6  -5  -4  -3  -2  -1   0  +1  +2  +3  +4  +5  +6
Mult:  25/100 28/100 33/100 40/100 50/100 66/100 100 150 200 250 300 350 400
Simplified for damage formula: Stage 0 = ×1, +1 = ×1.5, +2 = ×2, -1 = ×0.66, -2 = ×0.5
```
In Gen 1, when computing modified stats, the game multiplies the base stat by (2+stage)/2 for positive stages and 2/(2+abs(stage)) for negative. Values < 1/256 round up to 1.

### Battle Status Flags

**Player (D062–D064) and Enemy (D067–D069):**
Bit flags for Bide (accumulating), Thrash/Petal Dance, Multi-hit, Flinch, Charging (Fly/Dig/Razor Wind), confusion, X Accuracy used, Mist, Focus Energy, Substitute up, Recharging (Hyper Beam active), Rage, Leech Seed, Toxic bad poison, Light Screen, Reflect, Transformed into other Pokémon.

**Key flag for decisions:**
- If player has **Rage flag set**, the next attack is forced to Rage (you cannot select another move).
- If player has **Hyper Beam recharge flag** set, the Pokémon must recharge next turn.
- If **Bide flag** set and counter > 0, the Pokémon is storing energy.

---

## 1.9 — Overworld State Flags

The "wEventFlags" area (around D5F0–D7FF, and also D800–DFFF partially) contains hundreds of individual bit flags for:
- **Trainer defeated flags** — Each trainer has a unique bit. Once defeated, the bit is set. Reading this bit confirms you don't need to re-battle. Address: `DSpriteFlag` at D4xx area maps to map-local sprite show/hide. The `wMissableObjectFlags` (around D5CE–D6xx) control which NPCs and objects appear on maps.
- **Item received flags** — Each ground item has a flag. Once collected, the flag is set and the item disappears.
- **Key story flags** — Oak intro completed, spoke to Mom, received Pokédex, received Running Shoes, etc.

**Critical event flags:**
| Address (approx.) | Flag | Meaning |
|---|---|---|
| `D707` | Received Pokedex? | After Oak gives it. |
| `D70A` | Received Running Shoes | After Mom speaks to you outside Oak's Lab. **Required for B-button running.** |
| `D710` | Received Parcel | Oak's Parcel given, must deliver to Viridian Mart. |
| `D713` | Received Bicycle Voucher | After delivering Parcel. |
| `D719` | Defeated Brock | Bit flag. |
| `D720` | Defeated Misty | |
| `D725` | Defeated Lt. Surge | |
| `D735` | Entered Hall of Fame | After defeating Champion. |
| Multiple | `wFirstLockTrainer`, etc. | Various event progression flags. |

**To check if a specific trainer has been defeated:**
Each map has a "first trainer flag" address. The flag for trainer N on that map = map_first_flag + N. Use `AND` to test the bit. If flag is set, the trainer sprite is hidden.

---

## 1.10 — RNG State

| Address | Description |
|---------|-------------|
| `FF04` (`DIV`) | **DIV register.** Increments at 16384 Hz (~16384 times/second). Used extensively in the game's pseudo-RNG. |
| `FFD3`/`hRandomAdd` | **hRandomAdd** (HRAM). One of two RNG seeds. Updated each frame. |
| `FFD4`/`hRandomSub` | **hRandomSub** (HRAM). Second RNG seed. Updated each frame. |

The Gen 1 RNG is deterministic given the frame counter. In practice, you cannot predict exact RNG outcomes without knowing the starting seed, but you can read these values to verify the RNG is advancing (non-stuck).

---

## 1.11 — Key Item / Story State Quick Reference

| Address Group | Content | How to Interpret |
|---|---|---|
| `D700–D7FF` | Story event flags (bitfield for many events). | Bit set = event completed. Use with specific flag tables (Appendix D). |
| `D4xx–D5xx` | Map-local event flags (visible NPCs, object state). | Used by the engine to determine NPC/shortcut availability. |
| `D52A` | `wBikeFlags` / Running State | Whether the player is cycling (2) vs. walking (1) vs. surfing (3). |
| `D3AE` | `wFirstLockTrainer` | Address of the first trainer flag byte map. |
| `D4B0`-ish | Map connection data | Which connected map borders this map uses for scrolling transitions. |

---

## 1.12 — Save/SRAM Reference

SRAM Bank 1 (`A598–AD2B`):
- Player name, party data, bag items, money, badges, trainer ID, Pokédex flags, event flags.
- Mirror of most working RAM data above, saved periodically by the game.

SRAM Bank 0 (`A598–A5A2`): Player name (alternate location).

SRAM saves are typically triggered by the "SAVE" menu option, certain warps (between some maps), and after winning trainer battles.

---

*Continue to Section 2: Core Game Mechanics*
