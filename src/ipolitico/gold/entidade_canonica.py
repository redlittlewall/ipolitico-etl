"""Builder Gold da entidade canônica ``politico_id`` (issue 01).

Lê os Silver de identidade já ingeridos (``deputados``, ``deputados_detalhe``,
``senadores``, ``servidores``), executa a resolução do ``resolutor`` e escreve
as tabelas Gold ``politicos``, ``politicos_aliases`` e ``resolucoes`` de forma
**append-only** (lote Parquet por execução). A deduplicação é feita depois
pelo ``DataLakeOptimizer`` — o builder nunca sobrescreve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.gold._datalake import escrever_gold, ler_gold, ler_silver
from ipolitico.gold.resolutor import (
    CONF_BAIXA,
    montar_ancoras,
)

# Chaves de identidade das tabelas Gold (dedup + leitura deduplicada).
POLITICOS_PK = ["politico_id"]
ALIASES_PK = ["fonte", "id_natural"]
RESOLUCOES_PK = ["fonte_origem", "id_origem", "fonte_destino", "id_destino"]


@dataclass(frozen=True)
class CoberturaEntidadeCanonica:
    """Relatório de cobertura da entidade canônica (issue 01, acceptance).

    Attributes:
        total_politicos: Nº de pessoas únicas na tabela ``politicos``.
        total_aliases: Nº de aliases em ``politicos_aliases``.
        ancoras_camara: Políticos cuja âncora é ``pol_camara_*``.
        ancoras_senado: Políticos cuja âncora é ``pol_senado_*``.
        resolucoes_confirmadas: Resoluções fuzzy confirmadas (auditadas).
        resolucoes_candidatas_revisao: Resoluções de baixa confiança
            (candidatas a revisão humana).
        aliases_por_fonte: Contagem de aliases por fonte (camara, senado,
            senado_servidor).
    """

    total_politicos: int = 0
    total_aliases: int = 0
    ancoras_camara: int = 0
    ancoras_senado: int = 0
    resolucoes_confirmadas: int = 0
    resolucoes_candidatas_revisao: int = 0
    aliases_por_fonte: dict[str, int] = field(default_factory=dict)


class EntidadeCanonicaBuilder:
    """Constrói as tabelas Gold de identidade a partir dos Silver ingeridos.

    Args:
        base_dir: Diretório raiz do DataLake (padrão ``data/datalake``).
    """

    def __init__(self, base_dir: str = "data/datalake"):
        self.base_dir = Path(base_dir)

    def build(self) -> None:
        """Executa a resolução completa e persiste as tabelas Gold (command).

        Escreve ``politicos``, ``politicos_aliases`` e ``resolucoes`` em lotes
        append-only (nunca sobrescreve). Não responde: o relatório de cobertura
        é uma query separada, :meth:`cobertura`.

        Returns:
            ``None`` (Command-Query Separation — build persiste, não consulta).
        """
        deputados = self._ler_silver(DomainType.DEPUTADOS)
        detalhe = self._ler_silver(DomainType.DEPUTADOS_DETALHE)
        senadores = self._ler_silver(DomainType.SENADORES)
        servidores = self._ler_silver(DomainType.SERVIDORES)
        senadores_detalhe = self._ler_silver(DomainType.SENADORES_DETALHE)

        politicos, aliases, resolucoes = montar_ancoras(
            deputados,
            detalhe,
            senadores,
            servidores=None if servidores.is_empty() else servidores,
            senadores_detalhe=None if senadores_detalhe.is_empty() else senadores_detalhe,
        )

        self._escrever_gold("politicos", politicos)
        self._escrever_gold("politicos_aliases", aliases)
        self._escrever_gold("resolucoes", resolucoes)

    def cobertura(self) -> CoberturaEntidadeCanonica:
        """Relatório de cobertura da Gold persistida (query, sem mutação).

        Lê as três tabelas de identidade já deduplicadas (último
        ``captured_at`` vence) e computa as métricas. Num ambiente limpo,
        rodar após :meth:`build` produz os mesmos números da execução.

        Returns:
            ``CoberturaEntidadeCanonica`` preenchida (zeros sem dados).
        """
        politicos = ler_gold(self.base_dir, "politicos", chaves=POLITICOS_PK)
        aliases = ler_gold(self.base_dir, "politicos_aliases", chaves=ALIASES_PK)
        resolucoes = ler_gold(self.base_dir, "resolucoes", chaves=RESOLUCOES_PK)
        return self._relatorio(politicos, aliases, resolucoes)

    # ------------------------------------------------------------------
    #  Métodos internos
    # ------------------------------------------------------------------

    def _ler_silver(self, domain: DomainType) -> pl.DataFrame:
        """Lê todos os parquet Silver de um domínio (append-only, sem dedup).

        Args:
            domain: Domínio Silver a ler.

        Returns:
            DataFrame com o schema contratual de ``SILVER_SCHEMAS``; vazio
            (schema) quando o diretório não existe ou não tem arquivos.
        """
        return ler_silver(self.base_dir, domain)

    def _escrever_gold(self, table_name: str, df: pl.DataFrame) -> None:
        """Persiste um lote append-only da tabela Gold (nunca sobrescreve).

        Args:
            table_name: Nome da tabela Gold (diretório destino).
            df: Dados do lote; vazio é ignorado (nenhum arquivo criado).
        """
        escrever_gold(self.base_dir, table_name, df)

    @staticmethod
    def _relatorio(
        politicos: pl.DataFrame,
        aliases: pl.DataFrame,
        resolucoes: pl.DataFrame,
    ) -> CoberturaEntidadeCanonica:
        """Calcula o relatório de cobertura a partir das tabelas produzidas.

        Args:
            politicos: Tabela ``politicos`` (pode ser vazia).
            aliases: Tabela ``politicos_aliases`` (pode ser vazia).
            resolucoes: Tabela ``resolucoes`` (pode ser vazia).

        Returns:
            ``CoberturaEntidadeCanonica`` preenchida.
        """
        ancoras_camara = 0
        ancoras_senado = 0
        if not politicos.is_empty():
            ancoras_camara = (
                politicos.filter(pl.col("politico_id").str.starts_with("pol_camara_")).height
            )
            ancoras_senado = (
                politicos.filter(pl.col("politico_id").str.starts_with("pol_senado_")).height
            )
        confirmadas = 0
        candidatas = 0
        if not resolucoes.is_empty():
            confirmadas = resolucoes.filter(pl.col("confianca") != CONF_BAIXA).height
            candidatas = resolucoes.filter(pl.col("confianca") == CONF_BAIXA).height
        por_fonte: dict[str, int] = {}
        if not aliases.is_empty():
            contagem = aliases.group_by("fonte").agg(pl.len().alias("n")).sort("fonte")
            por_fonte = {row["fonte"]: row["n"] for row in contagem.iter_rows(named=True)}
        return CoberturaEntidadeCanonica(
            total_politicos=politicos.height,
            total_aliases=aliases.height,
            ancoras_camara=ancoras_camara,
            ancoras_senado=ancoras_senado,
            resolucoes_confirmadas=confirmadas,
            resolucoes_candidatas_revisao=candidatas,
            aliases_por_fonte=por_fonte,
        )
