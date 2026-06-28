import abc
from typing import Any

import polars as pl


class BaseExtractor(abc.ABC):
    """
    Interface base estrita para todos os Extratores.

    Garante o Princípio da Responsabilidade Única (SRP): a única função
    de um extrator é buscar dados da origem e retorná-los em formato bruto (raw),
    sem aplicar regras de negócio ou interagir com o destino (Sinks).
    """

    @abc.abstractmethod
    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """
        Executa a extração dos dados da origem.

        Args:
            **kwargs: Parâmetros contextuais para a extração
                      (ex: url, ano, parâmetros de paginação).

        Returns:
            pl.DataFrame: DataFrame contendo os dados estritamente brutos.
        """
        pass
