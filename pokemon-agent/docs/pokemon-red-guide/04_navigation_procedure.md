# SECTION 4: SYSTEMATIC NAVIGATION PROCEDURE
## The "Move-Check" Loop

---

## 4.1 — Core Navigation Algorithm

This is the universal pattern for all movement in Pokémon Red without visual feedback.

```
FUNCTION safe_move(direction, target_X, target_Y):
    // direction = "Up" | "Down" | "Left" | "Right"
    
    // STEP 1: Read current position
    current_X = read_memory(D361)
    current_Y = read_memory(D362)
    
    // STEP 2: Compute expected position after one step
    expected_X = current_X
    expected_Y = current_Y
    IF direction == "Up":    expected_Y = current_Y - 1
    IF direction == "Down":  expected_Y = current_Y + 2  // wait, +1
    IF direction == "Down":  expected_Y = current_Y + 1
    IF direction == "Left":  expected_X = current_X - 1
    IF direction == "Right": expected_X = current_X + 1
    
    // STEP 3: Press the direction button once
    press_direction(direction)
    wait_frames(30)  // allow the step to complete
    
    // STEP 4: Read new position
    new_X = read_memory(D361)
    new_Y = read_memory(D362)
    
    // STEP 5: Evaluate result
    IF new_X == expected_X AND new_Y == expected_Y:
        // SUCCESS: movement completed
        RETURN "moved"
    
    IF new_X == current_X AND new_Y == current_Y:
        // BLOCKED: an obstacle is in the way
        // Check if it's a dialog trigger (NPC in front of you):
        IF there_is_NPC_at(expected_X, expected_Y):
            // NPC is blocking path or just started dialog
            interact()          // talk to NPC / dismiss dialog
            advance_dialog_N_times(N)   // clear dialog (N from Dialog Database)
            press_direction(direction)  // try moving again
            RETURN "blocked_NPC_resolved"
        ELSE:
            // It's a wall, tree, or other obstacle
            // Try alternative path
            RETURN "blocked_wall"
    
    // STEP 6: Warp detection
    IF new_map_ID != original_map_ID:
        RETURN "warped"
    
    RETURN "unknown"
```

---

## 4.2 — "Feeling" Along Walls

When you don't know the exact layout, use wall-following:

```
FUNCTION feel_wall_and_move(direction_along_wall, wall_side):
    // wall_side = "left" | "right" (which side the wall is on)
    
    LOOP:
        // First try to move along the intended direction
        result = safe_move(direction_along_wall, ?, ?)
        
        IF result == "moved":
            // Check if wall is still present on the wall_side
            wall_check_dir = perpendicular_toward(wall_side, direction_along_wall)
            wall_X, wall_Y = compute_position_in_direction(wall_check_dir)
            temp_result = safe_move(wall_check_dir, ?, ?)
            // This will either hit wall (stay in place) or move into wall space
            
            IF temp_result == "blocked_wall":
                // Wall is still there, continue
                CONTINUE
            
            IF temp_result == "moved":
                // We've found a gap! We moved INTO the wall area.
                // Move back and continue along the new path
                opposite_dir = opposite(wall_check_dir)
                safe_move(opposite_dir, ?, ?)
                CONTINUE
        
        IF result == "blocked_wall":
            // Can't move forward along wall. Try turning into the wall.
            turn_dir = perpendicular_toward(wall_side, direction_along_wall)
            safe_move(turn_dir, ?, ?)
            // Adjust direction_along_wall
            
        IF result == "blocked_NPC_resolved":
            CONTINUE  // NPC was blocking, now resolved, try again
```

---

## 4.3 — Handling Warps (Doors, Stairs, Cave Entrances)

