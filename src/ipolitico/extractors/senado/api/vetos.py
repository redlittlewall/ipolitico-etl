"""Extratores para os domínios de vetos presidenciais do Senado.

Inclui:
- ``VetosPresidenciaisExtractor`` — lista de vetos por ano (``/materia/vetos/{ano}``)
- ``VetosDetalheExtractor`` — detalhes de um veto específico (``/plenario/resultado/veto/{codigo}``)

Ambos aplainam os objetos aninhados da nova API (``Materia``, ``MateriaVetada``,
``NormaGerada``, ``Mensagem``) em chaves flat separadas por underline.
"""

import json
import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)

# Caminho para navegar no envelope XML-heritage da API de veto (novo formato).
# A resposta tem a estrutura:
#   { "ListaVetosAnoCN": {
#       "Metadados": {...},
#       "Vetos": {
#         "Veto": [...]   ← array alvo
#     }}
_DATA_PATH_PRESIDENCIAIS = [
    "ListaVetosAnoCN",
    "Vetos",
    "Veto",
]

# Caminho para navegar no envelope XML-heritage da API de detalhe do veto (novo formato).
# A resposta tem a estrutura:
#   { "ResultadoVetoItemCN": {
#       "Metadados": {...},
#       "Veto": { ... }   ← objeto alvo (normalizado para lista)
#     }}
_DATA_PATH_DETALHE = [
    "ResultadoVetoItemCN",
    "Veto",
]

# Campos flat da API que devem ser mantidos no aplainamento
_FLAT_FIELDS = {
    "Codigo",
    "Total",
    "Assunto",
    "DataRecebimentoCongresso",
    "DataPublicacao",
    "DataSobrestacaoPauta",
    "SobrestandoPauta",
    "QuantidadeDispositivos",
    "UrlDispositivos",
    "PdfsResultadoVotacao",
}

# Objetos aninhados que devem ser aplainados (prefixo → chave no record)
_NESTED_OBJECTS = ("Materia", "MateriaVetada", "Mensagem")

# Sub-objetos que devem ser aplainados recursivamente dentro de objetos aninhados
_DEEP_NESTED = {"MateriaVetada": {"NormaGerada"}}


def _flatten_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Achata objetos aninhados do novo envelope da API de vetos em chaves flat.

    Exemplos de aplainamento::

        ``Materia.Codigo`` → ``Materia_Codigo``
        ``MateriaVetada.NormaGerada.NomeNorma`` → ``MateriaVetada_NormaGerada_NomeNorma``

    Args:
        record: Dicionário aninhado de um veto (nível ``Veto``).

    Returns:
        Dicionário flat com todas as chaves relevantes.
    """
    flat: dict[str, Any] = {}

    # 1. Campos flat da raiz do veto
    for key in _FLAT_FIELDS:
        if key in record:
            flat[key] = record[key]

    # 2. Objetos aninhados de primeiro nível (Materia, MateriaVetada, Mensagem)
    for prefix in _NESTED_OBJECTS:
        obj = record.get(prefix)
        if not isinstance(obj, dict):
            continue
        for k, v in obj.items():
            deep_parents = _DEEP_NESTED.get(prefix, set())
            if k in deep_parents and isinstance(v, dict):
                # Aplainamento recursivo (ex: MateriaVetada > NormaGerada > *)
                for sk, sv in v.items():
                    flat[f"{prefix}_{k}_{sk}"] = sv
            else:
                flat[f"{prefix}_{k}"] = v

    # 3. Dispositivos (apenas para detalhe) — serializado como JSON string
    dispositivos = record.get("Dispositivos")
    if dispositivos is not None:
        flat["Dispositivos"] = json.dumps(dispositivos, ensure_ascii=False)

    return flat


class VetosPresidenciaisExtractor(SenadoBaseExtractor):
    """Extrator da lista de vetos presidenciais por ano.

    Chama ``/materia/vetos/{ano}`` (que redireciona para o novo endpoint),
    aplaina o envelope ``ListaVetosAnoCN`` e achata objetos aninhados
    (Materia, MateriaVetada, Mensagem) em colunas flat. 1 job por ano.
    """

    async def extract(self, ano: int | None = None, **kwargs: Any) -> pl.DataFrame:
        """Extrai vetos presidenciais de um ano específico.

        Args:
            ano: Ano para filtrar (ex: 2020). Se omitido, usa o parâmetro
                 ``start_date`` extraído do kwargs (compatibilidade com
                 orquestrador que passa janela temporal).
            **kwargs: Parâmetros adicionais (aceita ``start_date``/``end_date``
                      como fallback).

        Returns:
            DataFrame com os dados brutos dos vetos do ano (campos aplainados).
            Retorna DataFrame vazio se a API não retornar dados.
        """
        if ano is None:
            sd = kwargs.get("start_date")
            ano = int(sd.split("-")[0]) if sd else None

        endpoint = f"materia/vetos/{ano}" if ano else "materia/vetos/1995"
        raw = await self.fetch_flat(endpoint)
        records = self.flatten_response(raw, _DATA_PATH_PRESIDENCIAIS)

        if not records:
            return pl.DataFrame()

        flat_records = [_flatten_record(r) for r in records]
        df = pl.DataFrame(flat_records, infer_schema_length=None)
        return self._inject_source_url(df, endpoint)


class VetosDetalheExtractor(SenadoBaseExtractor):
    """Extrator de detalhes de um ou mais vetos presidenciais.

    Chama ``/plenario/resultado/veto/{codigo}`` para cada código,
    aplaina o envelope ``ResultadoVetoItemCN`` e achata objetos aninhados
    (incluindo Dispositivos como JSON string). Usa o pattern de
    ``entity_ids`` (igual ``SenadoSenadoresDetalheExtractor``).
    """

    async def extract(
        self,
        entity_ids: list[int] | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai detalhes de um ou mais vetos.

        Args:
            entity_ids: Lista de códigos de veto. Se omitido ou vazio,
                        retorna DataFrame vazio.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos do(s) veto(s), campos aplainados
            e Dispositivos como JSON string.
        """
        if not entity_ids:
            return pl.DataFrame()

        batches: list[tuple[str, list[dict[str, Any]], dict[str, Any] | None]] = []
        for codigo in entity_ids:
            raw = await self.fetch_flat(f"plenario/resultado/veto/{codigo}")
            records = self.flatten_response(raw, _DATA_PATH_DETALHE)
            if records:
                flat_records = [_flatten_record(r) for r in records]
                batches.append((f"plenario/resultado/veto/{codigo}", flat_records, None))

        # DataFrame único com todos os vetos do lote: vetos com objetos
        # aninhados diferentes (ex: um sem ``Mensagem``) são unificados
        # (o concat por-veto falhava com SchemaError de largura).
        return self._build_batch_dataframe(batches)
