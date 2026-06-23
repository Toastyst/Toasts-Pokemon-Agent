"""
State parser for the pokemon-agent server response.

Handles the nested JSON structure and provides convenient flat fields.
Also handles the collision grid coordinate mapping:
  - The 9×10 collision viewport is centered on the player
  - Viewport row 0 = player_y - 4, viewport col 0 = player_x - 4
  - grid_row = y - player_y + 4
  - grid_col = x - player_x + 4
"""

from typing import Dict, Any, List, Optional, Tuple


def parse_game_state(raw_state: Dict[str, Any]) -> Dict[str, Any]:
    """Parse the nested /state response into a flat-ish structure."""
    if not raw_state:
        return {}

    player = raw_state.get("player", {})
    position = player.get("position", {})
    map_data = raw_state.get("map", {})
    flags = raw_state.get("flags", {})
    battle = raw_state.get("battle", {})
    dialog = raw_state.get("dialog", {})
    collision = raw_state.get("collision", {})
    raw_collision = raw_state.get("collision", {})

    parsed = {
        "player": {
            "name": player.get("name"),
            "x": position.get("x"),
            "y": position.get("y"),
            "facing": player.get("facing"),
            "badges": player.get("badges", []),
            "badge_count": player.get("badge_count", 0),
        },
        "map": {
            "map_id": map_data.get("map_id"),
            "map_name": map_data.get("map_name"),
        },
        "battle": battle,
        "dialog": dialog,
        "flags": flags,
        "party": raw_state.get("party", []),
        "bag": raw_state.get("bag", []),
        "collision": collision,
        "warps": raw_state.get("warps", []),
        "sprites": raw_state.get("sprites", []),
        "raw": raw_state,
    }

    # Convenience flat fields (for backward compatibility with existing code)
    # Only set if not already present (idempotent — state may already be parsed)
    if "map_name" not in parsed:
        parsed["map_name"] = parsed["map"]["map_name"]
    if "x" not in parsed:
        parsed["x"] = parsed["player"]["x"]
    if "y" not in parsed:
        parsed["y"] = parsed["player"]["y"]
    if "badges" not in parsed:
        parsed["badges"] = parsed["player"]["badges"]
    if "badge_count" not in parsed:
        parsed["badge_count"] = parsed["player"]["badge_count"]

    return parsed


def grid_to_coords(grid_row: int, grid_col: int, player_x: int, player_y: int) -> Tuple[int, int]:
    """Convert grid indices to game coordinates. Player position required for viewport offset."""
    y = grid_row + player_y - 4
    x = grid_col + player_x - 4
    return x, y


def coords_to_grid(x: int, y: int, player_x: int, player_y: int) -> Tuple[int, int]:
    """Convert game coordinates to grid indices. Player position required for viewport offset."""
    grid_row = y - player_y + 4
    grid_col = x - player_x + 4
    return grid_col, grid_row


def is_warp_tile(state: Dict[str, Any], x: int, y: int) -> bool:
    """Check if a game coordinate is a warp/stairs tile using warp RAM entries
    and per-tileset warp tile IDs."""
    # Check warp RAM entries first (most reliable)
    for w in state.get("raw", {}).get("warps", []):
        if w.get("x") == x and w.get("y") == y:
            return True

    # Check by collision grid tile IDs using per-tileset warp sets
    grid = get_collision_grid(state)
    if grid is None:
        return False

    player_x = state.get("x", 0)
    player_y = state.get("y", 0)
    grid_col, grid_row = coords_to_grid(x, y, player_x, player_y)

    if 0 <= grid_row < len(grid) and 0 <= grid_col < len(grid[0]):
        tile_ids = state.get("raw", {}).get("collision", {}).get("tile_ids", [])
        if 0 <= grid_row < len(tile_ids) and 0 <= grid_col < len(tile_ids[0]):
            tile_id = tile_ids[grid_row][grid_col]
            tileset = state.get("raw", {}).get("collision", {}).get("tileset", 0)
            from pokemon_agent.server.collision import TILESET_WARP_TILES
            return tile_id in TILESET_WARP_TILES.get(tileset, frozenset())
    return False


def is_walkable(state: Dict[str, Any], x: int, y: int) -> bool:
    """Check if a game coordinate is walkable using the collision grid AND sprite data.
    Out-of-bounds coordinates are treated as blocked.
    Tiles occupied by NPCs or items are NOT walkable (server blocks movement onto them)."""
    grid = get_collision_grid(state)
    if grid is None:
        return False

    player_x = state.get("x", 0)
    player_y = state.get("y", 0)
    grid_col, grid_row = coords_to_grid(x, y, player_x, player_y)

    if 0 <= grid_row < len(grid) and 0 <= grid_col < len(grid[0]):
        if not grid[grid_row][grid_col]:
            return False  # tile itself is blocked
    else:
        return False  # out of grid bounds

    # Check sprite collision — only NPCs block movement.
    # Items are walkable (you walk up to them and press A to interact).
    for sprite in state.get("sprites", []):
        sx, sy = sprite.get("x"), sprite.get("y")
        if sx == x and sy == y:
            if sprite.get("type") == "npc":
                return False  # NPCs block movement
            # Items do NOT block — agent walks to them and interacts

    return True


