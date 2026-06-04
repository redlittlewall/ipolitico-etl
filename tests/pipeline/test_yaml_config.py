"""Tests for YAML config entries for blocos_detalhe and proposicoes_detalhe."""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def config():
    config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "camara_pipeline.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


class TestBlocosDetalheYamlEntry:
    def test_blocos_detalhe_entry_exists(self, config):
        """YAML deve ter entry para blocos_detalhe."""
        assert "blocos_detalhe" in config["domain_configs"]

    def test_blocos_detalhe_extractor(self, config):
        """Entry blocos_detalhe deve usar BlocosDetalheExtractor."""
        entry = config["domain_configs"]["blocos_detalhe"]
        assert "detail_child.BlocosDetalheExtractor" in entry["extractor"]

    def test_blocos_detalhe_transformer(self, config):
        """Entry blocos_detalhe deve usar CamaraDetalheTransformer."""
        entry = config["domain_configs"]["blocos_detalhe"]
        assert "CamaraDetalheTransformer" in entry["transformer"]


class TestProposicoesDetalheYamlEntry:
    def test_proposicoes_detalhe_entry_exists(self, config):
        """YAML deve ter entry para proposicoes_detalhe."""
        assert "proposicoes_detalhe" in config["domain_configs"]

    def test_proposicoes_detalhe_extractor(self, config):
        """Entry proposicoes_detalhe deve usar ProposicoesDetalheExtractor."""
        entry = config["domain_configs"]["proposicoes_detalhe"]
        assert "detail_child.ProposicoesDetalheExtractor" in entry["extractor"]

    def test_proposicoes_detalhe_transformer(self, config):
        """Entry proposicoes_detalhe deve usar CamaraDetalheTransformer."""
        entry = config["domain_configs"]["proposicoes_detalhe"]
        assert "CamaraDetalheTransformer" in entry["transformer"]
