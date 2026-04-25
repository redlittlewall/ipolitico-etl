class BulkExtractor:
    """Extrai grandes volumes de dados via arquivos estáticos (JSON/CSV)."""

    BASE_URL = "http://dadosabertos.camara.leg.br/arquivos"

    async def download_ano(self, dataset: str, ano: int):
        """
        Ex: download_ano("despesas", 2024)
        Baixa o ZIP, extrai o JSON e retorna como DataFrame.
        """
        # url = f"{self.BASE_URL}/{dataset}/json/{dataset}-{ano}.json.zip"
        # async with httpx.AsyncClient() as client:
        # resp = await client.get(url)
        # Lógica para descompactar o ZIP em memória e ler com Polars
        # O Polars lê JSONs gigantes em milissegundos.
