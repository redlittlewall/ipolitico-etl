from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class DespesasBulkExtractor(BaseBulkExtractor):
    """
    Extrator em lote (Bulk) focado nos Dumps ZIP anuais de Cotas Parlamentares (CEAP).

    Responsável puramente pela extração (I/O) dos dados da fonte. Padronizações
    de schema, conversões complexas de moeda brasileira e formatação de datas
    são responsabilidades exclusivas do CamaraDespesasTransformer (Camada Silver).
    """

    domain_name = "despesas"
