from ipolitico.core.constants import ApiParams, ApiRoutes


class CamaraMetadataService:
    def __init__(self, client):
        self.client = client

    async def get_current_legislature_id(self, fallback: int = 57) -> int:
        """Serviço independente para regras de negócio da Câmara."""
        params = {
            ApiParams.ORDEM.value: ApiParams.ORDEM_DESC.value,
            ApiParams.ORDENAR_POR.value: "id",
            ApiParams.ITENS.value: 1,
        }
        dados = await self.client.fetch(ApiRoutes.LEGISLATURAS, params=params)
        if dados and len(dados) > 0:
            return int(dados[0]["id"])
        return fallback

    async def get_legislature_start_date(self, legislatura_id: int) -> str | None:
        """Busca a data de início de uma legislatura específica."""
        endpoint = f"{ApiRoutes.LEGISLATURAS.value}/{legislatura_id}"
        dados = await self.client.fetch(endpoint)
        if isinstance(dados, list) and dados:
            dados = dados[0]
        if isinstance(dados, dict):
            return dados.get("dataInicio")
        return None
