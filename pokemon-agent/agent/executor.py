"""
Executor - Handles actual execution of actions against the pokemon-agent server.

Key methods:
  - get_state(): fetch current game state
  - execute_actions(): send action list to server
  - step(): send single action, return new state
  - interact(): press A to interact with whatever is in front
  - navigate_toward(): greedy walk toward target coordinates using collision grid
  - check_special_tile(): detect warps, stairs, doors

Uses state_parser for proper collision grid coordinate mapping:
  grid_row = player_y - 3
  grid_col = player_x + 1
"""

import time
import requests
from typing import List, Dict, Any, Optional, Tuple

from pokemon_agent.agent.utils.state_parser import (
    parse_game_state,
    get_collision_grid,
    is_walkable,
    is_warp_tile,
    get_walkable_directions,
    grid_to_coords,
    coords_to_grid,
)


class Executor:
    DIRECTIONS = ["walk_up", "walk_down", "walk_left", "walk_right"]
    DIR_DELTA = {
        "walk_up":    (0, -1),
        "walk_down":  (0, 1),
        "walk_left":  (-1, 0),
        "walk_right": (1, 0),
    }

    def __init__(self, base_url: str = "http://localhost:8765", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_state(self) -> Optional[Dict[str, Any]]:
        """Fetch and parse current game state from server."""
        try:
            resp = requests.get(f"{self.base_url}/state", timeout=self.timeout)
            if resp.status_code == 200:
                return parse_game_state(resp.json())
            return None
        except Exception as e:
            print(f"[Executor] State error: {e}")
            return None

    def get_screenshot_b64(self) -> Optional[str]:
        """Fetch current screenshot from server and return as base64 string."""
        try:
            resp = requests.get(f"{self.base_url}/screenshot", timeout=self.timeout)
            if resp.status_code == 200:
                import base64
                return base64.b64encode(resp.content).decode("utf-8")
            return None
        except Exception as e:
            print(f"[Executor] Screenshot error: {e}")
            return None

    def execute_actions(self, actions: List[str], delay: float = 0.3) -> bool:
        """Send a list of actions to the server. Returns True on success."""
        try:
            resp = requests.post(
                f"{self.base_url}/action",
                json={"actions": actions},
                timeout=self.timeout
            )
            if delay > 0:
                time.sleep(delay)
            return resp.status_code == 200
        except Exception as e:
            print(f"[Executor] Action error: {e}")
            return False

    DIRECTION_MAP = {
        # Map both walk_* and press_* (directions) to server walk_* — walk
        # uses 60-frame tick (fast).  press_* for directions is treated as
        # movement (not dialog) so we don't want the 240-frame dialog wait.
        "walk_up": "walk_up",
        "walk_down": "walk_down",
        "walk_left": "walk_left",
        "walk_right": "walk_right",
        "press_up": "walk_up",
        "press_down": "walk_down",
        "press_left": "walk_left",
        "press_right": "walk_right",
    }

    def step(self, action: str) -> Optional[Dict[str, Any]]:
        """Send a single action and return the new state.

        Maps walk_* actions to press_* for reliability — press holds the
        button for 8 frames then waits 240 frames, avoiding partial tile
        transitions that can eat inputs after warps.
        """
        # Map walk directions to press directions for reliability
        server_action = self.DIRECTION_MAP.get(action, action)

        try:
            resp = requests.post(
                f"{self.base_url}/action",
                json={"actions": [server_action]},
                timeout=self.timeout
            )
            if resp.status_code != 200:
                return None

            try:
                result = resp.json()
                if "state_after" in result and result["state_after"]:
                    return parse_game_state(result["state_after"])
            except Exception:
                pass

            time.sleep(0.2)
            return self.get_state()
        except Exception as e:
            print(f"[Executor] Step error: {e}")
            return None

    def interact(self, max_dialog_steps: int = 10) -> Optional[Dict[str, Any]]:
        """
        Press A to interact. If dialog opens, advance through it.
        Returns final state after interaction.
        """
        self.execute_actions(["press_a"])
        state = self.get_state()

        if state and state.get("dialog", {}).get("active"):
            for _ in range(max_dialog_steps):
                self.execute_actions(["press_a"], delay=0.5)
                state = self.get_state()
                if state and not state.get("dialog", {}).get("active"):
                    break

        return state

    def simulate_actions(self, actions: list[str], state: Dict[str, Any]) -> tuple[list[str], list[str]]:
        """
        Simulate walk actions against the collision grid from the current state.
        Returns (valid_prefix, rejected_suffix).
        
        Checks each step sequentially. Stops at first collision.
        Press actions are always accepted.
        Warp tiles (from the warps array) are accepted — the server handles transitions.
        Out-of-bounds is blocked.
        """
        MAX_SIM_STEPS = 15
        
        DIR_DELTA = {
            "walk_up":    (0, -1),
            "walk_down":  (0, 1),
            "walk_left":  (-1, 0),
            "walk_right": (1, 0),
        }
        
        # Build set of known warp coords from the server's warps array
        warp_coords = set()
        for warp in state.get("raw", {}).get("warps", []):
            warp_coords.add((warp.get("x"), warp.get("y")))
        
        valid = []
        sim_x = state.get("x", 0)
        sim_y = state.get("y", 0)
        
        for i, action in enumerate(actions):
            if i >= MAX_SIM_STEPS:
                return valid, actions[len(valid):]
            
            if action in ("press_a", "press_b"):
                valid.append(action)
                continue
            
            dx, dy = DIR_DELTA.get(action, (0, 0))
            next_x, next_y = sim_x + dx, sim_y + dy
            
            # Check walkability — use grid, but also accept known warp tiles
            if not is_walkable(state, next_x, next_y):
                # Allow if it's a known warp tile (server-confirmed)
                if (next_x, next_y) not in warp_coords:
                    # Allow walking off a doormat warp tile in any direction.
                    # Doormat warps (dest_map=0xFF) fire when walking OFF the tile,
                    # even if the adjacent tile is marked as a wall in the collision grid.
                    if (sim_x, sim_y) not in warp_coords:
                        return valid, actions[len(valid):]
            
            valid.append(action)
            sim_x, sim_y = next_x, next_y
            
            # If we just stepped onto a warp tile, truncate here.
            # Remaining actions would execute in the wrong map after the warp.
            # The LLM will propose post-warp actions on the next turn.
            if (sim_x, sim_y) in warp_coords:
                return valid, actions[len(valid):]
        
        return valid, []
    
    def get_walkable(self, state: Dict[str, Any]) -> List[str]:
        """Return list of walkable directions from current position."""
        return get_walkable_directions(state)

    def find_warp_for_objective(self, state: Dict[str, Any],
                                objective: str) -> Optional[Tuple[int, int]]:
        """Find a warp tile whose destination matches the objective text.

        Returns (x, y) of the matching warp tile, or None if no match.
        Used by A* to path directly to building entrances.
        """
        if not objective:
            return None
        hint_lower = objective.lower()
        state_warps = state.get("warps", []) or state.get("raw", {}).get("warps", [])

        best_warp_match = None
        best_warp_score = -1
        for w in state_warps:
            dest_name = w.get("dest_name", "")
            if not dest_name:
                continue
            dest_lower = dest_name.lower()
            # Score: count how many significant words from the hint appear in dest_name
            score = 0
            hint_words = hint_lower.split()
            for word in hint_words:
                if len(word) >= 4 and word in dest_lower:
                    score += 10
                elif len(word) >= 3 and word in dest_lower:
                    score += 5
            # Also check if dest_name words appear in hint (bidirectional)
            dest_words = dest_lower.replace("'", "").replace("the ", "").split()
            for word in dest_words:
                if len(word) >= 4 and word in hint_lower:
                    score += 3
            # Penalize distance slightly so closer warps win on ties
            px, py = state.get("x", 0), state.get("y", 0)
            dist = abs(w.get("x", 0) - px) + abs(w.get("y", 0) - py)
            score -= dist * 0.01
            if score > best_warp_score:
                best_warp_score = score
                best_warp_match = w
        if best_warp_match and best_warp_score >= 5:
            return (best_warp_match.get("x", 0), best_warp_match.get("y", 0))
        return None

    def find_npc_interaction_target(self, state: Dict[str, Any],
                                     npc_x: int, npc_y: int) -> Optional[Tuple[Tuple[int, int], str]]:
        """Find the best standing position to interact with an NPC via counter.

        In Pokemon Red, NPCs behind counters can be interacted with from a
        walkable tile adjacent to the counter (on the opposite side from the NPC).
        The game routes the A-press interaction through the counter to the NPC.

        This function finds the nearest walkable tile adjacent to the NPC that is
        on the same side as the player, returning (stand_x, stand_y, face_direction).

        Returns: (stand_position, direction_to_face) or None if no valid tile found.
        """
        # Check 4 adjacent tiles to the NPC
        candidates = [
            ((npc_x, npc_y - 1), "press_up"),    # stand below NPC, face up — most common for counters
            ((npc_x, npc_y + 1), "press_down"),  # stand above NPC, face down
            ((npc_x - 1, npc_y), "press_right"), # stand right of NPC, face left
            ((npc_x + 1, npc_y), "press_left"),  # stand left of NPC, face right
        ]

        # Filter to walkable tiles only
        valid = []
        for (sx, sy), face_dir in candidates:
            if is_walkable(state, sx, sy):
                valid.append(((sx, sy), face_dir))

        if not valid:
            return None

        # Pick the closest one to the player
        px, py = state.get("x", 0), state.get("y", 0)
        valid.sort(key=lambda v: abs(v[0][0] - px) + abs(v[0][1] - py))
        return valid[0]

    def is_counter_npc(self, state: Dict[str, Any], npc_x: int, npc_y: int) -> bool:
        """Check if an NPC appears to be behind a counter (not directly walkable from player).

        Heuristic: If the NPC's tile is not walkable from the player's current
        position because there's a non-walkable tile (likely counter) between them,
        and there's at least one walkable adjacent tile to the NPC.
        """
        # Check if any tile adjacent to the NPC is walkable
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            if is_walkable(state, npc_x + dx, npc_y + dy):
                return True
        return False

    def pick_intermediate_target(self, state: Dict[str, Any],
                                direction_hint: str = "",
                                max_range: int = 7) -> Optional[Tuple[int, int]]:
        """Pick a walkable tile in the visible grid to use as an intermediate
        target when no explicit target_position is set.

        Strategy: Pick the walkable tile closest to the map edge in the
        direction of travel. E.g. for "go north" pick the northernmost
        walkable tile visible. This creates steady progress toward the exit
        without oscillation — each step the target shifts forward as the
        viewport shifts.

        If direction_hint contains a cardinal direction, restrict to tiles
        in that half-plane and pick the one closest to the leading edge.

        If no direction hint, pick the walkable tile closest to any edge.

        Returns (x, y) game coordinate or None if no walkable tiles found.
        """
        grid = get_collision_grid(state)
        if grid is None:
            return None

        px, py = state.get("x", 0), state.get("y", 0)
        rows, cols = len(grid), len(grid[0])

        # Parse direction from hint
        hint_dir = None
        if direction_hint:
            hint_lower = direction_hint.lower()
            for d in ["north", "south", "east", "west"]:
                if d in hint_lower:
                    hint_dir = d
                    break

        best = None
        best_score = -1
        for gr in range(rows):
            for gc in range(cols):
                if not grid[gr][gc]:
                    continue  # blocked
                gx, gy = grid_to_coords(gr, gc, px, py)
                # Skip current position
                if gx == px and gy == py:
                    continue
                dist = abs(gx - px) + abs(gy - py)
                if dist > max_range:
                    continue

                if hint_dir == "north":
                    # Prefer smallest gy (furthest north / top of screen)
                    # Score: higher = better.  Row 0 is best.
                    score = rows - gr
                    if gr == 0:
                        score += 5  # bonus for being at the edge
                elif hint_dir == "south":
                    score = gr
                    if gr == rows - 1:
                        score += 5
                elif hint_dir == "west":
                    score = cols - gc
                    if gc == 0:
                        score += 5
                elif hint_dir == "east":
                    score = gc
                    if gc == cols - 1:
                        score += 5
                else:
                    # No direction: prefer any edge
                    score = max(
                        gr, rows - 1 - gr,
                        gc, cols - 1 - gc
                    )

                if score > best_score:
                    best_score = score
                    best = (gx, gy)
        return best

    def compute_path(self, target_x: int, target_y: int, state: Dict[str, Any], max_steps: int = 15) -> List[str]:
        """
        Compute a path from current position to target coordinates.
        Returns list of walk actions (may be empty if no path found).
        Does NOT execute anything — just returns the path.

        Uses BFS when target is visible in the collision grid,
        otherwise uses greedy directional walk toward target.
        """
        from collections import deque

        start_x = state.get("x", 0)
        start_y = state.get("y", 0)
        if start_x == target_x and start_y == target_y:
            return []

        deltas = [
            ("walk_up",    0, -1),
            ("walk_down",  0,  1),
            ("walk_left", -1,  0),
            ("walk_right", 1,  0),
        ]

        # Check if target is in the collision grid
        grid = get_collision_grid(state)
        player_x, player_y = state.get("x", 0), state.get("y", 0)
        tgc, tgr = coords_to_grid(target_x, target_y, player_x, player_y)
        target_in_grid = (grid is not None
                          and 0 <= tgr < len(grid)
                          and 0 <= tgc < len(grid[0]))

        if target_in_grid and is_walkable(state, target_x, target_y):
            # BFS within visible grid
            queue = deque([(start_x, start_y, [])])
            visited = {(start_x, start_y)}
            while queue:
                cx, cy, actions = queue.popleft()
                if cx == target_x and cy == target_y:
                    return actions[:max_steps]
                if len(actions) >= max_steps:
                    continue
                for action_name, dx, dy in deltas:
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) in visited:
                        continue
                    if not is_walkable(state, nx, ny):
                        continue
                    if is_warp_tile(state, nx, ny) and (nx, ny) != (target_x, target_y):
                        continue
                    visited.add((nx, ny))
                    queue.append((nx, ny, actions + [action_name]))
        else:
            # Target not visible or target is a warp tile (marked not-walkable in grid)
            # Greedy walk in target direction, but check walkability of each step
            actions = []
            cx, cy = start_x, start_y
            for _ in range(max_steps):
                dx = target_x - cx
                dy = target_y - cy
                if dx == 0 and dy == 0:
                    break
                # Pick the primary direction toward target
                if abs(dy) >= abs(dx):
                    if dy < 0: action = "walk_up"
                    else: action = "walk_down"
                else:
                    if dx < 0: action = "walk_left"
                    else: action = "walk_right"
                # Check walkability before committing to this step
                dir_to_delta = {
                    "walk_up": (0, -1), "walk_down": (0, 1),
                    "walk_left": (-1, 0), "walk_right": (1, 0),
                }
                ddx, ddy = dir_to_delta[action]
                if not is_walkable(state, cx + ddx, cy + ddy):
                    # Primary direction blocked — try perpendicular
                    if action in ("walk_up", "walk_down"):
                        alt_actions = ["walk_left", "walk_right"]
                    else:
                        alt_actions = ["walk_up", "walk_down"]
                    found_alt = False
                    for alt in alt_actions:
                        adx, ady = dir_to_delta[alt]
                        if is_walkable(state, cx + adx, cy + ady):
                            action = alt
                            ddx, ddy = adx, ady
                            found_alt = True
                            break
                    if not found_alt:
                        break  # Completely stuck
                actions.append(action)
                cx, cy = cx + ddx, cy + ddy
            return actions
        return []

    def walk(self, direction: str, steps: int = 1) -> Optional[Dict[str, Any]]:
        """Walk in a direction for N steps. Returns final state."""
        actions = [direction] * steps
        self.execute_actions(actions, delay=0.2)
        return self.get_state()

    def navigate_toward(
        self,
        target_x: int,
        target_y: int,
        state: Dict[str, Any],
        max_steps: int = 30,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Navigate toward target coordinates.
        
        Two modes:
        1. BFS pathfinding when target is within the visible collision grid
        2. Directional walk when target is outside the grid (e.g., warp tiles)
           - Walks in the general direction of the target
           - Re-checks walkability after each step
           - The server handles transitions (warps, map changes)
        
        Returns (final_state, actions_taken).
        """
        from collections import deque

        start_x = state.get("x", 0)
        start_y = state.get("y", 0)

        if start_x == target_x and start_y == target_y:
            return state, []

        deltas = [
            ("walk_up",    0, -1),
            ("walk_down",  0, 1),
            ("walk_left",  -1, 0),
            ("walk_right", 1, 0),
        ]

        # Determine if target is inside the collision grid
        grid = get_collision_grid(state)
        player_x, player_y = state.get("x", 0), state.get("y", 0)
        tgc, tgr = coords_to_grid(target_x, target_y, player_x, player_y)
        target_in_grid = (grid is not None
                          and 0 <= tgr < len(grid)
                          and 0 <= tgc < len(grid[0]))

        if target_in_grid and is_walkable(state, target_x, target_y):
            # Mode 1: BFS within visible grid
            path_actions = self._bfs_path(
                start_x, start_y, target_x, target_y, state, deltas, max_steps
            )
        else:
            # Mode 2: Directional walk toward target (may be outside grid)
            path_actions = self._directional_walk(
                target_x, target_y, state, deltas, max_steps
            )

        if not path_actions:
            return state, []

        # Execute the computed path
        current_state = state
        for action in path_actions[:max_steps]:
            current_state = self.step(action) or current_state

        return current_state, path_actions[:max_steps]

    def _bfs_path(
        self,
        start_x: int, start_y: int,
        target_x: int, target_y: int,
        state: Dict[str, Any],
        deltas: list,
        max_steps: int,
    ) -> Optional[List[str]]:
        """BFS pathfinding within the visible collision grid.
        Excludes warp tiles unless the target IS a warp tile (to avoid
        accidentally pathing through warps that lead elsewhere)."""
        from collections import deque

        target_is_warp = is_warp_tile(state, target_x, target_y)

        queue = deque([(start_x, start_y, [])])
        visited = {(start_x, start_y)}

        while queue:
            cx, cy, actions = queue.popleft()

            if cx == target_x and cy == target_y:
                return actions

            if len(actions) >= max_steps:
                continue

            for action_name, dx, dy in deltas:
                nx, ny = cx + dx, cy + dy
                if (nx, ny) in visited:
                    continue
                if not is_walkable(state, nx, ny):
                    continue
                # Skip warp tiles unless the target is that exact warp
                if is_warp_tile(state, nx, ny) and (nx, ny) != (target_x, target_y):
                    continue
                visited.add((nx, ny))
                queue.append((nx, ny, actions + [action_name]))

        return None

    def _directional_walk(
        self,
        target_x: int, target_y: int,
        state: Dict[str, Any],
        deltas: list,
        max_steps: int,
    ) -> List[str]:
        """
        Walk in the general direction of target, even if it's outside the grid.
        Uses BFS within the visible grid to find the best next step toward target.
        Re-evaluates the grid after each step.
        """
        actions = []
        current_state = state

        for _ in range(max_steps):
            x = current_state.get("x", 0)
            y = current_state.get("y", 0)

            if x == target_x and y == target_y:
                break

            # Check if target is now within the visible grid
            grid = get_collision_grid(current_state)
            if grid:
                cur_x, cur_y = current_state.get("x", 0), current_state.get("y", 0)
                tgc, tgr = coords_to_grid(target_x, target_y, cur_x, cur_y)
                target_in_grid = (0 <= tgr < len(grid) and 0 <= tgc < len(grid[0]))
                if target_in_grid and is_walkable(current_state, target_x, target_y):
                    # Target is visible — use BFS for optimal path
                    bfs_actions = self._bfs_path(
                        x, y, target_x, target_y, current_state, deltas, max_steps - len(actions)
                    )
                    if bfs_actions:
                        for action in bfs_actions:
                            current_state = self.step(action) or current_state
                            actions.append(action)
                        return actions

            # Target not in grid — pick direction that reduces distance to target
            dx = target_x - x
            dy = target_y - y

            # Build prioritized direction list: primary axis first, then perpendicular
            walkable = set(get_walkable_directions(current_state))

            # Try the direct directions first, then perpendicular
            ordered_dirs = []
            if abs(dy) >= abs(dx):
                # Prioritize vertical
                if dy < 0:
                    ordered_dirs.append(("walk_up", 0, -1))
                elif dy > 0:
                    ordered_dirs.append(("walk_down", 0, 1))
                if dx < 0:
                    ordered_dirs.append(("walk_left", -1, 0))
                elif dx > 0:
                    ordered_dirs.append(("walk_right", 1, 0))
            else:
                # Prioritize horizontal
                if dx < 0:
                    ordered_dirs.append(("walk_left", -1, 0))
                elif dx > 0:
                    ordered_dirs.append(("walk_right", 1, 0))
                if dy < 0:
                    ordered_dirs.append(("walk_up", 0, -1))
                elif dy > 0:
                    ordered_dirs.append(("walk_down", 0, 1))

            # Also try remaining perpendicular directions
            for dname, ddx, ddy in deltas:
                if (dname, ddx, ddy) not in ordered_dirs:
                    ordered_dirs.append((dname, ddx, ddy))

            chosen = None
            for action_name, ddx, ddy in ordered_dirs:
                if action_name in walkable:
                    chosen = action_name
                    break

            if not chosen:
                break

            current_state = self.step(chosen) or current_state
            actions.append(chosen)

        return actions

    def find_nearest_warp(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find the nearest warp tile to the current position."""
        x = state.get("x", 0)
        y = state.get("y", 0)
        warps = state.get("warps", []) or state.get("raw", {}).get("warps", [])

        nearest = None
        nearest_dist = float("inf")

        for warp in warps:
            wx, wy = warp.get("x", -99), warp.get("y", -99)
            dist = abs(wx - x) + abs(wy - y)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = warp

        return nearest

    def check_special_tile(self, state: Dict[str, Any]) -> Optional[str]:
        """Check if the player is standing on or adjacent to a special tile."""
        x = state.get("x", 0)
        y = state.get("y", 0)
        raw = state.get("raw", {})
        tile_ids = raw.get("collision", {}).get("tile_ids", [])

        grid_col, grid_row = coords_to_grid(x, y, x, y)

        if 0 <= grid_row < len(tile_ids) and 0 <= grid_col < len(tile_ids[0]):
            tile_id = tile_ids[grid_row][grid_col]

            # Warp to 1F (stairs down)
            if tile_id == 8:
                return "warp_down"
            # Warp pad
            if tile_id in (0x10, 0x18):
                return "warp_pad"
            # Stairs
            if tile_id in (0x19, 0x20, 0x21):
                return "stairs"
            # Door
            if tile_id in (0x30, 0x31, 0x32):
                return "door"

        return None

    def get_suggested_direction(self, state: Dict[str, Any], chosen_starter: str = "",
                                 avoid_map_names: Optional[List[str]] = None,
                                 target_position: Optional[Tuple[int, int]] = None,
                                 skip_positions: Optional[set] = None,
                                 direction_hint: str = "",
                                 avoid_same_family: bool = False,
                                 planned_path: Optional[List[str]] = None) -> Optional[str]:
        """GPS tool: return a single suggested direction, or None when at target.

        Priority:
        0. If planned_path (A* route) is set, return its first step — this ensures
           the GPS hint is consistent with the A* route shown in the prompt.
        1. If target_position is set, guide toward that (x, y) coordinate.
        2. If chosen_starter is set, find the matching pokeball sprite and guide
           toward an adjacent tile.
        3. Fall back to nearest exit warp.
        Filters out warps leading to maps in avoid_map_names.
        skip_positions: set of (x, y) sprite positions to ignore (already checked
        and rejected — prevents GPS from guiding back to a known wrong ball).
        direction_hint: objective text hint (e.g. "go north", "enter Oak's Lab")
           used to prefer warps in a direction when no explicit target is set.
        avoid_same_family: when True, filter out warps whose destination shares
           the same building family name as the current map (prevents stairs
           loops like 1F→2F→1F when exiting a building).
        """
        # 0. If A* path is available, use its first step as the GPS hint
        if planned_path:
            return planned_path[0]
        px = state.get("x", 0)
        py = state.get("y", 0)
        current_map_id = state.get("map", {}).get("map_id", -1)
        current_map_name = state.get("map", {}).get("map_name", "")
        avoid = set(avoid_map_names or [])

        # 1. If we have an explicit target position, guide toward it
        if target_position is not None:
            tx, ty = target_position
            dx = tx - px
            dy = ty - py
            # Check if the target tile is a warp/doormat tile.
            # For warp tiles, the player must walk ONTO the tile (not stop adjacent),
            # because warps fire when stepping on the tile + continuing in the exit direction.
            target_is_warp = False
            for w in state.get("warps", []):
                if w.get("x") == tx and w.get("y") == ty:
                    target_is_warp = True
                    break
            # For non-warp targets, being adjacent means we need to face the target
            # then press A. If already facing the target, return None (press A now).
            # If not facing, return the direction to face it (may be blocked by item,
            # but changes facing).
            if not target_is_warp and abs(dx) <= 1 and abs(dy) <= 1:
                if dx == 0 and dy == 0:
                    return None  # on top of target — press A
                # Determine which direction to move toward the target.
                # For diagonal adjacency, prioritize the axis with greater distance,
                # or default to horizontal if equal.
                if abs(dx) >= abs(dy):
                    face_dir = "press_right" if dx > 0 else "press_left"
                else:
                    face_dir = "press_down" if dy > 0 else "press_up"
                # For item interaction (chosen_starter): check facing.
                # If already facing the item, return None (press A to interact).
                if chosen_starter:
                    facing = state.get("player", {}).get("facing", "")
                    dir_to_facing = {
                        "press_up": "up", "press_down": "down",
                        "press_left": "left", "press_right": "right",
                    }
                    if dir_to_facing.get(face_dir) == facing:
                        return None  # already facing — press A now
                return face_dir  # move toward target
            if target_is_warp and dx == 0 and dy == 0:
                # Player is standing ON the warp tile. Return the exit direction
                # so the agent knows which way to walk to trigger the warp.
                # For doormats (dest_map=0xFF, exit south): press_down.
                # For stairs (interior, dest_map < 0x80): press_up.
                warp_dir = "press_down"  # default for doormat exits
                for w in state.get("warps", []):
                    if w.get("x") == tx and w.get("y") == ty:
                        dm = w.get("dest_map", 0)
                        if dm != 0xFF and dm < 0x80:
                            warp_dir = "press_up"  # interior stairs
                        break
                return warp_dir
            # Build candidate directions in priority order (greater distance first)
            candidates = []
            if abs(dx) >= abs(dy):
                candidates.append(("press_right" if dx > 0 else "press_left", dx))
                candidates.append(("press_down" if dy > 0 else "press_up", dy))
            else:
                candidates.append(("press_down" if dy > 0 else "press_up", dy))
                candidates.append(("press_right" if dx > 0 else "press_left", dx))
            # Also add perpendicular directions as fallbacks
            all_dirs = ["press_up", "press_down", "press_left", "press_right"]
            for d in all_dirs:
                if d not in [c[0] for c in candidates]:
                    candidates.append((d, 0))
            # Check walkable directions from current position
            walkable = set(get_walkable_directions(state))
            walkable_press = set()
            for wd in walkable:
                walkable_press.add(wd.replace("walk_", "press_"))
            # Among walkable directions, pick the one that most reduces
            # Manhattan distance to the target. This prevents the GPS from
            # suggesting a direction that is walkable but takes the agent
            # away from the target (e.g. pressing left when target is to the right).
            dir_deltas = {
                "press_up": (0, -1),
                "press_down": (0, 1),
                "press_left": (-1, 0),
                "press_right": (1, 0),
            }
            best_dir = None
            best_dist = abs(dx) + abs(dy)  # current Manhattan distance
            for dir_name in walkable_press:
                ddx, ddy = dir_deltas[dir_name]
                new_dist = abs(dx - ddx) + abs(dy - ddy)
                if new_dist < best_dist:
                    best_dist = new_dist
                    best_dir = dir_name
            if best_dir:
                return best_dir
            # Fallback: return first candidate even if not walkable
            return candidates[0][0]

        # 1b. If direction_hint matches a known warp destination, target it directly.
        #     This ensures "Heal at Pokemon Center" paths to the Pokecenter warp,
        #     not just the nearest exit warp.
        if direction_hint:
            warp_pos = self.find_warp_for_objective(state, direction_hint)
            if warp_pos:
                wx, wy = warp_pos
                print(f"  [GPS-exec] Warp match for '{direction_hint[:40]}': "
                      f"({wx},{wy}) (score≥5)")
                dx = wx - px
                dy = wy - py
                if abs(dx) >= abs(dy):
                    primary = "press_right" if dx > 0 else "press_left"
                    secondary = "press_down" if dy > 0 else "press_up"
                else:
                    primary = "press_down" if dy > 0 else "press_up"
                    secondary = "press_right" if dx > 0 else "press_left"
                # Check walkability
                dir_to_delta = {
                    "press_up": (0, -1), "press_down": (0, 1),
                    "press_left": (-1, 0), "press_right": (1, 0),
                }
                pdx, pdy = dir_to_delta[primary]
                if is_walkable(state, px + pdx, py + pdy):
                    return primary
                sdx, sdy = dir_to_delta[secondary]
                if is_walkable(state, px + sdx, py + sdy):
                    return secondary
                return primary  # fallback

        # 2. If we have a chosen starter, guide to nearest unchecked pokeball
        # Labels are unreliable — the LLM identifies content via dialog.
        # Strategy: find nearest unchecked ball, move to an adjacent walkable
        # tile, then face the ball.  The LLM presses A to interact.
        if chosen_starter:
            _unchecked = []
            for sp in state.get("sprites", []):
                if sp.get("type") != "item":
                    continue
                _sp_pos = (sp.get("x"), sp.get("y"))
                if skip_positions and _sp_pos in skip_positions:
                    continue
                _unchecked.append(_sp_pos)
            if _unchecked:
                # Sort by distance to player
                _unchecked.sort(key=lambda b: abs(b[0] - px) + abs(b[1] - py))
                for sx, sy in _unchecked:
                    dx = sx - px
                    dy = sy - py
                    dist = abs(dx) + abs(dy)
                    if dist <= 1:
                        # Already adjacent — return direction to face the ball
                        face_dir = None
                        if dx == 0 and dy == -1:
                            face_dir = "press_up"
                        elif dx == 0 and dy == 1:
                            face_dir = "press_down"
                        elif dx == -1 and dy == 0:
                            face_dir = "press_left"
                        elif dx == 1 and dy == 0:
                            face_dir = "press_right"
                        if face_dir is None:
                            return None  # on top of item
                        facing = state.get("player", {}).get("facing", "")
                        dir_to_facing = {
                            "press_up": "up", "press_down": "down",
                            "press_left": "left", "press_right": "right",
                        }
                        if dir_to_facing.get(face_dir) == facing:
                            return None  # already facing — press A now
                        return face_dir
                    # Not adjacent — find best walkable neighbor to stand on
                    neighbors = [
                        (sx, sy + 1), (sx, sy - 1),
                        (sx + 1, sy), (sx - 1, sy),
                    ]
                    best_nx, best_ny, best_nd = None, None, 999
                    for nx, ny in neighbors:
                        if not is_walkable(state, nx, ny):
                            continue
                        nd = abs(nx - px) + abs(ny - py)
                        if nd < best_nd:
                            best_nd = nd
                            best_nx, best_ny = nx, ny
                    if best_nx is not None:
                        ndx = best_nx - px
                        ndy = best_ny - py
                        # Determine primary direction toward best neighbor
                        if abs(ndx) >= abs(ndy):
                            primary = "press_right" if ndx > 0 else "press_left"
                            secondary = "press_down" if ndy > 0 else "press_up"
                        else:
                            primary = "press_down" if ndy > 0 else "press_up"
                            secondary = "press_right" if ndx > 0 else "press_left"
                        # Check if primary direction is walkable from current pos
                        dir_to_delta = {
                            "press_up": (0, -1), "press_down": (0, 1),
                            "press_left": (-1, 0), "press_right": (1, 0),
                        }
                        pdx, pdy = dir_to_delta[primary]
                        if is_walkable(state, px + pdx, py + pdy):
                            return primary
                        # Primary blocked — try secondary
                        sdx, sdy = dir_to_delta[secondary]
                        if is_walkable(state, px + sdx, py + sdy):
                            return secondary
                        # Both blocked — let the LLM pick from walkable dirs
                        print(f"  [GPS-exec] Both primary ({primary}) and secondary ({secondary}) blocked")
                print(f"  [GPS-exec] No walkable path to any unchecked ball")
            else:
                print(f"  [GPS-exec] No unchecked balls on this map")

        # Fall back to nearest exit warp
        warps = state.get("warps", []) or state.get("raw", {}).get("warps", [])
        exit_warps = []
        # Extract building family name for same-family avoidance (e.g. "Red's House")
        map_family = current_map_name.split("2F")[0].split("1F")[0].split("3F")[0].strip() if current_map_name else ""
        for w in warps:
            dest_map = w.get("dest_map", -1)
            dest_name = w.get("dest_name", "")
            if dest_map == current_map_id:
                continue
            # Only avoid explicitly blacklisted maps (from completed objectives).
            if dest_name in avoid:
                print(f"  [GPS-exec] Skipping warp at ({w.get('x')},{w.get('y')}) → {dest_name} (in avoid)")
                continue
            # When avoid_same_family is set, filter out warps to other floors
            # of the same building (prevents 1F stairs→2F→1F loops during EXIT).
            # Do NOT filter doormats (dest_map=255) — those are real exits.
            if avoid_same_family and dest_map != 255 and map_family and map_family in dest_name:
                continue
            exit_warps.append(w)

        if not exit_warps:
            # No exit warps found — the map may have a boundary exit (e.g.,
            # Pallet Town north to Route 1) that isn't a warp entry.
            # If the objective suggests a cardinal direction, use it as GPS.
            hint_lower = (direction_hint or "").lower()
            for d in ["north", "south", "east", "west"]:
                if d in hint_lower:
                    dir_map = {"north": "press_up", "south": "press_down",
                               "west": "press_left", "east": "press_right"}
                    print(f"  [GPS-exec] No warps, using objective direction: {dir_map[d]} ({d})")
                    return dir_map[d]
            # No direction hint either — return None, LLM decides from grid
            print(f"  [GPS-exec] No exit warps after filtering (avoid={avoid})")
            return None

        print(f"  [GPS-exec] exit_warps after filter: {[(w.get('x'),w.get('y'),w.get('dest_name')) for w in exit_warps]}")

        # If we have a direction hint, prefer warps in that direction.
        # This helps distinguish "exit the map north" from "enter building".
        if direction_hint:
            hint_lower = direction_hint.lower()
            # Extract cardinal direction from hint
            desired_dir = None
            for d in ["north", "south", "east", "west"]:
                if d in hint_lower:
                    desired_dir = d
                    break
            if desired_dir:
                # Score warps: prefer ones on the desired side of the player
                # (e.g., "north" → prefer warps with y < py)
                def warp_directional_score(w):
                    wx, wy = w.get("x", 0), w.get("y", 0)
                    dist = abs(wx - px) + abs(wy - py)
                    bonus = 0
                    if desired_dir == "north" and wy < py:
                        bonus = -10  # prefer north
                    elif desired_dir == "south" and wy > py:
                        bonus = -10
                    elif desired_dir == "east" and wx > px:
                        bonus = -10
                    elif desired_dir == "west" and wx < px:
                        bonus = -10
                    return dist + bonus
                best = min(exit_warps, key=warp_directional_score)
            else:
                best = min(exit_warps, key=lambda w: abs(w.get("x", 0) - px) + abs(w.get("y", 0) - py))
        else:
            best = min(exit_warps, key=lambda w: abs(w.get("x", 0) - px) + abs(w.get("y", 0) - py))
        wx, wy = best.get("x", 0), best.get("y", 0)
        dx = wx - px
        dy = wy - py

        if abs(dx) >= abs(dy):
            primary = "press_right" if dx > 0 else "press_left"
            secondary = "press_down" if dy > 0 else "press_up"
        else:
            primary = "press_down" if dy > 0 else "press_up"
            secondary = "press_right" if dx > 0 else "press_left"
        dir_to_delta = {
            "press_up": (0, -1), "press_down": (0, 1),
            "press_left": (-1, 0), "press_right": (1, 0),
        }
        # Check walkability of the first step toward the warp
        pdx, pdy = dir_to_delta[primary]
        nx, ny = px + pdx, py + pdy
        is_warp_tile = any(w.get("x") == nx and w.get("y") == ny for w in exit_warps)
        # Also check if the next tile is a warp leading to an avoid map
        # (e.g., Oak's Lab doormat in Pallet Town when we just exited)
        next_is_avoid_warp = False
        if avoid:
            for w in state.get("warps", []):
                if w.get("x") == nx and w.get("y") == ny and w.get("dest_name") in avoid:
                    next_is_avoid_warp = True
                    break
        if next_is_avoid_warp:
            pass  # treat as blocked, try secondary
        elif is_warp_tile or is_walkable(state, nx, ny):
            return primary
        # Primary blocked — try secondary
        sdx, sdy = dir_to_delta[secondary]
        snx, sny = px + sdx, py + sdy
        is_warp_tile_2 = any(w.get("x") == snx and w.get("y") == sny for w in exit_warps)
        next_is_avoid_warp_2 = False
        if avoid:
            for w in state.get("warps", []):
                if w.get("x") == snx and w.get("y") == sny and w.get("dest_name") in avoid:
                    next_is_avoid_warp_2 = True
                    break
        if next_is_avoid_warp_2:
            pass  # treat as blocked
        elif is_warp_tile_2 or is_walkable(state, snx, sny):
            return secondary
        # Both blocked — return primary anyway
        print(f"  [GPS-exec] Exit warp path blocked, returning primary: {primary}")
        return primary