def get_walkable_directions(state: Dict[str, Any]) -> List[str]:
    """Get walkable directions from the player's current position.
    When standing on a warp tile, all directions are reported as walkable
    since the server handles warp transitions (e.g., walking south off a doormat)."""
    x = state.get("x", 0)
    y = state.get("y", 0)

    # If standing on a warp tile, all directions are potentially valid
    # — the server handles whether a warp triggers or not
    warp_coords = set()
    for warp in state.get("raw", {}).get("warps", []):
        warp_coords.add((warp.get("x"), warp.get("y")))
    if (x, y) in warp_coords:
        return ["walk_up", "walk_down", "walk_left", "walk_right"]

    deltas = {
        "walk_up":    (0, -1),
        "walk_down":  (0, 1),
        "walk_left":  (-1, 0),
        "walk_right": (1, 0),
    }

    walkable = []
    for direction, (dx, dy) in deltas.items():
        nx, ny = x + dx, y + dy
        if not is_walkable(state, nx, ny):
            continue
        # Skip warp tiles — walking onto them triggers unwanted transitions
        if is_warp_tile(state, nx, ny):
            continue
        walkable.append(direction)

    return walkable


def get_collision_grid(state: Dict[str, Any]) -> Optional[List[List[bool]]]:
    """Extract collision grid from state. True = walkable."""
    # Try parsed collision first
    collision = state.get("collision", {})
    walkable = collision.get("walkable")
    if walkable and isinstance(walkable, list):
        return walkable

    # Fallback: raw state
    raw = state.get("raw", {})
    collision_raw = raw.get("collision", {})
    walkable = collision_raw.get("walkable")
    if walkable and isinstance(walkable, list):
        return walkable

    return None


def render_collision_grid(state: Dict[str, Any]) -> str:
    """Render the collision grid as ASCII for LLM spatial reasoning.

    Shows the viewport area around the player:
    - @ = player position
    - . = walkable tile
    - # = wall / blocked tile
    - S = warp/stairs tile
    - I = item/NPC sprite (blocks movement)
    - ? = out of viewport bounds

    The grid is a 9×10 viewport centered on the player (per state_parser).
    """
    grid = get_collision_grid(state)
    if grid is None:
        return "(no collision grid available)"

    px = state.get("x", 0)
    py = state.get("y", 0)

    # Collect sprite positions for overlay
    sprite_map = {}
    for sp in state.get("sprites", []):
        sx, sy = sp.get("x"), sp.get("y")
        if sp.get("type") == "item":
            sprite_map[(sx, sy)] = "I"
        elif sp.get("type") == "npc":
            sprite_map[(sx, sy)] = "N"

    # Collect warp positions from warps array with door vs stairs classification
    warp_positions = {}  # (gx, gy) -> "D" or "S"
    warp_set = set()
    for w in state.get("warps", []):
        wx, wy = w.get("x"), w.get("y")
        dest_map = w.get("dest_map", -1)
        dest_name = w.get("dest_name", "")
        # Door/exit: dest_map == 255 (doormat sentinel) OR leads to outdoor map
        is_exit = (dest_map == 255 or
                   any(kw in dest_name.lower() for kw in
                       ["route", "town", "city", "island", "plateau"]))
        warp_set.add((wx, wy))
        warp_positions[(wx, wy)] = "D" if is_exit else "S"

    lines = []
    lines.append(f"  Viewport (9x10, player @ at ({px},{py}), Y down, X right):")

    # Show Y coordinates on the left, matching game coords
    for row_idx, row in enumerate(grid):
        tiles = []
        for col_idx, cell in enumerate(row):
            # Convert grid coords to game coords
            gx = px + (col_idx - 4)
            gy = py + (row_idx - 4)

            if gx == px and gy == py:
                # Player standing here — also show special tile type if present
                if (gx, gy) in warp_positions:
                    tiles.append("@" + warp_positions[(gx, gy)])
                else:
                    tiles.append("@")
            elif (gx, gy) in sprite_map:
                tiles.append(sprite_map[(gx, gy)])
            elif (gx, gy) in warp_positions:
                tiles.append(warp_positions[(gx, gy)])
            elif cell:
                tiles.append(".")
            else:
                tiles.append("#")
        # Show game Y coordinate on the left
        game_y = py + (row_idx - 4)
        lines.append(f"  {game_y:2d} {' '.join(tiles)}")

    # Add legend
    lines.append("  Legend: @=you  .=walkable  #=wall  S=stairs  D=doormat/exit  I=item  N=NPC")
    lines.append(f"  Viewport: X range [{px-4}..{px+4}], Y range [{py-4}..{py+4}]")
    return "\n".join(lines)
