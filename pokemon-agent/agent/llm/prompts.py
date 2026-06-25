"""Production-grade prompt builders for Guide, Navigation, and Critique agents.

Loads AGENT_CONTEXT.md at module level and parses it into focused knowledge
sections for each agent. System prompts combine role definition, domain
knowledge, and strict "output on LAST LINE only" rules for reliable parsing
(even with reasoning models that return thinking in reasoning_content).

Output formats:
- Guide: reasoning → LAST LINE: step_id only
- Navigation: reasoning → LAST LINE: action only
- Critique: reasoning → LAST LINE: PASS or FAIL only
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import json
import re

# ──────────────────────────────────────────────
# Load and parse AGENT_CONTEXT.md at module level
# ──────────────────────────────────────────────

def _parse_agent_context() -> Dict[str, str]:
    """Read AGENT_CONTEXT.md and split into sections keyed by ## header.
    Splits on '---' lines between headers as specified.
    """
    ctx_path = Path(__file__).parent.parent.parent.parent / 'docs' / 'AGENT_CONTEXT.md'
    if not ctx_path.exists():
        raise FileNotFoundError(f"AGENT_CONTEXT.md not found at {ctx_path}")
    content = ctx_path.read_text(encoding='utf-8')

    sections: Dict[str, str] = {}
    # Split entire document on '---' separators
    blocks = [b.strip() for b in content.split('---') if b.strip()]

    for block in blocks:
        # Locate the ## header (e.g. "## 1. Navigation Rules and Gotchas")
        header_match = re.search(r'^(##\s+\d+\.\s+[^\n]+)', block, re.MULTILINE)
        if header_match:
            header = header_match.group(1).strip()
            # Content starts after the header line
            start_idx = header_match.end()
            section_content = block[start_idx:].strip()
            sections[header] = section_content

    return sections


AGENT_SECTIONS = _parse_agent_context()

# Focused context bundles per agent role
CONTEXT_NAVIGATION = (
    AGENT_SECTIONS.get("## 1. Navigation Rules and Gotchas", "") +
    "\n\n" +
    AGENT_SECTIONS.get("## 5. Collision Map Usage", "")
).strip()

CONTEXT_GUIDE = (
    AGENT_SECTIONS.get("## 3. Walkthrough / Milestone Order (Early Game)", "") +
    "\n\n" +
    AGENT_SECTIONS.get("## 6. Starter Selection Details", "")
).strip()

CONTEXT_CRITIQUE = (
    AGENT_SECTIONS.get("## 2. Battle Strategy", "") +
    "\n\n" +
    AGENT_SECTIONS.get("## 3. Walkthrough / Milestone Order (Early Game)", "")
).strip()

# Temperature constants for each agent (low temp for deterministic outputs)
GUIDE_TEMP = 0.1
NAV_TEMP = 0.3
CRITIQUE_TEMP = 0.1


# ──────────────────────────────────────────────
# GUIDE AGENT
# ──────────────────────────────────────────────

GUIDE_SYSTEM = f"""You are the Guide Agent — the AUTHORITY on which objective the Pokémon Red agent should pursue next.

ROLE: Given the current game state, ALL available walkthrough steps (not yet completed), the completed IDs, and recent trajectory, pick the ONE step the agent should work on now. Your decision is final — the system trusts your reasoning.

CRITICAL RULE — STRICT EARLY-GAME SEQUENCE:
The early game is STRICTLY LINEAR. You CANNOT skip ahead. The order is:
1. EXIT_REDS_HOUSE_2F → EXIT_REDS_HOUSE_1F → WALK_TO_OAK_TRIGGER → CHOOSE_STARTER
2. RIVAL_BATTLE_1 (requires party non-empty)
3. EXIT_OAKS_LAB → ROUTE_1_NORTH → VIRIDIAN_CENTER → VIRIDIAN_MART → DELIVER_PARCEL
4. VIRIDIAN_FOREST → BOULDER_BADGE

