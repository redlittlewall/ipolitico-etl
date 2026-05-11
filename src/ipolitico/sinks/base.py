from abc import ABC, abstractmethod
from typing import Any, List, Optional, Union

import polars as pl

from ipolitico.core.constants import MedallionLayer


class BaseSink(ABC):
    """
    Interface Base para todos os sistemas de armazenamento (Sinks).
    Aplica o Padrão Strategy e o SRP.
    """

    @abstractmethod
    async def save(
        self,
        df: pl.DataFrame,
        table_name: str,
        layer: MedallionLayer = MedallionLayer.BRONZE,
        unique_keys: Optional[Union[str, List[str]]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Salva um DataFrame no armazenamento destino.

        Args:
            df (pl.DataFrame): Dados a serem salvos.
            table_name (str): Nome da tabela ou entidade destino.
            layer (str): Camada Medallion destino. Padrão "bronze".
            unique_keys (str | List[str], optional): Chaves para deduplicação no UPSERT.
            **kwargs: Parâmetros adicionais específicos do armazenamento.
        """
        pass
