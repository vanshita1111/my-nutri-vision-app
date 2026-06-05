"""
Build and seed the IFCT (Indian Food Composition Tables) data into PostgreSQL.

This script:
1. Reads the embedded_nutrition.json (curated IFCT values) from nutrition_engine
2. Seeds them into the 'foods' table in PostgreSQL

For the full IFCT 2017 dataset:
  - Download the Excel from: ifct2017.icmr.org.in
  - Place at: datasets/ifct2017_raw.xlsx
  - This script will parse and load all 528 entries

Usage:
    python datasets/build_ifct_db.py
"""

import asyncio
import json
import os
from pathlib import Path

import asyncpg


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://nutrition:nutrition@localhost:5432/nutrition_vision")
EMBEDDED_FILE = Path(__file__).parent.parent / "nutrition_engine" / "density_tables" / "embedded_nutrition.json"
IFCT_RAW = Path(__file__).parent / "ifct2017_raw.xlsx"


async def create_foods_table(conn):
    await conn.execute("""
        CREATE EXTENSION IF NOT EXISTS pg_trgm;

        CREATE TABLE IF NOT EXISTS foods (
            food_id             VARCHAR(50) PRIMARY KEY,
            name                TEXT NOT NULL,
            category            TEXT,
            source              VARCHAR(20) NOT NULL DEFAULT 'ifct',
            calories_per_100g   REAL,
            protein_g_per_100g  REAL,
            fat_g_per_100g      REAL,
            carbs_g_per_100g    REAL,
            fiber_g_per_100g    REAL,
            iron_mg_per_100g    REAL,
            calcium_mg_per_100g REAL,
            zinc_mg_per_100g    REAL,
            created_at          TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS foods_name_trgm_idx
            ON foods USING GIN (name gin_trgm_ops);
    """)
    print("foods table ready.")


async def seed_embedded(conn):
    """Seed from the embedded_nutrition.json curated table."""
    if not EMBEDDED_FILE.exists():
        print(f"Embedded file not found: {EMBEDDED_FILE}")
        return 0

    data = json.loads(EMBEDDED_FILE.read_text())
    count = 0

    for name, macros in data.items():
        if name.startswith("_"):
            continue
        food_id = name.lower().replace(" ", "_")
        await conn.execute("""
            INSERT INTO foods (food_id, name, source,
                calories_per_100g, protein_g_per_100g,
                fat_g_per_100g, carbs_g_per_100g, fiber_g_per_100g)
            VALUES ($1, $2, 'embedded', $3, $4, $5, $6, $7)
            ON CONFLICT (food_id) DO UPDATE SET
                calories_per_100g = EXCLUDED.calories_per_100g,
                protein_g_per_100g = EXCLUDED.protein_g_per_100g,
                fat_g_per_100g = EXCLUDED.fat_g_per_100g,
                carbs_g_per_100g = EXCLUDED.carbs_g_per_100g,
                fiber_g_per_100g = EXCLUDED.fiber_g_per_100g
        """,
            food_id, name,
            macros.get("calories"), macros.get("protein_g"),
            macros.get("fat_g"), macros.get("carbs_g"), macros.get("fiber_g"),
        )
        count += 1

    print(f"Seeded {count} items from embedded_nutrition.json")
    return count


async def seed_ifct_xlsx(conn):
    """Parse full IFCT 2017 Excel if available."""
    if not IFCT_RAW.exists():
        print(f"IFCT Excel not found at {IFCT_RAW}. Skipping full IFCT load.")
        print("Download from ifct2017.icmr.org.in and place at datasets/ifct2017_raw.xlsx")
        return 0

    try:
        import openpyxl
    except ImportError:
        print("openpyxl not installed. Run: pip install openpyxl")
        return 0

    wb = openpyxl.load_workbook(IFCT_RAW, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h).lower().strip() if h else "" for h in rows[0]]

    def col(h_name):
        try:
            return header.index(h_name)
        except ValueError:
            return None

    count = 0
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        name = str(row[0]).strip()
        food_id = f"ifct_{name.lower().replace(' ', '_')[:40]}"

        cal_col = col("energy (kcal)") or col("energy")
        prot_col = col("protein (g)") or col("protein")
        fat_col = col("total fat (g)") or col("fat")
        carb_col = col("carbohydrate (g)") or col("carbohydrate")
        fib_col = col("dietary fibre (g)") or col("fibre")

        def safe(c):
            try:
                return float(row[c]) if c is not None and row[c] is not None else None
            except (ValueError, TypeError):
                return None

        await conn.execute("""
            INSERT INTO foods (food_id, name, source,
                calories_per_100g, protein_g_per_100g,
                fat_g_per_100g, carbs_g_per_100g, fiber_g_per_100g)
            VALUES ($1, $2, 'ifct', $3, $4, $5, $6, $7)
            ON CONFLICT (food_id) DO NOTHING
        """, food_id, name, safe(cal_col), safe(prot_col), safe(fat_col), safe(carb_col), safe(fib_col))
        count += 1

    print(f"Loaded {count} IFCT entries from Excel.")
    return count


async def main():
    # Parse postgres DSN (asyncpg uses different format)
    dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    print(f"Connecting to {dsn.split('@')[-1]}...")

    conn = await asyncpg.connect(dsn)
    await create_foods_table(conn)
    await seed_embedded(conn)
    await seed_ifct_xlsx(conn)
    await conn.close()
    print("\nDone! Run 'make migrate' to apply full schema migrations.")


if __name__ == "__main__":
    asyncio.run(main())
