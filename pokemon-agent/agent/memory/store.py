"""
Memory + RAG Store for Pokémon Red LLM Agent.

Practical design focused on:
- Structured key-based memory for navigation (warps, items) and battle (opponent models)
- Lightweight semantic notes for dialog/exploration facts (simple keyword + recency)
- JSON persistence
- Token-efficient injection (summaries + top-k retrieval)
- Integration with existing Guide/Nav/Critique agents

No heavy vector DB deps; uses dicts + simple scoring for retrieval.
"""

import json
import os
from collections import deque, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set


@dataclass
class WarpEntry:
    """Navigation: discovered warp connection."""
    from_map: str
    from_x: int
    from_y: int
    to_map: str
    to_x: Optional[int] = None
    to_y: Optional[int] = None
    confidence: float = 1.0  # 1.0 = confirmed by traversal
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ItemEntry:
    """Navigation: discovered item or hidden item location."""
    map_name: str
    x: int
    y: int
    item_name: str  # e.g. "Poke Ball", "hidden_item", or specific like "HM01"
    item_type: str = "item"  # item, hidden, npc_gift, pokeball, etc.
    obtained: bool = False
    notes: str = ""
    confidence: float = 1.0  # 1.0 = confirmed by direct observation, 0.5 = inferred/label only
    source: str = "observation"  # "observation" = read from dialog, "sprite_label" = from server label, "inferred" = guessed
    superseded_by: Optional[str] = None  # set to the item_name of the newer entry that contradicts this
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class BattleLogEntry:
    """Battle memory: one battle outcome + observations."""
    opponent_trainer: str  # e.g. "Youngster Joey" or "Gym Leader Brock"
    opponent_pokemon: List[Dict[str, Any]]  # seen pokemon with moves, levels
    player_pokemon_used: List[str]
    outcome: str  # "win", "lose", "flee"
    key_events: List[str] = field(default_factory=list)  # "enemy used Tackle", "super effective"
    damage_observations: List[Dict] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class OpponentModel:
    """Per-Pokemon or per-trainer model for opponent modeling."""
    name: str
    species: str
    level: Optional[int] = None
    moves_seen: Set[str] = field(default_factory=set)
    type: Optional[str] = None
    estimated_hp: Optional[int] = None
    status_effects_seen: List[str] = field(default_factory=list)
    last_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""  # e.g. "always leads with Tackle"


@dataclass
class DialogFact:
    """Dialog / NPC knowledge entry."""
    npc_name: str
    map_name: str
    fact: str  # extracted key information
    category: str  # "item_location", "hint", "story", "warp_info"
    confidence: float = 0.9
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class MapKnowledge:
    """Partial map layout knowledge (discovered tiles, connections)."""
    map_name: str
    known_tiles: Dict[Tuple[int, int], str] = field(default_factory=dict)  # (x,y) -> tile_type or "walkable"
    connections: List[str] = field(default_factory=list)  # adjacent maps
    last_visited: str = field(default_factory=lambda: datetime.now().isoformat())


