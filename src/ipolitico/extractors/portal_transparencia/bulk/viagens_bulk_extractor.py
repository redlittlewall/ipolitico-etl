"""Extrator bulk do domínio cg_viagens — dump anual multi-CSV do portal.

O ZIP anual de viagens (``/download-de-dados/viagens/{YYYY}`` → ``{YYYY}_{data}
_Viagens.zip``) tem **4 CSVs heterogêneos** — ``*_Pagamento.csv``,
``*_Passagem.csv``, ``*_Trecho.csv`` e ``*_Viagem.csv`` (o dump não é um único
CSV como os demais módulos do portal). A entidade-pai é o ``*_Viagem.csv``
(22 colunas, latin-1, separador ";", ``identificador_processo_viagem`` único —
verificado no dump real de 2016: 855.805 linhas, 855.805 identificadores
distintos). Os outros 3 CSVs referenciam o mesmo processo de viagem várias
vezes (um trecho, uma passagem, um pagamento por viagem) e têm schemas
diferentes — concatená-los (comportamento do ``PortalTransparenciaBulkExtractor
._load_raw_df``) quebraria a unicidade da UK Silver e misturaria colunas.

A única diferença para o base é, portanto, ``_load_raw_df``: seleciona apenas o
membro ``*_Viagem.csv`` do ZIP e o lê via ``_read_single_csv`` — que aplica o
``rename_map`` do BULK_REGISTRY (coluna do CSV → contrato snake_case) e injeta
``_source_url``. Tudo o mais (URL anual por convenção de segmento, cache por
domínio, WAF-gracioso via ``PortalTransparenciaWAFError``) é herdado.
"""

from __future__ import annotations

import logging
import os
import zipfile

import polars as pl

from ipolitico.extractors.portal_transparencia.bulk.bulk_extractor import (
    PortalTransparenciaBulkExtractor,
)

logger = logging.getLogger(__name__)


class PortalViagensBulkExtractor(PortalTransparenciaBulkExtractor):
    """
    Extrator do dump anual de viagens (seleciona apenas o CSV da entidade-pai).

    Estende o ``PortalTransparenciaBulkExtractor`` apenas no carregamento do
    arquivo baixado: em vez de concatenar todos os CSVs do ZIP multi-membro,
    extrai somente o ``*_Viagem.csv`` (a entidade-pai, com ``identificador_
    processo_viagem`` único) e o lê com o ``rename_map`` do registry. URL,
    cache, download com resume via Range e WAF-gracioso são herdados.
    """

    def _load_raw_df(self, dest_path: str, workdir: str, url: str) -> pl.DataFrame:
        """
        Carrega o dump de viagens selecionando apenas o CSV da entidade-pai.

        O ZIP anual tem 4 CSVs heterogêneos (Pagamento/Passagem/Trecho/Viagem);
        o base concatenaria todos via ``diagonal_relaxed``, o que quebraria a
        unicidade do ``identificador_processo_viagem`` (os CSVs filhos repetem o
        processo por trecho/passagem/pagamento). Este override extrai só o
        membro ``*_Viagem.csv`` e delega a leitura ao ``_read_single_csv``
        (rename_map + ``_source_url``). ZIP sem esse membro → DataFrame vazio
        (não cai o job); ZIP corrompido ou corpo não-ZIP herda o base.

        Args:
            dest_path: Caminho do arquivo baixado (ZIP anual de viagens).
            workdir: Diretório de trabalho do download (extração do ZIP).
            url: URL de origem do dump (vira ``_source_url`` no DataFrame).

        Returns:
            DataFrame bruto do ``*_Viagem.csv`` com ``_source_url`` como
            primeira coluna, ou DataFrame vazio se o ZIP não tem o membro
            ``*_Viagem.csv`` ou está corrompido.
        """
        if zipfile.is_zipfile(dest_path):
            try:
                with zipfile.ZipFile(dest_path, "r") as zip_ref:
                    members = [m for m in zip_ref.namelist() if not m.endswith("/")]
                    viagem = [m for m in members if m.endswith("_Viagem.csv")]
                    if not viagem:
                        logger.warning(
                            f"ZIP de viagens sem membro *_Viagem.csv em {url}. Devolvendo vazio."
                        )
                        return pl.DataFrame()
                    zip_ref.extract(viagem[0], workdir)
                    return self._read_single_csv(os.path.join(workdir, viagem[0]), url)
            except zipfile.BadZipFile:
                logger.error(f"Arquivo ZIP corrompido baixado de {url}. Abortando.")
                return pl.DataFrame()

        # Corpo não-ZIP (CSV direto ou HTML de erro) — herda o base.
        return super()._load_raw_df(dest_path, workdir, url)

    def _read_single_csv(self, dest_path: str, url: str) -> pl.DataFrame:
        """
        Lê o *_Viagem.csv com parsing quote-aware (``quote_char='"'``).

        O dump real de viagens tem o campo **Motivo** com ``;`` DENTRO de aspas
        (ex: prosa citando vários números de PCDP). Com o padrão do base
        (``quote_char=None``), a linha vira 26 campos e o ``truncate_ragged_lines``
        corta os valores monetários reais, deixando fragmentos do Motivo nas
        colunas de valor (corrupção validada real no ticket 04: soma absurda
        2e18 no Silver de 2016). O RFC-4180 do CSV é standard (campos citados),
        então o parsing com aspas alinha tudo; a remoção manual de aspas que o
        base ainda executa vira no-op (o parser já consumiu as aspas estruturais
        e não sobra literal no valor).

        Args:
            dest_path: Caminho do CSV *_Viagem.csv extraído/baixado.
            url: URL de origem do dump (vira ``_source_url`` por linha).

        Returns:
            DataFrame bruto com ``_source_url`` como primeira coluna e as 22
            colunas do contrato alinhadas (monetárias com os valores reais).
        """
        return super()._read_single_csv(dest_path, url, quote_char='"')
