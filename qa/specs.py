"""Load persona and scenario specs from the QA directory."""
import json
from pathlib import Path

QA_DIR = Path(__file__).resolve().parent
PERSONAS_PATH = QA_DIR / "personas.json"
SCENARIO_DIR = QA_DIR / "scenarios"


def load_personas():
    data = json.loads(PERSONAS_PATH.read_text(encoding="utf-8"))
    return data["personas"]


def persona_by_id(persona_id):
    for persona in load_personas():
        if persona["id"] == persona_id:
            return persona
    choices = ", ".join(p["id"] for p in load_personas())
    raise ValueError(f"unknown persona '{persona_id}' (choose: {choices})")


def scenario_file(persona_id):
    matches = sorted(SCENARIO_DIR.glob(f"{persona_id}-*.json"))
    if not matches:
        raise FileNotFoundError(
            f"no scenario file for {persona_id} in {SCENARIO_DIR}; "
            "add one before running this persona"
        )
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches)
        raise ValueError(f"multiple scenario files for {persona_id}: {names}")
    return matches[0]


def load_scenarios(persona_id):
    path = scenario_file(persona_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("persona") != persona_id:
        raise ValueError(f"{path.name} declares persona {data.get('persona')!r}, not {persona_id!r}")
    scenarios = data.get("scenarios", [])
    ids = [scenario.get("id") for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate scenario ids in {path.name}")
    return scenarios


def load_scenario(persona_id, scenario_id):
    for scenario in load_scenarios(persona_id):
        if scenario["id"] == scenario_id:
            return scenario
    ids = ", ".join(s["id"] for s in load_scenarios(persona_id))
    raise ValueError(f"unknown scenario '{scenario_id}' for {persona_id} (choose: {ids})")
