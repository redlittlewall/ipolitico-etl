"""Extrator para o domínio SENADORES_DETALHE (detalhe por senador)."""

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)

_DATA_PATH = [
    "DetalheParlamentar",
    "Parlamentar",
]


class SenadoSenadoresDetalheExtractor(SenadoBaseExtractor):
    """Extrator de detalhes cadastrais de um senador.

    Chama ``/senador/{codigo}`` e achata o envelope XML-heritage
    para obter o dict de dados cadastrais do parlamentar.
    """

    async def extract(
        self,
        entity_ids: list[int] | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai detalhes de um ou mais senadores.

        Args:
            entity_ids: Lista de códigos de senador. Se omitido, extrai um único
                        registro (útil para fallback).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos do(s) senador(es), incluindo os
            dicionários aninhados ``IdentificacaoParlamentar`` e
            ``DadosBasicosParlamentar``.
        """
        if not entity_ids:
            return pl.DataFrame()

        all_records: list[dict[str, Any]] = []
        for codigo in entity_ids:
            raw = await self.fetch_flat(f"senador/{codigo}")
            records = self.flatten_response(raw, _DATA_PATH)
            if not records:
                continue
            source_url = self.build_source_url(f"senador/{codigo}")
            for record in records:
                # _source_url como primeira chave preserva a convenção de
                # _inject_source_url ("primeira coluna do DataFrame").
                all_records.append({"_source_url": source_url, **record})

        if not all_records:
            return pl.DataFrame()

        # DataFrame único com todos os senadores do lote: inferir o schema da
        # união de uma vez unifica structs aninhados com campos diferentes
        # (senador em exercício vs. histórico). O concat por-senador falhava
        # com "structs have different number of fields" no vstack.
        return pl.DataFrame(all_records, infer_schema_length=None)
