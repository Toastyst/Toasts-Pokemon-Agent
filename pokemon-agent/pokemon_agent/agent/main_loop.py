"""
Main loop — LLM-driven Observe → Guide → Navigate → Execute → Critique cycle.

Three LLM agents:
  GuideAgent:    Reads game state + walkthrough steps → picks next objective
  NavigationAgent: Reads objective + state → ONE action (walk/press_a/press_b/wait)
  CritiqueAgent:  Reads pre/post state + completion conditions → PASS/FAIL

Architecture: ONE action per LLM decision.
  1. Observe game state
  2. If dialog active: LLM decides press_a/press_b/press_start/wait (one at a time)
  3. If no dialog: LLM decides ONE navigation action (walk_up/down/left/right or press_a)
  4. Execute that single action
  5. Critique checks if objective is complete
  6. Repeat

The LLM is in FULL CONTROL of every button press. No batch execution.
No BFS path computation. The LLM sees the result of each action before
deciding the next one.

Objectives are treated as a strict sequential todo list from guide.json.
Once started, an objective is worked on until the Critique confirms completion (PASS).
The Guide is ONLY consulted when there is no active objective.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from pokemon_agent.agent.config import load_config, get_pokemon_agent_config
from pokemon_agent.agent.llm.client import LLMClient
from pokemon_agent.agent.llm.agents import GuideAgent, NavigationAgent, CritiqueAgent
from pokemon_agent.agent.executor import Executor
from pokemon_agent.agent.utils.state_parser import is_walkable as _is_walkable
from pokemon_agent.agent.utils.dashboard import push_objectives, push_event, push_token
from pokemon_agent.agent.memory.store import PokemonMemory, DialogFact, BattleLogEntry


class StandaloneAgent:
    def __init__(self, config_path: str = "config.yaml"):
        config = load_config(config_path)
        pa_config = get_pokemon_agent_config(config)
        planning_config = config.get("planning", {})

        self.base_url = pa_config.get("base_url", "http://localhost:8765")
        self.timeout = pa_config.get("timeout", 30)
        self.max_steps_per_objective = planning_config.get("max_steps_per_objective", 300)

        # LLM client (shared by all three agents)
        # Allow env var POKEMON_AGENT_PROVIDER to override config default_provider
        # (set by the game server when spawning the agent via /agent/start)
        provider = os.environ.get("POKEMON_AGENT_PROVIDER", config.get("default_provider", "local"))
        provider_cfg = config["providers"][provider]
        # Allow env var POKEMON_AGENT_MODEL to override the model name
        model_name = os.environ.get("POKEMON_AGENT_MODEL") or provider_cfg.get("model", "default")

        # Build provider registry for vision fallback routing
        # Each entry: provider_name → {base_url, api_key}
        vision_providers = {}
        for pname, pcfg in config.get("providers", {}).items():
            vision_providers[pname] = {
                "base_url": pcfg["base_url"],
                "api_key": pcfg.get("api_key", "not-needed"),
            }

        # Secondary API key for rate-limit failover
        fallback_key = os.environ.get("OPENROUTER_API_KEY2")
        if fallback_key:
            print(f"  [LLM] Fallback API key configured ({fallback_key[:10]}...)")

        self.llm = LLMClient(
            base_url=provider_cfg["base_url"],
            api_key=provider_cfg.get("api_key", "not-needed"),
            model=model_name,
            max_tokens=8192,
            timeout=120,
            vision_fallback_models=config.get("vision_fallback_models", []),
            providers=vision_providers,
            fallback_api_key=fallback_key,
        )

        # Three LLM agents
        self.guide_agent = GuideAgent(self.llm)
        self.nav_agent = NavigationAgent(self.llm)
        self.critique_agent = CritiqueAgent(self.llm)

        # Streaming token state — set before each agent call so the callback
        # knows which agent type is active.
        self._stream_agent_type = ""

        def _token_cb(chunk: str):
            """Forward a streaming token to the dashboard."""
            push_token(chunk, self._stream_agent_type, base_url=self.base_url)

        self.llm.set_token_callback(_token_cb)

        # Executor for real game interaction
        self.executor = Executor(base_url=self.base_url, timeout=self.timeout)

        # Load guide steps from guide.json
        self.guide_steps: List[Dict[str, Any]] = []
        self._load_guide()

        # Loop state
        self.step_count = 0
        self.running = False
        self.completed_ids: List[str] = []
        self.current_objective_id: Optional[str] = None
        self.current_objective: Optional[Dict[str, Any]] = None
        self.steps_on_current_objective = 0
        self.consecutive_no_progress = 0
        self.last_action: Optional[str] = None
        self.last_position: Optional[Tuple[int, int]] = None
        self.last_map: Optional[str] = None
        self.prev_map: Optional[str] = None
        self.current_position: Optional[Tuple[int, int]] = None
        self.objective_start_state: Optional[Dict[str, Any]] = None
        self.actions_on_objective: List[str] = []
        self.trajectory: List[Dict[str, Any]] = []
        self.recent_nav_history: List[Dict[str, Any]] = []  # rolling window of past nav turns

        # Short-term failure memory: maps (map_name, action) → failure count
        # Used to prevent repeating blocked actions in the same context
        self.failure_memory: Dict[str, int] = {}

        # Visited tiles per map: set of (x, y) for exploration awareness
        # Prevents the LLM from re-checking the same dead-end corridors
        self.visited_tiles: Dict[str, set] = {}  # map_name → {(x,y), ...}

        # Tile revisit counter: (map_name, x, y) → consecutive visit count
        # Used for two-tier loop detection (nudge at 3, firmer at 8)
        self.tile_visit_count: Dict[str, int] = {}

        # Track position 2 turns ago for ping-pong oscillation detection
        self.position_2_turns_ago: Optional[Tuple[int, int]] = None

        # Exit avoidance: set of doormat/warp positions we just exited through
        # Temporary — cleared when map changes or after N steps
        self.recent_exit_positions: List[Tuple[str, int, int]] = []  # (map_name, x, y)
        self.exit_avoidance_counter: int = 0  # steps since last exit
        self.last_move_direction: Optional[str] = None  # "up" | "down" | "left" | "right" | None

        # Planned path from A* — shown to LLM as a suggested route
        self.planned_path: List[str] = []  # e.g. ["walk_up", "walk_up", "walk_right"]

        # Long-term memory + RAG (persisted to disk)
        self.memory = PokemonMemory(persist_dir="memory")

        # Trajectory log path
        self.trajectory_path = Path("trajectory.jsonl")

        # Dashboard control state — polled each step so START/STOP/PAUSE buttons work
        self._control_state: str = "running"

    def _check_control_state(self) -> str:
        """Poll the game server /control endpoint. Returns 'running', 'paused', or 'stopped'."""
        try:
            r = requests.get(f"{self.base_url}/control", timeout=5)
            if r.ok:
                state = r.json().get("state", "running")
                self._control_state = state
                return state
        except Exception:
            pass
        return self._control_state

    def _load_guide(self):
        # Look for guide.json relative to the module location, not CWD
        module_dir = Path(__file__).parent.parent  # pokemon_agent/
        guide_path = module_dir / "guide" / "guide.json"
        if not guide_path.exists():
            # Fallback to CWD for backward compatibility
            guide_path = Path("guide.json")
        if guide_path.exists():
            with open(guide_path) as f:
                data = json.load(f)
            self.guide_steps = data.get("steps", [])
            print(f"[Agent] Loaded {self.guide_steps.__len__()} guide steps")
        else:
            print(f"[Agent] WARNING: guide.json not found")

    def observe(self) -> Optional[Dict[str, Any]]:
        """Fetch current game state from server."""
        state = self.executor.get_state()
        if state:
            self.current_position = (state.get("x", 0), state.get("y", 0))
        return state

    def _push_state(self, state_name: str):
        """Push a 'state' event so the dashboard can show what the agent is doing."""
        push_event("state", state_name, base_url=self.base_url)

    def _summarize_dialog(self, dialog_texts: list[str], map_name: str, npc_name: str = "unknown"):
        """Summarize a completed dialog into a clean log and store in memory.

        Args:
            dialog_texts: raw texts read from each dialog screen
            map_name: current map where dialog occurred
            npc_name: name of NPC (if known from sprites/state)
        """
        if not dialog_texts:
            return
        full_text = "\n".join(dialog_texts).strip()
        if len(full_text) < 10:
            return
        # Deduplicate: skip if we already stored this exact dialog
        if hasattr(self, '_last_dialog_hash'):
            import hashlib
            h = hashlib.md5(full_text.encode()).hexdigest()
            if h == self._last_dialog_hash:
                return
        system = """You are a dialog log cleaner for Pokemon Red.
