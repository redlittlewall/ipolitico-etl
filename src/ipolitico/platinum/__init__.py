"""Camada Platinum do iPolitico ETL (Issue 07).

Data Marts OBT (One Big Table) desnormalizados e agregações analíticas
consolidadas de custos ao erário e atividade parlamentar.
"""

from ipolitico.platinum.builder import PlatinumBuilder
from ipolitico.platinum.models import (
    OBT_POLITICO_CUSTO_MENSAL_SCHEMA,
    OBT_POLITICO_RESUMO_CARREIRA_SCHEMA,
    PK_OBT_POLITICO_CUSTO_MENSAL,
    PK_OBT_POLITICO_RESUMO_CARREIRA,
    TABLE_OBT_POLITICO_CUSTO_MENSAL,
    TABLE_OBT_POLITICO_RESUMO_CARREIRA,
    CoberturaPlatinum,
    mascarar_cpf,
)

__all__ = [
    "PlatinumBuilder",
    "CoberturaPlatinum",
    "TABLE_OBT_POLITICO_CUSTO_MENSAL",
    "TABLE_OBT_POLITICO_RESUMO_CARREIRA",
    "OBT_POLITICO_CUSTO_MENSAL_SCHEMA",
    "OBT_POLITICO_RESUMO_CARREIRA_SCHEMA",
    "PK_OBT_POLITICO_CUSTO_MENSAL",
    "PK_OBT_POLITICO_RESUMO_CARREIRA",
    "mascarar_cpf",
]
