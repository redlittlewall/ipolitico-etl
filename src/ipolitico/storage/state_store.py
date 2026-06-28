"""Interface StateStore para consulta de estado persistido (watermarks e IDs).

Substitui o papel que BaseSink desempenhava como state store, permitindo
que DataLakeRepository (e futuros repositórios) implementem a interface.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class StateStore(ABC):
    """
    Interface para consulta de estado persistido no Data Lake.

    Responsável por fornecer:
    - Watermarks (marca d'água para retomada incremental)
    - IDs existentes (para evitar re-processamento)
    """

    @abstractmethod
    def get_watermark(self, table_name: str, watermark_column: str) -> Optional[str]:
        """
        Retorna o maior valor da coluna watermark para uma tabela.

        Args:
            table_name: Nome da tabela/domínio (ex: 'deputados', 'despesas').
            watermark_column: Nome da coluna que serve como marca d'água
                (ex: 'dataDocumento', 'dataHoraInicio').

        Returns:
            O valor máximo em formato string ISO, ou None se não houver dados.
        """
        ...

    @abstractmethod
    def get_existing_ids(
        self,
        table_name: str,
        layer: str,
        column: str = "id",
    ) -> List[Any]:
        """
        Retorna os valores distintos de uma coluna ID já persistidos.

        Args:
            table_name: Nome da tabela/domínio (ex: 'deputados', 'votacoes').
            layer: Camada Medallion ('silver', 'gold').
            column: Nome da coluna de ID (padrão 'id').

        Returns:
            Lista de valores distintos encontrados, ou lista vazia se não
            houver dados ou a tabela não existir.
        """
        ...
