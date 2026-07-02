from __future__ import annotations

import abc
from typing import Any

import polars as pl


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
        para cada linha usando o valor dessa coluna como ``resource_id``.
        Caso contrário, a mesma URL (construída sem resource_id) é aplicada
        a todas as linhas.

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

        if resource_id_col is not None and resource_id_col in df.columns:
            source_urls = [
                self.build_source_url(endpoint, resource_id=str(rid), params=params)
                for rid in df[resource_id_col].to_list()
            ]
            return df.with_columns(pl.Series("_source_url", source_urls, dtype=pl.String)).select(
                ["_source_url"] + [c for c in df.columns if c != "_source_url"]
            )

        url = self.build_source_url(endpoint, params=params)
        return df.with_columns(pl.lit(url).alias("_source_url").cast(pl.String)).select(
            ["_source_url"] + [c for c in df.columns if c != "_source_url"]
        )
