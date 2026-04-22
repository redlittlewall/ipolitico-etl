import polars as pl

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import LEGISLATURA_ATUAL


class VotacoesExtractor:
    """
    Extrator de Votações e Votos Nominais.
    Essencial para o mapeamento de posicionamento político.
    """

    def __init__(self, client: CamaraClient):
        self.client = client

    async def extract_votacoes_recentes(self) -> pl.DataFrame:
        """
        Busca a lista de votações ocorridas na legislatura atual.
        """
        endpoint = "votacoes"
        params = {
            "idLegislatura": LEGISLATURA_ATUAL,
            "ordem": "DESC",
            "ordenarPor": "dataHoraRegistro",
        }

        dados = await self.client.fetch(endpoint, params=params)
        return pl.DataFrame(dados)

    async def extract_votos_por_votacao(self, votacao_id: str) -> pl.DataFrame:
        """
        Busca o voto de cada deputado para uma votação específica.
        """
        endpoint = f"votacoes/{votacao_id}/votos"

        try:
            dados = await self.client.fetch(endpoint)
            if not dados:
                return pl.DataFrame()

            df = pl.DataFrame(dados)
            # Adicionamos o ID da votação para permitir o JOIN no banco de dados
            return df.with_columns(pl.lit(votacao_id).alias("id_votacao"))
        except Exception:
            return pl.DataFrame()
