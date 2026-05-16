from ipolitico.pipeline.optimizer import DataLakeOptimizer


def test_optimizer_skips_when_silver_missing(tmp_path):
    opt = DataLakeOptimizer(base_dir=str(tmp_path))
    opt.compact_and_deduplicate("votacoes")
    assert not (tmp_path / "gold" / "votacoes" / "votacoes.parquet").exists()
