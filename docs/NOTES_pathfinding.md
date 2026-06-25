# Pathfinding Integration Notes

From investigation of `pokemon_agent/pathfinding.py`:

- Uses `find_path(start, goal, collision_map)` where start/goal are `(x, y)` tuples.
- `collision_map` is a dict `{(x,y): bool}` (True = walkable).
- Returns list of directions or `directions_to_actions()` for `walk_*` commands.
- The server already provides a collision grid via `/state`.

Next step when ready:
- Add coordinate conversion from relative collision grid (player at center) to absolute coords.
- Wire `Executor.navigate_to()` to call `navigate()` from the pathfinding module.
- Handle cases where goal is outside current viewport.