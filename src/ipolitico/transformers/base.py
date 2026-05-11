import abc
from typing import Any

import polars as pl


class BaseTransformer(abc.ABC):
    """
    Interface base para todas as classes de transformação de dados (Camada Inteligente).

    Define o contrato padrão que todos os transformers devem implementar,
    garantindo que o orquestrador (PipelineRunner) possa executá-los de
    forma agnóstica, sem precisar conhecer seus detalhes internos.
    """

    @abc.abstractmethod
    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Executa a transformação da regra de negócio (limpeza, tipagem, padronização).

        Args:
            df (pl.DataFrame): O DataFrame bruto (ex: dados espelhados da camada Bronze).
            **kwargs (Any): Metadados adicionais ou parâmetros de contexto necessários
                            para a transformação (ex: ano, limites temporais, watermarks).

        Returns:
            pl.DataFrame: O DataFrame limpo e transformado, pronto para a camada Silver/Gold.
        """
        pass
