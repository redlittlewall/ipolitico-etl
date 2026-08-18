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

# --- Configurações do Portal da Transparência (CGU — Poder Executivo Federal) ---
# Autenticação por chave gratuita do usuário (header ``chave-api-dados`` na API v3).
# A chave real vive SÓ no .env local (gitignored) — nunca versionada. Cada usuário
# gera a própria no portal; sem chave, o cliente loga um aviso e as chamadas falham
# com 401 (PortalTransparenciaAuthError).
PORTAL_API_BASE_URL = os.getenv("PORTAL_API_BASE_URL", "https://api.portaldatransparencia.gov.br")
PORTAL_API_KEY = os.getenv("PORTAL_API_KEY", "")
PORTAL_HTTP_CONCURRENCY = int(os.getenv("PORTAL_HTTP_CONCURRENCY", "10"))

# Bulk /download-de-dados: base dos dumps ZIP/CSV (host público, sem chave) e
# diretório persistente onde os dumps são guardados. Persistir (em vez de temp
# descartável) permite ao ``PortalTransparenciaClient.download_file`` retomar
# downloads interrompidos via Range header sem recomeçar do zero.
PORTAL_BULK_BASE_URL = os.getenv(
    "PORTAL_BULK_BASE_URL", "https://portaldatransparencia.gov.br/download-de-dados"
)
PORTAL_BULK_DIR = Path(os.getenv("PORTAL_BULK_DIR", str(DATA_DIR / "portal_dumps")))

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
