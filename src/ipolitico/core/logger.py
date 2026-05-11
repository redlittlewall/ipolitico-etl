import logging
from pathlib import Path


def setup_logger(name: str) -> logging.Logger:
    """
    Configura e retorna um logger padronizado para a aplicação.

    Garante que os logs sejam salvos no diretório isolado de estado,
    aplicando o princípio de Separação de Preocupações (arquivos físicos
    isolados do código-fonte).

    Args:
        name (str): Nome do logger (geralmente __name__ do módulo).

    Returns:
        logging.Logger: Instância configurada do logger.
    """
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    log_dir = project_root / "data" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "ipolitico_etl.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