EARLY GAME OVERRIDE (highest priority):
- If party is EMPTY and agent is in/near Oak's Lab or Pallet Town → MUST pick CHOOSE_STARTER
- If party is EMPTY and agent is in Red's House → pick EXIT_REDS_HOUSE_2F or EXIT_REDS_HOUSE_1F
- NEVER pick VIRIDIAN_CENTER, VIRIDIAN_MART, DELIVER_PARCEL, or any mid-game objective when party is empty

THINKING APPROACH:
1. Read the game state carefully (map, position, party, flags, badges, health).
2. Look at completed_ids to see what's already done.
3. Consider where the agent physically is — can it reach the objective from here?
4. Consider SAVE/LOAD scenarios: the agent might have been reloaded mid-game. Use game state as ground truth, completed_ids as imperfect hints.
5. Pick the most logical next step given CURRENT reality, respecting the strict sequence above.

PREREQUISITE CHAINS (important):
- VIRIDIAN_MART requires having healed at VIRIDIAN_CENTER first
- DELIVER_PARCEL requires having visited VIRIDIAN_MART to get Oak's Parcel
- VIRIDIAN_FOREST requires having delivered the parcel to Oak (has_pokedex)
If you pick a step, earlier steps in its chain are assumed done.

WHEN IN DOUBT:
- If party is empty → CHOOSE_STARTER (no exceptions)
- If party health is low and the agent is in Viridian City → VIRIDIAN_CENTER first
- If party is healed and in Viridian City → VIRIDIAN_MART (the parcel)
- If the agent has Oak's Parcel → DELIVER_PARCEL back in Pallet Town
- If flags show something is already done (e.g. party fully healed) — skip that step

You are an expert on Pokémon Red walkthrough progression and game mechanics.

KNOWLEDGE BASE:
{CONTEXT_GUIDE}

OUTPUT FORMAT RULES (STRICT):
- Write 1-4 sentences of reasoning. Explain WHY this step is the right one given current reality.
- The VERY LAST LINE of your entire response must contain ONLY the exact step_id (e.g. CHOOSE_STARTER).
- No JSON, no markdown, no quotes, no trailing text or periods after the step_id.

Example correct output:
Agent is in Oak's Lab with an empty party. The game was just reset. The only valid first objective is to pick a starter from the Poke Balls on the table.
CHOOSE_STARTER
"""

def build_guide_prompt(
    game_state_summary: str,
    available_steps: List[Dict[str, Any]],
    completed_ids: List[str],
    recent_actions: List[str],
    memory_context: str = "",
) -> Tuple[str, str]:
    """Build (system, user) for the Guide agent.

    available_steps: list of step dicts with 'id', 'description', 'start_conditions', 'completion_conditions'
    memory_context: compact memory summary from build_guide_memory_prompt()
    """
    if available_steps:
        avail_lines = []
        for s in available_steps:
            sid = s.get("id", "?")
            desc = s.get("description", "")
            conds = s.get("start_conditions", {})
            conds_str = ", ".join(f"{k}={v}" for k, v in conds.items()) if conds else "none"
            avail_lines.append(f"- {sid}: {desc} (needs: {conds_str})")
        avail_text = "\n".join(avail_lines)
    else:
        avail_text = "(no available steps listed)"
    completed_text = ", ".join(completed_ids[-10:]) if completed_ids else "none"
    recent_text = "\n".join(f"- {a}" for a in recent_actions[-5:]) if recent_actions else "none recorded"

    memory_text = ""
    if memory_context:
        memory_text = f"\n## Memory Summary\n{memory_context}\n"

    user_message = f"""## Current Game State Summary
{game_state_summary}
{memory_text}
## Available Step Candidates
{avail_text}

## Recently Completed Step IDs
{completed_text}

## Recent Actions
{recent_text}

