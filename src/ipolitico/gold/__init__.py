"""Camada Gold de identidade e métricas (issues 01–02 da etapa custo ao erário).

Builders que leem a camada Silver e produzem as tabelas Gold de entidade
canônica (``politicos``, ``politicos_aliases``, ``resolucoes``) e de custo ao
erário (``custo_erario``, ``observacoes_metricas``). Escrita **append-only**;
deduplicação é responsabilidade do ``DataLakeOptimizer`` (Gold), nunca da
ingestão.
"""
