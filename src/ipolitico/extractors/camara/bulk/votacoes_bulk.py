from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class VotacoesBulkExtractor(BaseBulkExtractor):
    """
    Extrator em lote (Bulk) do cabeçalho de votações.

    Retorna os dados estritamente no formato original (Raw) da Câmara.
    Castings de datahora serão delegados para o Transformer específico.
    """

    domain_name = "votacoes"


class VotosBulkExtractor(BaseBulkExtractor):
    """
    Extrator em lote (Bulk) dos votos individuais dos parlamentares.

    Extrai o CSV bruto. A renomeação de colunas (como 'idDeputado' para
    'deputado_id') e a tipagem de IDs ocorrem exclusivamente no processo
    de transformação.
    """

    domain_name = "votos"
