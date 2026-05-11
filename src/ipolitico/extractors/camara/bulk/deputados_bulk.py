from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class DeputadosBulkExtractor(BaseBulkExtractor):
    """
    Extrator em lote (Bulk) de dados cadastrais dos Deputados da Câmara.

    Responsável apenas por herdar as rotinas de I/O de rede e leitura bruta
    do BaseBulkExtractor. Regras de negócio, como a extração do 'id' numérico
    a partir da coluna 'uri', são delegadas ao CamaraDeputadosTransformer.
    """

    domain_name = "deputados"
