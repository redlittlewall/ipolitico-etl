import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Estrutura de Pastas (Baseado no Plano Diretor)[cite: 2] ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"

# Caminhos para Bancos de Dados e Logs
DB_PATH = DATA_DIR / "dbs" / os.getenv("DB_NAME", "ipolitico_state.db")
TELEMETRY_PATH = DATA_DIR / "dbs" / "api_telemetry.db"
LOG_PATH = DATA_DIR / "logs" / "ipolitico_etl.log"
DATALAKE_DIR = DATA_DIR / "datalake"

# --- Configurações da Câmara ---
CAMARA_API_BASE_URL = os.getenv("CAMARA_API_BASE_URL", "https://dadosabertos.camara.leg.br/api/v2")
CAMARA_PAGE_SIZE = int(os.getenv("CAMARA_PAGE_SIZE", 1000))
LEGISLATURA_ATUAL = int(os.getenv("LEGISLATURA_ATUAL", 57))

# Teto do backoff exponencial do CamaraClient (2^attempt) em segundos.
# Sem teto, a tentativa 10 dormiria 1024s (~17min). 30s é o mesmo teto já
# usado por Senado/Senado-adm/Portal (wait_exponential max=30).
CAMARA_MAX_BACKOFF_S = int(os.getenv("CAMARA_MAX_BACKOFF_S", "30"))

# Nº de falhas CONSECUTIVAS de servidor (500/502/503/504) em um mesmo recurso
# que coloca o recurso em quarentena: dali em diante ele é pulado instantâneo
# até o fim da execução (quarentena é em memória, por processo). 429 NÃO conta
# — é rate-limit global, não recurso podre.
CAMARA_QUARANTINE_THRESHOLD = int(os.getenv("CAMARA_QUARANTINE_THRESHOLD", "3"))

# --- Configurações do Senado ---
SENADO_API_BASE_URL = os.getenv("SENADO_API_BASE_URL", "https://legis.senado.leg.br/dadosabertos")
SENADO_HTTP_CONCURRENCY = int(os.getenv("SENADO_HTTP_CONCURRENCY", "10"))

# --- Configurações do Senado (API administrativa adm-dadosabertos) ---
# Sem autenticação; base usada pelos extratores dos domínios (issues 07-09)
# para montar o ``_source_url``. Concorrência própria e conservadora, no mesmo
# patamar das demais fontes (semáforo global protege o servidor).
SENADO_ADM_API_BASE_URL = os.getenv(
    "SENADO_ADM_API_BASE_URL", "https://adm.senado.gov.br/adm-dadosabertos/api/v1"
)
SENADO_ADM_HTTP_CONCURRENCY = int(os.getenv("SENADO_ADM_HTTP_CONCURRENCY", "10"))

# --- Tuning de Performance ---
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 10))
# Limite de GETs simultâneos no CamaraClient (respeitar fair use da API).
# 10 req/s comprovado 100% seguro.
CAMARA_HTTP_CONCURRENCY = int(os.getenv("CAMARA_HTTP_CONCURRENCY", str(MAX_CONCURRENT_REQUESTS)))

# Configuração de Logging
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
