#!/usr/bin/env python3
"""Verifica colunas reais da tabela no Supabase e compara com schema.sql.

Uso:
  python verify_schema.py
  python verify_schema.py --table cuidadores --schema-name public
  python verify_schema.py --database-url "postgresql://..."
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


TABLE_CONSTRAINT_PREFIXES = (
    "constraint",
    "primary",
    "foreign",
    "unique",
    "check",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verifica colunas reais x esperadas no Supabase")
    parser.add_argument("--table", default="cuidadores", help="Tabela a verificar (padrão: cuidadores)")
    parser.add_argument("--schema-name", default="public", help="Schema PostgreSQL (padrão: public)")
    parser.add_argument(
        "--schema-file",
        default="schema.sql",
        help="Caminho do schema SQL esperado (padrão: schema.sql)",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="URL de conexão. Se omitido, usa DATABASE_URL do .env/ambiente",
    )
    return parser.parse_args()


def normalize_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    if normalized.startswith("postgresql+asyncpg://"):
        return normalized.replace("postgresql+asyncpg://", "postgresql://", 1)
    return normalized


def mask_database_url(database_url: str) -> str:
    if "://" not in database_url or "@" not in database_url:
        return database_url

    prefix, rest = database_url.split("://", 1)
    credentials, host = rest.split("@", 1)
    if ":" not in credentials:
        return f"{prefix}://***@{host}"

    user, _password = credentials.split(":", 1)
    return f"{prefix}://{user}:***@{host}"


def read_schema(schema_file: Path) -> str:
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema não encontrado: {schema_file}")
    content = schema_file.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"Schema vazio: {schema_file}")
    return content


def extract_expected_columns(schema_sql: str, table_name: str) -> list[str]:
    pattern = re.compile(
        rf"CREATE\s+TABLE\s+(?:[\w]+\.)?{re.escape(table_name)}\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(schema_sql)
    if not match:
        raise ValueError(f"Não foi possível localizar CREATE TABLE {table_name} no schema.sql")

    block = match.group(1)
    expected: list[str] = []

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        line = line.split("--", 1)[0].strip()
        if not line:
            continue

        line = line.rstrip(",").strip()
        if not line:
            continue

        lower_line = line.lower()
        if lower_line.startswith(TABLE_CONSTRAINT_PREFIXES):
            continue

        token = line.split()[0].strip('"')
        if token:
            expected.append(token)

    return expected


async def fetch_real_columns(database_url: str, schema_name: str, table_name: str) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(database_url)
    try:
        rows = await conn.fetch(
            """
            SELECT
              column_name,
              data_type,
              udt_name,
              is_nullable,
              column_default,
              ordinal_position
            FROM information_schema.columns
            WHERE table_schema = $1
              AND table_name = $2
            ORDER BY ordinal_position;
            """,
            schema_name,
            table_name,
        )
        return rows
    finally:
        await conn.close()


async def async_main() -> int:
    load_dotenv()
    args = parse_args()

    schema_path = Path(args.schema_file).expanduser().resolve()
    raw_database_url = args.database_url or os.getenv("DATABASE_URL", "")

    if not raw_database_url:
        print("[ERRO] DATABASE_URL não informada. Defina no .env ou passe --database-url.")
        return 1

    database_url = normalize_database_url(raw_database_url)

    try:
        schema_sql = read_schema(schema_path)
        expected_cols = extract_expected_columns(schema_sql, args.table)

        print(f"[INFO] Banco: {mask_database_url(database_url)}")
        print(f"[INFO] Tabela: {args.schema_name}.{args.table}")
        rows = await fetch_real_columns(database_url, args.schema_name, args.table)

        real_cols = [r["column_name"] for r in rows]

        print("\n=== COLUNAS ESPERADAS (schema.sql) ===")
        for col in expected_cols:
            print(f"- {col}")

        print("\n=== COLUNAS REAIS (Supabase) ===")
        if not rows:
            print("(nenhuma coluna encontrada - tabela inexistente ou sem acesso)")
        else:
            for r in rows:
                nullable = "NULL" if r["is_nullable"] == "YES" else "NOT NULL"
                default = r["column_default"] or "<sem default>"
                print(
                    f"- {r['ordinal_position']:02d}. {r['column_name']} "
                    f"| tipo={r['data_type']} ({r['udt_name']}) "
                    f"| {nullable} | default={default}"
                )

        missing = [c for c in expected_cols if c not in real_cols]
        extra = [c for c in real_cols if c not in expected_cols]

        print("\n=== DIFERENÇAS ===")
        print("Colunas faltantes no Supabase:")
        if missing:
            for c in missing:
                print(f"- {c}")
        else:
            print("- nenhuma")

        print("Colunas extras no Supabase (não estão no schema.sql):")
        if extra:
            for c in extra:
                print(f"- {c}")
        else:
            print("- nenhuma")

        return 0
    except Exception as exc:
        print(f"[ERRO] Falha na verificação: {exc}")
        return 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
