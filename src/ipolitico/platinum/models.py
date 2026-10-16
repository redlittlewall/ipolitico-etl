"""Modelos e contratos da camada Platinum (Issue 07).

Data Marts OBT (One Big Table) e agregações analíticas de custos e atividade:
- ``obt_politico_custo_mensal``: grão mensal com rubricas discriminadas.
- ``obt_politico_resumo_carreira``: visão consolidada de toda a vida pública.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import polars as pl

# Nomes canônicos das tabelas Platinum
TABLE_OBT_POLITICO_CUSTO_MENSAL = "obt_politico_custo_mensal"
TABLE_OBT_POLITICO_RESUMO_CARREIRA = "obt_politico_resumo_carreira"

# Chaves primárias das tabelas
PK_OBT_POLITICO_CUSTO_MENSAL = ["id_politico_canônico", "ano_mes"]
PK_OBT_POLITICO_RESUMO_CARREIRA = ["id_politico_canônico"]

# Schema contratual: obt_politico_custo_mensal
OBT_POLITICO_CUSTO_MENSAL_SCHEMA: dict[str, pl.DataType] = {
    "id_politico_canônico": pl.String,
    "nome": pl.String,
    "cpf_mascarado": pl.String,
    "partido_atual": pl.String,
    "uf": pl.String,
    "cargo_atual": pl.String,
    "ano": pl.Int64,
    "mes": pl.Int64,
    "ano_mes": pl.String,
    "total_salario": pl.Float64,
    "total_ceap": pl.Float64,
    "total_ceaps": pl.Float64,
    "total_cartoes": pl.Float64,
    "total_viagens": pl.Float64,
    "total_verba_gabinete": pl.Float64,
    "custo_total_mes": pl.Float64,
}

# Schema contratual: obt_politico_resumo_carreira
OBT_POLITICO_RESUMO_CARREIRA_SCHEMA: dict[str, pl.DataType] = {
    "id_politico_canônico": pl.String,
    "nome": pl.String,
    "cpf_mascarado": pl.String,
    "partido_atual": pl.String,
    "uf": pl.String,
    "cargo_atual": pl.String,
    "custo_total_acumulado_historico": pl.Float64,
    "quantidade_mandatos": pl.Int64,
    "anos_em_exercicio": pl.Int64,
    "proposicoes_apresentadas": pl.Int64,
    "proposicoes_aprovadas": pl.Int64,
    "taxa_sucesso_legislativo": pl.Float64,
    "presenca_plenario_pct": pl.Float64,
    "votos_registrados": pl.Int64,
}


def mascarar_cpf(cpf: str | None) -> str | None:
    """Mascara um CPF no formato padrão dos portais públicos (***.XXX.XXX-**).

    Args:
        cpf: String bruta contendo CPF com ou sem pontuação/máscara.

    Returns:
        String no formato ``***.123.456-**`` ou ``None`` se nulo/inválido.
    """
    if not cpf or not isinstance(cpf, str):
        return None
    s = cpf.strip()
    if not s:
        return None
    if "*" in s:
        return s
    digits = re.sub(r"\D", "", s)
    if len(digits) == 11:
        return f"***.{digits[3:6]}.{digits[6:9]}-**"
    if len(digits) >= 6:
        return f"***.{digits[-6:-3]}.{digits[-3:]}-**"
    return s


@dataclass(frozen=True)
class CoberturaPlatinum:
    """Relatório analítico da camada Platinum (issue 07, acceptance).

    Attributes:
        total_politicos: Nº de políticos consolidados em ``obt_politico_resumo_carreira``.
        total_linhas_custo_mensal: Nº de registros mensais em ``obt_politico_custo_mensal``.
        custo_total_acumulado: Soma financeira de todos os custos no resumo da carreira.
        total_proposicoes_apresentadas: Total de proposições apresentadas contabilizadas.
        total_proposicoes_aprovadas: Total de proposições aprovadas contabilizadas.
        total_votos_registrados: Total de votos individuais registrados.
        tabelas_geradas: Lista de nomes de tabelas Platinum materializadas.
    """

    total_politicos: int = 0
    total_linhas_custo_mensal: int = 0
    custo_total_acumulado: float = 0.0
    total_proposicoes_apresentadas: int = 0
    total_proposicoes_aprovadas: int = 0
    total_votos_registrados: int = 0
    tabelas_geradas: tuple[str, ...] = field(default_factory=tuple)
