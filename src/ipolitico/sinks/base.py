from abc import ABC, abstractmethod

import polars as pl


class BaseSink(ABC):
    """
    Interface Base (Contrato) para todos os sistemas de armazenamento (Cofres).
    Seguindo o Padrão Strategy e o SRP.
    """

    @abstractmethod
    async def save(self, df: pl.DataFrame, table_name: str) -> None:
        """
        Método obrigatório para salvar um DataFrame.
        """
        pass
