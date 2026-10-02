"""Generate the synthetic 95-adjuster roster in demo/data/roster.json.

The extract pools 95 adjusters into 50 codes (ADJ-101..150); the demo treats
each code as one person and adds ADJ-151..195. 79 work T1-T2; 16 are T3
(12 seniors, 4 leads), and every T3 carries Bodily Injury. Seeded, so reruns
are byte-identical.

Run: uv run --project demo/backend python demo/data/gen_roster.py
"""

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "demo" / "backend"))

from models import Adjuster, Skill, Tier  # noqa: E402

SEED = 2025
OUT = Path(__file__).resolve().parent / "roster.json"

FIRST = [
    "Avery", "Blake", "Camila", "Darius", "Elena", "Farah", "Gavin", "Hana", "Isaac", "Jada",
    "Kenji", "Lena", "Marcus", "Nadia", "Omar", "Priya", "Quinn", "Rosa", "Samir", "Tess",
    "Uma", "Victor", "Wren", "Xavier", "Yara", "Zane",
]
LAST = [
    "Abbott", "Bishop", "Castillo", "Delgado", "Ellis", "Fischer", "Grant", "Hoang", "Ibarra",
    "Jensen", "Kowalski", "Lindqvist", "Moreno", "Nakamura", "Osei", "Park", "Quintero",
    "Ramirez", "Sato", "Thornton", "Underwood", "Vance", "Whitaker", "Yilmaz", "Zimmerman",
]

TOTAL = 95
SENIORS = 12
LEADS = 4


def build(seed: int = SEED) -> list[Adjuster]:
    rng = random.Random(seed)
    ids = [f"ADJ-{n}" for n in range(101, 101 + TOTAL)]
    names = rng.sample([f"{f} {l}" for f in FIRST for l in LAST], TOTAL)
    roles = ["lead"] * LEADS + ["senior"] * SENIORS + ["adjuster"] * (TOTAL - LEADS - SENIORS)
    rng.shuffle(roles)
    tiers = list(Tier)
    skills = list(Skill)

    roster = []
    for adj_id, name, role in zip(ids, names, roles):
        if role == "adjuster":
            top = rng.choice(tiers[:-1])
            adj_tiers = tiers[: tiers.index(top) + 1]
            adj_skills = rng.sample(skills, rng.randint(1, 3))
        else:
            adj_tiers = tiers
            others = [s for s in skills if s is not Skill.BODILY_INJURY]
            adj_skills = [Skill.BODILY_INJURY, *rng.sample(others, rng.randint(1, 2))]
        roster.append(
            Adjuster(
                id=adj_id,
                name=name,
                skills=sorted(adj_skills, key=skills.index),
                tiers=adj_tiers,
                role=role,
                current_load=rng.randint(0, 12),
                extract_code=int(adj_id[4:]) <= 150,
            )
        )
    return roster


def main() -> None:
    data = [a.model_dump(mode="json") for a in build()]
    OUT.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(REPO)} ({len(data)} adjusters)")


if __name__ == "__main__":
    main()
