"""Tests for DetailStrategy resolution of BLOCOS_DETALHE and PROPOSICOES_DETALHE."""

from unittest.mock import MagicMock

from ipolitico.core.constants import DomainType
from ipolitico.pipeline.planners.strategies import DetailStrategy, strategy_for


class TestDetailStrategyRegistration:
    def test_blocos_detalhe_registrado(self):
        """STRATEGY_REGISTRY deve ter DetailStrategy para BLOCOS_DETALHE."""
        strategy = strategy_for(DomainType.BLOCOS_DETALHE)
        assert isinstance(strategy, DetailStrategy)

    def test_proposicoes_detalhe_registrado(self):
        """STRATEGY_REGISTRY deve ter DetailStrategy para PROPOSICOES_DETALHE."""
        strategy = strategy_for(DomainType.PROPOSICOES_DETALHE)
        assert isinstance(strategy, DetailStrategy)


class TestDetailStrategyEntityResolution:
    """Testa a resolução de entity_ids via _resolve_detail_entity_ids."""

    def test_blocos_detalhe_resolve_ids_com_lake(self):
        """_resolve_detail_entity_ids deve retornar bloco_ids quando lake existe."""
        lake = MagicMock()
        lake.list_bloco_ids_silver_or_gold.return_value = [1, 2, 3]

        ids, upstream = DetailStrategy._resolve_detail_entity_ids(
            domain_val=DomainType.BLOCOS_DETALHE.value,
            start="2026-01-01",
            end="2026-06-01",
            current_leg=57,
            anchor_year=2023,
            lake=lake,
            state_store=None,
        )

        assert ids == [1, 2, 3]
        assert upstream == DomainType.BLOCOS.value
        lake.list_bloco_ids_silver_or_gold.assert_called_once_with(57)

    def test_blocos_detalhe_sem_lake_retorna_vazio(self):
        """_resolve_detail_entity_ids sem lake deve retornar [], upstream."""
        ids, upstream = DetailStrategy._resolve_detail_entity_ids(
            domain_val=DomainType.BLOCOS_DETALHE.value,
            start="2026-01-01",
            end="2026-06-01",
            current_leg=57,
            anchor_year=2023,
            lake=None,
            state_store=None,
        )

        assert ids == []
        assert upstream == DomainType.BLOCOS.value

    def test_proposicoes_detalhe_resolve_ids_com_lake(self):
        """_resolve_detail_entity_ids deve retornar proposicao_ids quando lake existe."""
        lake = MagicMock()
        lake.list_proposicao_ids_silver_or_gold.return_value = [100, 200, 300]

        ids, upstream = DetailStrategy._resolve_detail_entity_ids(
            domain_val=DomainType.PROPOSICOES_DETALHE.value,
            start="2026-01-01",
            end="2026-06-01",
            current_leg=57,
            anchor_year=2023,
            lake=lake,
            state_store=None,
        )

        assert ids == [100, 200, 300]
        assert upstream == DomainType.PROPOSICOES.value
        lake.list_proposicao_ids_silver_or_gold.assert_called_once_with("2026-01-01", "2026-06-01")

    def test_proposicoes_detalhe_sem_lake_retorna_vazio(self):
        """_resolve_detail_entity_ids sem lake deve retornar [], upstream."""
        ids, upstream = DetailStrategy._resolve_detail_entity_ids(
            domain_val=DomainType.PROPOSICOES_DETALHE.value,
            start="2026-01-01",
            end="2026-06-01",
            current_leg=57,
            anchor_year=2023,
            lake=None,
            state_store=None,
        )

        assert ids == []
        assert upstream == DomainType.PROPOSICOES.value
