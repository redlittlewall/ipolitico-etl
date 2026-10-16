"""Builder da Camada Platinum (Issue 07).

Constrói os Data Marts OBT (One Big Table) desnormalizados:
- ``obt_politico_custo_mensal``: Grão mensal por político com rubricas detalhadas.
- ``obt_politico_resumo_carreira``: Resumo histórico por político (custo + atividade).

Utiliza DuckDB (in-memory) com queries analíticas SQL vetorizadas e gera
DataFrames Polars gravados em ``data/datalake/platinum/*.parquet`` (compressão ZSTD).
Suporta exportação para SQLite e DuckDB relacional.
"""

from __future__ import annotations

import logging
import sqlite3
import tempfile
from pathlib import Path

import duckdb
import polars as pl

from ipolitico.core.constants import DomainType, MedallionLayer
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.gold._datalake import ler_silver
from ipolitico.gold.custo_erario import CUSTO_SCHEMA
from ipolitico.gold.resolutor import ALIAS_SCHEMA, POLITICO_SCHEMA
from ipolitico.platinum.models import (
    OBT_POLITICO_CUSTO_MENSAL_SCHEMA,
    OBT_POLITICO_RESUMO_CARREIRA_SCHEMA,
    TABLE_OBT_POLITICO_CUSTO_MENSAL,
    TABLE_OBT_POLITICO_RESUMO_CARREIRA,
    CoberturaPlatinum,
)

logger = logging.getLogger(__name__)


