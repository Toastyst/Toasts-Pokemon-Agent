"""Gen 1 collision-map extraction.

Reads the on-screen background tilemap (``wTileMap`` at 0xC3A0, a 20x18 grid
of 8x8 hardware tile ids) and the current tileset id (``wCurMapTileset`` at
0xD367), then classifies each of the 10x9 walkable *blocks* as walkable or
blocked using the authoritative per-tileset collision lists from the pokered
disassembly (``data/tilesets/collision_tile_ids.asm``).

A Gen 1 overworld "block" is 16x16 px = a 2x2 group of 8x8 tiles. The screen
shows 10 blocks across and 9 down. The player is locked to block (col 4,
row 4) — grid cell "E5". Walkability of a block is decided by its top-left
8x8 tile id, which is what the engine itself checks.

Output grid orientation: ``grid[row][col]`` with row 0 at the top, col 0 at
the left; ``True`` means walkable.

Special tile detection (stairs, doors, warps) uses two complementary methods:

1. **Warp RAM entries** (D3AE/D3AF): If the player's current position matches
   a warp entry, that cell is marked as a warp/trigger tile. This is the most
   reliable method — it comes from the game's own data structures.

2. **Per-tileset warp/door tile IDs**: From the disassembly files
   ``data/tilesets/warp_tile_ids.asm`` and ``data/tilesets/door_tile_ids.asm``.
   If a block's representative tile ID matches a known warp or door tile for
   the current tileset, it is flagged. This catches tiles the player is
   approaching (not just standing on).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

ADDR_TILEMAP = 0xC3A0       # wTileMap, 20x18 bytes
ADDR_TILESET = 0xD367       # wCurMapTileset
TILEMAP_W, TILEMAP_H = 20, 18

BLOCK_COLS = 10             # on-screen walkable blocks across
BLOCK_ROWS = 9             # on-screen walkable blocks down
PLAYER_COL = 4             # the block the player is locked to (cell E5)
PLAYER_ROW = 4

# Per-tileset walkable tile-id sets, transcribed from pokered
# data/tilesets/collision_tile_ids.asm. Key = wCurMapTileset value.
TILESET_WALKABLE: Dict[int, frozenset] = {
    0: frozenset({0x00, 0x10, 0x1B, 0x20, 0x21, 0x23, 0x2C, 0x2D, 0x2E, 0x30, 0x31, 0x33, 0x39, 0x3C, 0x3E, 0x52, 0x54, 0x58, 0x5B}),  # Overworld
    1: frozenset({0x01, 0x02, 0x03, 0x11, 0x12, 0x13, 0x14, 0x1A, 0x1C}),  # RedsHouse1
    2: frozenset({0x11, 0x1A, 0x1C, 0x3C, 0x5E}),  # Mart
    3: frozenset({0x1E, 0x20, 0x2E, 0x30, 0x34, 0x37, 0x39, 0x3A, 0x40, 0x51, 0x52, 0x5A, 0x5C, 0x5E, 0x5F}),  # Forest
    4: frozenset({0x01, 0x02, 0x03, 0x11, 0x12, 0x13, 0x14, 0x1A, 0x1C}),  # RedsHouse2
    5: frozenset({0x03, 0x11, 0x16, 0x19, 0x2B, 0x3C, 0x3D, 0x3F, 0x4A, 0x4C, 0x4D}),  # Dojo
    6: frozenset({0x11, 0x1A, 0x1C, 0x3C, 0x5E}),  # Pokecenter
    7: frozenset({0x03, 0x11, 0x16, 0x19, 0x2B, 0x3C, 0x3D, 0x3F, 0x4A, 0x4C, 0x4D}),  # Gym
    8: frozenset({0x01, 0x12, 0x14, 0x28, 0x32, 0x37, 0x44, 0x54, 0x5C}),  # House
    9: frozenset({0x01, 0x12, 0x14, 0x1A, 0x1C, 0x37, 0x38, 0x3B, 0x3C, 0x5E}),  # ForestGate
    10: frozenset({0x01, 0x12, 0x14, 0x1A, 0x1C, 0x37, 0x38, 0x3B, 0x3C, 0x5E}),  # Museum
    11: frozenset({0x0B, 0x0C, 0x13, 0x15, 0x18}),  # Underground
    12: frozenset({0x01, 0x12, 0x14, 0x1A, 0x1C, 0x37, 0x38, 0x3B, 0x3C, 0x5E}),  # Gate
    13: frozenset({0x04, 0x0D, 0x17, 0x1D, 0x1E, 0x23, 0x34, 0x37, 0x39, 0x4A}),  # Ship
    14: frozenset({0x0A, 0x1A, 0x32, 0x3B}),  # ShipPort
    15: frozenset({0x01, 0x10, 0x13, 0x1B, 0x22, 0x42, 0x52}),  # Cemetery
    16: frozenset({0x04, 0x0F, 0x15, 0x1F, 0x3B, 0x45, 0x47, 0x55, 0x56}),  # Interior
    17: frozenset({0x05, 0x15, 0x18, 0x1A, 0x20, 0x21, 0x22, 0x2A, 0x2D, 0x30}),  # Cavern
    18: frozenset({0x14, 0x17, 0x1A, 0x1C, 0x20, 0x38, 0x45}),  # Lobby
    19: frozenset({0x01, 0x05, 0x11, 0x12, 0x14, 0x1A, 0x1C, 0x2C, 0x53}),  # Mansion
    20: frozenset({0x0C, 0x16, 0x1E, 0x26, 0x34, 0x37}),  # Lab
    21: frozenset({0x0F, 0x1A, 0x1F, 0x26, 0x28, 0x29, 0x2C, 0x2D, 0x2E, 0x2F, 0x41}),  # Club
    22: frozenset({0x01, 0x10, 0x11, 0x13, 0x1B, 0x20, 0x21, 0x22, 0x30, 0x31, 0x32, 0x42, 0x43, 0x48, 0x52, 0x55, 0x58, 0x5E}),  # Facility
    23: frozenset({0x1B, 0x23, 0x2C, 0x2D, 0x3B, 0x45}),  # Plateau
}

# Per-tileset warp tile IDs, from pokered disassembly
# data/tilesets/warp_tile_ids.asm.
# These tiles trigger a map transition (stairs, doors, warps) when the player
# steps on them. Overlap with door_tile_ids is expected.
TILESET_WARP_TILES: Dict[int, frozenset] = {
    0:  frozenset({0x1B, 0x58}),                    # Overworld
    1:  frozenset({0x1A, 0x1C}),                    # RedsHouse1
    2:  frozenset({0x5E}),                           # Mart
    3:  frozenset({0x5A, 0x5C, 0x3A}),              # Forest
    4:  frozenset({0x1A, 0x1C}),                    # RedsHouse2
    5:  frozenset({0x4A}),                           # Dojo
    6:  frozenset({0x5E}),                           # Pokecenter
    7:  frozenset({0x4A}),                           # Gym
    8:  frozenset({0x54, 0x5C, 0x32}),              # House
    9:  frozenset({0x3B}),                           # ForestGate
    10: frozenset({0x3B}),                           # Museum
    11: frozenset({0x13}),                           # Underground
    12: frozenset({0x3B}),                           # Gate
    13: frozenset({0x37, 0x39, 0x1E, 0x4A}),        # Ship
    14: frozenset(),                                 # ShipPort (empty)
    15: frozenset({0x1B}),                           # Cemetery
    16: frozenset({0x15, 0x55, 0x04}),              # Interior
    17: frozenset({0x18, 0x1A, 0x22}),              # Cavern
    18: frozenset({0x1A, 0x1C, 0x38}),              # Lobby
    19: frozenset({0x1A, 0x1C, 0x53}),              # Mansion
    20: frozenset({0x34}),                           # Lab
    21: frozenset(),                                 # Club (empty)
    22: frozenset({0x43, 0x58, 0x20}),              # Facility
    23: frozenset({0x1B, 0x3B}),                    # Plateau
}

# Per-tileset door tile IDs, from pokered disassembly
# data/tilesets/door_tile_ids.asm.
# These tiles have a door graphic and may trigger a warp animation.
TILESET_DOOR_TILES: Dict[int, frozenset] = {
    0:  frozenset({0x1B, 0x58}),                    # Overworld
    1:  frozenset(),                                 # RedsHouse1 (uses warp_tiles)
    2:  frozenset({0x5E}),                           # Mart
    3:  frozenset({0x3A}),                           # Forest
    4:  frozenset(),                                 # RedsHouse2 (uses warp_tiles)
    5:  frozenset(),                                 # Dojo
    6:  frozenset(),                                 # Pokecenter
    7:  frozenset(),                                 # Gym
    8:  frozenset({0x54}),                           # House
    9:  frozenset({0x3B}),                           # ForestGate
    10: frozenset({0x3B}),                           # Museum
    11: frozenset(),                                 # Underground
    12: frozenset(),                                 # Gate
    13: frozenset({0x1E}),                           # Ship
    14: frozenset(),                                 # ShipPort
    15: frozenset(),                                 # Cemetery
    16: frozenset(),                                 # Interior
    17: frozenset(),                                 # Cavern
    18: frozenset({0x1C, 0x38, 0x1A}),              # Lobby
    19: frozenset({0x1A, 0x1C, 0x53}),              # Mansion
    20: frozenset({0x34}),                           # Lab
    21: frozenset(),                                 # Club
    22: frozenset({0x43, 0x58, 0x1B}),              # Facility
    23: frozenset({0x3B, 0x1B}),                    # Plateau
}

# Tile IDs that are warp pads or holes (from warp_pad_hole_tile_ids.asm).
# These set wStandingOnWarpPadOrHole when the player steps on them.
TILESET_WARP_PADS: Dict[int, frozenset] = {
    16: frozenset({0x55}),                           # Interior (warp pad)
    17: frozenset({0x22}),                           # Cavern (hole)
    22: frozenset({0x20}),                           # Facility (warp pad)
}

TILESET_WARP_HOLES: Dict[int, frozenset] = {
    17: frozenset({0x11}),                           # Cavern (hole)
    22: frozenset({0x11}),                           # Facility (hole)
}

COL_LABELS = "ABCDEFGHIJ"


def cell_label(col: int, row: int) -> str:
    return f"{COL_LABELS[col]}{row + 1}"


def read_block_tile_ids(emu) -> List[List[int]]:
    """Return the 9x10 grid of representative tile ids per block.

    The player's standing tile in ``wTileMap`` is screen tile (col 8, row 9),
    so the 16px block grid is sampled with a +1 row offset: block (bc, br)
    maps to tilemap tile (bc*2, br*2 + 1). This puts the player at block
    (col 4, row 4) = cell E5 and makes the "tile above" / collision checks
    line up with the engine's own movement rules.
    """
    tm = emu.read_range(ADDR_TILEMAP, TILEMAP_W * TILEMAP_H)
    grid: List[List[int]] = []
    for br in range(BLOCK_ROWS):
        row: List[int] = []
        for bc in range(BLOCK_COLS):
            tcol, trow = bc * 2, br * 2 + 1
            row.append(tm[trow * TILEMAP_W + tcol])
        grid.append(row)
    return grid


def build_collision_grid(emu) -> Dict:
    """Build a walkability grid for the current on-screen blocks.

    Returns a dict with:
        tileset: int
        walkable: 9x10 list of bool (True = can step there)
        tile_ids: 9x10 list of int (raw representative tile ids)
        player_cell: "E5"
    The player's own cell is always reported walkable.
    """
    tileset = emu.read_u8(ADDR_TILESET)
    walk_set = TILESET_WALKABLE.get(tileset, frozenset())
    tile_ids = read_block_tile_ids(emu)

    walkable: List[List[bool]] = []
    for br in range(BLOCK_ROWS):
        row: List[bool] = []
        for bc in range(BLOCK_COLS):
            tid = tile_ids[br][bc]
            row.append(tid in walk_set)
        walkable.append(row)
    # The player block is always passable (you're standing on it).
    walkable[PLAYER_ROW][PLAYER_COL] = True

    return {
        "tileset": tileset,
        "walkable": walkable,
        "tile_ids": tile_ids,
        "player_cell": cell_label(PLAYER_COL, PLAYER_ROW),
    }


def build_special_tiles(
    emu,
    collision: Dict,
    warps: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Detect special tiles (stairs, doors, warps, pads, holes) in the viewport.

    Uses two complementary methods:

    1. **Warp RAM entries**: If the player's current (x,y) matches a warp
       entry's trigger position, that cell is marked as a warp tile with
       destination info. This is the ground truth from the game engine.

    2. **Per-tileset tile IDs**: Each block's representative tile ID is checked
       against the disassembly-derived sets TILESET_WARP_TILES,
       TILESET_DOOR_TILES, TILESET_WARP_PADS, and TILESET_WARP_HOLES.
       This catches tiles the player is approaching.

    Parameters
    ----------
    emu : Emulator
        The running emulator instance.
    collision : Dict
        Output from ``build_collision_grid``.
    warps : list of dict, optional
        Output from ``RedBlueMemoryReader.read_warps()``. If None, warp RAM
        entries are not cross-referenced.

    Returns
    -------
    dict
        Keyed by cell label (e.g. "H2"), each value is a dict with:
          type: "stairs" | "door" | "warp" | "warp_pad" | "warp_hole"
          dest_map: int or None — destination map ID (from warp RAM only)
          dest_name: str or None — human-readable destination name
          source: "ram" | "tile_id" — which detection method found it
    """
    tileset = collision["tileset"]
    tile_ids = collision["tile_ids"]
    walkable = collision["walkable"]

    # Get player's absolute position
    px = emu.read_u8(0xD362)  # wXCoord
    py = emu.read_u8(0xD361)  # wYCoord

    # Per-tileset special tile ID sets
    warp_set = TILESET_WARP_TILES.get(tileset, frozenset())
    door_set = TILESET_DOOR_TILES.get(tileset, frozenset())
    pad_set = TILESET_WARP_PADS.get(tileset, frozenset())
    hole_set = TILESET_WARP_HOLES.get(tileset, frozenset())

    # Build a set of warp trigger positions from RAM for fast lookup
    warp_positions: Dict[tuple, Dict[str, Any]] = {}
    if warps:
        for w in warps:
            warp_positions[(w["y"], w["x"])] = w

    special: Dict[str, Dict[str, Any]] = {}

    for br in range(BLOCK_ROWS):
        for bc in range(BLOCK_COLS):
            # Compute absolute position of this block
            # Player is at viewport center (PLAYER_COL, PLAYER_ROW)
            abs_x = px + (bc - PLAYER_COL)
            abs_y = py + (br - PLAYER_ROW)

            label = cell_label(bc, br)
            tid = tile_ids[br][bc]
            is_walkable = walkable[br][bc]

            # Method 1: Check if player is standing on a warp entry
            if (abs_y, abs_x) in warp_positions:
                w = warp_positions[(abs_y, abs_x)]
                special[label] = {
                    "type": "warp",
                    "dest_map": w["dest_map"],
                    "dest_name": w["dest_name"],
                    "source": "ram",
                }
                continue  # RAM match is authoritative

            # Method 2: Check tile ID against per-tileset special sets
            # Only flag walkable tiles (blocked tiles can't be stepped on)
            if not is_walkable:
                continue

            if tid in pad_set:
                special[label] = {"type": "warp_pad", "source": "tile_id"}
            elif tid in hole_set:
                special[label] = {"type": "warp_hole", "source": "tile_id"}
            elif tid in warp_set:
                # Distinguish stairs from doors:
                # 1. If it's in the tileset door_set, it's a door
                # 2. If it matches a warp RAM entry with dest_map=255 (doormat/exit),
                #    it's a door regardless of tileset
                # 3. Otherwise it's stairs/warp
                is_door = tid in door_set
                if not is_door and (abs_y, abs_x) in warp_positions:
                    w = warp_positions[(abs_y, abs_x)]
                    if w.get("dest_map") == 255:
                        is_door = True
                if is_door:
                    special[label] = {"type": "door", "source": "tile_id"}
                else:
                    special[label] = {"type": "stairs", "source": "tile_id"}

    return special


