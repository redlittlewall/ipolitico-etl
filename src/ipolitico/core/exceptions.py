"""Exceções compartilhadas do iPolitico.

Vivem fora dos clients para que o ``PipelineRunner`` (genérico, multi-fonte)
consiga capturá-las sem se acoplar a um domínio específico. Outros clients
(Senado, Senado-adm, Portal) podem levantar ``ResourceQuarantinedError`` no
futuro com o mesmo mecanismo de quarentena.
"""


class ResourceQuarantinedError(Exception):
    """
    Um recurso da API entrou em quarentena por falhas 5xx consecutivas.

    Sinaliza que o endpoint (path + parâmetros estáveis) está respondendo erro
    de servidor de forma persistente — não é throttling que cede com backoff.
    O chamador deve tratar como "pula este recurso" e NÃO re-tentar: novas
    chamadas ao mesmo recurso sobem imediatamente, sem contato com a rede.

    Args:
        message: Recurso em quarentena, com URL legível para o log.

    Returns:
        N/A (é uma exceção).

    Raises:
        ResourceQuarantinedError: sempre que instanciada e lançada.
    """

    pass
