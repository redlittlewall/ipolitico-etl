"""Serviço de metadados para o Portal da Transparência (CGU).

O Portal da Transparência não tem o conceito de legislatura (é o Poder
Executivo Federal, não uma casa legislativa). O ``PipelineManager`` exige um
serviço de metadados para computar a ``legislatura``/``ano_âncora`` dos jobs —
irrelevante para os domínios do portal, que são bulk snapshot (o planner
``SnapshotWindowStrategy`` produz 1 job vazio, ignorando o ano âncora). Este
serviço devolve constantes com esse único propósito, documentando que o valor
não carrega significado de domínio.
"""

import logging

logger = logging.getLogger(__name__)

# Constante: o portal não tem legislaturas; o valor é só um placeholder estável
# para o contrato do PipelineManager (nunca alimenta janela temporal — todos os
# domínios do portal são snapshot bulk, sem partição por ano).
_PLACEHOLDER_LEG = 1
_PLACEHOLDER_START = "2000-01-01"


class PortalTransparenciaMetadataService:
    """
    Serviço de metadados para o Portal da Transparência (CGU).

    Diferente das casas legislativas (Câmara/Senado), o Executivo não tem
    legislatura: os métodos devolvem constantes placeholder, pois o
    ``PipelineManager`` os invoca incondicionalmente para o âncora de ano dos
    jobs — e os domínios do portal (bulk snapshot) não o consomem.
    """

    async def get_current_legislature_id(self, fallback: int = _PLACEHOLDER_LEG) -> int:
        """
        Retorna o ID "de legislatura" do portal (constante placeholder).

        O portal não tem legislaturas; o valor existe apenas para satisfazer o
        contrato do ``PipelineManager`` (nunca usado em janela temporal).

        Args:
            fallback: Ignorado — o portal devolve sempre o placeholder.

        Returns:
            Sempre ``_PLACEHOLDER_LEG`` (1).
        """
        return _PLACEHOLDER_LEG

    async def get_legislature_start_date(self, legislatura_id: int) -> str | None:
        """
        Retorna a data de início "de legislatura" (constante placeholder).

        Args:
            legislatura_id: Ignorado — o portal devolve sempre o placeholder.

        Returns:
            Sempre ``_PLACEHOLDER_START`` (``"2000-01-01"``).
        """
        return _PLACEHOLDER_START
