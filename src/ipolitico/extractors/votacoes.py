import polars as pl

from ipolitico.core.config import LEGISLATURA_ATUAL
from ipolitico.extractors.base import BaseExtractor


class VotacoesExtractor(BaseExtractor):
    async def extract(self, data_inicio: str = None) -> pl.DataFrame:
        """
        Implementa a extração incremental de votações.
        """
        if not data_inicio:
            data_inicio = self._get_last_watermark("votacoes", "dataHoraRegistro") or "2023-02-01"

        params = {
            "idLegislatura": LEGISLATURA_ATUAL,
            "dataInicio": data_inicio,
            "ordem": "ASC",
            "ordenarPor": "dataHoraRegistro",
        }

        dados = await self.client.fetch("votacoes", params=params)
        return pl.DataFrame(dados)

    async def extract_votos(self, votacao_id: str) -> pl.DataFrame:
        """: Votos nominais são uma sub-rota."""
        endpoint = f"votacoes/{votacao_id}/votos"
        dados = await self.client.fetch(endpoint)
        if not dados:
            return pl.DataFrame()
        return pl.DataFrame(dados).with_columns(pl.lit(votacao_id).alias("id_votacao"))
