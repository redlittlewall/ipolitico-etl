"""Helpers de I/O da camada Gold compartilhados pelos builders (issues 01–02).

Leitura de Silver por ``DomainType`` (tabela ausente → DataFrame vazio com o
schema contratual, sem exceção), leitura de Gold já otimizada ou dedup de lotes
append-only, e escrita de lote append-only com ``captured_at`` (padrão do
``DataLakeSink``). A dedup formal é responsabilidade do ``DataLakeOptimizer``;
aqui só se consome o estado mais recente dos lotes.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from ipolitico.core.constants import DomainType, MedallionLayer
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.sinks.datalake_sink import inject_captured_at, lote_parquet_path


def ler_silver(base_dir: str, domain: DomainType) -> pl.DataFrame:
    """Lê todos os parquet Silver de um domínio (append-only, sem dedup).

    Args:
        base_dir: Diretório raiz do DataLake.
        domain: Domínio Silver a ler.

    Returns:
        DataFrame com o schema contratual de ``SILVER_SCHEMAS``; vazio (schema)
        quando o diretório não existe ou não tem arquivos.
    """
    schema = SILVER_SCHEMAS[domain.value]
    dir_path = Path(base_dir) / MedallionLayer.SILVER / domain.value
    if not dir_path.exists():
        return pl.DataFrame(schema=schema)
    files = sorted(dir_path.glob("*.parquet"))
    if not files:
        return pl.DataFrame(schema=schema)
    frames = [pl.read_parquet(f) for f in files]
    return pl.concat(frames, how="vertical")


def ler_gold(
    base_dir: str,
    table_name: str,
    chaves: list[str] | None = None,
) -> pl.DataFrame:
    """Lê uma tabela Gold priorizando o arquivo otimizado ``{table}.parquet``.

    Quando só existem lotes append-only, concatena e deduplica pelas ``chaves``
    (último ``captured_at`` vence). Sem arquivos → DataFrame vazio sem colunas.

    Args:
        base_dir: Diretório raiz do DataLake.
        table_name: Nome da tabela Gold (diretório/arquivo otimizado).
        chaves: Colunas de identidade para dedup de lotes (ex.: ``fonte,
            id_natural``); ``None`` devolve os lotes concatenados.

    Returns:
        DataFrame deduplicado (ou vazio).
    """
    dir_path = Path(base_dir) / MedallionLayer.GOLD / table_name
    optimized = dir_path / f"{table_name}.parquet"
    if optimized.exists():
        return pl.read_parquet(optimized)
    if not dir_path.exists():
        return pl.DataFrame()
    files = sorted(dir_path.glob("*.parquet"))
    if not files:
        return pl.DataFrame()
    df = pl.concat([pl.read_parquet(f) for f in files], how="vertical")
    if chaves and "captured_at" in df.columns:
        df = df.sort("captured_at", descending=True).unique(subset=chaves, keep="first")
    return df


def escrever_gold(base_dir: str, table_name: str, df: pl.DataFrame) -> None:
    """Persiste um lote append-only da tabela Gold (nunca sobrescreve).

    Args:
        base_dir: Diretório raiz do DataLake.
        table_name: Nome da tabela Gold (diretório destino).
        df: Dados do lote; vazio é ignorado (nenhum arquivo criado).
    """
    if df.is_empty():
        return
    dir_path = Path(base_dir) / MedallionLayer.GOLD / table_name
    inject_captured_at(df).write_parquet(lote_parquet_path(dir_path))
