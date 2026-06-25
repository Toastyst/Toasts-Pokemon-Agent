# Memory + RAG Architecture Design for Pokémon Red LLM Agent

**Status:** P0 implemented (2026-06-22). P1 items pending.

## 1. Memory Stores (Data Structures)

**Long-term Structured Memory (key-based, JSON persisted):**
- `warps: Dict[str, WarpEntry]` — keyed by "map_x_y", stores discovered warp destinations.
- `items: List[ItemEntry]` — discovered pokeballs, HMs, key items with coordinates and obtained status.
- `opponent_models: Dict[str, OpponentModel]` — per-trainer/pokemon models tracking seen moves, levels, types.
- `battle_logs: deque[BattleLogEntry]` (max 50) — full battle outcomes for pattern learning.
- `dialog_facts: List[DialogFact]` — extracted NPC knowledge (item hints, story flags).
- `map_knowledge: Dict[str, MapKnowledge]` — partial tile knowledge + connections per map.
- `known_type_matchups` — Gen 1 chart + overrides learned from battles.

**Short-term / Working Memory:**
- `recent_events: deque` (max 20) — last actions/results for context.
- `exploration_failures: defaultdict` — prevent repeating blocked moves.
- `current_map`, trajectory context.

**RAG Component:** Lightweight keyword-overlap + map/recency scoring (no embeddings needed for 4K-8K context). `retrieve_relevant_facts(query, top_k=5)` mixes dialog + item facts.

## 2. Write Triggers ✅ P0

- **NavigationAgent / Executor:** After successful move that changes map or interacts with tile → `record_warp()` ✅, `record_item_discovery()` ✅, `update_map_knowledge()` ✅.
- **After any action result:** `record_event()` for short-term.
- **Battle end:** `record_battle(BattleLogEntry)` with observed pokemon/moves ✅.
- **Dialog resolution:** Parse dialog text → `record_dialog_fact(DialogFact(...))` for hints/item locations ✅.
- **CritiqueAgent:** On objective completion or failure → update relevant memory.

## 3. Read / Retrieval ✅ P0

- **Key-based:** `get_warps_for_map(map_name)`, `get_known_items_on_map()`, `get_opponent_model(trainer)`, `get_map_knowledge()`.
- **Lightweight RAG:** `retrieve_relevant_facts("where is the potion in Viridian", current_map=...)` — returns top-k scored facts.
- **Prompt builders:** `build_navigation_memory_prompt(current_map)` ✅, `build_battle_memory_prompt(opponent)` ✅, `build_guide_memory_prompt()` ✅ — return compact strings (<200 tokens).

## 4. Battle Integration ✅ P0

- When battle detected, pass `memory.build_battle_memory_prompt(opponent_trainer)` into battle prompts ✅.
- OpponentModel updated live: moves_seen accumulated ✅.
- Type chart queried via `get_type_effectiveness()`.
- Battle history used to avoid repeat mistakes ✅.

## 5. Navigation Integration ✅ P0

- NavigationAgent prompt augmented with `memory.build_navigation_memory_prompt(current_map)` ✅.
- Prevents re-exploring same dead-ends via failure_memory + map_knowledge.
- Discovery-based: items/warps written on observation, read for path decisions.

## 6. Persistence ✅

- JSON files in `memory/` dir: `warps.json`, `items.json`, `battle_logs.json`, etc.
- `PokemonMemory(persist_dir="memory")` auto-loads on init, `save_all()` on shutdown or periodically.
- Human-readable, easy to inspect/edit for debugging.
- Across restarts: agent resumes with discovered knowledge.

## 7. Token Budget Strategy

- Never dump full memory. Use summarized builders that return 3-8 lines max.
- Top-k=3-5 for RAG facts.
- Short-term only last 5 events.
- For 4K-8K context: memory injection ~150-300 tokens per turn.
- Hierarchical: Guide gets high-level summary, Nav gets map-specific, Battle gets opponent-specific.
- Pruning: battle_logs maxlen=50, dialog_facts capped at ~80 high-confidence.

## Integration Points with Existing Code ✅ P0

1. **main_loop.py**: `self.memory = PokemonMemory()` in `StandaloneAgent.__init__` ✅
2. **main_loop.py**: After `executor.step()`, call memory record_* based on state diff ✅
3. **main_loop.py**: On shutdown: `self.memory.save_all()` ✅
4. **agents.py**: `build_navigation_prompt` accepts `memory_summary` ✅
5. **prompts.py**: Memory section in prompts ✅
6. **main_loop.py**: Warp transitions, battle ends trigger memory writes ✅

## Recommended Implementation Order

1. ~~Implement `PokemonMemory` class + dataclasses~~ ✅
2. ~~Add persistence tests + basic write/read~~ ✅
3. ~~Integrate into `StandaloneAgent`~~ ✅
4. ~~Update `prompts.py` to support memory injection~~ ✅
5. ~~Modify NavigationAgent and GuideAgent to accept/use memory summaries~~ ✅
6. ~~Add battle memory hooks~~ ✅
7. ~~Add dialog parsing hook for fact extraction~~ ✅
8. **Test on early game (Pallet → Viridian) focusing on warp + item discovery** ← current
9. **P1: Strengthen RAG retrieval (all stores, better scoring)**
10. **P1: Persist visited_tiles into MapKnowledge**
11. **P1: Objective-level summaries**
12. P2: Type matchup learning from battles
13. P2: Graph-based spatial memory (NetPlay room partitioning, TME DAG)

## Example Memory Entries

**Navigation (Warp):**
```json
{
  "Pallet Town_3_7": {
    "from_map": "Pallet Town", "from_x": 3, "from_y": 7,
    "to_map": "Route 1", "confidence": 1.0
  }
}
```

**Item:**
```json
{
  "map_name": "Viridian Forest", "x": 5, "y": 12,
  "item_name": "Poke Ball", "obtained": false, "notes": "hidden in grass"
}
```

**Battle:**
```json
{
  "opponent_trainer": "Brock",
  "opponent_pokemon": [{"species": "Geodude", "level": 12, "moves": ["Tackle", "Rock Throw"]}],
  "outcome": "win",
  "key_events": ["Used Water Gun super effective"]
}
```

**Dialog Fact:**
```json
{
  "npc_name": "Oak's Aide", "map_name": "Pallet Town",
  "fact": "The HM01 is in the house north of the lab",
  "category": "item_location"
}
```
