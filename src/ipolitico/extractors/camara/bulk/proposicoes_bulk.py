from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class ProposicoesBulkExtractor(BaseBulkExtractor):
    """
    Extrator em lote (Bulk) para dados massivos de proposições legislativas.

    Retorna os dados estritamente no formato original (Raw). Castings de data
    e tipagem forte serão aplicados pela Camada Inteligente (Transformers).
    """

    domain_name = "proposicoes"
