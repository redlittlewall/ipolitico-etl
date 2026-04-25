"""
Configurações Globais do iPolitico ETL.
Centraliza os limites arquiteturais, variáveis de ambiente e tunning de performance.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Silencia logs verbosos de bibliotecas de infraestrutura
logging.getLogger("httpx").setLevel(logging.WARNING)

# --- Caminhos Base ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
SQLITE_DB_PATH = os.getenv("IPOLITICO_DB_PATH", str(BASE_DIR / "ipolitico.db"))

# --- Configurações da API Governamental ---
CAMARA_API_BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
LEGISLATURA_ATUAL = 57

# --- Tunning de Concorrência e Extração ---
# Limite de paginação da Câmara
CAMARA_PAGE_SIZE = 100

# Limite de Concorrência: Evita HTTP 429
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 10))