```
FUNCTION use_warp_tile(target_X, target_Y, target_map_after_warp):
    // 1. Navigate to the warp tile
    navigate_to(target_X, target_Y)
    
    // 2. Step ONTO the tile (direction depends on warp type)
    // For doors: step onto the doormat tile directly in front of the door
    original_map = read_memory(D35E)
    
    // 3. Wait for warp animation
    wait_frames(60)
    
    // 4. Check for warp
    new_map = read_memory(D35E)
    
    IF new_map == original_map:
        // Warp didn't trigger. Common causes:
        // a) Wrong tile — try adjacent tile
        // b) Need to face a specific direction — try interact()
        interact()
        wait_frames(30)
        new_map = read_memory(D35E)
        
        IF new_map == original_map:
            // Still didn't warp. Try interact again or move off and back on.
            press_direction("Down")  // step off
            wait_frames(15)
            press_direction("Up")    // step back on
            wait_frames(60)
            new_map = read_memory(D35E)
    
    IF new_map != original_map:
        // WARP SUCCESS
        new_X = read_memory(D361)
        new_Y = read_memory(D362)
        RETURN "warped to map " + new_map + " at (" + new_X + ", " + new_Y + ")"
    
    RETURN "warp failed — verify tile coordinates"
```

---

## 4.4 — Ledge Handling

Ledges are one-way — you can jump DOWN them but not climb back UP.

```
FUNCTION handle_ledge(ledge_X, ledge_Y, jump_direction):
    // Jump direction is always DOWN (south) in Gen 1 ledges
    // Position yourself on the tile ABOVE the ledge
    
    // Check: are we at the ledge tile?
    current_X = read_memory(D361)
    current_Y = read_memory(D362)
    
    IF current_X == ledge_X AND current_Y == ledge_Y:
        // This IS the ledge tile. Jumping south will make us fall down.
        press_direction("Down")
        wait_frames(30)
        // Verify: Y coordinate should have increased by 2 (fell one level)
        new_Y = read_memory(D362)
        IF new_Y > current_Y + 1:
            RETURN "fell through ledge"
    
    RETURN "not at ledge"
```

**IMPORTANT:** To go BACK UP a ledge from below, you must find an alternate path. Ledges are one-way in Gen 1.

---

## 4.5 — Surfing

Surf is used on water tiles. Requires a Pokémon that knows Surf and the Soul Badge.

```
FUNCTION start_surfing():
    // Position yourself on a water tile adjacent to land
    // Move onto the water tile
    // The game triggers the Surf prompt automatically
    // In memory-driven mode: move south from land edge onto water
    // If you're on water and game allows movement across it, Surf is active
    
    // To verify surfing state: read D52A (wWalkBikeSurfState). 
    // Value 3 = Surfing.
    state = read_memory(D52A)
    IF state == 3:
        RETURN "surfing"
    ELSE:
        RETURN "not surfing — need Surf HM + Soul Badge"
```

---

## 4.6 — Fly Usage

Requires any Pokémon knowing Fly and the Thunder Badge.

```
FUNCTION fly_to(town_map_ID):
    // 1. Open menu: press Start
    press_start()
    // 2. Navigate to Pokémon menu:
    press_down()   // move cursor to "POKEMON" in main menu
    press_down()   // ...
    // Exact position depends on main menu cursor state.
    // The default main menu has: POKEMON / ITEM / POKéDEX / etc.
    // Fly is in the FIELD MOVES menu of a Pokémon, not the main menu.
    
    // Correct Fly sequence:
    // Start → Down to POKEMON → A → select Pokémon with Fly → A on "FIELD" or scroll to Fly → A → Select destination from Fly map
    
    // Destination map IDs for Fly:
    // Pallet Town: 0x00
    // Viridian City: 0x01
    // Pewter City: 0x02
    // Cerulean City: 0x03
    // Vermilion City: 0x04
    // Lavender Town: 0x05
    // Celadon City: 0x06
    // Fuchsia City: 0x07
    // Cinnabar Island: 0x08
    // Indigo Plateau: 0x09
    // Saffron City: 0x0A
    // Your current position is also available as a Fly target
    
    // Note: Fly sets your "last visited Pokémon Center" for Teleport too.
```

