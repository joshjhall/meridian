"""Generate the synthetic 95-adjuster roster in demo/data/roster.json.

The extract pools 95 adjusters into 50 codes (ADJ-101..150); the demo treats
each code as one person and adds ADJ-151..195. 79 work T1-T2; 16 are T3
(12 seniors, 4 leads), and every T3 carries Bodily Injury. Five seniors are
specialists who never take T1, since juniors cover it: three work T2-T3 and
two T3 only. Specialists are picked from seniors with no open extract claims,
so no queue starts with work its owner can't take.

current_load is each adjuster's open claims in the extract ("Pending Review"
rows plus the six demo fixtures), the same claims the queues board shows, so
the board's load badge and the router's lightest-load pick start from one
count. Seeded, so reruns are byte-identical.

Run: uv run --project demo/backend python demo/data/gen_roster.py
"""

import json
import random
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "demo" / "backend"))

from claimspro_sim.store import seed_claims  # noqa: E402
from models import Adjuster, AdjusterRole, Skill, Tier  # noqa: E402

SEED = 2025
OUT = Path(__file__).resolve().parent / "roster.json"

FIRST = [
    "Avery",
    "Blake",
    "Camila",
    "Darius",
    "Elena",
    "Farah",
    "Gavin",
    "Hana",
    "Isaac",
    "Jada",
    "Kenji",
    "Lena",
    "Marcus",
    "Nadia",
    "Omar",
    "Priya",
    "Quinn",
    "Rosa",
    "Samir",
    "Tess",
    "Uma",
    "Victor",
    "Wren",
    "Xavier",
    "Yara",
    "Zane",
]
LAST = [
    "Abbott",
    "Bishop",
    "Castillo",
    "Delgado",
    "Ellis",
    "Fischer",
    "Grant",
    "Hoang",
    "Ibarra",
    "Jensen",
    "Kowalski",
    "Lindqvist",
    "Moreno",
    "Nakamura",
    "Osei",
    "Park",
    "Quintero",
    "Ramirez",
    "Sato",
    "Thornton",
    "Underwood",
    "Vance",
    "Whitaker",
    "Yilmaz",
    "Zimmerman",
]

TOTAL = 95
SENIORS = 12
LEADS = 4
T2_T3_SPECIALISTS = 3
T3_SPECIALISTS = 2


def build(seed: int = SEED) -> list[Adjuster]:
    rng = random.Random(seed)
    open_claims = Counter(c.adjuster_id for c in seed_claims())
    ids = [f"ADJ-{n}" for n in range(101, 101 + TOTAL)]
    names = rng.sample([f"{first} {last}" for first in FIRST for last in LAST], TOTAL)
    leads: list[AdjusterRole] = ["lead"] * LEADS
    seniors: list[AdjusterRole] = ["senior"] * SENIORS
    adjusters: list[AdjusterRole] = ["adjuster"] * (TOTAL - LEADS - SENIORS)
    roles = leads + seniors + adjusters
    rng.shuffle(roles)
    tiers = list(Tier)
    skills = list(Skill)

    roster = []
    for adj_id, name, role in zip(ids, names, roles, strict=True):
        if role == "adjuster":
            top = rng.choice(tiers[:-1])
            adj_tiers = tiers[: tiers.index(top) + 1]
            adj_skills = rng.sample(skills, rng.randint(1, 3))
        else:
            adj_tiers = tiers
            others = [s for s in skills if s is not Skill.BODILY_INJURY]
            adj_skills = [Skill.BODILY_INJURY, *rng.sample(others, rng.randint(1, 2))]
        # The old random load is still drawn, and dropped, so the seeded stream
        # (and every later adjuster's skills and tiers) stays as it was.
        rng.randint(0, 12)
        roster.append(
            Adjuster(
                id=adj_id,
                name=name,
                skills=sorted(adj_skills, key=skills.index),
                tiers=adj_tiers,
                role=role,
                current_load=open_claims[adj_id],
                extract_code=int(adj_id[4:]) <= 150,
            )
        )
    # Seniors with an empty queue, lowest IDs first, so the choice is stable.
    idle = [a for a in roster if a.role == "senior" and not open_claims[a.id]]
    specialists = T2_T3_SPECIALISTS + T3_SPECIALISTS
    if len(idle) < specialists:
        raise SystemExit(f"need {specialists} idle seniors for specialists, found {len(idle)}")
    for i, a in enumerate(idle[:specialists]):
        a.tiers = [Tier.T2, Tier.T3] if i < T2_T3_SPECIALISTS else [Tier.T3]
    return roster


def main() -> None:
    data = [a.model_dump(mode="json") for a in build()]
    OUT.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(REPO)} ({len(data)} adjusters)")


if __name__ == "__main__":
    main()
