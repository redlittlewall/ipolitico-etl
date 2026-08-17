from __future__ import annotations

import abc
from typing import Any

import polars as pl

# Chave reservada que marca, em cada registro bruto, o número da página de
# origem (issue 01). Taggeada pelo ``fetch_paginated`` da Câmara e consumida
# pelo ``_inject_source_url`` para montar a URL replayável com ``pagina=N``.
SOURCE_PAGE_COL = "_source_page"


class BaseExtractor(abc.ABC):
    """
    Interface base estrita para todos os Extratores.

    Garante o Princípio da Responsabilidade Única (SRP): a única função
    de um extrator é buscar dados da origem e retorná-los em formato bruto (raw),
    sem aplicar regras de negócio ou interagir com o destino (Sinks).

    Attributes:
        base_url: URL base da API. Subclasses concretas (ex: CamaraBaseExtractor)
                  devem sobrescrever este valor.
        source_url_format: Template opcional para URL de recurso específico.
                           Ex: ``"https://api.exemplo/v2/entidade/{resource_id}"``.
    """

    base_url: str = ""
    source_url_format: str | None = None

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

    def build_source_url(
        self,
        endpoint: str,
        resource_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> str:
        """
        Constrói a URL de auditoria para um registro.

        Regras:
        1. Se ``resource_id`` e ``source_url_format`` existirem, formata a URL
           do recurso específico via ``source_url_format.format(resource_id=...)``.
        2. Senão, constrói a URL a partir de ``base_url`` + ``endpoint`` +
           parâmetros de consulta (ordenados, ignorando valores None).

        Args:
            endpoint: Caminho relativo do recurso (ex: ``'deputados'``).
            resource_id: ID do recurso específico (opcional).
            params: Parâmetros de query string (opcional).

        Returns:
            str: URL absoluta de auditoria.
        """
        if resource_id is not None and self.source_url_format is not None:
            return self.source_url_format.format(resource_id=resource_id)

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
            if qs:
                url += f"?{qs}"
        return url

    def build_list_source_url(
        self,
        endpoint: str,
        params: dict[str, Any] | None,
        page: int | None = None,
    ) -> str:
        """
        Constrói a URL de auditoria de uma lista paginada, com página opcional.

        Para listas sem ID único (ex: despesas, discursos), a URL precisa ser
        replayável até o registro: ``pagina=N`` é mesclado aos parâmetros
        (ordenados) quando informado. Usada pelo ``_inject_source_url`` e por
        extratores que montam a URL por registro manualmente (ex: rotas
        filhas de partidos), evitando duplicar o merge de ``pagina``.

        Args:
            endpoint: Caminho relativo do recurso (ex: ``'deputados/1/despesas'``).
            params: Parâmetros de query string (opcional).
            page: Número exato da página de origem (opcional; sem página, a
                  URL aponta para a lista sem o parâmetro ``pagina``).

        Returns:
            str: URL absoluta de auditoria da lista.
        """
        merged = dict(params or {})
        if page is not None:
            merged["pagina"] = page
        return self.build_source_url(endpoint, params=merged)

    def _inject_source_url(
        self,
        df: pl.DataFrame,
        endpoint: str,
        resource_id_col: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> pl.DataFrame:
        """
        Adiciona a coluna ``_source_url`` como primeira coluna do DataFrame.

        Se ``resource_id_col`` for informado, constrói uma URL específica
        por linha (URL de detalhe do recurso, ex: ``.../deputados/123``),
        mesmo que a extração tenha marcado ``_source_page`` — a URL de
        detalhe já é o melhor replay direto ao registro.

        Caso contrário (lista paginada sem ID único, ex: despesas), usa a
        coluna ``_source_page`` — se presente — para montar por linha uma
        URL replayável com ``pagina=N`` mesclado nos parâmetros ordenados;
        sem ``_source_page``, a mesma URL (construída sem resource_id) é
        aplicada a todas as linhas. A coluna interna ``_source_page`` nunca
        vaza para o DataFrame de saída.

        Args:
            df: DataFrame de dados brutos.
            endpoint: Caminho relativo do recurso.
            resource_id_col: Nome da coluna cujo valor será usado como
                             ``resource_id`` (opcional).
            params: Parâmetros de query string (opcional).

        Returns:
            pl.DataFrame: DataFrame com ``_source_url`` como primeira coluna.
        """
        if df.is_empty():
            return df

        has_page = SOURCE_PAGE_COL in df.columns

        if resource_id_col is not None and resource_id_col in df.columns:
            source_urls = [
                self.build_source_url(endpoint, resource_id=str(rid), params=params)
                for rid in df[resource_id_col].to_list()
            ]
            df = df.with_columns(pl.Series("_source_url", source_urls, dtype=pl.String))
        else:
            pages = df[SOURCE_PAGE_COL].to_list() if has_page else None
            base_params = dict(params or {})
            if pages is None or all(page is None for page in pages):
                url = self.build_source_url(endpoint, params=base_params)
                df = df.with_columns(pl.lit(url).alias("_source_url").cast(pl.String))
            else:
                source_urls = [
                    self.build_list_source_url(endpoint, base_params, page) for page in pages
                ]
                df = df.with_columns(pl.Series("_source_url", source_urls, dtype=pl.String))

        if has_page:
            df = df.drop(SOURCE_PAGE_COL)
        return df.select(["_source_url"] + [c for c in df.columns if c != "_source_url"])
