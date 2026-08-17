"""Extratores para os 4 domínios de composição política do Senado.

Endpoints:
- ``/composicao/lista/blocos`` → BLOCOS_SENADO
- ``/composicao/lideranca`` → LIDERANCAS_SENADO
- ``/composicao/mesaSF`` → MESA_SENADO
- ``/composicao/mesaCN`` → MESA_CONGRESSO
"""

from __future__ import annotations

import json
import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)


class BlocosSenadoExtractor(SenadoBaseExtractor):
    """Extrator de blocos parlamentares do Senado.

    Chama ``GET /composicao/lista/blocos`` e achata o envelope XML-heritage
    ``ListaBlocoParlamentar.Blocos.Bloco[]``. Serializa a struct aninhada
    ``Membros`` como JSON string.
    """

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """Extrai lista de todos os blocos parlamentares do Senado.

        Args:
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos dos blocos (CodigoBloco, NomeBloco,
            NomeApelido, DataCriacao, Membros serializado como JSON string),
            ou DataFrame vazio se a API não retornar dados.
        """
        raw = await self.fetch_flat("composicao/lista/blocos")
        records = self.flatten_response(raw, ["ListaBlocoParlamentar", "Blocos", "Bloco"])

        if not records:
            return pl.DataFrame()

        # Serializa Membros (struct aninhada) como JSON string
        for record in records:
            membros = record.get("Membros")
            if isinstance(membros, (dict, list)):
                record["Membros"] = json.dumps(membros, ensure_ascii=False)

        df = pl.DataFrame(records, infer_schema_length=None)
        return self._inject_source_url(df, "composicao/lista/blocos")


class LiderancasSenadoExtractor(SenadoBaseExtractor):
    """Extrator de lideranças do Senado.

    Chama ``GET /composicao/lideranca``. Diferente dos outros endpoints
    do Senado, este retorna um **array JSON plano** no topo — sem envelope
    XML-heritage. O método ``extract`` usa o dado diretamente sem passar
    por ``flatten_response``.
    """

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """Extrai lista de todas as lideranças vigentes.

        Args:
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos das lideranças (codigo, casa,
            codigoParlamentar, nomeParlamentar, dataDesignacao, etc.),
            ou DataFrame vazio se a API não retornar dados.
        """
        raw = await self.fetch_flat("composicao/lideranca")

        # A API retorna array JSON plano — sem envelope XML-heritage
        if not isinstance(raw, list) or not raw:
            return pl.DataFrame()

        df = pl.DataFrame(raw, infer_schema_length=None)
        return self._inject_source_url(df, "composicao/lideranca")


class MesaSenadoExtractor(SenadoBaseExtractor):
    """Extrator da mesa diretora do Senado Federal.

    Chama ``GET /composicao/mesaSF`` e achata o envelope XML-heritage
    ``MesaSenado.Colegiados.Colegiado[]``. Para cada colegiado, mescla
    metadados (CodigoColegiado, NomeColegiado, SiglaColegiado) em cada
    cargo da lista ``Cargos.Cargo[]``. Serializa o campo ``Cargo``
    (array de strings) como JSON string.
    """

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """Extrai composição da mesa diretora do Senado.

        Para cada colegiado, itera sobre os cargos (Cargos.Cargo[]),
        anexando identificação do colegiado a cada cargo e serializando
        o array ``Cargo`` como JSON string.

        Args:
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com cargos e metadados do colegiado, ou DataFrame
            vazio se a API não retornar dados.
        """
        raw = await self.fetch_flat("composicao/mesaSF")
        colegiados = self.flatten_response(raw, ["MesaSenado", "Colegiados", "Colegiado"])

        if not colegiados:
            return pl.DataFrame()

        all_cargos: list[dict[str, Any]] = []
        for col in colegiados:
            cargos_data = col.get("Cargos", {})
            cargo_list = self._ensure_list(cargos_data.get("Cargo", []))

            for cargo in cargo_list:
                # Serializa array Cargo como JSON string
                raw_cargo = cargo.get("Cargo")
                if isinstance(raw_cargo, list):
                    cargo["Cargo"] = json.dumps(raw_cargo, ensure_ascii=False)

                # Anexa metadados do colegiado
                cargo["CodigoColegiado"] = col.get("CodigoColegiado")
                cargo["NomeColegiado"] = col.get("NomeColegiado")
                cargo["SiglaColegiado"] = col.get("SiglaColegiado")
                all_cargos.append(cargo)

        if not all_cargos:
            return pl.DataFrame()

        df = pl.DataFrame(all_cargos, infer_schema_length=None)
        return self._inject_source_url(df, "composicao/mesaSF")


class MesaCongressoExtractor(SenadoBaseExtractor):
    """Extrator da mesa diretora do Congresso Nacional.

    Chama ``GET /composicao/mesaCN`` e achata o envelope XML-heritage
    ``MesaCongresso.Colegiados.Colegiado[]``. Para cada colegiado, mescla
    metadados (CodigoColegiado, NomeColegiado, SiglaColegiado) em cada
    cargo da lista ``Cargos.Cargo[]``.
    """

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """Extrai composição da mesa diretora do Congresso Nacional.

        Para cada colegiado, itera sobre os cargos (Cargos.Cargo[]),
        anexando identificação do colegiado a cada cargo.

        Args:
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com cargos e metadados do colegiado, ou DataFrame
            vazio se a API não retornar dados.
        """
        raw = await self.fetch_flat("composicao/mesaCN")
        colegiados = self.flatten_response(raw, ["MesaCongresso", "Colegiados", "Colegiado"])

        if not colegiados:
            return pl.DataFrame()

        all_cargos: list[dict[str, Any]] = []
        for col in colegiados:
            cargos_data = col.get("Cargos", {})
            cargo_list = self._ensure_list(cargos_data.get("Cargo", []))

            for cargo in cargo_list:
                # Anexa metadados do colegiado
                cargo["CodigoColegiado"] = col.get("CodigoColegiado")
                cargo["NomeColegiado"] = col.get("NomeColegiado")
                cargo["SiglaColegiado"] = col.get("SiglaColegiado")
                all_cargos.append(cargo)

        if not all_cargos:
            return pl.DataFrame()

        df = pl.DataFrame(all_cargos, infer_schema_length=None)
        return self._inject_source_url(df, "composicao/mesaCN")
