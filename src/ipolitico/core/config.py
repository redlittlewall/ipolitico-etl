import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega variáveis de ambiente de um arquivo .env, se existir
load_dotenv()

# Mantém logs de INFO ou superior, mas silencia logs de bibliotecas como httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

# Caminhos Base
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Configurações da API Governamental
CAMARA_API_BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
LEGISLATURA_ATUAL = 57

# Configurações de Armazenamento (Sinks)
SQLITE_DB_PATH = os.getenv("IPOLITICO_DB_PATH", str(BASE_DIR / "ipolitico.db"))
