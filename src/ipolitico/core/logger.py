import logging
import os

from rich.logging import RichHandler


def setup_logger():
    """
    Configura o padrão Dual-Logging:
    1. RichHandler (Console): Formatação visual limpa, sem rastros verbosos.
    2. FileHandler (Arquivo): Log persistente e detalhado para debug de infraestrutura.
    """
    log_format_file = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_format_console = "%(message)s"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Limpa handlers antigos se houver
    if logger.hasHandlers():
        logger.handlers.clear()

    # Handler do Terminal (UX Rica)
    console_handler = RichHandler(rich_tracebacks=True, show_path=False)
    console_handler.setFormatter(logging.Formatter(log_format_console))
    logger.addHandler(console_handler)

    # Handler de Arquivo (Auditoria e Debug)
    log_file = os.getenv("IPOLITICO_LOG_FILE", "ipolitico_etl.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(log_format_file))
    # Para o arquivo, queremos capturar TUDO, inclusive nível DEBUG
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    # Silencia o barulho excessivo das bibliotecas HTTP base
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return logger
