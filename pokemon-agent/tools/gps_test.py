#!/usr/bin/env python3
"""GPS Test Tool — poll state, show GPS suggestion, wait for next move."""
import sys, time, json, urllib.request
sys.path.insert(0, '/home/toast/projects/pokemon-standalone-agent/src')

def get_state():
    return json.loads(urllib.request.urlopen('http://localhost:8765/state').read())

def get_walkable_directions(state):
    """Quick walkable check from collision grid."""
    grid = state.get('collision_grid', [])
    px, py = state['player']['position']['x'], state['player']['position']['y']
    dirs = []
    deltas = {'up': (0,-1), 'down': (0,1), 'left': (-1,0), 'right': (1,0)}
    for name, (dx, dy) in deltas.items():
        nx, ny = px + dx, py + dy
        if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]):
            if grid[ny][nx]:
                dirs.append(name)
    return dirs

def run_gps(state):
    """Call executor.get_suggested_direction with proper state."""
    from execution.executor import Executor
    ex = Executor(base_url="http://localhost:8765")
    # Only pass state — no chosen_starter for simple nav test
    return ex.get_suggested_direction(state=state)

def main():
    print("=== GPS Test Tool ===")
    print("Move around manually in the game. GPS will suggest directions.")
    print("Press Ctrl+C to exit.\n")
    
    last_pos = None
    last_map = None
    
    try:
        while True:
            state = get_state()
            pos = state['player']['position']
            map_name = state['map']['map_name']
            facing = state['player']['facing']
            px, py = pos['x'], pos['y']
            
            # Only print when position changes
            if (px, py) != last_pos or map_name != last_map:
                last_pos = (px, py)
                last_map = map_name
                
                walkable = get_walkable_directions(state)
                gps = run_gps(state)
                
                print(f"Pos: ({px},{py}) Map: {map_name} Facing: {facing}")
                print(f"  Walkable: {walkable}")
                print(f"  GPS says: {gps}")
                
                # Show warps
                warps = state.get('warps', [])
                if warps:
                    print(f"  Warps: {[(w['x'],w['y'],w.get('dest_name','?')) for w in warps]}")
                print()
            
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nExiting GPS test tool.")

if __name__ == '__main__':
    main()