def render_ascii_map(
    collision: Dict,
    special: Optional[Dict[str, Dict[str, Any]]] = None,
    legend: bool = True,
    player_pos: Optional[Dict[str, int]] = None,
    sprites: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Render the collision grid as a labelled ASCII map.

    Legend:
        @ = player (E5)   . = walkable   # = blocked
        S = stairs/warp   D = door       W = warp-pad/hole
        ● = item          ☻ = NPC
    Column headers show absolute X coord; row headers show absolute Y coord.
    """
    walkable = collision["walkable"]
    special = special or {}
    sprites = sprites or []
    lines: List[str] = []

    # Compute absolute coords for each column/row
    if player_pos:
        px = player_pos.get("x", 0)
        py = player_pos.get("y", 0)
    else:
        px = py = 0

    col_abs = [px + (c - PLAYER_COL) for c in range(BLOCK_COLS)]
    row_abs = [py + (r - PLAYER_ROW) for r in range(BLOCK_ROWS)]

    # Build a lookup: (abs_y, abs_x) -> sprite list
    sprite_cells: Dict[tuple, List[Dict[str, Any]]] = {}
    for sp in sprites:
        key = (sp["y"], sp["x"])
        sprite_cells.setdefault(key, []).append(sp)

    # Header: absolute X coords above each column (each cell is 3 chars: " X ")
    # Prefix matches row prefix width: 4 chars right-aligned + 1 space = 5
    header = "     " + "".join(f"{x:<3}" for x in col_abs)
    lines.append(header)

    for r in range(BLOCK_ROWS):
        cells = []
        for c in range(BLOCK_COLS):
            label = cell_label(c, r)
            abs_x = col_abs[c]
            abs_y = row_abs[r]
            if r == PLAYER_ROW and c == PLAYER_COL:
                # Player standing here — also show special tile type if present
                if label in special:
                    stype = special[label]["type"]
                    if stype == "door":
                        cells.append(" @D")  # player on doormat
                    elif stype == "stairs":
                        cells.append(" @S")  # player on stairs
                    elif stype in ("warp_pad", "warp_hole"):
                        cells.append(" @W")  # player on warp pad
                    elif stype == "warp":
                        cells.append(" @S")  # player on warp
                    else:
                        cells.append(" @ ")
                else:
                    cells.append(" @ ")
            elif (abs_y, abs_x) in sprite_cells:
                # Show sprite: ● for item, ☻ for NPC
                sp_list = sprite_cells[(abs_y, abs_x)]
                # Prefer item over NPC if both at same cell
                has_item = any(s.get("type") == "item" for s in sp_list)
                has_npc = any(s.get("type") == "npc" for s in sp_list)
                if has_item:
                    cells.append(" ● ")
                elif has_npc:
                    cells.append(" ☻ ")
                else:
                    cells.append(" ? ")
            elif label in special:
                stype = special[label]["type"]
                if stype == "stairs":
                    cells.append(" S ")
                elif stype == "door":
                    cells.append(" D ")
                elif stype in ("warp_pad", "warp_hole"):
                    cells.append(" W ")
                elif stype == "warp":
                    cells.append(" S ")
                else:
                    cells.append(" ? ")
            else:
                cells.append(" . " if walkable[r][c] else " # ")
        lines.append(f"{row_abs[r]:>4} " + "".join(cells))

    if legend:
        lines.append("")
        lines.append("@ you   . walkable   # blocked")
        lines.append("S stairs/warp  D door/doormat")
        lines.append("W warp-pad/hole  ● item  ☻ NPC")
    return "\n".join(lines)
