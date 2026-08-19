import polars as pl

from ipolitico.pipeline.optimizer import DataLakeOptimizer


def test_compact_and_deduplicate_respects_explicit_pk_cols(tmp_path):
    """Dedup Gold com ``pk_cols`` explícito mantém 1 linha por chave, mais recente."""
    silver = tmp_path / "silver" / "politicos"
    silver.mkdir(parents=True)
    pl.DataFrame(
        {
            "politico_id": ["pol_camara_1", "pol_camara_1"],
            "nome": ["A", "A_antigo"],
            "captured_at": ["2026-08-18T10:00:00", "2026-08-17T10:00:00"],
        }
    ).write_parquet(silver / "lote_1.parquet")

    opt = DataLakeOptimizer(base_dir=str(tmp_path))
    opt.compact_and_deduplicate(
        "politicos",
        source_layer="silver",
        target_layer="gold",
        pk_cols="politico_id",
    )

    result = pl.read_parquet(tmp_path / "gold" / "politicos" / "politicos.parquet")
    assert result.height == 1
    assert result["nome"].to_list() == ["A"]


def test_compact_and_deduplicate_pk_cols_compostas(tmp_path):
    """pk_cols pode ser composto (vírgula) — ex.: aliases (fonte, id_natural)."""
    silver = tmp_path / "silver" / "politicos_aliases"
    silver.mkdir(parents=True)
    pl.DataFrame(
        {
            "fonte": ["camara", "camara", "senado"],
            "id_natural": [1, 1, 2],
            "politico_id": ["pol_camara_1", "pol_camara_9", "pol_senado_2"],
            "captured_at": ["2026-08-18T10:00:00", "2026-08-17T10:00:00", "2026-08-18T10:00:00"],
        }
    ).write_parquet(silver / "lote_1.parquet")

    opt = DataLakeOptimizer(base_dir=str(tmp_path))
    opt.compact_and_deduplicate(
        "politicos_aliases",
        source_layer="silver",
        target_layer="gold",
        pk_cols="fonte, id_natural",
    )

    result = pl.read_parquet(tmp_path / "gold" / "politicos_aliases" / "politicos_aliases.parquet")
    assert result.height == 2
    # camara/1 manteve o mais recente (pol_camara_1); senado/2 ficou único
    assert set(result["politico_id"].to_list()) == {"pol_camara_1", "pol_senado_2"}