class PlatinumBuilder:
    """Constrói e exporta as tabelas analíticas OBT da Camada Platinum.

    Args:
        base_dir: Diretório raiz do DataLake (padrão ``data/datalake``).
    """

    def __init__(self, base_dir: str = "data/datalake"):
        self.base_dir = Path(base_dir)
        self.platinum_dir = self.base_dir / MedallionLayer.PLATINUM

    def build(self) -> CoberturaPlatinum:
        """Executa a transformação analítica completa e materializa a Camada Platinum.

        Lê as tabelas consolidadas da Gold (``politicos``, ``politicos_aliases``,
        ``custo_erario``) e fatos Silver, processa via DuckDB in-memory e grava
        os arquivos Parquet (ZSTD) em ``{base_dir}/platinum/*.parquet``.

        Returns:
            ``CoberturaPlatinum`` com as métricas do lote gerado.
        """
        # Leitura upstream Gold
        politicos = self._ler_gold("politicos", POLITICO_SCHEMA)
        aliases = self._ler_gold("politicos_aliases", ALIAS_SCHEMA)
        custo = self._ler_gold("custo_erario", CUSTO_SCHEMA)

        # Leitura upstream Silver
        deputados = self._ler_silver(DomainType.DEPUTADOS)
        senadores = self._ler_silver(DomainType.SENADORES)
        proposicoes = self._ler_silver(DomainType.PROPOSICOES)
        autores = self._ler_silver(DomainType.AUTORES)
        votacoes = self._ler_silver(DomainType.VOTACOES)
        votacoes_prop = self._ler_silver(DomainType.VOTACOES_PROPOSICOES)
        votacoes_obj = self._ler_silver(DomainType.VOTACOES_OBJETOS)
        votos = self._ler_silver(DomainType.VOTOS)
        votos_senado = self._ler_silver(DomainType.VOTOS_SENADO)
        presenca = self._ler_silver(DomainType.EVENTOS_PRESENCA_DEPUTADOS)

        df_custo_mensal, df_resumo_carreira = self.transform(
            politicos=politicos,
            politicos_aliases=aliases,
            custo_erario=custo,
            deputados=deputados,
            senadores=senadores,
            proposicoes=proposicoes,
            autores=autores,
            votacoes=votacoes,
            votacoes_proposicoes=votacoes_prop,
            votacoes_objetos=votacoes_obj,
            votos=votos,
            votos_senado=votos_senado,
            eventos_presenca_deputados=presenca,
        )

        # Garante diretório platinum
        self.platinum_dir.mkdir(parents=True, exist_ok=True)

        # Gravação Parquet (ZSTD)
        file_custo_mensal = self.platinum_dir / f"{TABLE_OBT_POLITICO_CUSTO_MENSAL}.parquet"
        file_resumo_carreira = self.platinum_dir / f"{TABLE_OBT_POLITICO_RESUMO_CARREIRA}.parquet"

        df_custo_mensal.write_parquet(file_custo_mensal, compression="zstd")
        df_resumo_carreira.write_parquet(file_resumo_carreira, compression="zstd")

        logger.info(
            "Camada Platinum gerada com sucesso: %d registros mensais, %d resumos de carreira.",
            df_custo_mensal.height,
            df_resumo_carreira.height,
        )

        return self._relatorio(df_custo_mensal, df_resumo_carreira)

    def cobertura(self) -> CoberturaPlatinum:
        """Lê os Parquets Platinum existentes e computa o relatório analítico (CQS).

        Returns:
            ``CoberturaPlatinum`` preenchida.
        """
        file_custo_mensal = self.platinum_dir / f"{TABLE_OBT_POLITICO_CUSTO_MENSAL}.parquet"
        file_resumo_carreira = self.platinum_dir / f"{TABLE_OBT_POLITICO_RESUMO_CARREIRA}.parquet"

        df_custo = (
            pl.read_parquet(file_custo_mensal)
            if file_custo_mensal.exists()
            else pl.DataFrame(schema=OBT_POLITICO_CUSTO_MENSAL_SCHEMA)
        )
        df_resumo = (
            pl.read_parquet(file_resumo_carreira)
            if file_resumo_carreira.exists()
            else pl.DataFrame(schema=OBT_POLITICO_RESUMO_CARREIRA_SCHEMA)
        )
        return self._relatorio(df_custo, df_resumo)

    def export_all(self, output_path: str, format: str = "sqlite") -> list[str]:
        """Exporta os datasets analíticos Platinum para SQLite ou DuckDB relacional.

        Args:
            output_path: Caminho do arquivo de destino (.db ou .duckdb).
            format: Formato de exportação (``sqlite`` ou ``duckdb``).

        Returns:
            Lista de nomes de tabelas exportadas com sucesso.
        """
        tables = [TABLE_OBT_POLITICO_CUSTO_MENSAL, TABLE_OBT_POLITICO_RESUMO_CARREIRA]
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if format.lower() == "duckdb":
            con = duckdb.connect(database=":memory:")
            try:
                con.execute(f"ATTACH '{out_path}' AS plat_db")
                for table in tables:
                    source_file = self.platinum_dir / f"{table}.parquet"
                    if source_file.exists():
                        con.execute(
                            f'CREATE OR REPLACE TABLE plat_db."{table}" AS '
                            f"SELECT * FROM read_parquet('{source_file}')"
                        )
            finally:
                con.close()
            return tables

        # SQLite nativo via sqlite3 (zero dependência de extensões binárias)
        conn = sqlite3.connect(out_path)
        try:
            for table in tables:
                source_file = self.platinum_dir / f"{table}.parquet"
                if not source_file.exists():
                    continue
                df = pl.read_parquet(source_file)
                conn.execute(f'DROP TABLE IF EXISTS "{table}"')
                cols_def = ", ".join([f'"{col}" TEXT' for col in df.columns])
                conn.execute(f'CREATE TABLE "{table}" ({cols_def})')

                placeholders = ", ".join(["?"] * len(df.columns))
                conn.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', df.iter_rows())

                # Cria índices para otimizar consultas analíticas
                conn.execute(
                    f'CREATE INDEX IF NOT EXISTS "idx_{table}_politico" '
                    f'ON "{table}" ("id_politico_canônico")'
                )
                if "ano_mes" in df.columns:
                    conn.execute(
                        f'CREATE INDEX IF NOT EXISTS "idx_{table}_ano_mes" '
                        f'ON "{table}" ("ano_mes")'
                    )
            conn.commit()
        finally:
            conn.close()

        return tables

    # ------------------------------------------------------------------
    #  Transformação analítica central (DuckDB OLAP)
    # ------------------------------------------------------------------

    def transform(
        self,
        politicos: pl.DataFrame,
        politicos_aliases: pl.DataFrame,
        custo_erario: pl.DataFrame,
        deputados: pl.DataFrame | None = None,
        senadores: pl.DataFrame | None = None,
        proposicoes: pl.DataFrame | None = None,
        autores: pl.DataFrame | None = None,
        votacoes: pl.DataFrame | None = None,
        votacoes_proposicoes: pl.DataFrame | None = None,
        votacoes_objetos: pl.DataFrame | None = None,
        votos: pl.DataFrame | None = None,
        votos_senado: pl.DataFrame | None = None,
        eventos_presenca_deputados: pl.DataFrame | None = None,
        **kwargs,
    ) -> tuple[pl.DataFrame, pl.DataFrame]:
        """Executa as transformações analíticas em DuckDB e devolve os dois DataFrames OBT.

        Args:
            politicos: Tabela Gold ``politicos``.
            politicos_aliases: Tabela Gold ``politicos_aliases``.
            custo_erario: Tabela Gold ``custo_erario``.
            deputados: Silver ``deputados`` (opcional).
            senadores: Silver ``senadores`` (opcional).
            proposicoes: Silver ``proposicoes`` (opcional).
            autores: Silver ``autores`` (opcional).
            votacoes: Silver ``votacoes`` (opcional).
            votacoes_proposicoes: Silver ``votacoes_proposicoes`` (opcional).
            votacoes_objetos: Silver ``votacoes_objetos`` (opcional).
            votos: Silver ``votos`` (opcional).
            votos_senado: Silver ``votos_senado`` (opcional).
            eventos_presenca_deputados: Silver ``eventos_presenca_deputados`` (opcional).
            kwargs: Suporte a aliases como ``presenca`` e ``votacoes_prop``.

        Returns:
            Tupla ``(df_obt_custo_mensal, df_obt_resumo_carreira)`` em conformidade
            estrita com seus schemas contratuais.
        """
        if eventos_presenca_deputados is None and "presenca" in kwargs:
            eventos_presenca_deputados = kwargs["presenca"]
        if votacoes_proposicoes is None and "votacoes_prop" in kwargs:
            votacoes_proposicoes = kwargs["votacoes_prop"]

        # Se politicos estiver vazio, devolve schemas vazios
        if politicos.is_empty():
            return (
                pl.DataFrame(schema=OBT_POLITICO_CUSTO_MENSAL_SCHEMA),
                pl.DataFrame(schema=OBT_POLITICO_RESUMO_CARREIRA_SCHEMA),
            )

        # Prepara fallbacks com schemas oficiais para ausentes
        deputados = (
            deputados
            if deputados is not None and not deputados.is_empty()
            else pl.DataFrame(schema=SILVER_SCHEMAS[DomainType.DEPUTADOS.value])
        )
        senadores = (
            senadores
            if senadores is not None and not senadores.is_empty()
            else pl.DataFrame(schema=SILVER_SCHEMAS[DomainType.SENADORES.value])
        )
        proposicoes = (
            proposicoes
            if proposicoes is not None and not proposicoes.is_empty()
            else pl.DataFrame(schema=SILVER_SCHEMAS[DomainType.PROPOSICOES.value])
        )
        autores = (
            autores
            if autores is not None and not autores.is_empty()
            else pl.DataFrame(schema=SILVER_SCHEMAS[DomainType.AUTORES.value])
        )
        votacoes = (
            votacoes
            if votacoes is not None and not votacoes.is_empty()
            else pl.DataFrame(schema=SILVER_SCHEMAS[DomainType.VOTACOES.value])
        )
        votacoes_proposicoes = (
            votacoes_proposicoes
            if votacoes_proposicoes is not None and not votacoes_proposicoes.is_empty()
            else pl.DataFrame(schema=SILVER_SCHEMAS[DomainType.VOTACOES_PROPOSICOES.value])
        )
        votacoes_objetos = (
            votacoes_objetos
            if votacoes_objetos is not None and not votacoes_objetos.is_empty()
            else pl.DataFrame(schema=SILVER_SCHEMAS[DomainType.VOTACOES_OBJETOS.value])
        )
        votos = (
            votos
            if votos is not None and not votos.is_empty()
            else pl.DataFrame(schema=SILVER_SCHEMAS[DomainType.VOTOS.value])
        )
        votos_senado = (
            votos_senado
            if votos_senado is not None and not votos_senado.is_empty()
            else pl.DataFrame(schema=SILVER_SCHEMAS[DomainType.VOTOS_SENADO.value])
        )
        eventos_presenca_deputados = (
            eventos_presenca_deputados
            if eventos_presenca_deputados is not None and not eventos_presenca_deputados.is_empty()
            else pl.DataFrame(schema=SILVER_SCHEMAS[DomainType.EVENTOS_PRESENCA_DEPUTADOS.value])
        )

        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            con = duckdb.connect(database=":memory:")

            tables_map = {
                "politicos": politicos,
                "politicos_aliases": politicos_aliases,
                "custo_erario": custo_erario,
                "deputados": deputados,
                "senadores": senadores,
                "proposicoes": proposicoes,
                "autores": autores,
                "votacoes": votacoes,
                "votacoes_proposicoes": votacoes_proposicoes,
                "votacoes_objetos": votacoes_objetos,
                "votos": votos,
                "votos_senado": votos_senado,
                "eventos_presenca_deputados": eventos_presenca_deputados,
            }

            for name, df in tables_map.items():
                p = tmp_path / f"{name}.parquet"
                df.write_parquet(p)
                con.execute(f"CREATE VIEW \"{name}\" AS SELECT * FROM read_parquet('{p}')")

            # ── 1. Query OBT Politico Custo Mensal ─────────────────────────
            query_custo_mensal = """
            WITH dep_ranked AS (
                SELECT id, partido, uf, idLegislatura,
                       ROW_NUMBER() OVER (PARTITION BY id ORDER BY idLegislatura DESC) as rn
                FROM deputados
            ),
            sen_ranked AS (
                SELECT codigo, uf, segunda_legislatura,
                       ROW_NUMBER() OVER (
                           PARTITION BY codigo ORDER BY segunda_legislatura DESC
                       ) as rn
                FROM senadores
            ),
            politico_meta AS (
                SELECT
                    p.politico_id AS id_politico_canônico,
                    COALESCE(p.nome_civil, 'Desconhecido') AS nome,
                    CASE
                        WHEN p.cpf IS NULL OR length(trim(p.cpf)) = 0 THEN NULL
                        WHEN contains(p.cpf, '*') THEN p.cpf
                        WHEN length(regexp_replace(p.cpf, '[^0-9]', '', 'g')) = 11 THEN
                            '***.' || substr(regexp_replace(p.cpf, '[^0-9]', '', 'g'), 4, 3) || '.'
                            || substr(regexp_replace(p.cpf, '[^0-9]', '', 'g'), 7, 3) || '-**'
                        WHEN length(regexp_replace(p.cpf, '[^0-9]', '', 'g')) >= 6 THEN
                            '***.' || substr(regexp_replace(p.cpf, '[^0-9]', '', 'g'),
                                length(regexp_replace(p.cpf, '[^0-9]', '', 'g')) - 5, 3) || '.'
                            || substr(regexp_replace(p.cpf, '[^0-9]', '', 'g'),
                                length(regexp_replace(p.cpf, '[^0-9]', '', 'g')) - 2, 3) || '-**'
                        ELSE p.cpf
                    END AS cpf_mascarado,
                    COALESCE(d.partido, NULL) AS partido_atual,
                    COALESCE(p.uf, d.uf, s.uf) AS uf,
                    CASE
                        WHEN p.politico_id LIKE 'pol_camara_%' THEN 'Deputado Federal'
                        WHEN p.politico_id LIKE 'pol_senado_%' THEN 'Senador'
                        WHEN d.id IS NOT NULL THEN 'Deputado Federal'
                        WHEN s.codigo IS NOT NULL THEN 'Senador'
                        ELSE 'Parlamentar'
                    END AS cargo_atual,
                    ROW_NUMBER() OVER (PARTITION BY p.politico_id) as meta_rn
                FROM politicos p
                LEFT JOIN (
                    SELECT politico_id, id_natural FROM politicos_aliases WHERE fonte = 'camara'
                ) a_cam ON p.politico_id = a_cam.politico_id
                LEFT JOIN (
                    SELECT id, partido, uf FROM dep_ranked WHERE rn = 1
                ) d ON a_cam.id_natural = d.id
                LEFT JOIN (
                    SELECT politico_id, id_natural FROM politicos_aliases WHERE fonte = 'senado'
                ) a_sen ON p.politico_id = a_sen.politico_id
                LEFT JOIN (
                    SELECT codigo, uf FROM sen_ranked WHERE rn = 1
                ) s ON a_sen.id_natural = s.codigo
            ),
            custos_mensais AS (
                SELECT
                    politico_id,
                    CAST(SUBSTR(mes, 1, 4) AS BIGINT) AS ano,
                    CAST(SUBSTR(mes, 6, 2) AS BIGINT) AS mes,
                    mes AS ano_mes,
                    COALESCE(SUM(
                        CASE WHEN LOWER(componente) = 'salario' THEN valor_total ELSE 0.0 END
                    ), 0.0) AS total_salario,
                    COALESCE(SUM(
                        CASE WHEN LOWER(componente) = 'ceap'
                             AND (LOWER(casa) = 'camara' OR casa IS NULL)
                             THEN valor_total ELSE 0.0 END
                    ), 0.0) AS total_ceap,
                    COALESCE(SUM(
                        CASE WHEN LOWER(componente) = 'ceaps'
                             OR (LOWER(componente) = 'ceap' AND LOWER(casa) = 'senado')
                             THEN valor_total ELSE 0.0 END
                    ), 0.0) AS total_ceaps,
                    COALESCE(SUM(
                        CASE WHEN LOWER(componente) LIKE '%cartao%'
                             OR LOWER(componente) LIKE '%cartões%'
                             THEN valor_total ELSE 0.0 END
                    ), 0.0) AS total_cartoes,
                    COALESCE(SUM(
                        CASE WHEN LOWER(componente) LIKE '%viage%'
                             THEN valor_total ELSE 0.0 END
                    ), 0.0) AS total_viagens,
                    COALESCE(SUM(
                        CASE WHEN LOWER(componente) IN ('assessores', 'verba_gabinete', 'gabinete')
                             THEN valor_total ELSE 0.0 END
                    ), 0.0) AS total_verba_gabinete,
                    COALESCE(SUM(valor_total), 0.0) AS custo_total_mes,
                    -- Window function: soma analítica cumulativa por político
                    SUM(SUM(valor_total)) OVER (
                        PARTITION BY politico_id ORDER BY mes
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) as custo_acumulado_window
                FROM custo_erario
                WHERE mes IS NOT NULL AND politico_id IS NOT NULL
                GROUP BY politico_id, mes
            )
            SELECT
                m.id_politico_canônico,
                m.nome,
                m.cpf_mascarado,
                m.partido_atual,
                m.uf,
                m.cargo_atual,
                c.ano,
                c.mes,
                c.ano_mes,
                c.total_salario,
                c.total_ceap,
                c.total_ceaps,
                c.total_cartoes,
                c.total_viagens,
                c.total_verba_gabinete,
                c.custo_total_mes
            FROM custos_mensais c
            JOIN politico_meta m ON c.politico_id = m.id_politico_canônico AND m.meta_rn = 1
            ORDER BY m.id_politico_canônico, c.ano_mes
            """

            out_mensal = tmp_path / "out_mensal.parquet"
            con.execute(
                f"COPY ({query_custo_mensal}) TO '{out_mensal}'"
                f" (FORMAT PARQUET, COMPRESSION 'ZSTD')"
            )
            df_custo_mensal = pl.read_parquet(out_mensal)

            # ── 2. Query OBT Politico Resumo Carreira ──────────────────────
            query_resumo_carreira = """
            WITH dep_ranked AS (
                SELECT id, partido, uf, idLegislatura,
                       ROW_NUMBER() OVER (PARTITION BY id ORDER BY idLegislatura DESC) as rn
                FROM deputados
            ),
            sen_ranked AS (
                SELECT codigo, uf, segunda_legislatura,
                       ROW_NUMBER() OVER (
                           PARTITION BY codigo ORDER BY segunda_legislatura DESC
                       ) as rn
                FROM senadores
            ),
            politico_meta AS (
                SELECT
                    p.politico_id AS id_politico_canônico,
                    COALESCE(p.nome_civil, 'Desconhecido') AS nome,
                    CASE
                        WHEN p.cpf IS NULL OR length(trim(p.cpf)) = 0 THEN NULL
                        WHEN contains(p.cpf, '*') THEN p.cpf
                        WHEN length(regexp_replace(p.cpf, '[^0-9]', '', 'g')) = 11 THEN
                            '***.' || substr(regexp_replace(p.cpf, '[^0-9]', '', 'g'), 4, 3) || '.'
                            || substr(regexp_replace(p.cpf, '[^0-9]', '', 'g'), 7, 3) || '-**'
                        WHEN length(regexp_replace(p.cpf, '[^0-9]', '', 'g')) >= 6 THEN
                            '***.' || substr(regexp_replace(p.cpf, '[^0-9]', '', 'g'),
                                length(regexp_replace(p.cpf, '[^0-9]', '', 'g')) - 5, 3) || '.'
                            || substr(regexp_replace(p.cpf, '[^0-9]', '', 'g'),
                                length(regexp_replace(p.cpf, '[^0-9]', '', 'g')) - 2, 3) || '-**'
                        ELSE p.cpf
                    END AS cpf_mascarado,
                    COALESCE(d.partido, NULL) AS partido_atual,
                    COALESCE(p.uf, d.uf, s.uf) AS uf,
                    CASE
                        WHEN p.politico_id LIKE 'pol_camara_%' THEN 'Deputado Federal'
                        WHEN p.politico_id LIKE 'pol_senado_%' THEN 'Senador'
                        WHEN d.id IS NOT NULL THEN 'Deputado Federal'
                        WHEN s.codigo IS NOT NULL THEN 'Senador'
                        ELSE 'Parlamentar'
                    END AS cargo_atual,
                    d.idLegislatura AS legislatura_dep,
                    s.segunda_legislatura AS legislatura_sen,
                    ROW_NUMBER() OVER (PARTITION BY p.politico_id) as meta_rn
                FROM politicos p
                LEFT JOIN (
                    SELECT politico_id, id_natural FROM politicos_aliases WHERE fonte = 'camara'
                ) a_cam ON p.politico_id = a_cam.politico_id
                LEFT JOIN (
                    SELECT id, partido, uf, idLegislatura FROM dep_ranked WHERE rn = 1
                ) d ON a_cam.id_natural = d.id
                LEFT JOIN (
                    SELECT politico_id, id_natural FROM politicos_aliases WHERE fonte = 'senado'
                ) a_sen ON p.politico_id = a_sen.politico_id
                LEFT JOIN (
                    SELECT codigo, uf, segunda_legislatura FROM sen_ranked WHERE rn = 1
                ) s ON a_sen.id_natural = s.codigo
            ),
            custos_agg AS (
                SELECT
                    politico_id,
                    COALESCE(SUM(valor_total), 0.0) AS custo_total_acumulado_historico,
                    COUNT(DISTINCT mandato) AS mandatos_custo,
                    COUNT(DISTINCT CAST(SUBSTR(mes, 1, 4) AS BIGINT)) AS anos_custo
                FROM custo_erario
                WHERE politico_id IS NOT NULL
                GROUP BY politico_id
            ),
            autores_politico AS (
                SELECT DISTINCT
                    COALESCE(
                        a_cam.politico_id,
                        a_sen.politico_id,
                        p.politico_id
                    ) AS politico_id,
                    aut.id_proposicao
                FROM autores aut
                LEFT JOIN (
                    SELECT politico_id, id_natural FROM politicos_aliases WHERE fonte = 'camara'
                ) a_cam
                    ON TRY_CAST(NULLIF(regexp_extract(aut.uri, 'deputados/([0-9]+)', 1), '')
                        AS BIGINT) = a_cam.id_natural
                LEFT JOIN (
                    SELECT politico_id, id_natural FROM politicos_aliases WHERE fonte = 'senado'
                ) a_sen
                    ON TRY_CAST(NULLIF(regexp_extract(aut.uri, 'senadores/([0-9]+)', 1), '')
                        AS BIGINT) = a_sen.id_natural
                LEFT JOIN politicos p ON LOWER(TRIM(aut.nome)) = LOWER(TRIM(p.nome_civil))
                WHERE COALESCE(a_cam.politico_id, a_sen.politico_id, p.politico_id) IS NOT NULL
            ),
            proposicoes_aprovadas_ids AS (
                SELECT DISTINCT vp.proposicao_id AS id_proposicao
                FROM votacoes_proposicoes vp
                JOIN votacoes v ON vp.idVotacao = v.id
                WHERE v.aprovacao = 1
                UNION
                SELECT DISTINCT vo.proposicao_id AS id_proposicao
                FROM votacoes_objetos vo
                JOIN votacoes v ON vo.idVotacao = v.id
                WHERE v.aprovacao = 1
            ),
            proposicoes_agg AS (
                SELECT
                    ap.politico_id,
                    COUNT(DISTINCT ap.id_proposicao) AS proposicoes_apresentadas,
                    COUNT(DISTINCT CASE WHEN apr.id_proposicao IS NOT NULL
                          THEN ap.id_proposicao END) AS proposicoes_aprovadas
                FROM autores_politico ap
                LEFT JOIN proposicoes_aprovadas_ids apr
                    ON ap.id_proposicao = apr.id_proposicao
                GROUP BY ap.politico_id
            ),
            votos_camara_mapped AS (
                SELECT
                    a_cam.politico_id,
                    v.votacao_id
                FROM votos v
                JOIN politicos_aliases a_cam
                    ON a_cam.fonte = 'camara' AND a_cam.id_natural = v.id_deputado
            ),
            votos_senado_mapped AS (
                SELECT
                    a_sen.politico_id,
                    CAST(vs.votacao_id AS VARCHAR) AS votacao_id
                FROM votos_senado vs
                JOIN politicos_aliases a_sen
                    ON a_sen.fonte = 'senado' AND a_sen.id_natural = vs.codigo_parlamentar
            ),
            todos_votos AS (
                SELECT * FROM votos_camara_mapped
                UNION ALL
                SELECT * FROM votos_senado_mapped
            ),
            votos_agg AS (
                SELECT
                    politico_id,
                    COUNT(1) AS votos_registrados,
                    COUNT(DISTINCT votacao_id) AS votacoes_distintas
                FROM todos_votos
                GROUP BY politico_id
            ),
            presenca_mapped AS (
                SELECT
                    a_cam.politico_id,
                    epd.idEvento
                FROM eventos_presenca_deputados epd
                JOIN politicos_aliases a_cam
                    ON a_cam.fonte = 'camara' AND a_cam.id_natural = epd.idDeputado
            ),
            presenca_agg AS (
                SELECT
                    politico_id,
                    COUNT(DISTINCT idEvento) AS eventos_presente
                FROM presenca_mapped
                GROUP BY politico_id
            ),
            total_eventos_const AS (
                SELECT COUNT(DISTINCT idEvento) AS total_eventos
                FROM eventos_presenca_deputados
            ),
            total_votacoes_const AS (
                SELECT COUNT(DISTINCT id) AS total_votacoes FROM votacoes
            )
            SELECT
                m.id_politico_canônico,
                m.nome,
                m.cpf_mascarado,
                m.partido_atual,
                m.uf,
                m.cargo_atual,
                COALESCE(c.custo_total_acumulado_historico, 0.0)
                    AS custo_total_acumulado_historico,
                CAST(GREATEST(
                    COALESCE(c.mandatos_custo, 0),
                    CASE WHEN m.legislatura_dep IS NOT NULL OR m.legislatura_sen IS NOT NULL
                         THEN 1 ELSE 0 END,
                    1
                ) AS BIGINT) AS quantidade_mandatos,
                CAST(GREATEST(
                    COALESCE(c.anos_custo, 0),
                    CASE WHEN COALESCE(c.mandatos_custo, 0) > 0
                         THEN c.mandatos_custo * 4 ELSE 0 END,
                    1
                ) AS BIGINT) AS anos_em_exercicio,
                CAST(COALESCE(pr.proposicoes_apresentadas, 0) AS BIGINT)
                    AS proposicoes_apresentadas,
                CAST(COALESCE(pr.proposicoes_aprovadas, 0) AS BIGINT)
                    AS proposicoes_aprovadas,
                ROUND(
                    CASE
                        WHEN COALESCE(pr.proposicoes_apresentadas, 0) > 0 THEN
                            (CAST(pr.proposicoes_aprovadas AS DOUBLE)
                             / CAST(pr.proposicoes_apresentadas AS DOUBLE))
                        ELSE 0.0
                    END,
                    4
                ) AS taxa_sucesso_legislativo,
                ROUND(
                    CASE
                        WHEN (SELECT total_eventos FROM total_eventos_const) > 0 THEN
                            LEAST(100.0,
                                (CAST(COALESCE(pres.eventos_presente, 0) AS DOUBLE) * 100.0)
                                / (SELECT total_eventos FROM total_eventos_const)
                            )
                        WHEN (SELECT total_votacoes FROM total_votacoes_const) > 0
                             AND COALESCE(v.votos_registrados, 0) > 0 THEN
                            LEAST(100.0,
                                (CAST(v.votacoes_distintas AS DOUBLE) * 100.0)
                                / (SELECT total_votacoes FROM total_votacoes_const)
                            )
                        ELSE 0.0
                    END,
                    2
                ) AS presenca_plenario_pct,
                CAST(COALESCE(v.votos_registrados, 0) AS BIGINT) AS votos_registrados
            FROM politico_meta m
            LEFT JOIN custos_agg c ON m.id_politico_canônico = c.politico_id
            LEFT JOIN proposicoes_agg pr ON m.id_politico_canônico = pr.politico_id
            LEFT JOIN votos_agg v ON m.id_politico_canônico = v.politico_id
            LEFT JOIN presenca_agg pres ON m.id_politico_canônico = pres.politico_id
            WHERE m.meta_rn = 1
            ORDER BY m.id_politico_canônico
            """

            out_resumo = tmp_path / "out_resumo.parquet"
            con.execute(
                f"COPY ({query_resumo_carreira}) TO '{out_resumo}'"
                f" (FORMAT PARQUET, COMPRESSION 'ZSTD')"
            )
            df_resumo_carreira = pl.read_parquet(out_resumo)

            con.close()

        # Garante schema e tipagem estrita
        df_custo_mensal = self._conforma_schema(df_custo_mensal, OBT_POLITICO_CUSTO_MENSAL_SCHEMA)
        df_resumo_carreira = self._conforma_schema(
            df_resumo_carreira, OBT_POLITICO_RESUMO_CARREIRA_SCHEMA
        )

        return df_custo_mensal, df_resumo_carreira

    # ------------------------------------------------------------------
    #  Helpers internos
    # ------------------------------------------------------------------

    def _ler_gold(self, table_name: str, fallback_schema: dict) -> pl.DataFrame:
        """Lê tabela Gold priorizando arquivo único ou consolidado de lotes."""
        gold_dir = self.base_dir / MedallionLayer.GOLD / table_name
        single_file = self.base_dir / MedallionLayer.GOLD / f"{table_name}.parquet"
        if single_file.exists():
            return pl.read_parquet(single_file)
        optimized = gold_dir / f"{table_name}.parquet"
        if optimized.exists():
            return pl.read_parquet(optimized)
        if not gold_dir.exists():
            return pl.DataFrame(schema=fallback_schema)
        files = sorted(gold_dir.glob("*.parquet"))
        if not files:
            return pl.DataFrame(schema=fallback_schema)
        return pl.concat([pl.read_parquet(f) for f in files], how="vertical")

    def _ler_silver(self, domain: DomainType) -> pl.DataFrame:
        """Lê fatos Silver do domínio especificado."""
        return ler_silver(str(self.base_dir), domain)

    @staticmethod
    def _conforma_schema(df: pl.DataFrame, schema: dict[str, pl.DataType]) -> pl.DataFrame:
        """Assegura presença e tipo de cada coluna do schema contratual."""
        if df.is_empty():
            return pl.DataFrame(schema=schema)
        exprs = []
        for col_name, dtype in schema.items():
            if col_name in df.columns:
                exprs.append(pl.col(col_name).cast(dtype).alias(col_name))
            else:
                exprs.append(pl.lit(None, dtype=dtype).alias(col_name))
        return df.select(exprs)

    @staticmethod
    def _relatorio(
        df_custo: pl.DataFrame,
        df_resumo: pl.DataFrame,
    ) -> CoberturaPlatinum:
        """Monta o dataclass de cobertura a partir dos DataFrames produzidos."""
        custo_total = 0.0
        proposicoes_apresentadas = 0
        proposicoes_aprovadas = 0
        votos_registrados = 0

        if not df_resumo.is_empty():
            custo_total = float(df_resumo["custo_total_acumulado_historico"].sum())
            proposicoes_apresentadas = int(df_resumo["proposicoes_apresentadas"].sum())
            proposicoes_aprovadas = int(df_resumo["proposicoes_aprovadas"].sum())
            votos_registrados = int(df_resumo["votos_registrados"].sum())

        return CoberturaPlatinum(
            total_politicos=df_resumo.height,
            total_linhas_custo_mensal=df_custo.height,
            custo_total_acumulado=custo_total,
            total_proposicoes_apresentadas=proposicoes_apresentadas,
            total_proposicoes_aprovadas=proposicoes_aprovadas,
            total_votos_registrados=votos_registrados,
            tabelas_geradas=(
                TABLE_OBT_POLITICO_CUSTO_MENSAL,
                TABLE_OBT_POLITICO_RESUMO_CARREIRA,
            ),
        )
