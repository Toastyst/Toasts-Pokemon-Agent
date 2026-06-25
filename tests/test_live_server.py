"""
Live Server Test Suite for Standalone Agent MVP

Run this while the pokemon-agent server is running.
Collects useful diagnostic data at each step.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from execution.executor import Executor
from planning.milestone_tracker import MilestoneTracker
from planning.planner import Planner
from planning.critique import Critique


def test_connectivity(executor: Executor):
    print("\n=== TEST 1: Connectivity & State Reading ===")
    state = executor.get_state()
    
    if state:
        print("✓ Successfully connected to server")
        print(f"  Map: {state.get('player', {}).get('map_name')}")
        print(f"  Position: ({state.get('player', {}).get('x')}, {state.get('player', {}).get('y')})")
        print(f"  Badges: {state.get('player', {}).get('badges')}")
        print(f"  Has collision grid: {'collision' in state}")
        return state
    else:
        print("✗ Failed to get state from server")
        return None


def test_action_execution(executor: Executor):
    print("\n=== TEST 2: Action Execution ===")
    
    actions_to_test = [
        ["walk_up"],
        ["walk_down"],
        ["press_a"],
    ]
    
    results = []
    for actions in actions_to_test:
        success = executor.execute_actions(actions)
        results.append((actions, success))
        status = "✓" if success else "✗"
        print(f"  {status} Sent actions: {actions}")
        time.sleep(0.5)  # small delay between actions
    
    return results


def test_planning_loop(executor: Executor, steps: int = 6):
    print(f"\n=== TEST 3: Planning Loop ({steps} steps) ===")
    
    tracker = MilestoneTracker("test_milestones.json")
    planner = Planner(tracker)
    critique = Critique()
    
    results = []
    
    for step in range(1, steps + 1):
        print(f"\n--- Step {step} ---")
        
        state = executor.get_state() or {}
        prev_state = dict(state)
        
        # Planning
        planner.generate_milestones(state)
        next_milestone = tracker.get_next_milestone()
        
        if not next_milestone:
            print("  No next milestone (all complete or not seeded)")
            break
            
        tasks = planner.decompose_task(next_milestone, state)
        print(f"  Milestone: {next_milestone}")
        print(f"  Tasks: {tasks}")
        
        # Execution
        for task in tasks:
            if task.get("action_type") == "navigate":
                executor.navigate_to(10, 5, state)
            else:
                executor.execute_actions(["walk_up"])
        
        time.sleep(0.8)
        
        # Critique
        new_state = executor.get_state() or {}
        verified = critique.verify_milestone(next_milestone, prev_state, new_state)
        
        if verified:
            tracker.mark_completed(next_milestone, step)
            print(f"  ✓ Milestone verified")
        else:
            print(f"  ✗ Not verified")
        
        progress = tracker.get_progress_summary()
        print(f"  Progress: {progress['completed']}/{progress['total']} ({progress['progress_percent']}%)")
        
        results.append({
            "step": step,
            "milestone": next_milestone,
            "verified": verified,
            "progress": progress
        })
    
    return results


def main():
    print("=== Standalone Agent - Live Server Test Suite ===")
    
    executor = Executor(base_url="http://localhost:8765", timeout=20)
    
    # Test 1
    state = test_connectivity(executor)
    if not state:
        print("\nAborting tests - cannot connect to server")
        return
    
    # Test 2
    action_results = test_action_execution(executor)
    
    # Test 3
    planning_results = test_planning_loop(executor, steps=6)
    
    print("\n=== TEST SUMMARY ===")
    print(f"State reading: {'PASS' if state else 'FAIL'}")
    print(f"Action execution: {sum(1 for _, s in action_results if s)}/{len(action_results)} successful")
    print(f"Planning loop completed {len(planning_results)} steps")


if __name__ == "__main__":
    main()