Pick the ONE step_id the agent should work on next based on current game state and progress.
Consider SAVE/LOAD scenarios - the agent may have been reloaded with partial progress.
Use game state as ground truth. completed_ids are hints but may be incomplete after restarts.
Reason briefly, then output ONLY the step_id on the LAST LINE."""

    return GUIDE_SYSTEM, user_message


# ──────────────────────────────────────────────
# NAVIGATION AGENT
# ──────────────────────────────────────────────

NAVIGATION_SYSTEM = f"""You are the Navigation Agent for Pokémon Red.

ROLE: You decide ONE button press per turn. That's it. One action, then you get a fresh look at the game state and decide the next one.

This is how the game works:
- You press ONE button (press_up, press_down, press_left, press_right, press_a, press_b, wait)
- The game updates
- You see the new state and press ONE more button
- Repeat until the objective is complete

You are in FULL CONTROL of every button press. You decide when to walk, when to press A to interact, when to press B to advance dialog, and when to wait.

{CONTEXT_NAVIGATION}

DIRECTION MAPPING (CRITICAL):
- Y increases DOWNWARD, X increases RIGHTWARD
- press_up = decrease Y (move toward top of screen)
- press_down = increase Y (move toward bottom of screen)
- press_left = decrease X (move toward left of screen)
- press_right = increase X (move toward right of screen)

ACTION SPACE (pick ONE per turn):
- press_up, press_down, press_left, press_right — move one tile (MOVEMENT ONLY, never interacts)
- press_a — interact with the tile you are FACING (the direction you are looking), NOT the tile you are standing on. If you are facing right, you interact with the tile to your right. If you are below an item facing right, pressing A will NOT reach the item above you.
- press_b — advance dialog text / dismiss text / say NO
- press_start — confirm on naming screens (alphabet grid)
- wait — do nothing for a tick (useful during scripted sequences)

CRITICAL RULE — FACING BEFORE INTERACTING:
To interact with an item, NPC, or door, you MUST:
1. Stand adjacent to the target (next to it, not on top of it)
2. Face toward the target (press the direction button toward it first)
3. THEN press_a while facing it

If the GPS says "press_up", it means "face up by pressing press_up". On the NEXT turn, if the GPS says you're at your target, THEN press_a.

IF YOU ARE BELOW AN ITEM (item Y is less than your Y): press_up first to face it, then press_a on the next turn.
IF YOU ARE ABOVE AN ITEM (item Y is greater than your Y): press_down first to face it, then press_a on the next turn.
IF YOU ARE LEFT OF AN ITEM (item X is greater than your X): press_right first to face it, then press_a on the next turn.
IF YOU ARE RIGHT OF AN ITEM (item X is less than your X): press_left first to face it, then press_a on the next turn.

DO NOT press_a if you are not facing the target. It will fail silently.

COUNTER NPCS: Some NPCs stand behind counters (Pokemon Center nurse, Mart clerk). The counter tile is # — you cannot walk onto it. Stand on the walkable tile directly below the counter (with # above you), face up, press A. The game routes your interaction through the counter to the NPC.