class PokemonMemory:
    """
    Central memory module.
    - Long-term structured stores (JSON persisted)
    - Short-term working memory (recent events, current context)
    - Retrieval methods optimized for token budget
    """

    def __init__(self, persist_dir: str = "memory"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Long-term structured memory
        self.warps: Dict[str, WarpEntry] = {}  # key: f"{map}_{x}_{y}"
        self.items: List[ItemEntry] = []
        self.battle_logs: deque = deque(maxlen=50)  # recent battles
        self.opponent_models: Dict[str, OpponentModel] = {}  # key: species or trainer_pokemon
        self.dialog_facts: List[DialogFact] = []
        self.map_knowledge: Dict[str, MapKnowledge] = {}

        # Short-term / working memory
        self.recent_events: deque = deque(maxlen=20)
        self.current_map: Optional[str] = None
        self.known_type_matchups: Dict[str, Dict[str, float]] = self._init_type_chart()

        # Battle turn history (within-current-battle tracking)
        self.battle_turn_history: List[Dict[str, Any]] = []
        self._current_battle_active: bool = False

        # Failure / exploration memory (lightweight)
        self.exploration_failures: Dict[str, int] = defaultdict(int)  # (map, action) -> count

        self._load()

    def _init_type_chart(self) -> Dict[str, Dict[str, float]]:
        """Full Gen 1 type chart. Values: 0=immune, 0.5=not very, 1=normal, 2=super effective."""
        return {
            "Normal":   {"Rock": 0.5, "Ghost": 0.0},
            "Fire":     {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 2.0, "Bug": 2.0, "Rock": 0.5, "Dragon": 0.5},
            "Water":    {"Fire": 2.0, "Water": 0.5, "Grass": 0.5, "Ground": 2.0, "Rock": 2.0, "Dragon": 0.5},
            "Electric": {"Water": 2.0, "Electric": 0.5, "Grass": 0.5, "Ground": 0.0, "Flying": 2.0, "Dragon": 0.5},
            "Grass":    {"Fire": 0.5, "Water": 2.0, "Grass": 0.5, "Poison": 0.5, "Ground": 2.0, "Flying": 0.5, "Bug": 0.5, "Rock": 2.0, "Dragon": 0.5},
            "Ice":      {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 0.5, "Ground": 2.0, "Flying": 2.0, "Dragon": 2.0},
            "Fighting": {"Normal": 2.0, "Ice": 2.0, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2.0, "Ghost": 0.0},
            "Poison":   {"Grass": 2.0, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Bug": 2.0},
            "Ground":   {"Fire": 2.0, "Electric": 2.0, "Grass": 0.5, "Poison": 2.0, "Flying": 0.0, "Bug": 0.5, "Rock": 2.0},
            "Flying":   {"Electric": 0.5, "Grass": 2.0, "Fighting": 2.0, "Bug": 2.0, "Rock": 0.5},
            "Psychic":  {"Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5},
            "Bug":      {"Fire": 0.5, "Grass": 2.0, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Psychic": 2.0, "Ghost": 0.5},
            "Rock":     {"Fire": 2.0, "Ice": 2.0, "Fighting": 0.5, "Ground": 0.5, "Flying": 2.0, "Bug": 2.0},
            "Ghost":    {"Normal": 0.0, "Psychic": 2.0, "Ghost": 2.0},
            "Dragon":   {"Dragon": 2.0},
        }

    # ──────────────────────────────────────────────
    # WRITE TRIGGERS (called by agents / main_loop)
    # ──────────────────────────────────────────────

    def record_warp(self, from_map: str, from_x: int, from_y: int, to_map: str, **kwargs):
        key = f"{from_map}_{from_x}_{from_y}"
        entry = WarpEntry(from_map=from_map, from_x=from_x, from_y=from_y, to_map=to_map, **kwargs)
        self.warps[key] = entry
        self._save_category("warps")

    def record_item_discovery(self, map_name: str, x: int, y: int, item_name: str, **kwargs):
        entry = ItemEntry(map_name=map_name, x=x, y=y, item_name=item_name, **kwargs)
        # Check for existing entry at the same position
        existing_idx = None
        for i, prev in enumerate(self.items):
            if prev.map_name == map_name and prev.x == x and prev.y == y:
                existing_idx = i
                break
        if existing_idx is not None:
            prev = self.items[existing_idx]
            # Same name → update timestamp, don't duplicate
            if prev.item_name == item_name:
                prev.discovered_at = entry.discovered_at
                # Upgrade confidence if new source is better
                if entry.confidence > prev.confidence:
                    prev.confidence = entry.confidence
                    prev.source = entry.source
                if entry.notes:
                    prev.notes = entry.notes
                self._save_category("items")
                return
            # Different name → contradiction! Prefer higher confidence (observation > sprite_label)
            if entry.confidence >= prev.confidence:
                # New entry wins — mark old as superseded
                prev.superseded_by = item_name
                self.items.append(entry)
                print(f"  [Memory] Contradiction at ({x},{y}): was '{prev.item_name}' (conf={prev.confidence}), now '{item_name}' (conf={entry.confidence}) — old entry superseded")
            else:
                # Old entry has higher confidence — keep it, but note the contradiction
                entry.superseded_by = prev.item_name
                self.items.append(entry)
                print(f"  [Memory] Contradiction at ({x},{y}): new '{item_name}' (conf={entry.confidence}) conflicts with existing '{prev.item_name}' (conf={prev.confidence}) — keeping existing")
            self._save_category("items")
            return
        # No existing entry — just add
        self.items.append(entry)
        self._save_category("items")

    def record_battle(self, battle_log: BattleLogEntry):
        self.battle_logs.append(battle_log)
        # Update opponent models
        for p in battle_log.opponent_pokemon:
            key = f"{battle_log.opponent_trainer}_{p.get('species', 'unknown')}"
            if key not in self.opponent_models:
                self.opponent_models[key] = OpponentModel(
                    name=p.get('name', ''), species=p.get('species', '')
                )
            model = self.opponent_models[key]
            model.moves_seen.update(p.get('moves', []))
            if p.get('level'):
                model.level = p.get('level')
        self._save_category("battle_logs")
        self._save_category("opponent_models")

    def record_dialog_fact(self, fact: DialogFact):
        self.dialog_facts.append(fact)
        # Keep only recent + high confidence
        if len(self.dialog_facts) > 100:
            self.dialog_facts = sorted(self.dialog_facts, key=lambda f: f.confidence, reverse=True)[:80]
        self._save_category("dialog_facts")

    def update_map_knowledge(self, map_name: str, tiles: Optional[Dict[Tuple[int,int], str]] = None, connections: Optional[List[str]] = None):
        if map_name not in self.map_knowledge:
            self.map_knowledge[map_name] = MapKnowledge(map_name=map_name)
        mk = self.map_knowledge[map_name]
        if tiles:
            mk.known_tiles.update(tiles)
        if connections:
            mk.connections.extend([c for c in connections if c not in mk.connections])
        mk.last_visited = datetime.now().isoformat()
        self._save_category("map_knowledge")

    def record_event(self, event: str, metadata: Optional[Dict] = None):
        self.recent_events.append({"event": event, "meta": metadata or {}, "ts": datetime.now().isoformat()})

    # ──────────────────────────────────────────────
    # BATTLE HISTORY (within-current-battle tracking)
    # ──────────────────────────────────────────────

    def start_battle(self, opponent: str, battle_type: str = "wild"):
        """Call when battle starts. Resets turn history."""
        self._current_battle_active = True
        self.battle_turn_history = []
        self.record_event(f"Battle started vs {opponent}")

    def record_battle_turn(self, turn: int, action: str, result_summary: str,
                            enemy_hp: Optional[int] = None,
                            my_hp: Optional[int] = None,
                            enemy_move: Optional[str] = None,
                            my_move: Optional[str] = None,
                            effectiveness: Optional[str] = None):
        """Record one turn of battle history."""
        if not self._current_battle_active:
            self._current_battle_active = True
        entry = {
            "turn": turn,
            "action": action,
            "summary": result_summary,
            "enemy_hp": enemy_hp,
            "my_hp": my_hp,
            "enemy_move": enemy_move,
            "my_move": my_move,
            "effectiveness": effectiveness,
        }
        self.battle_turn_history.append(entry)

    def end_battle(self, outcome: str, opponent: str):
        """Call when battle ends. Records final state and archives."""
        self._current_battle_active = False
        self.record_event(f"Battle ended vs {opponent}: {outcome}")
        # Archive to battle logs
        log = BattleLogEntry(
            opponent_trainer=opponent,
            opponent_pokemon=[],  # filled by caller if available
            player_pokemon_used=[],
            outcome=outcome,
            key_events=[e["summary"] for e in self.battle_turn_history[-5:]],
        )
        self.battle_logs.append(log)
        self._save_category("battle_logs")
        # Keep turn history available for a bit, then clear
        # (it's short-lived by nature)

    def get_battle_history_summary(self, last_n: int = 3) -> str:
        """Get compact battle history for prompt injection."""
        if not self.battle_turn_history:
            return "No battle history yet."
        lines = []
        for entry in self.battle_turn_history[-last_n:]:
            turn = entry.get("turn", "?")
            summary = entry.get("summary", "")
            lines.append(f"Turn {turn}: {summary}")
        return "\n".join(lines)

    def is_battle_active(self) -> bool:
        return self._current_battle_active

    def record_exploration_failure(self, map_name: str, action: str):
        key = f"{map_name}:{action}"
        self.exploration_failures[key] += 1

    # ──────────────────────────────────────────────
    # READ / RETRIEVAL (key-based + lightweight semantic)
    # ──────────────────────────────────────────────

    def get_warps_for_map(self, map_name: str) -> List[WarpEntry]:
        return [w for w in self.warps.values() if w.from_map == map_name]

    def get_known_items_on_map(self, map_name: str, only_unobtained: bool = True) -> List[ItemEntry]:
        items = [i for i in self.items if i.map_name == map_name]
        if only_unobtained:
            items = [i for i in items if not i.obtained]
        return items

    def get_opponent_model(self, identifier: str) -> Optional[OpponentModel]:
        return self.opponent_models.get(identifier)

    def get_relevant_battle_history(self, opponent_name: str, limit: int = 5) -> List[BattleLogEntry]:
        return [b for b in list(self.battle_logs)[-limit:] if opponent_name.lower() in b.opponent_trainer.lower()]

    def get_dialog_facts(self, category: Optional[str] = None, map_name: Optional[str] = None, limit: int = 10) -> List[DialogFact]:
        facts = self.dialog_facts
        if category:
            facts = [f for f in facts if f.category == category]
        if map_name:
            facts = [f for f in facts if f.map_name == map_name]
        return sorted(facts, key=lambda f: f.timestamp, reverse=True)[:limit]

    def get_map_knowledge(self, map_name: str) -> Optional[MapKnowledge]:
        return self.map_knowledge.get(map_name)

    # Simple semantic retrieval for notes/facts (keyword overlap + recency)
    def retrieve_relevant_facts(self, query: str, top_k: int = 5, current_map: Optional[str] = None) -> List[Dict]:
        """Lightweight RAG: score facts by keyword overlap + recency + map relevance."""
        scored = []
        query_lower = query.lower()
        keywords = set(query_lower.split())

        for fact in [asdict(f) for f in self.dialog_facts] + [asdict(i) for i in self.items[-20:]]:  # mix dialog + recent items
            text = str(fact.get('fact', '')) + str(fact.get('item_name', '')) + str(fact.get('notes', ''))
            text_lower = text.lower()
            overlap = len(keywords & set(text_lower.split()))
            recency_bonus = 1.0  # could compute from timestamp
            map_bonus = 2.0 if current_map and fact.get('map_name') == current_map else 0.5
            score = overlap * 2 + recency_bonus + map_bonus
            if score > 0:
                scored.append((score, fact))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored[:top_k]]

    def get_type_effectiveness(self, move_type: str, defender_type: str) -> float:
        """Query type chart. Returns: 0=immune, 0.5=not very, 1=normal, 2=super effective."""
        chart = self.known_type_matchups.get(move_type, {})
        return chart.get(defender_type, 1.0)

    def get_short_term_summary(self) -> str:
        """Concise summary for prompt injection."""
        recent = list(self.recent_events)[-5:]
        return "\n".join([e["event"] for e in recent])

    # ──────────────────────────────────────────────
    # PROMPT INJECTION HELPERS (token efficient)
    # ──────────────────────────────────────────────

    def build_navigation_memory_prompt(self, current_map: str) -> str:
        """Build compact memory section for NavigationAgent."""
        parts = []
        warps = self.get_warps_for_map(current_map)
        if warps:
            parts.append("Known warps from here: " + ", ".join(f"({w.from_x},{w.from_y})→{w.to_map}" for w in warps[:3]))

        items = self.get_known_items_on_map(current_map)
        if items:
            # Filter out superseded entries, sort by confidence
            active = [i for i in items if i.superseded_by is None]
            superseded = [i for i in items if i.superseded_by is not None]
            if active:
                item_lines = []
                for i in sorted(active, key=lambda x: -x.confidence):
                    source_tag = ""
                    if i.source == "sprite_label":
                        source_tag = " [label only, unverified]"
                    elif i.source == "observation":
                        source_tag = " [confirmed by dialog]"
                    item_lines.append(f"{i.item_name} at ({i.x},{i.y}){source_tag}")
                parts.append("Known items here: " + "; ".join(item_lines[:4]))
            if superseded:
                # Show contradictions as warnings
                for i in superseded[:2]:
                    parts.append(f"⚠ CONTRADICTION at ({i.x},{i.y}): memory said '{i.item_name}' but later found '{i.superseded_by}'")

        mk = self.get_map_knowledge(current_map)
        if mk and mk.known_tiles:
            parts.append(f"Explored {len(mk.known_tiles)} tiles on this map.")

        facts = self.retrieve_relevant_facts(f"items locations warps on {current_map}", top_k=3, current_map=current_map)
        if facts:
            parts.append("Relevant knowledge: " + "; ".join(str(f)[:80] for f in facts))

        return "\n".join(parts) if parts else "No prior memory for this map."

    def build_battle_memory_prompt(self, opponent_trainer: str) -> str:
        """Build opponent model summary for battle decisions."""
        models = [m for m in self.opponent_models.values() if opponent_trainer.lower() in m.name.lower() or any(opponent_trainer.lower() in k.lower() for k in self.opponent_models)]
        if not models:
            return "No prior battle data on this opponent."

        lines = []
        for m in models[:2]:
            moves = ", ".join(list(m.moves_seen)[:3]) if m.moves_seen else "unknown moves"
            lines.append(f"- {m.species} (lv{m.level}): moves seen [{moves}]")
        history = self.get_relevant_battle_history(opponent_trainer, limit=2)
        if history:
            lines.append(f"Recent outcome: {history[0].outcome}")
        return "\n".join(lines)

    def build_guide_memory_prompt(self) -> str:
        """High-level facts for GuideAgent objective selection."""
        recent_battles = len(self.battle_logs)
        known_maps = len(self.map_knowledge)
        items_found = len([i for i in self.items if not i.obtained])
        return f"Memory summary: {recent_battles} battles logged, {known_maps} maps partially known, {items_found} items discovered but not obtained."

    # ──────────────────────────────────────────────
    # PERSISTENCE
    # ──────────────────────────────────────────────

    def _save_category(self, category: str):
        path = self.persist_dir / f"{category}.json"
        data = {}
        if category == "warps":
            data = {k: asdict(v) for k, v in self.warps.items()}
        elif category == "items":
            data = [asdict(i) for i in self.items]
        elif category == "battle_logs":
            data = [asdict(b) for b in self.battle_logs]
        elif category == "dialog_facts":
            data = [asdict(f) for f in self.dialog_facts]
        elif category == "map_knowledge":
            data = {}
            for k, v in self.map_knowledge.items():
                d = asdict(v)
                # Convert tuple keys (x,y) -> "x,y" strings for JSON
                if d.get("known_tiles"):
                    d["known_tiles"] = {f"{x},{y}": t for (x, y), t in d["known_tiles"].items()}
                data[k] = d
        elif category == "opponent_models":
            data = {}
            for k, v in self.opponent_models.items():
                d = asdict(v)
                # Convert sets to lists for JSON
                if isinstance(d.get("moves_seen"), (set, frozenset)):
                    d["moves_seen"] = sorted(d["moves_seen"])
                data[k] = d
        path.write_text(json.dumps(data, indent=2, default=str))

    def _load(self):
        for category in ["warps", "items", "battle_logs", "opponent_models", "dialog_facts", "map_knowledge"]:
            path = self.persist_dir / f"{category}.json"
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text())
                if category == "warps":
                    self.warps = {k: WarpEntry(**v) for k, v in data.items()}
                elif category == "items":
                    self.items = [ItemEntry(**i) for i in data]
                elif category == "battle_logs":
                    self.battle_logs = deque([BattleLogEntry(**b) for b in data], maxlen=50)
                elif category == "opponent_models":
                    self.opponent_models = {}
                    for k, v in data.items():
                        if "moves_seen" in v and isinstance(v["moves_seen"], list):
                            v["moves_seen"] = set(v["moves_seen"])
                        self.opponent_models[k] = OpponentModel(**v)
                elif category == "dialog_facts":
                    self.dialog_facts = [DialogFact(**f) for f in data]
                elif category == "map_knowledge":
                    self.map_knowledge = {}
                    for k, v in data.items():
                        if "known_tiles" in v and isinstance(v["known_tiles"], dict):
                            v["known_tiles"] = {
                                (int(s.split(",")[0]), int(s.split(",")[1])): t
                                for s, t in v["known_tiles"].items()
                            }
                        self.map_knowledge[k] = MapKnowledge(**v)
            except Exception as e:
                print(f"[Memory] Failed to load {category}: {e}")

    def save_all(self):
        for cat in ["warps", "items", "battle_logs", "opponent_models", "dialog_facts", "map_knowledge"]:
            self._save_category(cat)

    def clear_short_term(self):
        self.recent_events.clear()

    def record_building_exit(self, building_name: str, outside_map: str, exit_pos: Tuple[int, int]):
        """Record that we just exited a building. Used to prevent immediately re-entering."""
        self.recent_events.append({
            "event": "building_exit",
            "building": building_name,
            "outside_map": outside_map,
            "exit_pos": list(exit_pos),
            "ts": datetime.now().isoformat()
        })
        if len(self.recent_events) > 10:
            self.recent_events = self.recent_events[-10:]

    def get_recently_exited_buildings(self, within_seconds: int = 300) -> List[str]:
        """Get list of building names we recently exited (to avoid re-entering)."""
        now = datetime.now()
        recent = []
        for evt in reversed(self.recent_events):
            if evt.get("event") == "building_exit":
                try:
                    ts = datetime.fromisoformat(evt["ts"])
                    if (now - ts).total_seconds() < within_seconds:
                        recent.append(evt["building"])
                except:
                    pass
        return recent
