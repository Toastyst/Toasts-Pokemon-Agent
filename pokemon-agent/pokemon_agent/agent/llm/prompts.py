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

GUIDE_SYSTEM = f"""You are the Guide Agent in an autonomous Pokémon Red player system.

ROLE: Given a game state summary, the list of available walkthrough steps with their start_conditions, already completed step IDs, and recent actions, select the SINGLE next step_id the player should pursue.

CRITICAL RULE: Only select a step if the current game state MATCHES its start_conditions. For example, if a step requires map_name="Red's House 2F" but the current map is "Pallet Town", do NOT select that step even if it's the first in the walkthrough order. Skip steps whose conditions are already satisfied (the game has moved past them).

If ALL remaining steps have start_conditions that don't match the current state, select the one that is furthest along in the walkthrough order whose conditions CAN still be satisfied, or the next logical step given current progress.

You are an expert on the exact early-game milestone order and starter selection mechanics.

KNOWLEDGE BASE:
{CONTEXT_GUIDE}

OUTPUT FORMAT RULES (STRICT):
- Write 1-4 sentences of reasoning. Explain WHY this step is correct given the current map, position, and progress. Explicitly reference start_conditions matching.
- The VERY LAST LINE of your entire response must contain ONLY the exact step_id (e.g. EXIT_REDS_HOUSE_2F).
- No JSON, no markdown, no quotes, no trailing text or periods after the step_id.
- The step_id must exactly match one of the available_steps provided.

Example correct output:
Current map is Pallet Town at (12,12), party is empty, no badges. EXIT_REDS_HOUSE_2F requires Red's House 2F so skip. EXIT_REDS_HOUSE_1F requires Red's House 1F so skip. WALK_TO_OAK_TRIGGER requires Pallet Town with empty party - this matches. Select it.
WALK_TO_OAK_TRIGGER"""

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
## Available Step Candidates (with start_conditions)
{avail_text}

## Recently Completed Step IDs
{completed_text}

## Recent Actions
{recent_text}

Which step_id should the agent work on next?
Check each step's start_conditions against the current game state. Skip steps whose conditions don't match.
Steps with empty start_conditions are always eligible — use the game state to pick the most relevant one.
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

MAP READING (use the grid below):
The collision grid shows your immediate surroundings. @ is you, . is walkable, # is a wall, S is a warp/stairs, I is an item/NPC.
Use the grid to plan your route. If the GPS suggestion conflicts with the objective, TRUST THE OBJECTIVE — the GPS may be outdated or wrong.
If your last action was blocked (didn't move), try a DIFFERENT direction that is walkable on the grid.

DOORMAT EXITS: If you are standing on a D (doormat) tile, press_down to exit. The server overrides collision for doormat exits — it's OK if the tile below shows #.

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
) -> Tuple[str, str]:
    """Build (system, user) for the Navigation agent.

    player_pos / player_map: current tile coordinates used to show visited
    tile context in the prompt (which tiles have been explored already).
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

    # When GPS returns None, the player is facing the target — press A now.
    # When GPS returns a direction, it's a HINT — the LLM should use the collision
    # grid to decide if that direction makes sense for the objective.
    if suggested_direction is None:
        if chosen_starter:
            suggest_text = "★★★ YOU ARE FACING YOUR TARGET! Press press_a NOW to interact! ★★★"
        else:
            suggest_text = "★★★ GPS has no specific target. Use the objective + collision grid to pick the best direction. ★★★"
    else:
        suggest_text = f"GPS suggests: {suggested_direction} (hint only — verify against the map grid and objective)"

    # Add off-screen target info if GPS is guiding toward a warp that's not visible
    offscreen_text = ""
    if suggested_direction and game_state and suggested_direction.startswith("press_"):
        # Check if there's a warp the GPS might be guiding toward that's off-screen
        dir_map = {"press_up": (0,-1), "press_down": (0,1), "press_left": (-1,0), "press_right": (1,0)}
        ddx, ddy = dir_map.get(suggested_direction, (0,0))
        px = game_state.get("x", 0)
        py = game_state.get("y", 0)
        # Look for warps in the suggested direction that are outside the viewport
        for w in game_state.get("warps", []):
            wx, wy = w.get("x", 0), w.get("y", 0)
            # Check if warp is in the suggested direction
            in_dir = False
            if ddx > 0 and wx > px:
                in_dir = True
            elif ddx < 0 and wx < px:
                in_dir = True
            elif ddy > 0 and wy > py:
                in_dir = True
            elif ddy < 0 and wy < py:
                in_dir = True
            if in_dir:
                dist = abs(wx - px) + abs(wy - py)
                if dist > 5:  # outside viewport range
                    dest = w.get("dest_name", "exit")
                    tile_type = "doormat" if w.get("dest_map") == 255 else "stairs/warp"
                    offscreen_text = f"\n★ EXIT TILE ({tile_type}) at ({wx},{wy}) is {dist} tiles away in the {suggested_direction.replace('press_','')} direction — keep moving that way!"
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

    # Build visited-tile context — show the LLM which nearby walkable tiles
    # it has already been to, so it can avoid re-exploring dead ends.
    visited_text = ""
    if player_pos and player_map and game_state:
        from pokemon_agent.agent.utils.state_parser import get_collision_grid
        grid = get_collision_grid(game_state)
        if grid:
            px, py = player_pos
            visited_nearby = []
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    nx, ny = px + dx, py + dy
                    if (nx, ny) == (px, py):
                        continue
                    gr, gc = 4 + dy, 5 + dx
                    if 0 <= gr < len(grid) and 0 <= gc < len(grid[0]):
                        if grid[gr][gc]:
                            visited_nearby.append(f"({nx},{ny})")
            if visited_nearby:
                visited_text = ("\n## Nearby explored tiles: "
                               + ", ".join(visited_nearby[:12])
                               + "\n(Gray = previously visited, prefer unvisited directions when exploring)")

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