MAP READING (use the grid below):
The collision grid shows your immediate surroundings. @ is you, . is walkable, # is a wall, S is a warp/stairs, I is an item/NPC.
Use the grid to plan your route. The A* path (shown as "Suggested Route") is computed to avoid walls and obstacles — FOLLOW IT even if the direct line to the target looks clear. Walls and trees may block your path even when the target is visible.
If your last action was blocked (didn't move), try a DIFFERENT direction that is walkable on the grid.

STAIRS AND WARP TILES: S tiles (stairs/warp) and D tiles (doormat/exit) are WALKABLE. You can step on them normally. Stepping on S triggers a floor transition (e.g., stairs between floors). Stepping on D triggers a map exit (e.g., leaving a building). Do NOT avoid these tiles — use them to reach your objective.
DOORMAT EXITS: If you are standing on a D (doormat) tile, press_down to exit. The server overrides collision for doormat exits — it's OK if the tile below shows #.

CONNECTED MAPS: Some maps are connected without warp tiles (e.g., Pallet Town ↔ Route 1). To transition between connected maps, walk to the edge of the current map in the direction of the destination. There is NO "exit tile" — the map name changes automatically when you cross the boundary. If the objective says "go to Route 1" and you're in Pallet Town, just walk north until the map name changes.

BUILDING ENTRANCES: Warps labeled "building entrance" lead INTO a building (e.g., "→ Red's House 1F"). Do NOT use these unless the objective specifically says to enter that building. To EXIT a building, look for a D (doormat) tile or an "exit to outside" warp.

OUTPUT FORMAT RULES (STRICT):
- Write 1-3 sentences of reasoning. Explain WHY this action advances the objective.
- The VERY LAST LINE of your entire response must contain ONLY the action name.
- No JSON, no markdown, no quotes, no trailing text.

Examples of correct output:

Example 1 — navigating to a warp:
I'm at (6,5) and need to reach the doormat exit at (2,7). Going left gets me closer.
press_left

Example 2 — below an item (MUST face up first):
I'm at (8,4) and the Squirtle Pokeball is at (8,3) directly above me. I am facing right, so I need to press_up to face the item first. On the next turn I will press_a.
press_up

Example 3 — facing the item already (NOW press A):
I'm at (8,4) and the Squirtle Pokeball is at (8,3) directly above me. I am already facing up toward it. Pressing press_a will interact with the Pokeball.
press_a

Example 4 — blocked direction:
press_down was blocked, so I'll try press_right instead.
press_right"""

def build_navigation_prompt(
    objective: str,
    hints: List[str],
    position: Any,
    facing: str,
    dialog_active: bool,
    warps: Optional[List[Dict[str, Any]]] = None,
    suggested_direction: Optional[str] = None,
    last_action: Optional[str] = None,
    last_position: Any = None,
    current_position: Any = None,
    game_state: Optional[Dict[str, Any]] = None,
    walkable_directions: Optional[List[str]] = None,
    chosen_starter: str = "",
    failure_memory: Optional[Dict[str, int]] = None,
    memory_context: str = "",
    recent_history: Optional[List[Dict[str, Any]]] = None,
    player_pos: Optional[Tuple[int, int]] = None,
    player_map: str = "",
    visited_tiles: Optional[set] = None,
) -> Tuple[str, str]:
    """Build (system, user) for the Navigation agent.

    player_pos / player_map: current tile coordinates used to show visited
    tile context in the prompt (which tiles have been explored already).
    visited_tiles: set of (x,y) tiles actually visited on this map — used
    to discourage oscillation and re-exploration.
    """
    hints_text = "\n".join(f"- {h}" for h in hints) if hints else ""

    pos_str = str(position) if position is not None else "?"
    curr_str = str(current_position) if current_position is not None else pos_str

    feedback = ""
    if last_action and last_position is not None and current_position is not None:
        if last_position == current_position:
            walkable_str = ', '.join(walkable_directions) if walkable_directions else 'unknown'
            feedback = f"\n⚠️ BLOCKED: '{last_action}' did NOT move you. DO NOT repeat '{last_action}'. Try one of: {walkable_str}"
        else:
            feedback = f"\n'{last_action}' moved: {last_position} -> {current_position}"

    sprites_text = ""
    if game_state:
        sprites = game_state.get("sprites", [])
        if sprites:
            lines = []
            for sp in sprites:
                lines.append(f"({sp.get('x','?')},{sp.get('y','?')}) {sp.get('name','?')}")
            sprites_text = "\n" + "\n".join(lines)

    starter_line = f"\nChosen starter: {chosen_starter}" if chosen_starter else ""

    # When GPS returns None, provide context about available warps so the LLM
    # can make an informed decision about which direction to go.
    if suggested_direction is None:
        if chosen_starter:
            suggest_text = "★★★ YOU ARE FACING YOUR TARGET! Press press_a NOW to interact! ★★★"
        else:
            # Show available warps to help the LLM decide
            warp_hint = ""
            if game_state:
                warps = game_state.get("warps", [])
                if warps:
                    warp_lines = []
                    for w in warps:
                        wx, wy = w.get("x", "?"), w.get("y", "?")
                        dest = w.get("dest_name", "?")
                        dest_map = w.get("dest_map", -1)
                        outdoor_keywords = ["route", "town", "city", "island", "plateau"]
                        is_outdoor = any(kw in dest.lower() for kw in outdoor_keywords)
                        is_doormat = dest_map == 255
                        if is_doormat:
                            tile_type = "doormat (exit to outside)"
                        elif is_outdoor:
                            tile_type = "map exit"
                        else:
                            tile_type = "building entrance"
                        warp_lines.append(f"  ({wx},{wy}) → {dest} ({tile_type})")
                    warp_hint = "\nAvailable warps/exits:\n" + "\n".join(warp_lines)
            suggest_text = (f"★★★ GPS has no specific target coordinate. "
                           f"Use the objective + collision grid to pick the best direction.{warp_hint} ★★★")
    else:
        suggest_text = f"GPS suggests: {suggested_direction} (hint only — verify against the map grid and objective)"

    # Add off-screen target info if GPS is guiding toward a warp that's not visible
    offscreen_text = ""
    if suggested_direction and game_state and suggested_direction.startswith("press_"):
        dir_map = {"press_up": (0,-1), "press_down": (0,1), "press_left": (-1,0), "press_right": (1,0)}
        ddx, ddy = dir_map.get(suggested_direction, (0,0))
        px = game_state.get("x", 0)
        py = game_state.get("y", 0)
        current_map_name = game_state.get("map_name", "")
        for w in game_state.get("warps", []):
            wx, wy = w.get("x", 0), w.get("y", 0)
            in_dir = False
            if ddx > 0 and wx > px: in_dir = True
            elif ddx < 0 and wx < px: in_dir = True
            elif ddy > 0 and wy > py: in_dir = True
            elif ddy < 0 and wy < py: in_dir = True
            if not in_dir:
                continue
            dist = abs(wx - px) + abs(wy - py)
            if dist > 5:
                dest = w.get("dest_name", "?")
                dest_map = w.get("dest_map", -1)
                # Classify the warp: building entrance vs map exit vs doormat
                outdoor_keywords = ["route", "town", "city", "island", "plateau"]
                is_outdoor = any(kw in dest.lower() for kw in outdoor_keywords)
                is_doormat = dest_map == 255
                if is_doormat:
                    tile_type = "doormat (exit)"
                elif is_outdoor:
                    tile_type = "map exit"
                else:
                    tile_type = "building entrance"
                # Only highlight as an exit if it leads to an outdoor map or is a doormat
                if is_outdoor or is_doormat:
                    offscreen_text = f"\n★ EXIT TILE ({tile_type}) at ({wx},{wy}) is {dist} tiles away — keep moving {suggested_direction.replace('press_','')}!"
                else:
                    offscreen_text = f"\n★ Warp to {dest} ({tile_type}) at ({wx},{wy}) is {dist} tiles away — keep moving {suggested_direction.replace('press_','')}!"
                break

    # Build failure memory warning — only show if the blocked direction is
    # still relevant (same map, and the direction is currently walkable but
    # was blocked before at this general area).
    failure_text = ""
    if failure_memory:
        # Show failures relevant to current map
        relevant = {k: v for k, v in failure_memory.items() if k.count(":") > 0}
        if relevant:
            top = sorted(relevant.items(), key=lambda x: -x[1])[:3]
            failure_text = "\n⚠️ Previously blocked: " + "; ".join(
                f"{k.split(':')[1]} (x{v})" for k, v in top
            )
            failure_text += "\nThese may be blocked by temporary obstacles or map changes. If the direction is walkable now, it may be worth trying again."

    # Build memory section for prompt injection
    memory_text = ""
    if memory_context:
        memory_text = f"\n## Memory (prior discoveries):\n{memory_context}"

    # Build visited-tile context — show the LLM which nearby tiles have
    # actually been visited (from persistent tracking), so it can avoid
    # oscillation and re-exploration of dead ends.
    visited_text = ""
    if player_pos and player_map and visited_tiles:
        px, py = player_pos
        # Show nearby visited tiles (within 5-tile radius)
        nearby_visited = []
        for dy in range(-5, 6):
            for dx in range(-5, 6):
                nx, ny = px + dx, py + dy
                if (nx, ny) == (px, py):
                    continue
                if (nx, ny) in visited_tiles:
                    nearby_visited.append(f"({nx},{ny})")
        if nearby_visited:
            visited_text = ("\n## Tiles you have already visited on this map:\n"
                           + ", ".join(nearby_visited[:15])
                           + "\nDo NOT revisit these tiles unless the objective requires it. "
                           + "Pick an UNVISITED direction to make progress.")

    # Build starter progress — guide the LLM to check balls via dialog.
    # Sprite labels no longer contain starter names (removed to force
    # generalization) — the LLM MUST read dialog to identify each ball.
    starter_progress = ""
    if chosen_starter:
        starter_progress = f"\n## ★ FINDING {chosen_starter.upper()} ★\n"
        starter_progress += f"You pre-committed to {chosen_starter}. "
        starter_progress += f"There are 3 Poke Balls on the table. Check them one by one.\n"
        starter_progress += f"The GPS guides you to a tile beside each ball, then tells you which way to face it.\n"
        starter_progress += f"At each ball: face it (GPS returns a direction), press A to interact, read the dialog.\n"
        starter_progress += f"The dialog will show a Pokedex entry, then ask \"Do you want [pokemon]?\"\n"
        starter_progress += f"If it asks \"Do you want {chosen_starter}?\" — press A (YES).\n"
        starter_progress += f"If it asks about a DIFFERENT pokemon — press B (NO) to decline.\n"
        starter_progress += f"CRITICAL: Dialog text is GROUND TRUST. Sprite labels are unreliable/wrong.\n"
        starter_progress += f"If you already checked a ball and recorded what's inside, DO NOT check it again.\n"

    # Build collision grid ASCII
    grid_text = ""
    if game_state:
        from pokemon_agent.agent.utils.state_parser import render_collision_grid
        grid_text = "\n\n## Collision Grid (your immediate surroundings)\n" + render_collision_grid(game_state)

    # Build recent history section
    history_text = ""
    if recent_history:
        lines = []
        for i, entry in enumerate(recent_history):
            action = entry.get("action", "?")
            reasoning = entry.get("reasoning", "")
            from_pos = entry.get("from_pos", "?")
            to_pos = entry.get("to_pos", "?")
            lines.append(f"  Turn -{len(recent_history)-i}: {action} | {from_pos} -> {to_pos}")
            if reasoning:
                # Truncate long reasoning to keep prompt compact
                short_reason = reasoning[:120].replace("\n", " ")
                lines.append(f"    Reasoning: {short_reason}")
        history_text = "\n## Recent turns:\n" + "\n".join(lines) + "\n"

    user_message = f"""{objective}{starter_line}

{feedback}{history_text}{failure_text}{memory_text}{visited_text}{starter_progress}
Position: ({curr_str}) facing {facing}
Walkable: {', '.join(walkable_directions) if walkable_directions else 'unknown'}
Suggest: {suggest_text}{offscreen_text}
Sprites:{sprites_text}{grid_text}
{hints_text}

One action: press_up/down/left/right, press_a, press_b, wait."""

    return NAVIGATION_SYSTEM, user_message


# ──────────────────────────────────────────────
# CRITIQUE AGENT
# ──────────────────────────────────────────────

CRITIQUE_SYSTEM = f"""You are the Critique Agent for objective verification in Pokémon Red.

ROLE: Determine whether the current objective has been completed by comparing the formal completion_conditions against the observed state_diff and the actions_taken.

CRITICAL: The objective is only complete if the state CHANGED to match the completion_conditions as a result of the actions taken. If the state already matched before the actions, the objective was already complete - but the Guide should have moved on. In this case, still PASS (the condition is satisfied) so the loop can advance.

However, if the state does NOT match the completion_conditions after the actions, output FAIL.

You understand battle outcomes, map transitions, flag changes, party updates, and the overall walkthrough milestones.

KNOWLEDGE BASE:
{CONTEXT_CRITIQUE}

OUTPUT FORMAT RULES (STRICT):
- Write 1-3 sentences of reasoning. Compare the completion_conditions to the observed state_after. Explicitly state whether each condition is met.
- The VERY LAST LINE must contain ONLY the word PASS or FAIL (uppercase).
- No other text on the last line.

Example correct output (PASS):
completion_conditions require map_name="Oak's Lab". State after actions shows map_name="Oak's Lab". Condition satisfied.
PASS

Example correct output (FAIL):
completion_conditions require map_name="Oak's Lab". State after actions shows map_name="Pallet Town". The player has not reached the required location.
FAIL"""

def build_critique_prompt(
    objective_description: str,
    completion_conditions: Dict[str, Any],
    state_diff: str,
    actions_taken: List[str],
    state_after: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Build (system, user) for the Critique agent."""
    conds_text = json.dumps(completion_conditions, indent=2) if completion_conditions else "{}"
    actions_text = ", ".join(actions_taken) if actions_taken else "none"
    after_text = ""
    if state_after:
        after_text = f"\n## State After Actions\n- Map: {state_after.get('map_name', '?')}\n- Position: ({state_after.get('x', '?')}, {state_after.get('y', '?')})\n- Party size: {len(state_after.get('party', []))}\n- Badges: {state_after.get('badge_count', 0)}\n- Dialog active: {state_after.get('dialog', {}).get('active', False)}\n- Scripted movement: {state_after.get('dialog', {}).get('scripted_movement', False)}\n- In battle: {state_after.get('battle', {}).get('in_battle', False)}\n"

    user_message = f"""## Objective Description
{objective_description}

## Completion Conditions
{conds_text}

## Observed State Diff (changes from before to after)
{state_diff}
{after_text}
## Actions Taken
{actions_text}

Was the objective achieved?
Compare EACH completion condition against the state after actions. All must be met for PASS.
Reason briefly, then output ONLY PASS or FAIL on the LAST LINE."""

    return CRITIQUE_SYSTEM, user_message


# ──────────────────────────────────────────────
# Helper functions (kept per requirements)
# ──────────────────────────────────────────────

def _format_state_summary(game_state: Dict[str, Any]) -> str:
    """Format game state into a concise summary string."""
    lines = []
    lines.append(f"- Map: {game_state.get('map_name', '?')} (id={game_state.get('map', {}).get('map_id', '?')})")
    lines.append(f"- Position: ({game_state.get('x', '?')}, {game_state.get('y', '?')})")
    lines.append(f"- Facing: {game_state.get('player', {}).get('facing', '?')}")
    lines.append(f"- Dialog active: {game_state.get('dialog', {}).get('active', False)}")
    lines.append(f"- Scripted movement: {game_state.get('dialog', {}).get('scripted_movement', False)}")
    lines.append(f"- In battle: {game_state.get('battle', {}).get('in_battle', False)}")
    lines.append(f"- Party size: {len(game_state.get('party', []))}")
    lines.append(f"- Badges: {game_state.get('badge_count', 0)}")
    flags = game_state.get("flags", {})
    true_flags = [k for k, v in flags.items() if v and isinstance(v, bool)]
    if true_flags:
        lines.append(f"- Flags set: {', '.join(true_flags)}")
    warps = game_state.get("warps", [])
    if warps:
        lines.append(f"- Warps: {warps}")
    return "\n".join(lines)


def _get_nested_value(state: Dict[str, Any], path: str) -> Any:
    """Get a value from nested dict using dot notation."""
    keys = path.split(".")
    current = state
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current
