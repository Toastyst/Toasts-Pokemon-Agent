"""
Battle Agent — Knowledge-augmented battle decision maker for Pokémon Red.

Uses:
- Full Gen 1 type chart (from Memory)
- Battle turn history (within-battle tracking)
- Opponent modeling (from Memory)
- Scripted safety net for obviously bad moves
- Gym leader knowledge base (from pokemon-red-guide data)
"""

from typing import Any, Dict, List, Optional, Tuple


# ── Gen 1 Gym Leader Knowledge Base ──────────────────────────────────
# Extracted from pokemon-red-guide/06_battle_system.md Section 6.4-6.7
GYM_LEADER_KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    "Rival": {
        "description": "Your rival Blue/Gary. Starter depends on your choice.",
        "strategy": "Use super effective moves. Your starter is level 5, his is level 5. Tackle/Scratch/Vine Whip all work.",
    },
    "Brock": {
        "description": "Pewter Gym. Rock/Ground types.",
        "team": ["Geodude Lv12", "Onix Lv14"],
        "super_effective": ["Water", "Grass", "Fighting", "Ice"],
        "not_very_effective": ["Normal", "Fire", "Electric", "Poison", "Flying"],
        "strategy": "Water/Grass moves are 2×. Onix uses Screech (lowers your Defense). Bide stores damage — use weak moves until ready.",
    },
    "Misty": {
        "description": "Cerulean Gym. Water types.",
        "team": ["Staryu Lv18", "Starmie Lv21"],
        "super_effective": ["Electric", "Grass"],
        "strategy": "Electric moves are 2×. Starmie has high Special/Speed. Keep HP high.",
    },
    "Lt. Surge": {
        "description": "Vermilion Gym. Electric types.",
        "team": ["Voltorb Lv21", "Pikachu Lv18", "Raichu Lv24"],
        "super_effective": ["Ground"],
        "immune": ["Ground"],
        "strategy": "Ground moves are immune to Electric AND super effective. Raichu has Thunderbolt — keep HP above 40%.",
    },
    "Erika": {
        "description": "Celadon Gym. Grass types.",
        "team": ["Victreebel Lv29", "Tangela Lv24", "Vileplume Lv29"],
        "super_effective": ["Fire", "Ice", "Flying", "Bug", "Psychic"],
        "strategy": "Fire moves are 4× vs Victreebel. Sleep Powder can incapacitate — kill quickly.",
    },
    "Koga": {
        "description": "Fuchsia Gym. Poison types.",
        "team": ["Koffing Lv37", "Muk Lv39", "Koffing Lv37", "Weezing Lv43"],
        "super_effective": ["Psychic", "Ground"],
        "strategy": "Toxic from Weezing is very dangerous — damage increases each turn. Use Psychic to sweep.",
    },
    "Sabrina": {
        "description": "Saffron Gym. Psychic types.",
        "team": ["Kadabra Lv38", "Mr. Mime Lv37", "Venomoth Lv38", "Alakazam Lv43"],
        "super_effective": ["Bug"],
        "note": "In Gen 1, Ghost moves have NO effect on Psychic (bug). Only Bug is super effective. Use strong physical attackers or level advantage.",
        "strategy": "Psychic types have NO weakness from Ghost in Gen 1. Use strong physical Normal moves or Bug moves. Alakazam is very fast.",
    },
    "Blaine": {
        "description": "Cinnabar Gym. Fire types.",
        "team": ["Growlithe Lv42", "Ponyta Lv40", "Rapidash Lv42", "Arcanine Lv47"],
        "super_effective": ["Water", "Rock", "Ground"],
        "strategy": "Water moves are 2×. Arcanine is fast and powerful with Take Down recoil.",
    },
    "Giovanni": {
        "description": "Viridian Gym. Ground/Rock types.",
        "team": ["Rhyhorn Lv45", "Dugtrio Lv42", "Nidoqueen Lv44", "Nidoking Lv45", "Rhydon Lv50"],
        "super_effective": ["Water", "Grass", "Ice"],
        "strategy": "Water moves are 4× vs Rhyhorn/Rhydon. Grass from Venusaur is 4×. Surf from Blastoise works on all.",
    },
}


def get_gym_leader_info(trainer_name: str) -> Optional[Dict[str, Any]]:
    """Look up gym leader knowledge by name (fuzzy match)."""
    name_lower = trainer_name.lower()
    for key, info in GYM_LEADER_KNOWLEDGE.items():
        if key.lower() in name_lower or name_lower in key.lower():
            return info
    return None


