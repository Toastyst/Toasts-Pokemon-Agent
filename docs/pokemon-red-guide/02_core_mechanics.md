# SECTION 2: CORE GAME MECHANICS — FORMULAS & LOGIC

**Pokémon Red Version (Generation 1)**

All formulas below exactly match the Generation 1 engine implementation.
"DV" = Gen 1 term for what later generations call IV (Individual Value).

---

## 2.1 — Stat Calculation

### HP Stat
```
HP = floor(((Base_HP + DV_HP) × 2 + floor(ceil(sqrt(EV_HP)) / 4)) × Level / 100) + Level + 10
```

### Non-HP Stats (Attack, Defense, Speed, Special)
```
Stat = floor(((Base_Stat + DV_Stat) × 2 + floor(ceil(sqrt(EV_Stat)) / 4)) × Level / 100) + 5
```

### DV (IV) Extraction from the IV Word

The IV word (2 bytes at party offset +27) encodes four 4-bit DVs:

```
IV_word (little-endian, read as 16-bit word):
  Bits 15–12: Attack DV
  Bits 11–8:  Defense DV
  Bits 7–4:   Speed DV
  Bits 3–0:   Special DV

DV value range: 0–15 (each)
HP DV = (Attack DV AND 1)×8 + (Defense DV AND 1)×4 + (Speed DV AND 1)×2 + (Special DV AND 1)
HP DV range: 0–15
```

**Special note:** In Gen 1, Special Attack and Special Defense share the same DV and stat. There is no individual Sp.Atk/Sp.Def DV — this is why traded Pokémon asymmetry doesn't work.

### Stat Experience (EV)

- Each stat can accumulate up to 65,535 EVs (2 bytes, little-endian).
- When gaining stat experience in battle, the game adds the defeated Pokémon's base stats to the winner's EVs (capped at 65535 per stat).
- **Gen 1 does NOT divide EVs by the number of participants** — total base stats of the fainted Pokémon are added regardless of how many Pokémon participated.
- The formula contribution: `floor(ceil(sqrt(EVs)) / 4)` — meaning diminishing returns, but massive EVs are still worthwhile.
- `Exp. All` distributes EVs as if each Pokémon participated. With Exp. All, each party member gets full base stat EVs from the fainted Pokémon (no division).

### Effect of DVs on Power

