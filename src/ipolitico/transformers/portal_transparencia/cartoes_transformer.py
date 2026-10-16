"""Transformador para o domínio CG_CARTOES — rota dupla (bulk mensal + API v3).

O domínio tem duas fontes (ticket 04): o dump bulk mensal de
``/download-de-dados/{cpgf,cpcc,cpdc}/{YYYYMM}`` (FULL_LOAD) e a API v3
``/api-de-dados/cartoes`` por bloco mensal (INCREMENTAL). O transformer
detecta a rota pelo **shape** do DataFrame e normaliza ambas para o mesmo
contrato Silver ``SILVER_SCHEMAS[cg_cartoes]``.

Correções de fonte validada real (ticket 04) sobre as premissas do contrato:

1. **``favorecido`` ≡ ``estabelecimento``.** A API não tem campo "favorecido";
   o ``estabelecimento`` da API é a MESMA entidade do ``FAVORECIDO`` do CSV
   bulk (o comerciante que recebeu o pagamento do cartão). A rota API deriva
   ``favorecido_cpfCnpj`` (dígitos canônicos) e ``favorecido_nome`` do
   ``estabelecimento`` — sem isso a UK composta não é determinística entre as
   rotas e o overlap bulk×API não deduplicaria no Gold.
2. **``cpcc`` do bulk NÃO tem colunas de portador** (módulo omitido; cpgf/cpdc
   têm). Rows bulk de CPCC ficam com ``portador_*`` nulo — a UK não alinha o
   overlap bulk×API para CPCC (a API tem portador mascarado); limitação
   documentada, volume de CPCC é pequeno e a dedup dentro de cada rota segue
   valendo.
3. **CPF/CNPJ do favorecido em dígitos canônicos** nas duas rotas (bulk já vem
   ``"79379491017744"``; API ``"38.056.949/0001-86"`` → ``"38056949000186"``).
   O CPF do portador é mascarado com o MESMO formato nas duas rotas
   (``"***.195.852-**"``) e não é normalizado. **Documento ausente, vazio ou
   mascarado na API vira nulo** (não "542243"): o ``pl.coalesce`` escolheria
   ``""`` sobre o nulo e o CPF mascarado ``"***.542.243-**"`` canonicalizaria
   para lixo de dígitos — ``_full_document`` guarda o coalesce.
6. **UK = composta + ``id`` da API** (correção da validação real, 19/08). A
   premissa do ticket "colisão ≈ zero (7 campos)" estava errada: a API
   mascarada fundiria ~645 transações DISTINTAS/mês ("SEM INFORMACAO",
   "NAO SE APLICA", beneficiários CPDC). O ``id`` é o único discriminador
   dessas linhas; no bulk (id nulo) a composta deduplica os duplicados exatos
   de fonte. Consequência: o overlap bulk×API NÃO deduplica no Gold — o usuário
   escolhe a estratégia por janela (FULL_LOAD bulk / INCREMENTAL API).
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer
from ipolitico.transformers.br_locale import convert_br_currency_columns

# Discriminador da rota bulk: coluna única do CSV (o DTO da API não a tem).
_BULK_MARKER = "VALOR TRANSAÇÃO"

# Mapeamento CSV bulk (colunas reais após ``_read_single_csv``) → contrato.
# Colunas por módulo não mapeadas (``ANO/MÊS EXTRATO``, extras de cpcc/cpdc)
# são tratadas fora do mapa.
_BULK_COLUMN_MAP: dict[str, str] = {
    "CÓDIGO ÓRGÃO SUPERIOR": "unidadeGestora_orgaoMaximo_codigo",
    "NOME ÓRGÃO SUPERIOR": "unidadeGestora_orgaoMaximo_nome",
    "CÓDIGO ÓRGÃO": "unidadeGestora_orgaoVinculado_codigoSIAFI",
    "NOME ÓRGÃO": "unidadeGestora_orgaoVinculado_nome",
    "CÓDIGO UNIDADE GESTORA": "unidadeGestora_codigo",
    "NOME UNIDADE GESTORA": "unidadeGestora_nome",
    "CPF PORTADOR": "portador_cpfFormatado",
    "NOME PORTADOR": "portador_nome",
    "CNPJ OU CPF FAVORECIDO": "favorecido_cpfCnpj",
    "NOME FAVORECIDO": "favorecido_nome",
    "TRANSAÇÃO": "transacao_descricao",
    "DATA TRANSAÇÃO": "dataTransacao",
    "VALOR TRANSAÇÃO": "valorTransacao",
}

# Módulo do bulk → tipoCartao (id, codigo, descricao). Descrições oficiais
# validadas na API v3 (ticket 04): CPGF, Compras Centralizadas, Defesa Civil.
_CARTAO_BY_MODULE: dict[str, tuple[int, str, str]] = {
    "cpgf": (1, "1", "Cartão de Pagamento do Governo Federal - CPGF"),
    "cpcc": (2, "2", "Cartão de Pagamento de Compras Centralizadas - CPCC"),
    "cpdc": (3, "3", "Cartão de Pagamento da Defesa Civil - CPDC"),
}

# Campos da struct ``unidadeGestora`` do DTO da API → colunas do contrato.
_UG_FLAT_FIELDS: dict[str, str] = {
    "codigo": "unidadeGestora_codigo",
    "nome": "unidadeGestora_nome",
    "descricaoPoder": "unidadeGestora_descricaoPoder",
}
_UG_VINCULADO_FIELDS: dict[str, str] = {
    "codigoSIAFI": "unidadeGestora_orgaoVinculado_codigoSIAFI",
    "cnpj": "unidadeGestora_orgaoVinculado_cnpj",
    "sigla": "unidadeGestora_orgaoVinculado_sigla",
    "nome": "unidadeGestora_orgaoVinculado_nome",
}
_UG_MAXIMO_FIELDS: dict[str, str] = {
    "codigo": "unidadeGestora_orgaoMaximo_codigo",
    "sigla": "unidadeGestora_orgaoMaximo_sigla",
    "nome": "unidadeGestora_orgaoMaximo_nome",
}


def _struct_field_names(dtype: pl.DataType) -> set[str]:
    """Nomes dos campos de um dtype Struct (``fields`` é lista de ``Field``)."""
    return {f.name for f in dtype.fields}


def _full_document(expr: pl.Expr) -> pl.Expr:
    """Expressão de documento (CNPJ/CPF) completo: nulo se ausente/vazio/mascarado.

    Args:
        expr: Campo string do documento no DTO da API (pode ser nulo, ``""`` ou
            CPF mascarado ``"***.xxx.xxx-**"``).

    Returns:
        Expressão com o valor original quando é um documento completo (sem
        mascaramento ``*``); nulo caso contrário. Guarda aplicada ANTES do
        ``pl.coalesce`` — o coalesce pula nulos, mas escolheria ``""`` (ou o CPF
        mascarado) sobre o campo alternativo sem ela.
    """
    # Cast p/ String evita ``str.contains`` sobre coluna de dtype Null (campo
    # 100 % nulo numa página — o ``when`` então resolve tudo para nulo).
    s = expr.cast(pl.String, strict=False)
    return (
        pl.when(s.is_not_null() & (s != "") & ~s.str.contains("*", literal=True))
        .then(expr)
        .otherwise(pl.lit(None))
    )


class PortalCartoesTransformer(BaseTransformer):
    """Aplica o contrato Silver ao DataFrame das duas rotas de cartões.

    Detecta a rota pelo shape (coluna ``VALOR TRANSAÇÃO`` do CSV bulk vs
    structs aninhadas do DTO da API), normaliza ambas para o contrato união
    e aplica a tipagem estrita de ``SILVER_SCHEMAS[cg_cartoes]``.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto (bulk ou API) em conformidade com o contrato.

        Args:
            df: DataFrame bruto do extrator — rota bulk (colunas uppercase do
                CSV, ``_source_url`` com o módulo no caminho) ou rota API
                (structs ``tipoCartao``/``estabelecimento``/``unidadeGestora``/
                ``portador``). Valores monetários em string BR.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de
            ``SILVER_SCHEMAS[cg_cartoes]``. DataFrame vazio retorna vazio
            (sem colunas adicionadas).
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_CARTOES.value]

        if _BULK_MARKER in df.columns:
            df = self._normalize_bulk(df)
        else:
            df = self._normalize_api(df)

        # ── Moeda BR (string → Float64) em ambas as rotas ──────────────────
        df = convert_br_currency_columns(df, ["valorTransacao"])

        # ── Strings vazias reais viram nulo (padrão dos demais domínios) ────
        df = self._null_empty_strings(df, contract)

        # ── Campos top-level ausentes viram nulo (contrato exige a coluna) ──
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])

    @staticmethod
    def _null_empty_strings(df: pl.DataFrame, contract: dict) -> pl.DataFrame:
        """Converte strings vazias de colunas String do contrato em nulo.

        Args:
            df: DataFrame normalizado da rota.
            contract: ``SILVER_SCHEMAS[cg_cartoes]`` (para filtrar colunas
                String do contrato).

        Returns:
            DataFrame com strings vazias das colunas String do contrato como
            nulo; demais colunas inalteradas.
        """
        string_cols = [c for c in contract if contract[c] == pl.String and c in df.columns]
        if not string_cols:
            return df
        return df.with_columns(
            [
                pl.when(pl.col(c) == "").then(pl.lit(None)).otherwise(pl.col(c)).alias(c)
                for c in string_cols
            ]
        )

    def _normalize_bulk(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Normaliza o CSV bulk (colunas uppercase) para o contrato.

        Args:
            df: DataFrame do CSV bulk (colunas uppercase PT, ``_source_url``
                com o módulo no penúltimo segmento do caminho).

        Returns:
            DataFrame com as colunas do contrato preenchidas pela rota bulk
            (``mesExtrato`` combinado, ``tipoCartao`` derivado do módulo).
        """
        df = df.rename({k: v for k, v in _BULK_COLUMN_MAP.items() if k in df.columns})

        # Módulo no penúltimo segmento do ``_source_url``:
        # ``.../download-de-dados/cpgf/202506`` → ``cpgf``.
        module = pl.col("_source_url").str.split("/").list.get(-2)
        tipo_codigo = module.replace_strict(
            {m: v[1] for m, v in _CARTAO_BY_MODULE.items()}, default=pl.lit(None)
        )
        tipo_descricao = module.replace_strict(
            {m: v[2] for m, v in _CARTAO_BY_MODULE.items()}, default=pl.lit(None)
        )

        # CPF/CNPJ do favorecido em dígitos canônicos (correção 3 do docstring):
        # a UK composta alinha entre as rotas só se AMBAS canonicalizam — o bulk
        # já vem sem pontuação ("79379491017744"), mas a API vem formatado
        # ("02.012.862/0001-60") e um dump futuro pode publicar formatado.
        # Documento mascarado ("*") vira nulo, mesma regra da rota API.
        if "favorecido_cpfCnpj" in df.columns:
            doc = pl.col("favorecido_cpfCnpj").cast(pl.String, strict=False)
            df = df.with_columns(
                pl.when(doc.is_not_null() & ~doc.str.contains("*", literal=True))
                .then(doc.str.replace_all(r"\D", ""))
                .otherwise(pl.lit(None))
                .alias("favorecido_cpfCnpj")
            )

        # ``MÊS EXTRATO`` + ``ANO EXTRATO`` → ``mesExtrato`` "MM/AAAA"
        # (ex: "06"/"2025" → "06/2025"). O ``DATA TRANSAÇÃO`` do CSV pode ser
        # de mês anterior (extrato ≠ transação) — por isso a combinação.
        df = df.with_columns(
            mesExtrato=pl.col("MÊS EXTRATO").str.zfill(2) + "/" + pl.col("ANO EXTRATO"),
            tipoCartao_id=tipo_codigo.cast(pl.Int64, strict=False),
            tipoCartao_codigo=tipo_codigo,
            tipoCartao_descricao=tipo_descricao,
        )
        return df.drop(["ANO EXTRATO", "MÊS EXTRATO"])

    def _normalize_api(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Normaliza o DTO da API v3 (structs aninhadas) para o contrato.

        Args:
            df: DataFrame do DTO (structs ``tipoCartao``/``estabelecimento``/
                ``unidadeGestora``/``portador``, ``_source_url`` injetado).

        Returns:
            DataFrame com as colunas do contrato preenchidas pela rota API
            (structs achatadas; ``favorecido_*`` derivado do ``estabelecimento``).
        """

        def field_exprs(struct_col: str, mapping: dict[str, str]) -> list[pl.Expr]:
            """Expressões de achatamento plano (1 nível) de uma struct."""
            if struct_col not in df.columns or df.schema[struct_col] != pl.Struct:
                return []
            names = _struct_field_names(df.schema[struct_col])
            return [
                pl.col(struct_col).struct.field(src).alias(tgt)
                for src, tgt in mapping.items()
                if src in names
            ]

        df = df.with_columns(
            field_exprs(
                "tipoCartao",
                {
                    "id": "tipoCartao_id",
                    "codigo": "tipoCartao_codigo",
                    "descricao": "tipoCartao_descricao",
                },
            )
            + field_exprs(
                "estabelecimento",
                {
                    "id": "estabelecimento_id",
                    "cpfFormatado": "estabelecimento_cpfFormatado",
                    "cnpjFormatado": "estabelecimento_cnpjFormatado",
                    "numeroInscricaoSocial": "estabelecimento_numeroInscricaoSocial",
                    "nome": "estabelecimento_nome",
                    "razaoSocialReceita": "estabelecimento_razaoSocialReceita",
                    "nomeFantasiaReceita": "estabelecimento_nomeFantasiaReceita",
                    "tipo": "estabelecimento_tipo",
                },
            )
            + field_exprs(
                "portador",
                {
                    "cpfFormatado": "portador_cpfFormatado",
                    "nis": "portador_nis",
                    "nome": "portador_nome",
                },
            )
        )

        # ``unidadeGestora`` tem structs aninhadas (``orgaoVinculado`` e
        # ``orgaoMaximo``) — achatadas em dois níveis.
        if "unidadeGestora" in df.columns and df.schema["unidadeGestora"] == pl.Struct:
            ug = pl.col("unidadeGestora")
            ug_dtype = df.schema["unidadeGestora"]
            ug_names = _struct_field_names(ug_dtype)
            exprs = [
                ug.struct.field(src).alias(tgt)
                for src, tgt in _UG_FLAT_FIELDS.items()
                if src in ug_names
            ]
            for nested_col, fields_map in (
                ("orgaoVinculado", _UG_VINCULADO_FIELDS),
                ("orgaoMaximo", _UG_MAXIMO_FIELDS),
            ):
                if nested_col not in ug_names:
                    continue
                inner = next(f.dtype for f in ug_dtype.fields if f.name == nested_col)
                inner_names = _struct_field_names(inner)
                exprs += [
                    ug.struct.field(nested_col).struct.field(src).alias(tgt)
                    for src, tgt in fields_map.items()
                    if src in inner_names
                ]
            df = df.with_columns(exprs)

        # ``favorecido_*`` derivado do ``estabelecimento`` — a API não expõe o
        # favorecido; ele É o estabelecimento (correção 1 do docstring). A parte
        # composta da UK alinha entre rotas para transações com documento.
        # CNPJ/CPF em dígitos canônicos (correção 3): documento ausente/vazio/
        # mascarado ("*") vira nulo — o coalesce escolheria ``""`` sobre o nulo e
        # o CPF mascarado canonicalizaria para lixo de dígitos ("542243").
        if "estabelecimento" in df.columns and df.schema["estabelecimento"] == pl.Struct:
            estab = pl.col("estabelecimento")
            estab_names = _struct_field_names(df.schema["estabelecimento"])
            if "nome" in estab_names:
                exprs = [estab.struct.field("nome").alias("favorecido_nome")]
                if "cnpjFormatado" in estab_names and "cpfFormatado" in estab_names:
                    exprs.append(
                        pl.coalesce(
                            _full_document(estab.struct.field("cnpjFormatado")),
                            _full_document(estab.struct.field("cpfFormatado")),
                        )
                        .str.replace_all(r"\D", "")
                        .alias("favorecido_cpfCnpj")
                    )
                df = df.with_columns(exprs)

        # Structs já achatadas não entram no contrato — descartadas.
        return df.drop(
            [
                c
                for c in ("tipoCartao", "estabelecimento", "unidadeGestora", "portador")
                if c in df.columns
            ]
        )
