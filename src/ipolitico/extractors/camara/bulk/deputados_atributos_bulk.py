from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class DeputadosAtributosBulkExtractor(BaseBulkExtractor):
    """
    Extrator em lote customizado para atributos biográficos massivos dos deputados
    (ex: Profissões e Ocupações).

    Fornece os dados estritamente em seu formato bruto (Raw). O mapeamento
    e a padronização de chaves estrangeiras (ex: renomear 'id' para 'id_deputado')
    devem ser realizados pelo respectivo Transformer na Camada Silver.
    """

    # Se atributos específicos necessitarem de domain_names dinâmicos,
    # as classes que herdarem desta (ex: ProfissoesBulkExtractor) os definirão.
    pass