Given raw text captured screen-by-screen from a game dialog, combine it into
a single clean dialog log. Remove duplicates and fragments. Fix obvious OCR
errors. Preserve conversation order. Output ONLY the cleaned dialog text."""
        user = f"Raw dialog text from {map_name} (NPC: {npc_name}):\n\n{full_text}"
        summary = self.llm.chat(
            system, user, temperature=0.1, max_tokens=1024, agent_type="dialog-summary"
        )
        if not summary:
            summary = full_text  # fallback to raw text
        summary = summary.strip()
        # Store hash to avoid re-summarizing same dialog
        import hashlib
        self._last_dialog_hash = hashlib.md5(full_text.encode()).hexdigest()
        # Store in memory
        self.memory.record_dialog_fact(
            DialogFact(
                npc_name=npc_name,
                map_name=map_name,
                fact=summary,
                category="dialog_log",
            )
        )
        return summary

    def _check_start_conditions(self, game_state: Dict[str, Any], step: Dict[str, Any]) -> bool:
        """Programmatically check if game state matches a step's start_conditions."""
        conditions = step.get("start_conditions", {})
        # Empty start_conditions = always eligible (LLM decides from context)
        if not conditions:
            return True
        return self._check_conditions(game_state, conditions)

    def _check_completion_conditions(self, game_state: Dict[str, Any], step: Dict[str, Any]) -> bool:
        """Programmatically check if game state matches a step's completion_conditions."""
        conditions = step.get("completion_conditions", {})
        if not conditions:
            return False
        return self._check_conditions(game_state, conditions)

    def _check_conditions(self, game_state: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        """Generic condition checker used by both start and completion checks."""
        for key, expected in conditions.items():
            if expected == "empty":
                val = self._get_nested(game_state, key)
                if val and len(val) > 0:
                    return False
            elif expected == "nonempty":
                val = self._get_nested(game_state, key)
                if not val or (isinstance(val, list) and len(val) == 0):
                    return False
            elif expected == "any":
                continue
            elif expected == "health=100%":
                # Special: check if all party members are at full HP
                party = game_state.get("party", [])
                if not party:
                    return False
                for p in party:
                    hp = p.get("hp", 0)
                    max_hp = p.get("max_hp", 0)
                    if max_hp > 0 and hp < max_hp:
                        return False
                continue
            elif isinstance(expected, bool):
                val = self._get_nested(game_state, key)
                if bool(val) != expected:
                    return False
            elif isinstance(expected, str):
                val = self._get_nested(game_state, key)
                if expected.startswith("!"):
                    # Negation: value must NOT match the suffix
                    if str(val) == expected[1:]:
                        return False
                else:
                    if str(val) != expected:
                        return False
            elif isinstance(expected, (int, float)):
                val = self._get_nested(game_state, key)
                if val is None or int(val) != int(expected):
                    return False
        return True

    def _detect_reentry(self, game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect if the agent re-entered a building from a completed objective.

        Only triggers when the map JUST CHANGED to a completed building — not
        when the agent is still there working on the next sequential objective.

        Returns a synthetic 'exit this building' objective if re-entry detected.
        """
        current_map = game_state.get("map_name", "")
        if not current_map:
            return None

        # Only trigger on map CHANGE — if we were already on this map at the
        # end of last turn, this is not a re-entry (we never left)
        if self.prev_map == current_map:
            return None

        # Known building maps (interior maps that you exit through doormats)
        building_indicators = ["1F", "2F", "3F", "4F", "5F", "B1F", "B2F",
                               "House", "Lab", "Mart", "Center", "Pokecenter",
                               "Gym", "Tower", "Mansion", "Hideout", "Co.",
                               "Dojo", "Museum", "Plant", "Lighthouse"]
        is_building = any(ind in current_map for ind in building_indicators)
        if not is_building:
            return None

        # If any uncompleted objective expects us to be on this map, don't flag re-entry
        # (the guide intentionally placed us here for the next step)
        for step in self.guide_steps:
            if step["id"] not in self.completed_ids:
                step_conditions = step.get("start_conditions", {})
                if step_conditions.get("map_name") == current_map:
                    return None  # We're supposed to be here

        # Check if we have a completed objective that was ON this map
        # If so, we somehow walked back in — generate exit objective
        for step in self.guide_steps:
            if step["id"] in self.completed_ids:
                step_conditions = step.get("start_conditions", {})
                if step_conditions.get("map_name") == current_map:
                    reentry_id = f"REEXIT_{step['id']}"
                    print(f"  [Guide] RE-ENTRY DETECTED: {current_map} (completed objective: {step['id']})")
                    return {
                        "id": reentry_id,
                        "description": f"Exit {current_map} — you already completed this objective!",
                        "category": "recovery",
                        "start_conditions": {},
                        "completion_conditions": {"map_name": "!{}".format(current_map)},
                        "hints": [
                            f"You already completed {step['id']} in {current_map}. Do NOT go back in!",
                            "Find the doormat/exit tile and leave this building.",
                            "Look for D tiles on the collision grid."
                        ],
                        "target_position": None,
                    }
        return None

    def guide(self, game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Call GuideAgent to determine the next objective.
        Only called when there is no active objective.
        Returns the guide step dict, or None if all done.
        """
        # 0. RE-ENTRY CHECK: detect if agent accidentally re-entered a completed building
        reentry_obj = self._detect_reentry(game_state)
        if reentry_obj:
            push_event("think", f"Re-entry detected in {game_state.get('map_name')} — exiting!", base_url=self.base_url)
            return reentry_obj

        candidates = [
            s for s in self.guide_steps
            if s["id"] not in self.completed_ids
        ]

        if not candidates:
            return None

        # Build memory context for Guide agent
        guide_memory = ""
        if hasattr(self, 'memory'):
            guide_memory = self.memory.build_guide_memory_prompt()

        # Filter candidates by start_conditions
        eligible = [
            s for s in candidates
            if self._check_start_conditions(game_state, s)
        ]

        # If no candidates match start_conditions, use all candidates
        # (the LLM will pick the right one from context)
        if not eligible:
            eligible = candidates

        result = self.guide_agent.act(
            game_state=game_state,
            guide_steps=eligible[:8],  # Limit to 8 to keep context small
            completed_ids=self.completed_ids,
            trajectory=self.trajectory,
            memory_context=guide_memory,
        )

        step_id = result.get("step_id")
        reasoning = result.get("reasoning", "")

        # Try LLM-selected step first (if it passes start_condition check)
        if step_id:
            for step in self.guide_steps:
                if step["id"] == step_id and step["id"] not in self.completed_ids:
                    if self._check_start_conditions(game_state, step):
                        print(f"  [Guide] Selected: {step_id} (start_conditions match)")
                        push_event("think", f"New objective: {step['description']}", base_url=self.base_url)
                        return step
                    else:
                        print(f"  [Guide] LLM selected {step_id} but start_conditions don't match — overriding")

        # Fallback: pick first eligible candidate whose start_conditions match
        for step in eligible:
            if self._check_start_conditions(game_state, step):
                print(f"  [Guide] Fallback (sequential): {step['id']} (start_conditions match)")
                push_event("think", f"New objective: {step['description']}", base_url=self.base_url)
                return step

        # Last resort: first candidate (shouldn't reach here)
        if candidates:
            print(f"  [Guide] WARNING: No candidates match start_conditions. Using first: {candidates[0]['id']}")
            return candidates[0]
        return None

    def _get_dest_map_for_action(self, game_state: Dict[str, Any], action: str) -> Optional[str]:
        """Check what map the agent would end up on after executing an action.
        Returns the destination map name if the action triggers a warp/door,
        or None if the action just walks on the current map.
        """
        px = game_state.get("x", 0)
        py = game_state.get("y", 0)
        dir_deltas = {
            "press_up": (0, -1), "walk_up": (0, -1),
            "press_down": (0, 1), "walk_down": (0, 1),
            "press_left": (-1, 0), "walk_left": (-1, 0),
            "press_right": (1, 0), "walk_right": (1, 0),
        }
        delta = dir_deltas.get(action)
        if not delta:
            return None
        nx, ny = px + delta[0], py + delta[1]
        # Check if the destination tile is a warp tile
        for w in game_state.get("warps", []):
            if w.get("x") == nx and w.get("y") == ny:
                return w.get("dest_name", "")
        return None

    def _compute_astar_path(self, game_state: Dict[str, Any],
                            target_position: Optional[Tuple[int, int]],
                            max_steps: int = 10,
                            suggested_direction: Optional[str] = None) -> List[str]:
        """Compute A* path from current position toward target.

        Uses the executor's BFS pathfinding which handles both on-grid
        and off-grid targets. Returns list of walk_* actions, empty if
        no target or no path found. Does NOT execute anything.
        """
        if target_position is None:
            # No explicit target — if GPS has a suggested direction, compute
            # a short path in that direction to give the LLM a starting route
            if suggested_direction and suggested_direction.startswith("press_"):
                dir_to_delta = {
                    "press_up": (0, -1), "press_down": (0, 1),
                    "press_left": (-1, 0), "press_right": (1, 0),
                }
                dx, dy = dir_to_delta.get(suggested_direction, (0, 0))
                if dx != 0 or dy != 0:
                    px, py = game_state.get("x", 0), game_state.get("y", 0)
                    # Walk up to max_steps in the suggested direction (or until blocked)
                    actions = []
                    cx, cy = px, py
                    for _ in range(max_steps):
                        nx, ny = cx + dx, cy + dy
                        if not _is_walkable(game_state, nx, ny):
                            break
                        if dx > 0:
                            actions.append("walk_right")
                        elif dx < 0:
                            actions.append("walk_left")
                        elif dy > 0:
                            actions.append("walk_down")
                        else:
                            actions.append("walk_up")
                        cx, cy = nx, ny
                    return actions
            return []
        current_x = game_state.get("x", 0)
        current_y = game_state.get("y", 0)
        tx, ty = target_position
        if current_x == tx and current_y == ty:
            return []
        try:
            path = self.executor.compute_path(tx, ty, game_state,
                                             max_steps=max_steps)
            return path
        except Exception as e:
            print(f"  [A*] Path computation failed: {e}")
            return []

    def _detect_oscillation(self) -> Optional[str]:
        """Detect ping-pong oscillation and return a nudge message.

        Two-tier system:
        - 3+ revisits to same tile → gentle nudge
        - 6+ revisits → firmer "stuck" notice
        - Ping-pong (pos A → B → A → B) → perpendicular suggestion
        """
        nudge = None
        cur = self.current_position
        old = self.last_position
        older = getattr(self, 'position_2_turns_ago', None)

        # Ping-pong detection: compares current pos with pos 2 turns ago
        # and last pos is a different tile (A→B→A pattern)
        if cur and older and cur == older and old and old != cur:
            nudge = ("⚠️ OSCILLATION DETECTED: You recently went "
                     f"{older} → {old} → {cur} (ping-pong). Try a "
                     f"DIFFERENT direction than {old} — you've already "
                     f"been between these two tiles.")

        # Tile revisit counting
        if cur:
            map_name = "current"  # simplified key
            tile_key = f"{map_name}:{cur[0]}:{cur[1]}"
            self.tile_visit_count[tile_key] = \
                self.tile_visit_count.get(tile_key, 0) + 1
            count = self.tile_visit_count[tile_key]

            if count >= 6:
                nudge = (f"⚠️ STUCK: You have visited tile {cur} {count} "
                         f"times. You are likely in a loop. Try a "
                         f"completely different direction.")
            elif count >= 3 and nudge is None:
                # Only gentle nudge if no ping-pong detected
                nudge = (f"⚠️ TILE REVISIT: You've been at {cur} {count} "
                         f"times. Consider trying a different direction "
                         f"than your recent actions.")

        return nudge

    def _get_exit_nudge(self, map_name: str) -> Optional[str]:
        """If we just exited a building, return a nudge to not walk back."""
        if not getattr(self, 'exit_avoidance_counter', 0):
            return None
        if self.exit_avoidance_counter > 10:
            # Clear after 10 steps — agent has moved well away
            self.recent_exit_positions.clear()
            self.exit_avoidance_counter = 0
            return None
        # Show the exit position(s) to avoid — larger radius (5 tiles)
        parts = []
        pos = getattr(self, 'current_position', None)
        if pos:
            px, py = pos
        else:
            px, py = -99, -99
        for mname2, ex, ey in self.recent_exit_positions:
            if mname2 == map_name:
                dist = abs(ex - px) + abs(ey - py)
                if dist <= 5:
                    parts.append(f"({ex},{ey})")
        if parts:
            # Calculate which direction leads back toward the exit
            avoid_dirs = []
            for mname2, ex, ey in self.recent_exit_positions:
                if mname2 != map_name:
                    continue
                dx = ex - px
                dy = ey - py
                if abs(dx) >= abs(dy):
                    avoid_dirs.append("press_left" if dx > 0 else "press_right")
                else:
                    avoid_dirs.append("press_up" if dy > 0 else "press_down")
            avoid_str = ", ".join(set(avoid_dirs))
            return ("🚪 EXIT COMMITMENT REQUIRED: You just exited through doormat/warp(s) at "
                    + ", ".join(parts)
                    + f". AVOID: {avoid_str}"
                    + " — you just came from there."
                    + " Pick a DIFFERENT direction and COMMIT to it for at least 5 steps."
                    + " Do NOT go back inside — keep exploring outside!")
        return None

    def _update_visited_tiles(self, map_name: str, pos: Tuple[int, int]):
        """Record that we've been on this tile in this map."""
        if map_name not in self.visited_tiles:
            self.visited_tiles[map_name] = set()
        self.visited_tiles[map_name].add(pos)

    def navigate(self, objective: str, hints: List[str], game_state: Dict[str, Any],
                 walkable_directions: Optional[list] = None, chosen_starter: str = "",
                 target_position: Optional[Tuple[int, int]] = None,
                 failure_memory: Optional[Dict[str, int]] = None,
                 memory_context: str = "") -> dict:
        """
        Call NavigationAgent to get ONE action.

        The LLM sees the game state and decides a single button press.
        Returns dict with keys: "action" (str), "reasoning" (str)

        Pre-call analysis adds:
        - A* planned route shown as a hint in the prompt
        - Tile visit tracking for loop detection
        - Ping-pong oscillation nudge
        - Building-exit awareness nudge
        - No-progress nudge (consecutive steps on same tile)
        """
        # Get a GPS suggestion for navigation (single direction toward target)
        chosen = getattr(self, '_chosen_starter', '') or ''
        # Build set of sprite positions already checked and rejected (from memory)
        # so the GPS doesn't guide back to a known wrong ball
        skip_positions = set()
        if chosen and hasattr(self, 'memory'):
            _map = game_state.get("map_name", "")
            _items = self.memory.get_known_items_on_map(_map, only_unobtained=True)
            print(f"  [GPS-debug] map={_map!r} chosen={chosen!r} items_on_map={len(_items)}")
            for item in _items:
                print(f"    item: ({item.x},{item.y}) type={item.item_type} name={item.item_name} notes={item.notes!r}")
                if item.item_type == "pokeball" and item.notes and ("NO" in item.notes or "Said NO" in item.notes):
                    skip_positions.add((item.x, item.y))
                    print(f"      → SKIP")
            print(f"  [GPS-debug] skip_positions={skip_positions}")
        # Build list of map names to avoid (maps we've already been to / completed)
        avoid_maps = []
        for s in self.guide_steps:
            if s["id"] in self.completed_ids:
                for cond_key, cond_val in s.get("start_conditions", {}).items():
                    if cond_key == "map_name" and isinstance(cond_val, str):
                        avoid_maps.append(cond_val)
        # Also avoid buildings we just exited (prevents walking back in)
        if hasattr(self, 'memory'):
            recently_exited = self.memory.get_recently_exited_buildings()
            for b in recently_exited:
                if b not in avoid_maps:
                    avoid_maps.append(b)
        # When the current objective is to EXIT a building, also avoid the
        # current map — this prevents GPS from guiding to stairs that go back
        # UP to a floor we already left (e.g. Red's House 1F stairs → 2F).
        if objective and "exit" in objective.lower():
            current_map = game_state.get("map_name", "")
            if current_map and current_map not in avoid_maps:
                avoid_maps.append(current_map)
        suggested_direction = self.executor.get_suggested_direction(
            game_state, chosen_starter=chosen, avoid_map_names=avoid_maps,
            target_position=target_position, skip_positions=skip_positions,
            direction_hint=objective,
            avoid_same_family=bool(objective and "exit" in objective.lower()))
        if not chosen:
            print(f"  [GPS-debug] map={game_state.get('map_name')!r} avoid={avoid_maps} suggested={suggested_direction}")

        # --- P0b: Compute A* path and store for prompt injection ---
        # If no target_position, pick an intermediate target in the direction
        # of the objective so A* has a goal to path toward.
        # Also: if direction_hint matches a known warp destination, set
        # target_position to the warp tile so A* paths directly to it.
        if target_position is None and game_state:
            _warp_target = self.executor.find_warp_for_objective(game_state, objective)
            if _warp_target:
                target_position = _warp_target
                print(f"  [A*] Warp target: {target_position} (from objective: {objective[:50]})")
            else:
                _intermediate = self.executor.pick_intermediate_target(
                    game_state, direction_hint=objective)
                if _intermediate:
                    target_position = _intermediate
                    print(f"  [A*] Auto-target: {target_position} (from objective: {objective[:50]})")
        self.planned_path = self._compute_astar_path(
            game_state, target_position, max_steps=8,
            suggested_direction=suggested_direction)
        if self.planned_path:
            print(f"  [A*] Planned route ({len(self.planned_path)} steps): "
                  f"{', '.join(self.planned_path[:5])}"
                  f"{'...' if len(self.planned_path) > 5 else ''}")
            # Validate A* first step: if it leads off the current map (into
            # a building, wrong warp), discard it and trust GPS instead.
            astar_first = self.planned_path[0]
            dest_map = self._get_dest_map_for_action(game_state, astar_first)
            current_map = game_state.get("map_name", "")
            if dest_map and dest_map != current_map:
                print(f"  [A*] REJECTED — first step leads to {dest_map}, not {current_map}. Trusting GPS: {suggested_direction}")
                self.planned_path = []
            else:
                # Override GPS with A* first step if path found
                suggested_direction = astar_first

        # --- P1: Detect oscillation and build nudge ---
        oscillation_nudge = self._detect_oscillation()

        # --- P2: No-progress detection ---
        no_progress_nudge = None
        if (self.current_position and self.last_position and
                self.current_position == self.last_position and
                not game_state.get("dialog", {}).get("active", False) and
                not game_state.get("dialog", {}).get("scripted_movement", False)):
            self.consecutive_no_progress += 1
            if self.consecutive_no_progress >= 4:
                no_progress_nudge = (
                    f"⚠️ NO PROGRESS for {self.consecutive_no_progress} steps. "
                    f"Position unchanged at {self.current_position}. "
                    f"Walkable: {', '.join(walkable_directions) if walkable_directions else 'unknown'}."
                )
        else:
            self.consecutive_no_progress = 0

        # --- P3: Exit awareness nudge ---
        exit_nudge = self._get_exit_nudge(game_state.get("map_name", ""))

        # --- Combine nudges into memory_context ---
        nudges = []
        if self.planned_path:
            path_str = " → ".join(self.planned_path[:5])
            if len(self.planned_path) > 5:
                path_str += f" ... ({len(self.planned_path)} total)"
            nudges.append(f"## Suggested Route (A* path to target):\n{path_str}")
        if oscillation_nudge:
            nudges.append(oscillation_nudge)
        if no_progress_nudge:
            nudges.append(no_progress_nudge)
        if exit_nudge:
            nudges.append(exit_nudge)
        if nudges:
            memory_context = (memory_context or "") + "\n\n" + "\n\n".join(nudges)

        # --- Track visited tiles (P2) ---
        map_name = game_state.get("map_name", "")
        pos = self.current_position
        if pos and map_name:
            self._update_visited_tiles(map_name, pos)

        # --- Viewer steering input (Twitch chat redemptions) ---
        from pokemon_agent.agent.llm.steering import get_steering_inputs
        pending_steering = get_steering_inputs()
        viewer_input = None
        if pending_steering:
            # Combine all pending inputs into one prompt section
            parts = []
            for s in pending_steering:
                parts.append(f"- {s['username']}: {s['message']}")
            viewer_input = "\n".join(parts)
            print(f"  [Steering] {len(pending_steering)} viewer command(s): {viewer_input[:100]}")

        result = self.nav_agent.act(
            objective=objective,
            hints=hints,
            game_state=game_state,
            suggested_direction=suggested_direction,
            last_action=self.last_action,
            last_position=self.last_position,
            current_position=self.current_position,
            walkable_directions=walkable_directions,
            chosen_starter=chosen_starter,
            failure_memory=self.failure_memory,
            memory_context=memory_context,
            recent_history=self.recent_nav_history[-4:],
            player_pos=pos,
            player_map=map_name,
            viewer_input=viewer_input,
        )

        action = result.get("action", "wait")
        reasoning = result.get("reasoning", "")

        print(f"  [Nav] Action: {action} | {reasoning}")
        push_event("decision", f"{action}\n{reasoning}", base_url=self.base_url)

        # Store this turn's nav decision for future context
        self.recent_nav_history.append({
            "action": action,
            "reasoning": reasoning,
            "from_pos": self.last_position,
            "to_pos": self.current_position,
        })
        if len(self.recent_nav_history) > 5:
            self.recent_nav_history.pop(0)

        # --- Update position_2_turns_ago for ping-pong detection ---
        self.position_2_turns_ago = self.last_position

        return result

    def execute_action(self, action: str) -> Optional[Dict[str, Any]]:
        """Send a single action to the server and return new state."""
        self.last_position = self.current_position
        self.last_action = action
        # Track last movement direction for anti-oscillation
        dir_map = {
            "press_up": "up", "press_down": "down",
            "press_left": "left", "press_right": "right",
        }
        self.last_move_direction = dir_map.get(action)
        new_state = self.executor.step(action)
        if new_state:
            self.current_position = (new_state.get("x", 0), new_state.get("y", 0))
        return new_state

    def critique(
        self,
        objective_description: str,
        completion_conditions: Dict[str, Any],
        state_before: Dict[str, Any],
        state_after: Dict[str, Any],
        actions_taken: List[str],
    ) -> Tuple[bool, str]:
        """
        Call CritiqueAgent to verify objective completion.
        Returns (success, reason).
        """
        result = self.critique_agent.act(
            objective_description=objective_description,
            completion_conditions=completion_conditions,
            state_before=state_before,
            state_after=state_after,
            actions_taken=actions_taken,
        )
        success = result.get("success", False)
        reason = result.get("reason", "")
        return success, reason

    def log_trajectory(
        self,
        objective_id: str,
        objective_desc: str,
        action: str,
        state_before: Dict[str, Any],
        state_after: Dict[str, Any],
        success: bool,
        critique_reason: str,
    ):
        """Log a trajectory entry."""
        entry = {
            "step": self.step_count,
            "timestamp": datetime.utcnow().isoformat(),
            "objective_id": objective_id,
            "objective_description": objective_desc,
            "action": action,
            "success": success,
            "critique": critique_reason[:500],
            "map": state_after.get("map_name", "?"),
            "position": (state_after.get("x"), state_after.get("y")),
        }

        self.trajectory.append(entry)
        if len(self.trajectory) > 100:
            self.trajectory = self.trajectory[-100:]

        with open(self.trajectory_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def run(self, max_steps: int = 1000):
        """
        Main observe → guide → navigate → execute → critique loop.

        ONE action per step. The LLM decides every button press.
        """
        self.running = True
        print("=" * 60)
        print("  LLM-Driven Pokemon Red Agent — Starting")
        print(f"  Model: {self.llm.model} @ {self.base_url}")
        print(f"  Guide steps: {len(self.guide_steps)}")
        print(f"  Max steps per objective: {self.max_steps_per_objective}")
        print("  Architecture: ONE action per LLM decision")
        print("=" * 60)

        # Push initial objectives to dashboard so they're visible from the start
        if self.guide_steps:
            initial_objectives = [
                {"tier": "primary" if i == 0 else "secondary", "text": s["description"], "done": False}
                for i, s in enumerate(self.guide_steps[:8])
            ]
            push_objectives(initial_objectives, base_url=self.base_url)
            push_event("key_moment", f"Run started — {len(self.guide_steps)} objectives loaded", base_url=self.base_url)

        for step in range(max_steps):
            if not self.running:
                break

            self.step_count += 1
            print(f"\n--- Step {self.step_count} ---")

            # 0. CHECK DASHBOARD CONTROL — poll /control for pause/stop
            ctrl = self._check_control_state()
            if ctrl == "stopped":
                print("[Control] Stopped by dashboard — exiting")
                push_event("key_moment", "Agent stopped by dashboard", base_url=self.base_url)
                self.running = False
                break
            if ctrl == "paused":
                print("[Control] Paused by dashboard — waiting for resume...")
                self._push_state("paused")
                push_event("key_moment", "Agent paused", base_url=self.base_url)
                while True:
                    time.sleep(2)
                    ctrl = self._check_control_state()
                    if ctrl != "paused":
                        break
                print(f"[Control] Resumed (state={ctrl})")
                push_event("key_moment", "Agent resumed", base_url=self.base_url)

            # 1. OBSERVE
            self._push_state("observe")
            state = self.observe()
            if not state:
                print("[!] No state from server. Stopping.")
                break

            # Re-entry detection needs to know what map we were on BEFORE this
            # turn's observe. Shift: prev_map = last_map (from end of previous
            # turn), then update last_map to current for next turn.
            current_map_name = state.get("map_name", "")
            self.prev_map = self.last_map  # map at end of last turn
            self.last_map = current_map_name  # map at start of this turn

            print(f"  Map: {state.get('map_name', '?')} | "
                  f"Pos: ({state.get('x', '?')}, {state.get('y', '?')}) | "
                  f"Party: {len(state.get('party', []))} | "
                  f"Badges: {state.get('badge_count', 0)}")

            # 1c. HANDLE BATTLE
            if state.get("battle", {}).get("in_battle", False):
                battle_steps = 0
                enemy = state.get("battle", {}).get("enemy", {})
                trainer_name = state.get("battle", {}).get("trainer_name", enemy.get("species", "Wild"))
                battle_type = state.get("battle", {}).get("type", "wild")
                print(f"  [Battle] In battle vs {trainer_name} — entering battle loop")
                self._push_state("battle")
                push_event("think", "Battle started!", base_url=self.base_url)

                # Notify memory that battle started
                if hasattr(self, 'memory'):
                    self.memory.start_battle(trainer_name, battle_type)

                while state and state.get("battle", {}).get("in_battle", False):
                    battle = state.get("battle", {})

                    # Advance any initial battle text (trainer send-out, etc.)
                    # before asking the LLM for a decision.
                    self.executor.step("press_b")
                    self.executor.step("press_b")

                    # Build knowledge-augmented prompt using BattleAgent
                    from pokemon_agent.agent.llm.battle_agent import build_battle_prompt, parse_battle_action, safety_net_override
                    system, user = build_battle_prompt(state, self.memory if hasattr(self, 'memory') else None, [])

                    self._stream_agent_type = "battle"
                    response = self.llm.chat(system, user, temperature=0.1)
                    self._stream_agent_type = ""
                    action = parse_battle_action(response) if response else "fight_move1"

                    # Scripted safety net override
                    if hasattr(self, 'memory'):
                        action = safety_net_override(action, state, self.memory)

                    # Block "run" for trainer battles — running is not possible
                    # from trainer battles in Pokemon Red. Force fight_move1.
                    if action == "run" and battle.get("type") == "trainer":
                        print(f"  [Battle] Run blocked — cannot escape trainer battle. Forcing fight_move1.")
                        action = "fight_move1"

                    print(f"  [Battle] LLM chose: {action}")

                    # Execute the battle action sequence
                    if action == "run":
                        self.executor.step("press_a")      # open menu
                        self.executor.step("press_down")   # cursor to RUN
                        self.executor.step("press_right")  # cursor to RUN
                        self.executor.step("press_a")      # select RUN
                        self.executor.step("press_b")      # advance result text
                        self.executor.step("press_b")
                        self.executor.step("press_b")
                        self.executor.step("press_b")
                    elif action.startswith("switch_"):
                        # Switch: B to cancel menu, then POKEMON → select slot
                        slot = int(action.split("_")[1]) if "_" in action else 2
                        self.executor.step("press_a")      # open menu
                        self.executor.step("press_down")   # cursor to POKEMON
                        self.executor.step("press_a")      # select POKEMON
                        for _ in range(slot - 1):
                            self.executor.step("press_down")  # move to slot
                        self.executor.step("press_a")      # confirm switch
                        self.executor.step("press_b")      # advance result text
                        self.executor.step("press_b")
                        self.executor.step("press_b")
                        self.executor.step("press_b")
                    elif action == "item":
                        self.executor.step("press_a")      # open menu
                        self.executor.step("press_down")
                        self.executor.step("press_down")   # cursor to ITEM
                        self.executor.step("press_a")      # open items
                        self.executor.step("press_a")      # select Potion
                        self.executor.step("press_a")      # use on active Pokemon
                        self.executor.step("press_b")      # advance result text
                        self.executor.step("press_b")
                        self.executor.step("press_b")
                        self.executor.step("press_b")
                    else:
                        # FIGHT + move selection
                        move_idx = {"fight_move1": 0, "fight_move2": 1, "fight_move3": 2, "fight_move4": 3}.get(action, 0)
                        self.executor.step("press_a")      # open menu (FIGHT default)
                        self.executor.step("press_a")      # select FIGHT
                        for _ in range(move_idx):
                            self.executor.step("press_down")  # move cursor to desired move
                        self.executor.step("press_a")      # confirm move
                        # Advance battle text after the move executes
                        for _ in range(4):
                            self.executor.step("press_b")

                    state = self.observe()
                    battle_steps += 1

                    # Record turn in memory
                    if hasattr(self, 'memory') and state:
                        new_enemy = state.get("battle", {}).get("enemy", {})
                        new_party = state.get("party", [])
                        my_mon_new = new_party[0] if new_party else {}
                        obs = f"{action} used. Enemy HP {new_enemy.get('hp','?')}/{new_enemy.get('max_hp','?')}, My HP {my_mon_new.get('hp','?')}/{my_mon_new.get('max_hp','?')}"
                        self.memory.record_battle_turn(
                            turn=battle_steps,
                            action=action,
                            result_summary=obs,
                            enemy_hp=new_enemy.get("hp"),
                            my_hp=my_mon_new.get("hp"),
                        )

                    if battle_steps > 30:
                        print("  [Battle] WARNING: battle stuck after 30 turns, breaking")
                        break

                # Battle ended
                outcome = "win" if state and state.get("party") and any(m.get("hp", 0) > 0 for m in state.get("party", [])) else "lose"
                print(f"  [Battle] Ended after {battle_steps} turns — {outcome}")
                push_event("think", f"Battle over ({battle_steps} turns) — {outcome}", base_url=self.base_url)

                if hasattr(self, 'memory') and state:
                    # Build opponent pokemon list from battle state
                    enemy_data = state.get("battle", {}).get("enemy", {})
                    opponent_pokemon = []
                    if enemy_data:
                        opponent_pokemon.append({
                            "species": enemy_data.get("species", "unknown"),
                            "level": enemy_data.get("level"),
                            "moves": [m.get("name", "?") for m in enemy_data.get("moves", [])],
                        })
                    # Also include party data for what we used
                    party_data = state.get("party", [])
                    player_used = [p.get("species", "?") for p in party_data] if party_data else []
                    self.memory.record_battle(
                        battle_log=BattleLogEntry(
                            opponent_trainer=trainer_name,
                            opponent_pokemon=opponent_pokemon,
                            player_pokemon_used=player_used,
                            outcome=outcome,
                            key_events=[e.get("summary", "") for e in self.memory.battle_turn_history[-5:]],
                        )
                    )
                    self.memory.end_battle(outcome, trainer_name)

            # 1d. HANDLE DIALOG — Vision-based dialog reading (one action at a time)
            if state and state.get("dialog", {}).get("active", False):
                dialog_steps = 0
                self._last_dialog_texts = []  # collect dialog texts for memory
                print("  [Dialog] Dialog active — entering vision-based dialog loop")
                self._push_state("dialog")
                push_event("think", "Dialog active — reading with vision", base_url=self.base_url)

                while state and state.get("dialog", {}).get("active", False):
                    # If a battle started while we were in dialog (e.g., rival
                    # challenge dialog → battle), exit immediately so the battle
                    # handler can take over on the next main-loop iteration.
                    if state.get("battle", {}).get("in_battle", False):
                        print("  [Dialog] Battle started during dialog — exiting dialog loop")
                        break

                    # Screenshot → vision model → dialog text
                    screenshot_b64 = self.executor.get_screenshot_b64()
                    dialog_text = ""
                    if screenshot_b64:
                        self._stream_agent_type = "dialog-vision"
                        dialog_text = self.llm.chat_vision(
                            image_b64=screenshot_b64,
                            text_prompt="Read the dialog text on the Pokemon Red game screen. Output ONLY the exact text shown in the dialog box. If there is no visible dialog text, output 'NO_TEXT'.",
                        ) or ""
                        self._stream_agent_type = ""
                        # Only collect non-empty, non-error results
                        if dialog_text and dialog_text.strip() and dialog_text.strip() != "NO_TEXT":
                            self._last_dialog_texts.append(dialog_text)
                            print(f"  [Dialog] Screen says: {dialog_text[:120]}")
                        else:
                            print(f"  [Dialog] Vision returned empty/NO_TEXT — skipping collection")
                    else:
                        print("  [Dialog] Screenshot failed, defaulting to press_b")

                    # If vision failed repeatedly, wait and retry once before asking LLM
                    if not dialog_text or not dialog_text.strip() or dialog_text.strip() == "NO_TEXT":
                        # Wait for dialog to fully render, then retry screenshot + vision
                        print("  [Dialog] Vision empty — waiting 60 frames and retrying...")
                        self.executor.step("wait_60")
                        screenshot_b64 = self.executor.get_screenshot_b64()
                        if screenshot_b64:
                            self._stream_agent_type = "dialog-vision"
                            dialog_text = self.llm.chat_vision(
                                image_b64=screenshot_b64,
                                text_prompt="Read the dialog text on the Pokemon Red game screen. Output ONLY the exact text shown in the dialog box.",
                            ) or ""
                            self._stream_agent_type = ""
                            if dialog_text and dialog_text.strip() and dialog_text.strip() != "NO_TEXT":
                                self._last_dialog_texts.append(dialog_text)
                                print(f"  [Dialog] Retry says: {dialog_text[:120]}")
                            else:
                                print("  [Dialog] Retry also empty — will use state-based fallback")
                        # If still empty, use a state-based guess
                        if not dialog_text or not dialog_text.strip() or dialog_text.strip() == "NO_TEXT":
                            dialog_text = "[Vision failed — dialog is active but text could not be read. Use game state to infer context.]"
                            print("  [Dialog] Using state-based fallback for dialog decision")

                    # Let the LLM decide the action based on dialog + state + objective
                    obj_desc = ""
                    if self.current_objective:
                        obj_desc = self.current_objective.get("description", "")
                    chosen = getattr(self, '_chosen_starter', '') or ''
                    self._stream_agent_type = "dialog"
                    action = self.nav_agent.decide_dialog_action(
                        dialog_text=dialog_text,
                        objective=obj_desc,
                        game_state=state,
                        chosen_starter=chosen,
                    )
                    self._stream_agent_type = ""
                    print(f"  [Dialog] LLM chose: {action}")
                    push_event("think", f"Dialog: {dialog_text[:80]} → {action}", base_url=self.base_url)
                    self._last_dialog_action = action  # track for memory recording

                    # Execute the single action
                    if action == "wait":
                        self.executor.step("wait_60")
                    elif action == "press_a":
                        self.executor.step("press_a")
                    elif action == "press_start":
                        self.executor.step("press_start")
                    elif action == "press_b":
                        self.executor.step("press_b")
                    else:
                        self.executor.step("press_b")  # safety fallback

                    state = self.observe()
                    dialog_steps += 1
                    if dialog_steps > 50:
                        print("  [Dialog] WARNING: dialog stuck after 50 steps, breaking")
                        break

                # --- Summarize full dialog into clean log ---
                summary_text = None
                if hasattr(self, '_last_dialog_texts') and self._last_dialog_texts and state:
                    # Try to identify NPC name from nearby sprites
                    npc_name = "unknown"
                    for sp in state.get("sprites", []):
                        if sp.get("type") == "npc":
                            npc_name = sp.get("name", "npc")
                            break
                    summary_text = self._summarize_dialog(
                        self._last_dialog_texts,
                        map_name=state.get("map_name", "?"),
                        npc_name=npc_name,
                    )

                done_msg = f"Dialog done ({dialog_steps} steps)"
                if summary_text:
                    done_msg += f"\n\n{summary_text}"
                print(f"  [Dialog] {done_msg}")
                push_event("think", done_msg, base_url=self.base_url)

                # --- Record dialog discoveries in memory ---
                # Handle both when CHOOSE_STARTER is active AND when a starter dialog
                # appears before the objective is set (e.g., auto-dialog on map entry)
                is_choose_starter = (self.current_objective and self.current_objective.get("id") == "CHOOSE_STARTER")
                if is_choose_starter and state and hasattr(self, '_last_dialog_texts') and self._last_dialog_texts:
                    full_dialog = " ".join(self._last_dialog_texts)
                    was_starter_offer = "do you want" in full_dialog.lower() or "pokémon, " in full_dialog.lower()

                    if was_starter_offer:
                        # Check if party gained a Pokemon — that's the ground truth
                        # for whether YES was pressed on the starter offer
                        _party = state.get("party", [])
                        _prev_party_size = getattr(self, '_prev_party_size', 0)
                        said_yes = len(_party) > _prev_party_size
                        self._prev_party_size = len(_party)
                        last_dialog_action = getattr(self, '_last_dialog_action', 'press_b')
                        print(f"  [Memory] Starter dialog: said {'YES' if said_yes else 'NO'} (party: {_prev_party_size}→{len(_party)})")
                        # Memory recording for starter selection
                        if not said_yes:
                            # Said NO — record what we found using DIALOG content (ground truth)
                            # and SPRITE position (not player position)
                            px = state.get("x", 0)
                            py = state.get("y", 0)
                            current_map = state.get("map_name", "?")
                            # Find nearest sprite to get the BALL POSITION
                            nearest_sprite = None
                            nearest_dist = 999
                            for sp in state.get("sprites", []):
                                if sp.get("type") == "item":
                                    d = abs(sp.get("x", 0) - px) + abs(sp.get("y", 0) - py)
                                    if d < nearest_dist:
                                        nearest_dist = d
                                        nearest_sprite = sp
                            # Determine what's in the ball from DIALOG (ground truth)
                            # The dialog shows the Pokedex entry with the Pokemon name
                            dialog_lower = full_dialog.lower()
                            ball_content = None
                            for name in ["bulbasaur", "charmander", "squirtle"]:
                                if name in dialog_lower:
                                    ball_content = name.capitalize()
                                    break
                            if ball_content and nearest_sprite:
                                sp_x = nearest_sprite.get("x", px)
                                sp_y = nearest_sprite.get("y", py)
                                sprite_label = nearest_sprite.get("name", "unknown")
                                chosen = getattr(self, '_chosen_starter', '')
                                notes = f"Said NO (wanted {chosen})"
                                if ball_content.lower() not in sprite_label.lower():
                                    notes += f" — sprite label said '{sprite_label}' but dialog showed '{ball_content}'"
                                self.memory.record_item_discovery(
                                    map_name=current_map, x=sp_x, y=sp_y,
                                    item_name=f"Pokeball ({ball_content})",
                                    item_type="pokeball",
                                    confidence=1.0,
                                    source="observation",
                                    notes=notes,
                                )
                                print(f"  [Memory] Recorded: Pokeball ({ball_content}) at ({sp_x},{sp_y}) — said NO (dialog ground truth)")
                            elif nearest_sprite:
                                # Could not determine content from dialog, fall back to sprite label (low confidence)
                                sp_x = nearest_sprite.get("x", px)
                                sp_y = nearest_sprite.get("y", py)
                                sprite_label = nearest_sprite.get("name", "unknown ball")
                                chosen = getattr(self, '_chosen_starter', '')
                                self.memory.record_item_discovery(
                                    map_name=current_map, x=sp_x, y=sp_y,
                                    item_name=sprite_label,
                                    item_type="pokeball",
                                    confidence=0.5,
                                    source="sprite_label",
                                    notes=f"Said NO (wanted {chosen}) — content from sprite label only, dialog unclear",
                                )
                                print(f"  [Memory] Recorded (low confidence): {sprite_label} at ({sp_x},{sp_y}) — said NO")

                # Clear dialog texts for next time
                self._last_dialog_texts = []
                self._last_dialog_action = None

            # If state became None during dialog handling, re-observe
            if state is None:
                state = self.observe()
            if not state:
                print("[!] No state from server. Stopping.")
                break

            # 1d. WAIT FOR SCRIPTED MOVEMENT
            if state and state.get("dialog", {}).get("scripted_movement", False):
                start_script_pos = (state.get("x"), state.get("y"))
                print(f"  [Script] Scripted movement active at {start_script_pos} — ticking until done...")
                self._push_state("scripted")
                push_event("think", "Scripted movement — waiting", base_url=self.base_url)
                script_wait = 0
                max_script_wait = 20
                while state and state.get("dialog", {}).get("scripted_movement", False):
                    self.executor.step("wait_60")
                    time.sleep(0.5)
                    state = self.observe()
                    if not state:
                        break
                    script_wait += 1
                    cur_pos = (state.get("x"), state.get("y"))
                    if cur_pos != start_script_pos:
                        start_script_pos = cur_pos
                        script_wait = 0
                    if script_wait >= max_script_wait:
                        print(f"  [Script] No player movement in {max_script_wait} ticks, breaking")
                        break
                if state:
                    print(f"  [Script] Ended after {script_wait} ticks. Map: {state.get('map_name')} Pos: ({state.get('x')},{state.get('y')})")
                    push_event("think", f"Scripted movement done ({script_wait} ticks)", base_url=self.base_url)

            # Re-observe if state was lost during scripted movement
            if state is None:
                state = self.observe()
            if not state:
                print("[!] No state from server. Stopping.")
                break

            # 2. GUIDE — only when no active objective
            if self.current_objective is None:
                self._push_state("guide")
                self._stream_agent_type = "guide"
                guide_step = self.guide(state)
                self._stream_agent_type = ""
                if guide_step is None:
                    print("[✓] No more objectives. Done!")
                    push_event("key_moment", "All objectives complete!", base_url=self.base_url)
                    break

                self.current_objective_id = guide_step["id"]
                self.current_objective = guide_step
                self.steps_on_current_objective = 0
                self.consecutive_no_progress = 0
                self.actions_on_objective = []
                self.objective_start_state = state
                self.tile_visit_count.clear()  # fresh tile tracking per objective
                # For CHOOSE_STARTER: pre-commit to a starter
                if guide_step["id"] == "CHOOSE_STARTER":
                    self._chosen_starter = self._pick_starter()
                    print(f"  ★ CHOSEN STARTER: {self._chosen_starter}")
                    push_event("key_moment", f"Chose {self._chosen_starter}! Find it on the table.", base_url=self.base_url)
                else:
                    # Clear starter commitment so GPS doesn't stay in starter mode
                    if hasattr(self, '_chosen_starter'):
                        del self._chosen_starter
                print(f"  ★ New objective: {guide_step['description']}")

            obj = self.current_objective
            hints = obj.get("hints", [])
            completion_conditions = obj.get("completion_conditions", {})

            # 3. NAVIGATE — LLM picks ONE action
            walkable_dirs = self.executor.get_walkable(state)
            chosen = getattr(self, '_chosen_starter', '') or ''
            # Extract target_position from current objective step (e.g. WALK_TO_OAK_TRIGGER)
            target_pos = None
            tp = obj.get("target_position")
            if tp and isinstance(tp, (list, tuple)) and len(tp) == 2:
                target_pos = (int(tp[0]), int(tp[1]))
            # For CHOOSE_STARTER: pre-commit to a starter and use GPS to find it
            if obj.get("id") == "CHOOSE_STARTER" and chosen:
                # Don't set target_position — let the chosen_starter GPS path
                # find the matching sprite by name and guide the agent there
                print(f"  [Starter] Looking for {chosen}: GPS will guide to the matching Poke Ball")
            # Build memory context for nav prompt
            memory_context = ""
            if hasattr(self, 'memory') and state:
                memory_context = self.memory.build_navigation_memory_prompt(
                    state.get("map_name", "?")
                )
                # Add building exit warning
                recently_exited = self.memory.get_recently_exited_buildings()
                if recently_exited:
                    buildings = ", ".join(recently_exited)
                    memory_context += f"\n\n⚠️ RECENTLY EXITED: {buildings} — do NOT walk back inside! Move away from these buildings."
                # Add pokeball-specific memory with provenance
                items = self.memory.get_known_items_on_map(state.get("map_name", "?"))
                pokeball_items = [i for i in items if i.item_type == "pokeball" and i.superseded_by is None]
                if pokeball_items:
                    # Build a "checked balls" map
                    checked_lines = []
                    for i in sorted(pokeball_items, key=lambda x: (x.y, x.x)):
                        source_tag = "✓" if i.source == "observation" else "?"
                        checked_lines.append(f"  ({i.x},{i.y}): {i.item_name} [{source_tag} {i.source}]")
                    memory_context += "\n\n## Checked Poke Balls (DO NOT re-check these):\n" + "\n".join(checked_lines)
                    memory_context += "\n\nRULE: If you have already checked a ball and recorded what's inside, DO NOT check it again. Navigate to an unchecked ball."

            # 3. NAVIGATE — LLM picks ONE action
            self._push_state("navigate")
            self._stream_agent_type = "nav"
            nav_result = self.navigate(obj["description"], hints, state,
                                       walkable_directions=walkable_dirs,
                                       chosen_starter=chosen,
                                       target_position=target_pos,
                                       memory_context=memory_context)
            self._stream_agent_type = ""
            action = nav_result.get("action", "wait")

            # 4. EXECUTE — single action
            new_state = self.execute_action(action)
            self.actions_on_objective.append(action)
            self.steps_on_current_objective += 1

            if new_state:
                print(f"  [Exec] {action} → ({new_state.get('x')},{new_state.get('y')}) map={new_state.get('map_name','?')}")
            else:
                print(f"  [Exec] {action} → no state returned")
                new_state = state

            # 5. CRITIQUE — check if objective is complete
            self._push_state("critique")
            self._stream_agent_type = "critique"
            success, critique_reason = self.critique(
                objective_description=obj["description"],
                completion_conditions=completion_conditions,
                state_before=self.objective_start_state or state,
                state_after=new_state,
                actions_taken=self.actions_on_objective,
            )
            self._stream_agent_type = ""

            # Short console print
            if success:
                print(f"  [Critique]: ✓ PASS")
            else:
                # Extract just the key failure reason (first line, trimmed)
                fail_reason = critique_reason.split("\n")[0].strip()
                if not fail_reason:
                    fail_reason = "required state not true"
                print(f"  [Critique]: ✗ FAIL — {fail_reason}")

            push_event("critique", f"{'PASS' if success else 'FAIL'} — {critique_reason}", base_url=self.base_url)

            # 6. LOG
            self.log_trajectory(
                obj["id"], obj["description"], action,
                self.objective_start_state or state, new_state, success, critique_reason,
            )

            # 7. FAILURE MEMORY — track actions that didn't move the player
            if new_state and self.last_position:
                old_x, old_y = self.last_position
                new_x = new_state.get("x", old_x)
                new_y = new_state.get("y", old_y)
                if new_x == old_x and new_y == old_y:
                    # Action didn't move us — record failure
                    map_name = new_state.get("map_name", "?")
                    fail_key = f"{map_name}:{action}"
                    self.failure_memory[fail_key] = self.failure_memory.get(fail_key, 0) + 1
                    print(f"  [Memory] {action} blocked in {map_name} (x{self.failure_memory[fail_key]})")
                else:
                    # Movement succeeded — clear failures for this map
                    map_name = new_state.get("map_name", "?")
                    keys_to_clear = [k for k in self.failure_memory if k.startswith(f"{map_name}:")]
                    for k in keys_to_clear:
                        del self.failure_memory[k]

            # 7b. BUILDING EXIT DETECTION — record when we leave a building
            if new_state and self.last_map and hasattr(self, 'memory'):
                prev_map = self.last_map
                curr_map = new_state.get("map_name", "?")
                if prev_map != curr_map:
                    # Record the warp/transition in memory
                    exit_x = new_state.get("x", 0)
                    exit_y = new_state.get("y", 0)
                    entry_x = self.last_position[0] if self.last_position else exit_x
                    entry_y = self.last_position[1] if self.last_position else exit_y
                    self.memory.record_warp(
                        from_map=prev_map, from_x=entry_x, from_y=entry_y,
                        to_map=curr_map, to_x=exit_x, to_y=exit_y,
                    )
                    # Also record the reverse (we can backtrack if needed)
                    self.memory.record_warp(
                        from_map=curr_map, from_x=exit_x, from_y=exit_y,
                        to_map=prev_map, to_x=entry_x, to_y=entry_y,
                        confidence=0.8,  # slightly lower — might be one-way
                    )
                    print(f"  [Memory] Warp: {prev_map}({entry_x},{entry_y}) ↔ {curr_map}({exit_x},{exit_y})")
                    # Detect building → outdoor transition
                    # Heuristic: buildings have floor numbers, known interior names,
                    # or are in the guide's building list; outdoor maps don't.
                    building_keywords = ["1F", "2F", "3F", "4F", "5F", "B1F", "B2F",
                                         "House", "Lab", "Mart", "Center", "Pokecenter",
                                         "Gym", "Tower", "Mansion", "Hideout", "Co.",
                                         "Dojo", "Museum", "Plant", "Lighthouse",
                                         "Club", "Restaurant", "Dept.", "Store"]
                    is_building = any(s in prev_map for s in building_keywords)
                    is_outdoor = not any(s in curr_map for s in building_keywords)
                    if is_building and is_outdoor:
                        # Set exit avoidance: remember where we exited so the
                        # nudge can warn against walking back onto the doormat
                        self.recent_exit_positions.append((curr_map, exit_x, exit_y))
                        self.exit_avoidance_counter = 0
                        # Persist building exit event so GPS can avoid re-entry
                        self.memory.record_building_exit(
                            building_name=prev_map, outside_map=curr_map,
                            exit_pos=(exit_x, exit_y))
                        print(f"  [Memory] Exited {prev_map} → {curr_map} (don't go back!)")
                    # Increment exit avoidance counter (cleared on map change)
                    self.exit_avoidance_counter += 1
                    # P0-2: Record explored tiles for map knowledge
                    if self.last_position:
                        self.memory.update_map_knowledge(
                            prev_map,
                            tiles={self.last_position: "walkable"},
                        )
                        self.memory.update_map_knowledge(
                            curr_map,
                            tiles={(exit_x, exit_y): "entry_point"},
                            connections=[prev_map],
                        )

            # 8. UPDATE
            if success:
                self.completed_ids.append(obj["id"])
                print(f"  ★★ {obj['id']} COMPLETED!")
                push_event("key_moment", f"Completed: {obj['description']}", base_url=self.base_url)
                self.current_objective = None
                self.current_objective_id = None
                self.objective_start_state = None
                self.actions_on_objective = []
                self.steps_on_current_objective = 0
                self.failure_memory.clear()  # clear memory on objective change
                self.tile_visit_count.clear()
                self.recent_exit_positions.clear()
                self.exit_avoidance_counter = 0
            elif self.steps_on_current_objective >= self.max_steps_per_objective:
                force_complete = False
                for cond_key, cond_val in completion_conditions.items():
                    actual = self._get_nested(new_state, cond_key)
                    if actual == cond_val:
                        force_complete = True
                    else:
                        force_complete = False
                        break

                if force_complete:
                    print(f"  ⚠ Max steps reached but conditions met. Completing {obj['id']}.")
                    self.completed_ids.append(obj["id"])
                    push_event("key_moment", f"Completed (max steps): {obj['description']}", base_url=self.base_url)
                else:
                    print(f"  ⚠ Max steps ({self.max_steps_per_objective}) for {obj['id']}. Force-skipping.")
                    push_event("think", f"Skipped {obj['id']} after {self.max_steps_per_objective} steps", base_url=self.base_url)
                    self.completed_ids.append(obj["id"])

                self.current_objective = None
                self.current_objective_id = None
                self.objective_start_state = None
                self.actions_on_objective = []
                self.steps_on_current_objective = 0
                self.tile_visit_count.clear()
                self.recent_exit_positions.clear()
                self.exit_avoidance_counter = 0

            # Progress
            completed = len(self.completed_ids)
            total = len(self.guide_steps)
            remaining = [s["id"] for s in self.guide_steps if s["id"] not in self.completed_ids]
            print(f"  Progress: {completed}/{total} ({round(completed/max(total,1)*100,1)}%) | "
                  f"Objective: {obj['id']} ({self.steps_on_current_objective} steps) | "
                  f"Next: {remaining[0] if remaining else 'none'}")

            # Small delay between steps
            time.sleep(0.3)

        self.running = False
        # Save memory to disk
        if hasattr(self, 'memory'):
            self.memory.save_all()
            print(f"  [Memory] Saved — {len(self.memory.warps)} warps, {len(self.memory.items)} items, {len(self.memory.battle_logs)} battles")
        print("\n" + "=" * 60)
        print("  Run Finished")
        print(f"  Steps: {self.step_count}")
        print(f"  Completed: {len(self.completed_ids)}/{len(self.guide_steps)}")
        if self.completed_ids:
            print(f"  Completed IDs: {', '.join(self.completed_ids[-5:])}")
        print("=" * 60)
        push_event("key_moment",
                   f"Run finished — {len(self.completed_ids)}/{len(self.guide_steps)} objectives in {self.step_count} steps",
                   base_url=self.base_url)
        # Push final objective state (all done)
        if self.guide_steps:
            final_objectives = [
                {"tier": "primary" if i == 0 else "secondary", "text": s["description"],
                 "done": s["id"] in self.completed_ids}
                for i, s in enumerate(self.guide_steps[:8])
            ]
            push_objectives(final_objectives, base_url=self.base_url)

    @staticmethod
    def _get_nested(state: Dict[str, Any], path: str) -> Any:
        """Get a nested value from state using dot notation."""
        keys = path.split(".")
        current = state
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

    def stop(self):
        self.running = False

    def _pick_starter(self) -> str:
        """Ask the LLM to pick a starter Pokemon. Returns the chosen starter name."""
        system = """You are about to receive your FIRST Pokemon ever in Pokemon Red. This is the most exciting moment of the game!

The three starter options are:
1. BULBASAUR — Grass/Poison type. Strong against the first two gyms (Brock/Rock, Misty/Water). Learns Razor Leaf early. A loyal, steady partner.
2. CHARMANDER — Fire type. Strong against Bug types in Viridian Forest and Grass gym (Erika). Struggles against first two gyms but becomes powerful. A brave, feisty partner.
3. SQUIRTLE — Water type. Strong against the first gym (Brock/Rock). Learns Water Gun early. A cool, good all-rounder.

Choose the starter that YOU want. This Pokemon will be your partner for the ENTIRE journey through Kanto!"""
        user = """Which starter Pokemon do you want for your playthrough of Pokemon Red?

Think about:
- Which type advantages appeal to you?
- Which Pokemon looks coolest to you?
- Which one will be most fun to train?

Explain your choice in 1-2 sentences, then output ONLY the starter name (Bulbasaur, Charmander, or Squirtle) on the LAST LINE."""
        response = self.llm.chat(system, user, temperature=0.7)
        chosen = None
        if response:
            # Push the full reasoning to the dashboard
            push_event("think", f"Starter choice reasoning: {response[:300]}", base_url=self.base_url)
            lower = response.lower()
            if "bulbasaur" in lower:
                chosen = "Bulbasaur"
            elif "charmander" in lower:
                chosen = "Charmander"
            elif "squirtle" in lower:
                chosen = "Squirtle"
        if not chosen:
            import random
            chosen = random.choice(["Bulbasaur", "Charmander", "Squirtle"])
        return chosen


if __name__ == "__main__":
    agent = StandaloneAgent()
    agent.run()