In Gen 1, DVs also influence hidden move power:
- **Hidden Power** (not available as a TM in Gen 1, but the stat value is computed from DVs) — used by glitch Pokémon.
- **Psywave** (Sabrina's TM46): Damage = random(0 to floor(1.5×Level)). DV-independent.

---

## 2.2 — Damage Calculation

### Step 1: Classify Move as Physical or Special

| Category | Types |
|----------|-------|
| **Physical** | Bug, Fighting, Flying, Ghost, Ground, Normal, Poison, Rock |
| **Special** | Dragon, Electric, Fire, Grass, Ice, Psychic, Water |

*Physical moves use Attack/Defense. Special moves use Special/Special. Light Screen/Reflect apply to Special/Physical respectively.*

### Step 2: Compute Raw A (Attack) and D (Defense) Values

```
If CRITICAL HIT:
    A = Attacker's UNMODIFIED Attack/Special stat (ignores all stage modifiers, Reflect, Light Screen)
    D = Defender's UNMODIFIED Defense/Special stat
    L = Attacker's Level × 2    (level doubling!)
Else:
    A = Attacker's MODIFIED Attack/Special (apply stage modifiers: see Section 1.8)
    D = Defender's MODIFIED Defense/Special
        If Reflect active (Physical move): D ×= 2
        If Light Screen active (Special move): D ×= 2
    L = Attacker's Level (NO doubling)
```

**Stage modifier table (internal 0–12 → effective multiplier on stat):**
```
Index (stage):  0(-6)  1(-5)  2(-4)  3(-3)  4(-2)  5(-1)  6(0)  7(+1)  8(+2)  9(+3)  10(+4)  11(+5)  12(+6)
For positive: (Index) / 4  → e.g., stage 8(+2) → multiplier = 8/4 = 2.0
For negative: 4 / (Index)  → wait, actually: for negative stages, 4/(4+abs(stage))
Better mnemonic: Stage +6 → 350/100, +5 → 300/100, +4 → 250/100, +3 → 200/100, +2 → 150/100, +1 → 133/100
  0 → 100/100, -1 → 100/133, -2 → 100/150, -3 → 100/200, -4 → 100/250, -5 → 100/300, -6 → 100/350
Simplified: New_Stat = Base × Num / Denom where:
  Stage ≥ 0: Num = (Stage+2)×100, Denom = 200       (i.e., 100%, 133%, 166%, 200%, etc.)
  Stage < 0: Num = 200, Denom = (2-Stage)×100
```
*In practice, the game does: for positive stages, Stat × (stage+2) / 2. For negative, Stat × 2 / (2-stage). Then floor and cap.*

### Step 3: Overflow Handling

```
If A ≥ 256 OR D ≥ 256:
    A = floor(A / 4) AND 0xFF
    D = floor(D / 4) AND 0xFF
    If A == 0: A = 1    (A can never be 0 — but D CAN be 0!)
```
⚠️ **If D == 0**, the game does NOT protect against it. This causes a division-by-zero which in most emulators defaults to an extremely high damage value (or glitched damage). In practice, use X Defend/Defense boosts to avoid this.

### Step 4: Base Damage

```
Base = (L × 2 ÷ 5) + 2    (integer floor division)
Base = Base × Power        (move's base power)
Base = Base × A ÷ D        (integer floor)
Base = Base ÷ 50           (integer floor)
If Base > 997: Base = 997  (cap)
Base = Base + 2
```

### Step 5: Apply Modifiers (in order)

```
Modified = Base

// STAB (Same-Type Attack Bonus)
If move type matches attacker's Type 1 OR Type 2:
    Modified = Modified + floor(Modified / 2)

// Type Effectiveness (check each defender type)
T1 = effectiveness(move type, defender type 1)    // 0.5, 1, 2, or 0 (immune)
T2 = effectiveness(move type, defender type 2)    // (ignore if types are the same)
Modified = Modified × T1 × T2

// Note: In Gen 1, done as: floor(floor(Modified × T1_numerator / 10) × T2_numerator / 10)
// Where effective: ×20/10, neutral: ×10/10, not very effective: ×5/10, immune: ×0/10 = MISS

If result == 0: Move misses (immune type interaction).
```

### Step 6: Random Variance

```
If Modified == 1:
    Final = 1
Else:
    R = random integer in [217, 255]    // inclusive, uniform distribution
    Final = (Modified × R) ÷ 255        // floor division
    If Final > defender's max_HP: Final = defender's max_HP cap may apply
```

**Damage range:** 85.1% to 100% of Modified damage. (217/255 = 0.851...)

**Special Gen 1 notes:**
- Critical hits use UNMODIFIED defender's Defense (not the boosted/modified version) AND ignore Reflect/Light Screen.
- Critical hit level doubling means: a Lv. 30 attacker with a crit hits like Lv. 60. This is why high-crit moves (Slash, Karate Chop) are devastating.
- The `+2` in base damage formula means even super ineffective battles still deal at least 1-2 damage.

---

## 2.3 — Critical Hit Rate

### Formula

```
Critical rate = Base_Speed / 2    (integer division, this gives a byte value)
// Compare this byte to a random byte (0–255). If random < critical_rate → critical hit.
```

**Base crit rate by species (Base_Speed stat from Pokéductus):**
| Base_Speed | Crit rate byte | Approx. chance |
|---|---|---|
| 50 | 25 | ~9.8% |
| 75 | 37 | ~14.5% |
| 90 | 45 | ~17.6% |
| 100 | 50 | ~19.6% |
| Full list per species, see species data. |

### Moves with Elevated Critical Hit Rate

Certain moves have **×8 (octuple)** the normal critical hit rate:
- **Karate Chop** (HM-compatible move?)
- **Razor Leaf**
- **Slash**
- **Crabhammer**
- **Aeroblast** (not in Gen 1)

Move is flagged with "high critical hit bit" in the move data. When this bit is set:
```
Crit_rate = min(Base_Speed × 4, 255)
```
So a Pokémon with Base Speed 90 using Slash: crit rate = min(360, 255) = 255 = **100% crit chance.**

### Focus Energy Bug ⚠️

In Gen 1, **Focus Energy REDUCES** the critical hit rate instead of raising it. After using Focus Energy:
```
Crit_rate = Base_Speed / 8    (integer division, floor)
```
This is a **bug**. Never use Focus Energy attempting to increase crits. It makes crits *less* likely.

---

## 2.4 — Capture Rate Formula (Gen 1)

### Formula for Regular Poké Balls

```
// Only works if ball_id is a regular Poké Ball with ball_factor > 0
HP_factor = (Max_HP × 4000) / (Current_HP × max(1, Ball_factor))
If HP_factor > 255: HP_factor = 255
Status_bonus = 0
    If status is sleep or freeze: Status_bonus = 20
    If status is poison, burn, or paralysis: Status_bonus = 10
Catch_rate_move = max(1, Catch_rate + Status_bonus)    // This is a "bonus" byte:
    Actually the ball bonus byte = Ball_bonus + Status_bonus

Roll = random byte (0–255)

// Shake check (the game does):
// If Catch_rate_move >= Roll → check passes (1 of up to 3 checks)
// Then do HP check: if random(0,255) < min(255, HP_factor) → passes
// The number of passed checks determines if capture happens.

// Simplified probability for standard Poké Ball (ball_factor=12):
// Capture = approximately: 1 - (1 - min(1, Catch_rate/255) × HP_factor/255)^3
// In practice, if Catch_rate × HP_factor is high enough → guaranteed capture.
```

### Ball Bonuses

| Ball | Ball Factor | Notes |
|------|-------------|-------|
| Poké Ball | 12 | Standard |
| Great Ball | 12 | Actually bugged in Gen 1 — uses same factor! |
| Ultra Ball | 12 | Bug: same as standard ball? Actually Ultra Ball has ball_factor=12, BUT the internal logic treats it differently: with Ultra Ball, the HP_factor formula changes to use 8000 instead of 4000. |
| Master Ball | 0 | Always captures (ball_factor=0, special-cased) |
| Safari Ball | 12 | Safari Zone only |

**⚠️ Great Ball Bug:** In Gen 1, the Great Ball is NOT actually better than Poké Ball for most captures due to a bug in the formula. Ultra Ball uses `Max_HP × 8000 / (Current_HP × 12)` instead of `×4000`, making it actually better.

### HP Threshold for Guaranteed Capture (approximate)

For a Pokémon at 1 HP, with max HP 50, Catch Rate 255 (Rattata-level):
- HP_factor = (50 × 8000) / (1 × 12) = 400000 / 12 ≈ 33333 → capped at 255
- Status bonus = 20 (if asleep)
- Therefore: almost guaranteed capture with Ultra Ball on sleeping 1-HP Rattata.

### Maximize Capture Odds

1. Lower target to 1 HP (False Swipe doesn't exist in Gen 1; instead use super effective moves carefully, or Horn Drill misses at high HP).
2. Apply sleep (Sleep Powder, Hypnosis) — best status bonus (20).
3. Use Ultra Ball (not Great Ball due to bug).
4. Use Master Ball for legendaries if you don't have a Master Ball to spare.

---

## 2.5 — Type Effectiveness Table (Gen 1)

**Complete table. Rows = attacking type, Columns = defending type. Values: 2=Super Effective, 1=Neutral, 0.5=Not Very Effective, 0=No Effect (immune).**

| ATK ↓ / DEF → | NOR | FIR | WAT | GRA | ELE | ICE | FIG | POI | GRO | FLY | PSY | BUG | ROC | GHO | DRA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Normal** | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0.5 | 0 | 1 |
| **Fire** | 1 | 0.5 | 0.5 | 2 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 2 | 0.5 | 1 | 0.5 |
| **Water** | 1 | 2 | 0.5 | 0.5 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 2 | 1 | 0.5 |
| **Grass** | 1 | 0.5 | 2 | 0.5 | 1 | 1 | 1 | 0.5 | 2 | 0.5 | 1 | 0.5 | 2 | 1 | 0.5 |
| **Electric**| 1 | 1 | 2 | 0.5 | 0.5 | 1 | 1 | 1 | 0 | 2 | 1 | 1 | 1 | 1 | 0.5 |
| **Ice** | 1 | 1 | 0.5 | 2 | 1 | 0.5 | 1 | 1 | 2 | 2 | 1 | 1 | 1 | 1 | 2 |
| **Fighting**| 2 | 1 | 1 | 1 | 1 | 2 | 1 | 0.5 | 1 | 0.5 | 0.5 | 0.5 | 2 | 0 | 1 |
| **Poison**| 1 | 1 | 1 | 2 | 1 | 1 | 1 | 0.5 | 0.5 | 1 | 1 | 2 | 0.5 | 0.5 | 1 |
| **Ground**| 1 | 2 | 1 | 0.5 | 2 | 1 | 1 | 2 | 1 | 0 | 1 | 0.5 | 2 | 1 | 1 |
| **Flying**| 1 | 1 | 1 | 2 | 0.5 | 1 | 2 | 1 | 1 | 1 | 1 | 2 | 0.5 | 1 | 1 |
| **Psychic**| 1 | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 1 | 1 | 0.5 | 1 | 1 | 1 | 1 |
| **Bug** | 1 | 0.5 | 1 | 2 | 1 | 1 | 0.5 | 2 | 1 | 0.5 | 2 | 1 | 1 | 0.5 | 1 |
| **Rock** | 1 | 2 | 1 | 1 | 1 | 2 | 0.5 | 1 | 0.5 | 2 | 1 | 2 | 1 | 1 | 1 |
| **Ghost** | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 2 | 1 |
| **Dragon**| 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 |

**Key observations for Gen 1:**
- **Ghost is immune to Normal AND Fighting** (effectively blocks many physical attacks).
- **Psychic is immune to Ghost** (Gen 1 only — this was changed in Gen 2+). Psychic types have no effective weaknesses in Gen 1 except Bug (which is not very effective due to Poison-dual-typing of most Bug types).
- **Ground is immune to Electric** (critical for Raichu/Surge).
- **Ghost move only hits Normal types in Gen 0x19 confusion. The "Ghost is immune to Normal/Fighting" rule is special.

---

## 2.6 — Accuracy and Evasion

### Base accuracy check

```
Move_accuracy is stored as a percentage value (0–100, or 255 for always-hit moves).
Modified accuracy = Move_accuracy × Accuracy_stage_multiplier × Evasion_stage_multiplier

If random_byte < Modified accuracy → move hits.
```

### Accuracy/Evasion Stage Modifiers (same formula as stat stages)

| Stage | Multiplier |
|-------|-----------|
| -6 | 33/100 |
| -5 | 38/100 |
| -4 | 43/100 |
| -3 | 50/100 |
| -2 | 60/100 |
| -1 | 75/100 |
| 0 | 100/100 |
| +1 | 133/100 |
| +2 | 166/100 |
| +3 | 200/100 |
| +4 | 233/100 |
| +5 | 266/100 |
| +6 | 300/100 |

### X Accuracy

Using X Accuracy sets a flag that makes the first accuracy check always pass. BUT in Gen 1, **X Accuracy also raises accuracy by 1 stage internally**. The first move after X Accuracy will almost always hit. Subsequent moves return to normal checks.

### Always-Hit Moves

Moves with accuracy byte = 0xFE or 0xFF in Gen 1:
- **Swift** (never misses)
- **Horn Drill, Guillotine, Fissure, Sheer Cold** (OHKO moves — use separate accuracy formula)

### OHKO Move Accuracy

```
Hit if: Attacker_Level - Defender_Level + 30 > random(0, 100)
```
OHKO moves have 30% base hit rate + level difference. If defender is higher level than attacker, the move miss chance increases drastically.

---

## 2.7 — Status Conditions

### Paralysis
- **Chance per turn:** 25% probability the Pokémon cannot move (full paralysis).
- **Speed:** Reduced to 25% of current Speed (same as -6 stage, but applied *after* normal modifiers).
- Cured by: Parlyz Heal, Full Heal, Full Restore, waiting it out on bench (cured on switch).

### Burn
- **Attack:** Reduced to 50% of current Attack (same as -2 stage, applied *after* normal modifiers).
- **Residual damage:** Lose 1/16 of max HP at end of each turn.
- Cured by: Burn Heal, Full Heal, Full Restore.

### Poison
- **Residual damage:** Lose 1/16 of max HP at end of each turn (does NOT increase over time; only Toxic does).
- Cured by: Antidote, Full Heal, Full Restore.

### Toxic (Bad Poison)
- **Residual damage:** Lose N/16 of max HP at end of each turn, where N starts at 1 and increases by 1 each turn the Pokémon remains in battle.
- N is preserved if the Pokémon stays in. If switched out and back in, N resets to 1.
- Does NOT wear off on its own. Extremely dangerous.

### Sleep
- **Duration:** 1–7 turns (random when inflicted). Sleep in Gen 1 does NOT end when damaged.
- Pokémon cannot move while asleep.
- Cured by: Awakening, Full Heal, Full Restore, or natural wake-up counter reaching 0.
- After waking, the Pokémon gets a full turn (wake-up does NOT consume the turn).

### Freeze
- **No thaw chance per turn in Gen 1!** ⚠️ In Gen 1, there is no automatic 10% thaw chance. A frozen Pokémon **stays frozen** indefinitely unless:
  - Hit by a Fire-type move (Will-O-Wisp doesn't exist; Fire Blast, Flamethrower, Ember, Fire Spin, etc.).
  - Haze is used (thaws both sides).
  - Full Heal / Ice Heal cures it.
  - The frozen Pokémon uses a move that thaws it (none in Gen 1).
- **Freeze is effectively permanent** without outside help.

### Confusion
- **Duration:** 1–5 turns.
- **Per turn:** 50% chance of dealing self-damage (40 base power, type-less physical move using Attack vs. Defense).
- Cured by: switching out, waiting for counter to expire, or Haze.
- When confused Pokémon hits itself, the "confusion damage" uses a special damage calc (power 40, no STAB, no type modifiers).

---

## 2.8 — Experience and Leveling

### Experience Yield

```
// Per fainted enemy:
Base_exp = floor(Base_Experience_of_defeated × Level_of_defeated / 7)

// Trainer battle bonus:
If trainer battle: Base_exp × 3 / 2 (1.5× multiplier)

// Division across party:
n = number_of_participants (including those holding Exp. All who didn't actually fight)
Each participant gets: Base_exp / n

// Exp. All effect:
Each Pokémon NOT participating (holding Exp. All): Gets (Base_exp / 2) / n_nonparticipating
```

**In Gen 1, Exp. All effectively gives the active Pokémon full exp AND splits half the remaining exp among non-participating party members.**

### Experience Groups

| Group | Experience to reach Lv. N (total) | Pokémon using this |
|---|---|---|
| **Fast** | `floor(N³ × 4 / 5)` | Butterfree, Beedrill, Pidgey/Raticate line, Spearow/Ekans/Fearow line, Clefairy/Clefable, Jigglypuff/Wigglytuff, etc. |
| **Medium Fast** | `N³` | Most Pokémon. Includes: Bulbasaur, Charmander, Squirtle evolutions, Nido lines, Geodude/Graveler/Golem, etc. The **default**. |
| **Medium Slow** | `floor(1.2 × N³ - 15 × N² + 100 × N - 140)` | Pikachu, Abra line, Machop line, Gastly line, starters (for some). These require more experience at high levels. |
| **Slow** | `floor(1.25 × N³)` | Lapras, Snorlax, Mewtwo, Mew, legendaries, and some late-game Pokémon. These require the most experience. |

### Level-up mechanics

- When experience exceeds the threshold for the next level, level up occurs.
- The level byte updates (party offset +33, also +3).
- Stat changes are computed on the fly from the new level.
- Moves are learned by level. If a new move is learned, the game asks (via text box, not readable) — for memory-driven play, you must press `advance_dialog` through the learn sequence: typically `advance_dialog` until the "learned [MOVE]!" message completes, then handle the "forget a move?" prompt (press `Down` then `A` for "NO" to cancel learning, or press `A` for "YES" and select the move to replace).

---

## 2.9 — Multi-Turn Moves

### Wrap / Bind / Clamp / Fire Spin

```
// On first use: Deals damage, prevents switching.
// Subsequent turns: Deals burst damage (same formula, power varies: Wrap=15, Bind=15, Clamp=35, Fire Spin=15).
// Duration: 2–5 turns (random, including the first turn).
```

**⚠️ Gen 1 Wrap Bug:** When the trapped Pokémon faints from Wrap damage, the trapping Pokémon continues to "wrap" for the remaining duration of the move, doing nothing. This is a minor quirk.

**⚠️ Switching out while wrapped:** In Gen 1, switching out ENDS the wrap effect immediately. The trapping Pokémon's next target (if switching back in) is free. This is different from later generations.

### Bide

1. Turn 1: Use Bide. The Pokémon is now "biding" and will NOT attack for 2–3 turns. All incoming damage is accumulated.
2. Turn 2–3: Bide again (forced). Accumulates all damage from both sides, including self-damage from confusion.
3. Release: Deals 2× the total accumulated damage to the opponent.

**Bug:** If the opponent switches, Bide hits whatever comes out.

### Focus Energy (Bug)

See Section 2.3. Focus Energy in Gen 1 REDUCES critical hit rate. Do not use it.

### Rage

- When hit while using Rage, Attack increases by 1 stage per hit (capped at +6).
- The user is locked into Rage for its duration of battle (cannot use another menu option until it faints or the battle ends).
- Even if Rage would KO the opponent, the attack boost persists.

### Hyper Beam

- Power 150, 90% accuracy.
- If Hyper Beam KOs the target: NO recharge turn (skips recharge, unique Gen 1 quirk).
- If Hyper Beam doesn't KO: MUST recharge for 1 turn (the Hyper Beam recharge flag prevents other moves from being selected).

---

## 2.10 — Priority Moves (Gen 1)

In Gen 1, speed determines move order UNLESS a priority move is involved.

**Only one priority move exists in Gen 1:**

- **Quick Attack** (Priority +1): Always goes first if both Pokémon are using non-priority moves.
  - Power: 40, Accuracy: 100%, PP: 30.
  - Many Pokémon learn it: Rattata/Raticate, Pikachu (not Raichu naturally), Scyther, Farfetch'd, etc.

**Counter** has priority -1 (always goes second) against physical moves, but the mechanics are quirky in Gen 1 (counters the last physical damage received, of any amount, not capped, and works against any special attack by glitch — "Swapping" damage).

---

## 2.11 — Switch Mechanics

- Switching costs one turn. The incoming Pokémon enters and can then act on the next turn.
- If the active Pokémon faints and you switch, the switch happens at the end of the turn. The new Pokémon takes the incoming attack (if there was one queued from the opponent's faster action).
- **Switch priority in Gen 1 is AFTER speed:** The switch always happens first regardless of Speed stats. Whoever switches first comes in first (on simultaneous switches, the game uses the link cable direction or internal byte ordering).

---

## 2.12 — Badge Effects (Stat Bonuses) Quick Reference

| Badge | Stat Boost | Notes |
|--------|-----------|-------|
| BoulderBadge | Attack +12.5% | Applies to all party Pokémon in in-game battles. |
| ThunderBadge | Defense +12.5% | *(NOT Speed — common misconception from in-game text)* |
| SoulBadge | Speed +12.5% | *(NOT Defense — common misconception from in-game text)* |
| VolcanoBadge | Special +12.5% | |

**These boosts:** Only apply in in-game battles, NOT link cable battles. Applied after stat stage modifiers. Subject to the stat-modification glitch (using X items can reset them).

---

## 2.13 — Obedience Mechanics

Traded Pokémon (Trainer ID ≠ Player ID) may disobey if level exceeds badge threshold:

| # Badges | Max Obedient Level |
|----------|-------------------|
| 0 | 10 |
| 1 | 10 (no change) |
| 2 | 30 (Cascade Badge) |
| 3 | 30 |
| 4 | 50 (Rainbow Badge) |
| 5 | 50 |
| 6 | 70 (Marsh Badge) |
| 7 | 70 |
| 8+ | 101 (Earth Badge) |

Disobedience behavior is random each turn:
- 25%: Pokémon ignores order, uses random move
- 25%: Pokémon does nothing (nap, loaf, etc.)
- 25%: Take confusion damage (if not already confused)
- 15%: Follow orders normally anyway

**Pokémon with your own Trainer ID ALWAYS obey, regardless of level.**

---

## 2.14 — Weight/Height (Gen 1)

Gen 1 stores weight and height as display-only data. They do not affect gameplay formulas (no Low Kick, Grass Knot, etc. in Gen 1).

---

## 2.15 — Day Care

The Day Care is located on Route 4 (south of Cerulean City, accessible from Cycling Road area). It raises one Pokémon, gaining 1 experience point per step. The Pokémon cannot learn new moves or evolve while at Day Care in Gen 1. The Day Care person's position determines how many steps you've taken (divide steps by 256 for the experience gain).

---

*Continue to Section 3: Map & Navigation Database*
