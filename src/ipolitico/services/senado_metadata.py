"""Serviço de metadados para a API do Senado Federal.

Versão simplificada que retorna a legislatura atual com base no ano corrente,
sem consulta à API (o Senado não expõe endpoints de legislatura como a Câmara).
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SenadoMetadataService:
    """
    Serviço de metadados para o Senado.

    Como a API do Senado não expõe um endpoint de legislaturas dedicado
    (diferente da Câmara), esta implementação calcula a legislatura atual
    a partir do ano corrente.

    As legislaturas no Senado duram 4 anos e coincidem com as da Câmara
    (ex: 57ª: 2023-2027, 58ª: 2027-2031).
    """

    LEGISLATURA_INICIO = {57: 2023, 58: 2027, 59: 2031, 60: 2035}

    def __init__(self) -> None:
        self._current_leg = self._resolve_legislatura(datetime.now().year)

    @staticmethod
    def _resolve_legislatura(year: int) -> int:
        """Retorna o número da legislatura para um dado ano."""
        for leg, start_year in sorted(
            SenadoMetadataService.LEGISLATURA_INICIO.items(), reverse=True
        ):
            if year >= start_year:
                return leg
        return 57  # fallback

    async def get_current_legislature_id(self, fallback: int = 57) -> int:
        """
        Retorna o ID da legislatura atual.

        Args:
            fallback: Valor padrão se não for possível determinar.

        Returns:
            Número da legislatura atual.
        """
        return self._current_leg

    async def get_legislature_start_date(self, legislatura_id: int) -> str | None:
        """
        Retorna a data de início de uma legislatura.

        Args:
            legislatura_id: Número da legislatura (ex: 57).

        Returns:
            Data ISO da primeira sessão, ou None se desconhecida.
        """
        start_year = self.LEGISLATURA_INICIO.get(legislatura_id)
        if start_year:
            return f"{start_year}-02-01"
        return None
