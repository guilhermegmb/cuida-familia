import logging
import json
from datetime import datetime


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_interacao(telefone: str, papel: str, mensagem: str):
    logger = get_logger("interacao")
    logger.info(f"[{papel.upper()}] {telefone} → {mensagem[:120]}{'...' if len(mensagem) > 120 else ''}")


def log_erro(evento: str, detalhes: dict = None, telefone: str = None):
    logger = get_logger("erro")
    info = f"EVENTO={evento}"
    if telefone:
        info += f" TELEFONE={telefone}"
    if detalhes:
        info += f" DETALHES={json.dumps(detalhes, ensure_ascii=False)}"
    logger.error(info)