---

## 4.7 — Menu Navigation Reference

### Main Menu (opened with START)
Cursor positions (starting from top = 0):
| Index | Option | How to select |
|-------|--------|---------------|
| 0 | POKEMON | Press START, then A (first item) |
| 1 | ITEM | START, Down, A |
| 2 | POKéDEX | START, Down, Down, A |
| 3 | POKéMON (second) | START, Down×3, A |
| ... | etc | ... |
| 7 | OPTION | START, Down×7, A |
| 8 | EXIT | START, Down×8, A |

### Bag Menu
After selecting ITEM from main menu:
| Index | Category |
|-------|----------|
| 0 | Items (regular) |
| 1 | Key Items |
| 2 | Poké Balls |
| 3+ | TMs/HMs (after scrolling) |

To use a healing item (e.e. Potion):
```
1. START → Down → A (open ITEM menu)
2. Down → A (select Items category)  
3. Navigate to item by pressing Down repeatedly
   (Items appear in the order they are in your bag)
4. A (select item)
5. A (select first party Pokémon to use it on)
6. Wait for the confirm message
```

### Saving the Game
```
START → Down to SAVE (index N depends on menu version) → A → 
Confirm with A on "SAVE" in the sub-menu → 
advance_dialog through "SAVING... DON'T TURN OFF THE POWER."
→ Wait for completion (2+ seconds)
```

---

## 4.8 — Direction + Coordinate Change Reference

| Direction | Key | X change | Y change |
|-----------|-----|----------|----------|
| Down | ↓ | 0 | +1 |
| Up | ↑ | 0 | -1 |
| Left | ← | -1 | 0 |
| Right | → | +1 | 0 |

**Block coordinates (2×2 tile groups):**
- `wXBlock` = `wXCoord / 2` (floor)
- `wYBlock` = `wYCoord / 2` (floor)

---

## 4.9 — Troubleshooting Common Navigation Failures

| Symptom | Cause | Solution |
|---------|-------|----------|
| Coordinates don't change after direction press | Wall/obstacle/NPC | Try interact, then advance_dialog. Or try different direction. |
| Coordinates change but not in expected direction | You're facing a different direction than you think. | Read sprite facing byte at C109 + 0x10×sprite_num. |
| Map ID changed unexpectedly | You stepped on a warp tile. | Check if warp was intentional. If not, navigate back. |
| Stuck in dialog loop | NPC has branching dialog and you're triggering "NO" path that restarts. | Track advance_dialog count. Try advancing more. For YES/NO: default = YES (press A directly). NO = press Down then A. |
| Can't leave building | You need to step on the correct exit warp tile (usually at the bottom of the room). | Walk to bottom of room, usually Y = map_max_Y - 2. |
| Trainer won't battle you | Already defeated (flag set). | Read the trainer flag byte. If already set, skip. |
| Entering a new map but position is wrong | Warp landed you at wrong destination. Verify warp save data. | Some warps have variable destinations based on which tile you entered from. Try again from a slightly different position. |

---

## 4.10 — Speed Optimization Tips

1. **Run with B:** After obtaining Running Shoes (bit in D70A set), hold B while pressing directions for 2× speed.
2. **Bicycle:** After obtaining Bicycle, press SELECT to mount for 3× speed (faster than running). Must be on land (not in buildings, caves still work).
3. **Repel:** Use Repel from the bag to avoid wild encounters below level threshold. Repel lasts 256 steps.
4. **Super Repel:** Same but costs more but lasts just as long (actually same duration, just different item).
5. **Max Repel:** Most cost-effective.

### Repel Usage Memory Check
- Repel step counter is at memory address `D087` (approx). When it reaches 0, repel wears off.

---

*Continue to Section 5: Complete Walkthrough*
