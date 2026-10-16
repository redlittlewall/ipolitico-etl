import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.pipeline.optimizer import DataLakeOptimizer


def test_resolve_pk_cols_for_usa_uk_declarada_no_portal():
    """Portal usa a UK declarada (cartões composta+id); Câmara fica na introspecção."""
    pk_cartoes = DataLakeOptimizer.resolve_pk_cols_for(DomainType.CG_CARTOES)
    assert pk_cartoes == (
        "tipoCartao_codigo, mesExtrato, dataTransacao, valorTransacao, "
        "portador_cpfFormatado, favorecido_cpfCnpj, unidadeGestora_codigo, id"
    )
    assert DataLakeOptimizer.resolve_pk_cols_for(DomainType.CG_EMENDAS) == "codigoEmenda"
    # Câmara: introspecção genérica (sem UK declarada para o dedup do Gold).
    assert DataLakeOptimizer.resolve_pk_cols_for(DomainType.DEPUTADOS) is None


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


def test_cartoes_rota_dupla_uk_composta_mais_id(tmp_path):
    """UK composta+`id` (cg_cartoes): bulk deduplica duplicados de fonte, a API
    nunca merge transações distintas e o overlap bulk×API NÃO colapsa.

    Correção da validação real (ticket 04): a composta colide em transações
    DISTINTAS da API com documentos mascarados → `id` na UK é o discriminador.
    Sem o `id`, a introspecção faria PARTITION BY id → as linhas bulk (id nulo)
    colapsariam em UMA partição, perdendo dados.
    """
    silver = tmp_path / "silver" / "cg_cartoes"
    silver.mkdir(parents=True)
    base = {
        "tipoCartao_codigo": "1",
        "mesExtrato": "06/2025",
        "dataTransacao": "14/05/2025",
        "valorTransacao": 1000.0,
        "portador_cpfFormatado": "***.382.302-**",
        "favorecido_cpfCnpj": None,
        "unidadeGestora_codigo": "135008",
    }
    pl.DataFrame(
        [
            # bulk: mesmo composite, id nulo → duplicado exato de fonte → 1
            {**base, "id": None, "captured_at": "2026-08-19T10:00:00"},
            {**base, "id": None, "captured_at": "2026-08-19T09:00:00"},
            # API: mesmo composite, ids DISTINTOS ("SEM INFORMACAO") → ambos
            {**base, "id": 1, "captured_at": "2026-08-19T10:00:00"},
            {**base, "id": 2, "captured_at": "2026-08-19T10:00:00"},
            # overlap: bulk (id nulo) + API (id 3) mesmo composite → ambos
            {
                **base,
                "id": None,
                "favorecido_cpfCnpj": "38056949000186",
                "captured_at": "2026-08-19T09:00:00",
            },
            {
                **base,
                "id": 3,
                "favorecido_cpfCnpj": "38056949000186",
                "captured_at": "2026-08-19T10:00:00",
            },
        ]
    ).write_parquet(silver / "lote_1.parquet")

    pk = ", ".join(
        (
            "tipoCartao_codigo",
            "mesExtrato",
            "dataTransacao",
            "valorTransacao",
            "portador_cpfFormatado",
            "favorecido_cpfCnpj",
            "unidadeGestora_codigo",
            "id",
        )
    )
    opt = DataLakeOptimizer(base_dir=str(tmp_path))
    opt.compact_and_deduplicate(
        "cg_cartoes",
        source_layer="silver",
        target_layer="gold",
        pk_cols=pk,
    )

    result = pl.read_parquet(tmp_path / "gold" / "cg_cartoes" / "cg_cartoes.parquet")
    # 1 bulk (dup de fonte deduplicado) + 2 API distintas + overlap 2 = 5
    assert result.height == 5
    assert result["id"].null_count() == 2  # 2 linhas bulk (id nulo) preservadas
    assert set(result["id"].drop_nulls().to_list()) == {1, 2, 3}