def build_type_chart_summary() -> str:
    """Compact type chart summary for prompt injection (~150 tokens)."""
    return """GEN 1 TYPE CHART (key matchups):
Fire > Grass/Ice/Bug | Fire < Water/Rock
Water > Fire/Ground/Rock | Water < Grass/Electric
Grass > Water/Ground/Rock | Grass < Fire/Ice/Poison/Bug/Flying
Electric > Water/Flying | Electric < Ground | Electric: 0 vs Ground
Ground > Fire/Electric/Poison/Rock | Ground < Grass/Bug | Ground: 0 vs Flying
Psychic > Fighting/Poison | Psychic < Bug | Psychic: IMMUNE to Ghost (Gen1 bug)
Fighting > Normal/Ice/Rock | Fighting < Poison/Bug/Flying/Psychic | Fighting: 0 vs Ghost
Ghost > Psychic/Ghost | Ghost < nothing super | Ghost: 0 vs Normal (immune both ways)
Ice > Grass/Ground/Flying/Dragon | Ice < Fire/Water/Ice
Dragon > Dragon | Dragon < nothing super
STAB bonus: 1.5× when move type matches Pokemon type
Effectiveness: 2× super, 0.5× not very, 0× immune"""


def build_battle_prompt(
    battle_state: Dict[str, Any],
    memory: Any,  # PokemonMemory
    turn_history: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """
    Build knowledge-augmented battle prompt.

    Returns (system_prompt, user_prompt) tuple.
    """
    enemy = battle_state.get("battle", {}).get("enemy", {})
    party = battle_state.get("party", [])
    my_mon = party[0] if party else {}
    trainer_name = battle_state.get("battle", {}).get("trainer_name", "")
    battle_type = battle_state.get("battle", {}).get("type", "wild")

    # ── System prompt: type chart + decision framework ──
    system = f"""You are the Battle Agent for Pokémon Red. Choose ONE battle action per turn.

{build_type_chart_summary()}

BATTLE MENU: FIGHT (default) → A, then Down N for move N, A.
RUN = Down+Right from FIGHT menu, then A.
POKEMON MENU: Right 1 from FIGHT → A, then down N for pokemon N+1 → A (switch), A (confirm).
ITEM = Down 1 from FIGHT.

DECISION PRIORITY:
1. If enemy HP is low → use strongest move to finish
2. If your HP < 25% → use recovery item or switch to tankier Pokemon
3. If you have a super effective move → use it (2× or 4× damage)
4. If STAB move available (same type as your Pokemon) → use strongest STAB
5. Otherwise → use highest power neutral move
6. If all Pokemon are fainted → blackout (automatic)

GEN 1 QUIRKS:
- Psychic types are IMMUNE to Ghost moves (bug)
- Ghost moves have NO effect on Normal types
- Special stat = both Sp.Atk AND Sp.Def
- Crits based on Speed
- Wrap/Bind traps opponent (they can't act)
- Focus Energy REDUCES crit rate (bug)"""

    # ── User prompt: current state + history + knowledge ──
    enemy_species = enemy.get("species", "?")
    enemy_level = enemy.get("level", "?")
    enemy_hp = enemy.get("hp", "?")
    enemy_max_hp = enemy.get("max_hp", "?")
    enemy_status = enemy.get("status", "none")
    enemy_types = enemy.get("types", [])

    my_species = my_mon.get("species", "?")
    my_level = my_mon.get("level", "?")
    my_hp = my_mon.get("hp", "?")
    my_max_hp = my_mon.get("max_hp", "?")
    my_status = my_mon.get("status", "none")
    my_types = my_mon.get("types", [])
    my_moves = my_mon.get("moves", [])
    my_pp = my_mon.get("pp", [])

    # Format moves with PP
    moves_str = ""
    for i, move in enumerate(my_moves):
        if isinstance(move, dict):
            name = move.get("name", "?")
            pp = my_pp[i] if i < len(my_pp) else "?"
            move_type = move.get("type", "?")
            power = move.get("power", "?")
            moves_str += f"  Move{i+1}: {name} ({move_type}, PWR:{power}, PP:{pp})\n"
        else:
            moves_str += f"  Move{i+1}: {move}\n"

    # Party status
    party_str = ""
    for i, mon in enumerate(party):
        active = " ← ACTIVE" if i == 0 else ""
        party_str += f"  Slot{i+1}: {mon.get('species','?')} Lv{mon.get('level','?')} HP {mon.get('hp','?')}/{mon.get('max_hp','?')}{active}\n"

    # Opponent model from memory
    opponent_info = ""
    if memory and trainer_name:
        opp_model = memory.get_opponent_model(trainer_name)
        if opp_model and opp_model.moves_seen:
            opponent_info = f"\nOPPONENT MEMORY: {opp_model.species} — moves seen: {', '.join(opp_model.moves_seen)}\n"

    # Gym leader knowledge
    gym_info = ""
    if trainer_name:
        gym = get_gym_leader_info(trainer_name)
        if gym:
            gym_info = f"\nGYM LEADER KNOWLEDGE: {gym.get('description', '')}\n"
            if "super_effective" in gym:
                gym_info += f"  Super effective types: {', '.join(gym['super_effective'])}\n"
            if "strategy" in gym:
                gym_info += f"  Strategy: {gym['strategy'][:100]}\n"

    # Turn history
    history_str = ""
    if turn_history:
        history_str = "\nBATTLE HISTORY (last 3 turns):\n"
        for entry in turn_history[-3:]:
            history_str += f"  Turn {entry.get('turn', '?')}: {entry.get('summary', '')}\n"

    # Memory battle history (from previous battles vs this opponent)
    memory_battle_str = ""
    if memory:
        mem_summary = memory.get_battle_history_summary(last_n=3)
        if mem_summary and "No battle history" not in mem_summary:
            memory_battle_str = f"\nPREVIOUS BATTLE VS THIS OPPONENT:\n{mem_summary}\n"

    # Type effectiveness analysis
    effectiveness_analysis = ""
    if my_moves and enemy_types:
        effectiveness_analysis = "\nTYPE ANALYSIS:\n"
        for i, move in enumerate(my_moves):
            if isinstance(move, dict):
                move_type = move.get("type", "")
                move_name = move.get("name", f"Move{i+1}")
                if move_type and memory:
                    eff_text = []
                    for et in enemy_types:
                        eff = memory.get_type_effectiveness(move_type, et)
                        if eff == 0.0:
                            eff_text.append(f"IMMUNE vs {et}")
                        elif eff == 0.5:
                            eff_text.append(f"not very vs {et}")
                        elif eff >= 2.0:
                            eff_text.append(f"SUPER vs {et}")
                    if eff_text:
                        effectiveness_analysis += f"  {move_name}: {', '.join(eff_text)}\n"

    user = f"""=== BATTLE STATE ===
{'Trainer' if battle_type == 'trainer' else 'Wild'} battle vs {enemy_species} Lv{enemy_level}
Enemy HP: {enemy_hp}/{enemy_max_hp} | Status: {enemy_status} | Types: {', '.join(enemy_types) if enemy_types else 'unknown'}

Your Pokemon: {my_species} Lv{my_level}
Your HP: {my_hp}/{my_max_hp} | Status: {my_status} | Types: {', '.join(my_types) if my_types else 'unknown'}
Moves:
{moves_str}
Party:
{party_str}{opponent_info}{gym_info}{history_str}{memory_battle_str}{effectiveness_analysis}

Choose ONE action: fight_move1, fight_move2, fight_move3, fight_move4, run, switch_N (e.g. switch_2), or item.
Output ONLY the action on the LAST LINE."""

    return system, user


def parse_battle_action(response: str) -> str:
    """Parse battle action from LLM response."""
    if not response:
        return "fight_move1"

    last_line = response.strip().split("\n")[-1].lower().strip()

    # Check for specific actions
    if "run" in last_line:
        return "run"
    if "switch_2" in last_line or "switch 2" in last_line:
        return "switch_2"
    if "switch_3" in last_line or "switch 3" in last_line:
        return "switch_3"
    if "item" in last_line:
        return "item"
    if "move4" in last_line or "move_4" in last_line:
        return "fight_move4"
    if "move3" in last_line or "move_3" in last_line:
        return "fight_move3"
    if "move2" in last_line or "move_2" in last_line:
        return "fight_move2"
    if "move1" in last_line or "move_1" in last_line:
        return "fight_move1"

    # Fallback: check full response
    lower = response.lower()
    if "run" in lower:
        return "run"
    if "switch" in lower:
        return "switch_2"  # default to slot 2
    if "item" in lower:
        return "item"

    return "fight_move1"  # safest default


def safety_net_override(
    action: str,
    battle_state: Dict[str, Any],
    memory: Any,
) -> str:
    """
    Scripted safety net — override obviously bad LLM decisions.
    Returns the (possibly overridden) action.
    """
    enemy = battle_state.get("battle", {}).get("enemy", {})
    party = battle_state.get("party", [])
    my_mon = party[0] if party else {}
    enemy_types = enemy.get("types", [])
    my_moves = my_mon.get("moves", [])
    my_hp = my_mon.get("hp", 0)
    my_max_hp = my_mon.get("max_hp", 1)

    # Find the selected move
    move_idx = 0
    if action == "fight_move2":
        move_idx = 1
    elif action == "fight_move3":
        move_idx = 2
    elif action == "fight_move4":
        move_idx = 3

    if my_moves and move_idx < len(my_moves):
        move = my_moves[move_idx]
        if isinstance(move, dict):
            move_type = move.get("type", "")
            move_name = move.get("name", "")

            # Check for immune moves
            if move_type and enemy_types and memory:
                for et in enemy_types:
                    eff = memory.get_type_effectiveness(move_type, et)
                    if eff == 0.0:
                        # Move is immune — find a better one
                        for i, alt_move in enumerate(my_moves):
                            if isinstance(alt_move, dict):
                                alt_type = alt_move.get("type", "")
                                if alt_type:
                                    alt_eff = memory.get_type_effectiveness(alt_type, et)
                                    if alt_eff > 0:
                                        return f"fight_move{i+1}"
                        # All moves immune? Use fight as last resort
                        break

    # Low HP safety: if below 15% and no healing, try to run (wild only)
    if my_hp > 0 and my_max_hp > 0:
        hp_pct = my_hp / my_max_hp
        if hp_pct < 0.15 and battle_state.get("battle", {}).get("type") == "wild":
            # Only run if we have other Pokemon alive
            alive = sum(1 for m in party if m.get("hp", 0) > 0)
            if alive > 1:
                return "switch_2"

    return action
