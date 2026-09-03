"""Seed des 122 indicateurs éducatifs depuis le manifeste JSON."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://togoqa:togoqa_dev@localhost:5432/togoqa",
)

MANIFEST = os.path.join(os.path.dirname(__file__), "../manifests/indicators.json")


def load_indicators():
    with open(MANIFEST, encoding="utf-8") as f:
        data = json.load(f)
    return data["indicators"]


def seed():
    engine = create_engine(DATABASE_URL)
    indicators = load_indicators()

    upsert_sql = text("""
        INSERT INTO indicators (code, label, definition, unit, aliases, category, meta)
        VALUES (:code, :label, :definition, :unit, :aliases, :category, :meta)
        ON CONFLICT (code) DO UPDATE SET
            label = EXCLUDED.label,
            definition = EXCLUDED.definition,
            unit = EXCLUDED.unit,
            aliases = EXCLUDED.aliases,
            category = EXCLUDED.category,
            meta = EXCLUDED.meta
    """)

    with engine.begin() as conn:
        for ind in indicators:
            meta = {}
            if ind.get("dimensions"):
                meta["dimensions"] = ind["dimensions"]
            if ind.get("value_type"):
                meta["value_type"] = ind["value_type"]
            if ind.get("formula"):
                meta["formula"] = ind["formula"]
            if ind.get("source_hints"):
                meta["source_hints"] = ind["source_hints"]
            if ind.get("notes"):
                meta["notes"] = ind["notes"]

            all_aliases = ind.get("aliases", [])

            conn.execute(upsert_sql, {
                "code": ind["code"],
                "label": ind["label"],
                "definition": ind.get("definition"),
                "unit": ind.get("unit", "nombre"),
                "aliases": all_aliases if all_aliases else None,
                "category": ind.get("category"),
                "meta": json.dumps(meta, ensure_ascii=False) if meta else None,
            })

    print(f"Seeded {len(indicators)} indicators.")


if __name__ == "__main__":
    seed()
