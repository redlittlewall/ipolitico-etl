import pytest
import respx

from ipolitico.core.client import CamaraClient
from ipolitico.core.constants import DomainType
from ipolitico.core.warmup import WARMUP_CONFIG, WarmupSpec, build_warmup_urls

BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"


class TestWarmupSpec:
    """Testes para o módulo warmup.py — WarmupSpec e build_warmup_urls."""

    def test_warmup_config_has_only_known_domains(self):
        """WARMUP_CONFIG deve conter apenas os 3 domínios 504-prone."""
        expected = {
            DomainType.DEPUTADOS_HISTORICO,
            DomainType.EVENTOS_PAUTA,
            DomainType.RELACIONADAS,
        }
        assert set(WARMUP_CONFIG.keys()) == expected

    def test_build_warmup_urls_single_key(self):
        """build_warmup_urls com id_keys = ["deputado_id"] e lista de jobs."""
        spec = WARMUP_CONFIG[DomainType.DEPUTADOS_HISTORICO]
        jobs = [
            {"deputado_id": 178957},
            {"deputado_id": 74186},
            {"deputado_id": 178957},  # duplicata
        ]
        urls = build_warmup_urls(BASE_URL, jobs, spec)
        assert len(urls) == 2  # deduplicado
        assert f"{BASE_URL}/deputados/178957/historico" in urls
        assert f"{BASE_URL}/deputados/74186/historico" in urls

    def test_build_warmup_urls_list_key(self):
        """build_warmup_urls com is_list_key=True acha valores de lista."""
        spec = WARMUP_CONFIG[DomainType.EVENTOS_PAUTA]
        jobs = [
            {"evento_ids": [100, 200]},
            {"evento_ids": [200, 300]},  # 200 repetido
        ]
        urls = build_warmup_urls(BASE_URL, jobs, spec)
        assert len(urls) == 3  # 100, 200, 300
        assert f"{BASE_URL}/eventos/100/pauta" in urls
        assert f"{BASE_URL}/eventos/200/pauta" in urls
        assert f"{BASE_URL}/eventos/300/pauta" in urls

    def test_build_warmup_urls_empty_jobs(self):
        """build_warmup_urls com jobs vazio retorna lista vazia."""
        spec = WARMUP_CONFIG[DomainType.DEPUTADOS_HISTORICO]
        assert build_warmup_urls(BASE_URL, [], spec) == []

    def test_build_warmup_urls_jobs_without_key(self):
        """build_warmup_urls com jobs sem a chave esperada retorna vazio."""
        spec = WarmupSpec(route_template="test/{id}/route", id_keys=["missing_key"])
        urls = build_warmup_urls(BASE_URL, [{"other": 1}], spec)
        assert urls == []

    def test_build_warmup_urls_proposicoes_relacionadas(self):
        """build_warmup_urls para PROPOSICOES/RELACIONADAS."""
        spec = WARMUP_CONFIG[DomainType.RELACIONADAS]
        jobs = [
            {"proposicao_ids": [490116, 490115]},
            {"proposicao_ids": [490114]},
        ]
        urls = build_warmup_urls(BASE_URL, jobs, spec)
        assert len(urls) == 3
        assert f"{BASE_URL}/proposicoes/490116/relacionadas" in urls

    def test_build_warmup_urls_ignores_none_values(self):
        """build_warmup_urls deve ignorar valores None."""
        spec = WARMUP_CONFIG[DomainType.DEPUTADOS_HISTORICO]
        urls = build_warmup_urls(BASE_URL, [{"deputado_id": None}], spec)
        assert urls == []

    def test_build_warmup_urls_ignores_none_in_list(self):
        """build_warmup_urls deve ignorar None dentro de listas."""
        spec = WARMUP_CONFIG[DomainType.EVENTOS_PAUTA]
        urls = build_warmup_urls(BASE_URL, [{"evento_ids": [100, None]}], spec)
        assert len(urls) == 1
        assert f"{BASE_URL}/eventos/100/pauta" in urls


class TestCamaraClientWarmup:
    """Testes para CamaraClient.warmup_for_domain()."""

    @pytest.mark.asyncio
    async def test_warmup_for_domain_skips_unknown_domain(self):
        """warmup_for_domain não deve fazer requisições para domínios fora do WARMUP_CONFIG."""
        client = CamaraClient()
        with respx.mock:
            # Um rota da raiz (ex: /votacoes) NÃO deve ser chamada
            route = respx.get(f"{BASE_URL}/votacoes")
            await client.warmup_for_domain(DomainType.VOTACOES, [{}])
            assert route.call_count == 0

    @pytest.mark.asyncio
    async def test_warmup_for_domain_makes_requests(self):
        """warmup_for_domain deve fazer uma requisição GET para cada URL única."""
        client = CamaraClient()
        jobs = [{"deputado_id": 178957}, {"deputado_id": 74186}]

        with respx.mock:
            route_1 = respx.get(f"{BASE_URL}/deputados/178957/historico").respond(status_code=200)
            route_2 = respx.get(f"{BASE_URL}/deputados/74186/historico").respond(status_code=200)

            await client.warmup_for_domain(DomainType.DEPUTADOS_HISTORICO, jobs)

            assert route_1.call_count == 1
            assert route_2.call_count == 1

    @pytest.mark.asyncio
    async def test_warmup_for_domain_best_effort_on_error(self):
        """warmup_for_domain não deve quebrar se a API retornar erro."""
        client = CamaraClient()
        jobs = [{"deputado_id": 999999}]  # ID que provavelmente não existe

        with respx.mock:
            respx.get(f"{BASE_URL}/deputados/999999/historico").respond(status_code=500)

            # Não deve lançar exceção
            await client.warmup_for_domain(DomainType.DEPUTADOS_HISTORICO, jobs)

    @pytest.mark.asyncio
    async def test_warmup_for_domain_dedup_warmed_urls(self):
        """_warmed_urls deve evitar re-aquecer a mesma URL na mesma sessão."""
        client = CamaraClient()
        jobs = [{"deputado_id": 178957}]

        with respx.mock:
            route = respx.get(f"{BASE_URL}/deputados/178957/historico").respond(status_code=200)

            # Primeira chamada: deve fazer 1 GET
            await client.warmup_for_domain(DomainType.DEPUTADOS_HISTORICO, jobs)
            assert route.call_count == 1

            # Segunda chamada: saltado por _warmed_urls
            await client.warmup_for_domain(DomainType.DEPUTADOS_HISTORICO, jobs)
            assert route.call_count == 1  # não incrementou

    @pytest.mark.asyncio
    async def test_warmup_for_domain_empty_jobs(self):
        """warmup_for_domain com jobs vazio não deve fazer requisições."""
        client = CamaraClient()
        with respx.mock:
            route = respx.get(f"{BASE_URL}/deputados/").respond(status_code=200)
            await client.warmup_for_domain(DomainType.DEPUTADOS_HISTORICO, [])
            assert route.call_count == 0

    @pytest.mark.asyncio
    async def test_warmup_for_domain_sequential_not_parallel(self):
        """Verifica que as requisições são sequenciais (1 por vez) — não testamos
        paralelismo diretamente, mas garantimos que URLs em lote são processadas."""
        client = CamaraClient()
        jobs = [{"deputado_id": i} for i in range(1, 6)]

        with respx.mock:
            routes = [
                respx.get(f"{BASE_URL}/deputados/{i}/historico").respond(status_code=200)
                for i in range(1, 6)
            ]
            await client.warmup_for_domain(DomainType.DEPUTADOS_HISTORICO, jobs)
            for r in routes:
                assert r.call_count == 1
