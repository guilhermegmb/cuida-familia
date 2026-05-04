#!/usr/bin/env python3
"""Aplica o schema.sql no banco PostgreSQL/Supabase definido em DATABASE_URL.

Uso:
    python init_db.py
    python init_db.py --schema ./schema.sql
    python init_db.py --database-url "postgresql+asyncpg://..."
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aplicar schema SQL no Supabase/PostgreSQL")
    parser.add_argument(
        "--schema",
        default="schema.sql",
        help="Caminho do arquivo schema SQL (padrão: schema.sql)",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="URL de conexão. Se omitido, usa DATABASE_URL do ambiente/.env",
    )
    return parser.parse_args()


def normalize_database_url(database_url: str) -> str:
    """Converte URL SQLAlchemy async para formato aceito pelo asyncpg."""
    normalized = database_url.strip()
    if normalized.startswith("postgresql+asyncpg://"):
        return normalized.replace("postgresql+asyncpg://", "postgresql://", 1)
    return normalized


def read_schema_file(schema_path: Path) -> str:
    if not schema_path.exists():
        raise FileNotFoundError(f"Arquivo de schema não encontrado: {schema_path}")

    content = schema_path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Arquivo de schema vazio: {schema_path}")
    return content


async def apply_schema(database_url: str, schema_sql: str) -> None:
    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute(schema_sql)
    finally:
        await conn.close()


def mask_database_url(database_url: str) -> str:
    # Evita imprimir senha completa em logs.
    if "@" not in database_url or "://" not in database_url:
        return database_url

    prefix, rest = database_url.split("://", 1)
    if "@" not in rest:
        return database_url

    credentials, host = rest.split("@", 1)
    if ":" not in credentials:
        return f"{prefix}://***@{host}"

    user, _password = credentials.split(":", 1)
    return f"{prefix}://{user}:***@{host}"


async def async_main() -> int:
    load_dotenv()
    args = parse_args()

    schema_path = Path(args.schema).expanduser().resolve()
    raw_database_url = args.database_url or os.getenv("DATABASE_URL", "")

    if not raw_database_url:
        print("[ERRO] DATABASE_URL não informada. Defina no .env ou use --database-url.")
        return 1

    database_url = normalize_database_url(raw_database_url)

    try:
        print(f"[INFO] Lendo schema: {schema_path}")
        schema_sql = read_schema_file(schema_path)

        print(f"[INFO] Conectando no banco: {mask_database_url(database_url)}")
        await apply_schema(database_url, schema_sql)

        print("[OK] Schema aplicado com sucesso.")
        return 0
    except FileNotFoundError as exc:
        print(f"[ERRO] {exc}")
        return 1
    except (ValueError, asyncpg.PostgresError) as exc:
        print(f"[ERRO] Falha ao aplicar schema: {exc}")
        return 1
    except Exception as exc:  # fallback defensivo
        print(f"[ERRO] Falha inesperada: {exc}")
        return 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
