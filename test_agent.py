#!/usr/bin/env python3
"""Teste local do AgentService via terminal (simulação de WhatsApp).

Uso:
    python test_agent.py
    python test_agent.py --phone +5511999999999
"""

from __future__ import annotations

import argparse
import asyncio

from dotenv import load_dotenv

from src.database.session import get_session_factory
from src.services.agent_service import AgentService
from src.utils.formatters import normalize_whatsapp_number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulador terminal do agente CuidaFamília")
    parser.add_argument(
        "--phone",
        default="+5511999999999",
        help="Número do cuidador em formato WhatsApp/E.164 (padrão: +5511999999999)",
    )
    return parser.parse_args()


async def run_terminal_chat(phone_number: str) -> None:
    session_factory = get_session_factory()
    agent = AgentService()

    print("\n=== CuidaFamília | Simulador de WhatsApp (Terminal) ===")
    print(f"Número simulado: {phone_number}")
    print("Comandos: /exit para sair | /help para ajuda\n")

    while True:
        user_text = input("Você: ").strip()

        if not user_text:
            print("[info] Mensagem vazia, tente novamente.\n")
            continue

        if user_text.lower() in {"/exit", "sair", "exit", "quit"}:
            print("Encerrando simulador. Até mais! 👋")
            break

        if user_text.lower() == "/help":
            print(
                "\nDicas rápidas:\n"
                "- Cadastre perfil: 'Meu nome é ...'\n"
                "- Cadastre pessoa cuidada: 'Cuido da minha mãe ...'\n"
                "- Lembretes: 'Me lembre de dar ... às 20h'\n"
                "- Alertas: descreva sintomas/ocorrências\n"
            )
            continue

        try:
            async with session_factory() as db:
                reply = await agent.process_incoming_message(
                    db=db,
                    from_phone=phone_number,
                    message_text=user_text,
                )
                print(f"Agente: {reply}\n")
        except Exception as exc:
            print(f"[erro] Falha ao processar mensagem: {exc}\n")


def main() -> int:
    load_dotenv()
    args = parse_args()
    phone_number = normalize_whatsapp_number(args.phone)

    asyncio.run(run_terminal_chat(phone_number))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
