"""Testes do builder Gold "custo ao erário" (issue 02) — mappers puros e CustoErarioBuilder."""

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.gold.custo_erario import (
    TABELA_SP,
    CoberturaCustoErario,
    CustoErarioBuilder,
    _mandato_de_mes,
    resolver_assessores_camara_estimativa,
    resolver_assessores_senado,
    resolver_auxilio_moradia_camara,
    resolver_auxilio_moradia_senado,
    resolver_ceap_camara,
    resolver_ceap_senado,
    resolver_salario_camara,
    resolver_salario_senado,
)
from ipolitico.gold.resolutor import FONTE_CAMARA, FONTE_SENADO


# ─────────────────────────────────────────────────────────────────────────────
# TABELA_SP (estimativa assessores Câmara, PDF vig. 18/02/2026)
# ─────────────────────────────────────────────────────────────────────────────
def test_tabela_sp_25_niveis_monotonicos():
    assert list(TABELA_SP) == [f"SP{i:02d}" for i in range(1, 26)]
    assert TABELA_SP["SP01"] == 1710.83
    assert TABELA_SP["SP25"] == 12979.45
    valores = list(TABELA_SP.values())
    assert all(a < b for a, b in zip(valores, valores[1:]))


def test_mandato_heuristica_57_a_59():
    assert _mandato_de_mes("2023-01") == 57
    assert _mandato_de_mes("2026-12") == 57
    assert _mandato_de_mes("2027-01") == 58
    assert _mandato_de_mes("2030-12") == 58
    assert _mandato_de_mes("2031-01") == 59


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
def _aliases():
    return pl.DataFrame(
        {
            "fonte": [FONTE_CAMARA, FONTE_CAMARA, FONTE_SENADO, FONTE_SENADO],
            "id_natural": [5, 6, 77, 88],
            "politico_id": ["pol_camara_5", "pol_camara_6", "pol_senado_77", "pol_senado_88"],
            "metodo": ["chave_natural"] * 4,
            "confianca": ["alta"] * 4,
            "_source_url": ["u/a"] * 4,
        }
    )


def _senadores():
    return pl.DataFrame(
        {
            "_source_url": ["u/s77", "u/s88"],
            "codigo": [77, 88],
            "nome": ["MARIA SILVA", "JOSE SOUZA"],
            "nome_completo": ["MARIA SILVA", "JOSE SOUZA"],
            "sexo": ["F", "M"],
            "uf": ["CE", "SP"],
            "codigo_mandato": [None, None],
            "descricao_participacao": [None, None],
            "primeira_legislatura": [None, None],
            "segunda_legislatura": [56, 56],
        }
    )


def _remuneracoes_senadores():
    return pl.DataFrame(
        {
            "_source_url": ["u/r1", "u/r2", "u/r3", "u/r4"],
            "sequencial": [1, 2, 1, 2],
            "nome": ["MARIA SILVA", "JOSE SOUZA", "MARIA SILVA", "JOSE SOUZA"],
            "mes": [7, 7, 6, 6],
            "ano": [2026, 2026, 2026, 2026],
            "tipo_folha": ["Normal", "Normal", "Normal", "Normal"],
            "remuneracao_basica": [1000.0, 2000.0, 500.0, 2500.0],
            "vantagens_pessoais": [200.0, 0.0, 50.0, 0.0],
            "funcao_comissionada": [300.0, 0.0, 100.0, 0.0],
            "gratificacao_natalina": [0.0] * 4,
            "horas_extras": [0.0] * 4,
            "outras_eventuais": [0.0] * 4,
            "abono_permanencia": [0.0] * 4,
            "imposto_renda": [500.0, 300.0, 100.0, 300.0],
            "previdencia": [200.0, 100.0, 50.0, 100.0],
            "diarias": [100.0, 0.0, 0.0, 0.0],
            "auxilios": [500.0, 0.0, 0.0, 0.0],
            "vantagens_indenizatorias": [300.0, 0.0, 0.0, 0.0],
        }
    )


def _remuneracoes_com_assessores():
    """Remunerações de senadores + 2 assessores de gabinete (ANA/CARLOS)."""
    assessores = pl.DataFrame(
        {
            "_source_url": ["u/rA", "u/rB"],
            "sequencial": [101, 102],
            "nome": ["ANA RIBEIRO", "CARLOS LIMA"],
            "mes": [7, 7],
            "ano": [2026, 2026],
            "tipo_folha": ["Normal", "Normal"],
            "remuneracao_basica": [8000.0, 9000.0],
            "vantagens_pessoais": [0.0, 0.0],
            "funcao_comissionada": [0.0, 0.0],
            "gratificacao_natalina": [0.0, 0.0],
            "horas_extras": [0.0, 0.0],
            "outras_eventuais": [0.0, 0.0],
            "abono_permanencia": [0.0, 0.0],
            "imposto_renda": [0.0, 0.0],
            "previdencia": [0.0, 0.0],
            "diarias": [0.0, 0.0],
            "auxilios": [0.0, 0.0],
            "vantagens_indenizatorias": [0.0, 0.0],
        }
    )
    return pl.concat([_remuneracoes_senadores(), assessores], how="vertical")


def _despesas_ceaps():
    return pl.DataFrame(
        {
            "_source_url": ["u/c1", "u/c2", "u/c3"],
            "id": [1, 2, 3],
            "tipoDocumento": ["Nota Fiscal"] * 3,
            "ano": [2026, 2026, 2026],
            "mes": [7, 6, 7],
            "codSenador": [77, 77, 88],
            "nomeSenador": ["MARIA SILVA", "MARIA SILVA", "JOSE SOUZA"],
            "tipoDespesa": ["Passagem"] * 3,
            "cpfCnpj": [None] * 3,
            "fornecedor": [None] * 3,
            "documento": [None] * 3,
            "data": [None] * 3,
            "detalhamento": [None] * 3,
            "valorReembolsado": [150.5, 100.0, 200.0],
        }
    )


def _servidores_gabinete():
    return pl.DataFrame(
        {
            "_source_url": ["u/sv1", "u/sv2", "u/sv3"],
            "sequencial": [101, 102, 103],
            "nome": ["ANA RIBEIRO", "CARLOS LIMA", "MARIA SILVA"],
            "vinculo": [None] * 3,
            "situacao": [None] * 3,
            "ano_admissao": [None] * 3,
            "padrao": [None] * 3,
            "especialidade": [None] * 3,
            "cargo": [None] * 3,
            "funcao": [None] * 3,
            "lotacao_sigla": ["GAB"] * 3,
            "lotacao_nome": ["Gabinete do Senador Maria Silva"] * 3,
            "categoria_codigo": [None] * 3,
            "categoria_nome": [None] * 3,
            "tipo_cessao": [None] * 3,
            "orgao_origem": [None] * 3,
            "orgao_destino": [None] * 3,
        }
    )


def _folha_pagamento():
    return pl.DataFrame(
        {
            "_source_url": ["u/f1", "u/f2", "u/f3"],
            "cargo": ["Deputado 5", "Deputado 6", "Servidor"],
            "grupo_funcional": ["Parlamentar", "Parlamentar", "Analista"],
            "folha": ["Normal"] * 3,
            "ano_ingresso": [2023] * 3,
            "remuneracao_fixa": [30000.0, 20000.0, 10000.0],
            "vantagens_pessoais": [5000.0, 0.0, 0.0],
            "funcao_comissao": [1000.0, 0.0, 0.0],
            "gratificacao_natalina": [0.0] * 3,
            "ferias": [0.0] * 3,
            "outras_remuneracoes_eventuais": [0.0] * 3,
            "abono_permanencia": [100.0, 0.0, 0.0],
            "redutor_constitucional": [0.0] * 3,
            "contribuicao_previdenciaria": [1000.0, 500.0, 0.0],
            "imposto_renda": [9000.0, 3000.0, 0.0],
            "remuneracao_apos_descontos": [0.0] * 3,
            "diarias": [200.0, 0.0, 0.0],
            "auxilios": [4000.0, 2000.0, 0.0],
            "vantagens_indenizatorias": [0.0] * 3,
            # Contrato Silver atual da folha não tem mês → teste injeta (documentado
            # no mapper: ``resolver_salario_camara`` exige ``ano``/``mes``).
            "ano": [2026, 2026, 2026],
            "mes": [7, 6, 7],
        }
    )


def _despesas_camara():
    return pl.DataFrame(
        {
            "_source_url": ["u/d1", "u/d2", "u/d3"],
            "id_deputado": [5, 5, 6],
            "ano": [2026, 2026, 2026],
            "mes": [7, 7, 6],
            "tipoDespesa": ["Passagem"] * 3,
            "codDocumento": [1, 2, 3],
            "tipoDocumento": ["Nota Fiscal"] * 3,
            "dataDocumento": [None] * 3,
            "numDocumento": [None] * 3,
            "parcela": [None] * 3,
            "valorDocumento": [1100.0, 1100.0, 1000.0],
            "valorGlosa": [100.0, 100.0, 0.0],
            "valorLiquido": [1000.0, 1000.0, 1000.0],
            "nomeFornecedor": [None] * 3,
            "cnpjCpfFornecedor": [None] * 3,
            "urlDocumento": [None] * 3,
        }
    )


def _funcionarios():
    return pl.DataFrame(
        {
            "_source_url": ["u/fu1", "u/fu2", "u/fu3"],
            "ponto": [None] * 3,
            "codGrupo": [None] * 3,
            "grupo": [None] * 3,
            "nome": ["ANA RIBEIRO", "CARLOS LIMA", "OUTRO ASSESSOR"],
            "cargo": ["SP09C", "SP03C", "SP09C"],
            "lotacao": [
                "GAB. 5/25 - MARIA SILVA",
                "GAB. 5/25 - MARIA SILVA",
                "GAB. 6/25 - JOSE SOUZA",
            ],
            "atoNomeacao": [None] * 3,
            "dataNomeacao": ["2026-08-01"] * 3,
            "dataInicioHistorico": [None] * 3,
            "dataPubNomeacao": [None] * 3,
            "funcao": [None] * 3,
            "uriLotacao": [None] * 3,
        }
    )


def _deputados():
    return pl.DataFrame(
        {
            "id": [5, 6],
            "nome": ["MARIA SILVA", "JOSE SOUZA"],
            "uf": ["CE", "SP"],
            "idLegislatura": [57, 57],
            "_source_url": ["u/d5", "u/d6"],
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# Senado — mappers
# ─────────────────────────────────────────────────────────────────────────────
def test_salario_senado_soma_rubricas_positivas_por_politico_mes():
    out = resolver_salario_senado(_remuneracoes_senadores(), _senadores(), _aliases())
    linha = out.sort(["politico_id", "mes"])
    # MARIA: 2026-06 = 500+50+100 = 650; 2026-07 = 1000+200+300 = 1500
    # JOSE: 2026-06 = 2500; 2026-07 = 2000 (descontos/auxílios/diárias ficam fora)
    assert linha["politico_id"].to_list() == [
        "pol_senado_77", "pol_senado_77", "pol_senado_88", "pol_senado_88",
    ]
    assert linha["mes"].to_list() == ["2026-06", "2026-07", "2026-06", "2026-07"]
    assert linha["valor_total"].to_list() == [650.0, 1500.0, 2500.0, 2000.0]
    assert set(linha["casa"].unique()) == {"senado"}
    assert set(linha["componente"].unique()) == {"salario"}
    assert set(linha["metodo"].unique()) == {"exato"}
    assert set(linha["mandato"].unique()) == {57}


def test_auxilio_moradia_senado_so_auxilios():
    out = resolver_auxilio_moradia_senado(_remuneracoes_senadores(), _senadores(), _aliases())
    # apenas a linha com auxilios > 0 (MARIA, 2026-07, 500.0)
    assert out.height == 1
    assert out["politico_id"].to_list() == ["pol_senado_77"]
    assert out["mes"].to_list() == ["2026-07"]
    assert out["valor_total"].to_list() == [500.0]
    assert out["componente"].to_list() == ["auxilio_moradia"]


def test_ceap_senado_soma_valor_reembolsado_por_mes():
    out = resolver_ceap_senado(_despesas_ceaps(), _aliases())
    assert out.height == 3
    assert set(out["componente"].unique()) == {"ceap"}
    assert out.sort(["politico_id", "mes"])["valor_total"].to_list() == [100.0, 150.5, 200.0]


def test_assessores_senado_gabinete_exclui_proprio_senador():
    out = resolver_assessores_senado(
        _remuneracoes_com_assessores(), _servidores_gabinete(), _senadores(), _aliases()
    )
    # ANA (8000) + CARLOS (9000) do gabinete de MARIA → pol_senado_77;
    # a remuneração da própria MARIA (senadora) fica de fora do assessores.
    assert out.height == 1
    assert out["politico_id"].to_list() == ["pol_senado_77"]
    assert out["valor_total"].to_list() == [17000.0]
    assert out["componente"].to_list() == ["assessores"]
    assert out["metodo"].to_list() == ["exato"]


def test_assessores_senado_homonimo_nao_atribuido():
    serv = pl.DataFrame(
        {
            "_source_url": ["u/sv1", "u/sv2"],
            "sequencial": [101, 102],
            "nome": ["JOAO", "JOAO"],
            "vinculo": [None] * 2,
            "situacao": [None] * 2,
            "ano_admissao": [None] * 2,
            "padrao": [None] * 2,
            "especialidade": [None] * 2,
            "cargo": [None] * 2,
            "funcao": [None] * 2,
            "lotacao_sigla": ["GAB"] * 2,
            "lotacao_nome": ["Gabinete do Senador Maria Silva"] * 2,
            "categoria_codigo": [None] * 2,
            "categoria_nome": [None] * 2,
            "tipo_cessao": [None] * 2,
            "orgao_origem": [None] * 2,
            "orgao_destino": [None] * 2,
        }
    )
    rem = pl.DataFrame(
        {
            "_source_url": ["u/rJ"],
            "sequencial": [1],
            "nome": ["JOAO"],
            "mes": [7],
            "ano": [2026],
            "tipo_folha": ["Normal"],
            "remuneracao_basica": [5000.0],
            "vantagens_pessoais": [0.0],
            "funcao_comissionada": [0.0],
            "gratificacao_natalina": [0.0],
            "horas_extras": [0.0],
            "outras_eventuais": [0.0],
            "abono_permanencia": [0.0],
            "imposto_renda": [0.0],
            "previdencia": [0.0],
            "diarias": [0.0],
            "auxilios": [0.0],
            "vantagens_indenizatorias": [0.0],
        }
    )
    out = resolver_assessores_senado(rem, serv, _senadores(), _aliases())
    assert out.is_empty()


# ─────────────────────────────────────────────────────────────────────────────
# Câmara — mappers
# ─────────────────────────────────────────────────────────────────────────────
def test_salario_camara_soma_rubricas_do_parlamentar():
    out = resolver_salario_camara(_folha_pagamento(), _aliases())
    linha = out.sort("politico_id")
    # dep5 (2026-07) = 30000+5000+1000+100 = 36100; dep6 (2026-06) = 20000;
    # linha "Servidor" (não-Parlamentar) fica fora.
    assert linha["politico_id"].to_list() == ["pol_camara_5", "pol_camara_6"]
    assert linha["valor_total"].to_list() == [36100.0, 20000.0]
    assert linha["mes"].to_list() == ["2026-07", "2026-06"]
    assert set(linha["casa"].unique()) == {"camara"}
    assert set(linha["componente"].unique()) == {"salario"}


def test_auxilio_moradia_camara_usa_coluna_auxilios():
    out = resolver_auxilio_moradia_camara(_folha_pagamento(), _aliases())
    assert out.sort("politico_id")["valor_total"].to_list() == [4000.0, 2000.0]
    assert set(out["componente"].unique()) == {"auxilio_moradia"}


def test_ceap_camara_soma_valor_liquido_por_mes():
    out = resolver_ceap_camara(_despesas_camara(), _aliases())
    # dep5 (2026-07) = 1000+1000 = 2000; dep6 (2026-06) = 1000
    assert out.sort("politico_id")["valor_total"].to_list() == [2000.0, 1000.0]
    assert set(out["componente"].unique()) == {"ceap"}
    assert set(out["metodo"].unique()) == {"exato"}


def test_assessores_camara_estimativa_por_tabela_sp():
    out = resolver_assessores_camara_estimativa(
        _funcionarios(), _deputados(), "2026-08", _aliases()
    )
    linha = out.sort("politico_id")
    # dep5: SP09 + SP03; dep6: SP09
    assert linha["politico_id"].to_list() == ["pol_camara_5", "pol_camara_6"]
    assert linha["valor_total"].to_list() == [
        TABELA_SP["SP09"] + TABELA_SP["SP03"],
        TABELA_SP["SP09"],
    ]
    assert linha["mes"].to_list() == ["2026-08"] * 2
    assert set(linha["metodo"].unique()) == {"estimativa_documentada"}
    assert set(linha["mandato"].unique()) == {57}


# ─────────────────────────────────────────────────────────────────────────────
# CustoErarioBuilder — integração (leitura Silver/aliases + escrita Gold)
# ─────────────────────────────────────────────────────────────────────────────
def _salvar_silver(tmp_path, domain: DomainType, df: pl.DataFrame) -> None:
    d = tmp_path / "silver" / domain.value
    d.mkdir(parents=True, exist_ok=True)
    df.write_parquet(d / "lote_test.parquet")


def _salvar_aliases(tmp_path, aliases: pl.DataFrame) -> None:
    d = tmp_path / "gold" / "politicos_aliases"
    d.mkdir(parents=True, exist_ok=True)
    aliases.with_columns(pl.lit("2026-08-01T00:00:00").alias("captured_at")).write_parquet(
        d / "lote_test.parquet"
    )


def test_builder_produz_custo_e_observacoes_append_only(tmp_path):
    _salvar_silver(tmp_path, DomainType.SENADORES, _senadores())
    _salvar_silver(tmp_path, DomainType.REMUNERACOES, _remuneracoes_com_assessores())
    _salvar_silver(tmp_path, DomainType.SERVIDORES, _servidores_gabinete())
    _salvar_silver(tmp_path, DomainType.DESPESAS_CEAPS, _despesas_ceaps())
    _salvar_aliases(tmp_path, _aliases())

    builder = CustoErarioBuilder(base_dir=str(tmp_path))
    builder.build()
    cov = builder.cobertura()

    assert isinstance(cov, CoberturaCustoErario)
    # salario(4) + auxilio(1) + ceap(3) + assessores(1) = 9
    assert cov.total_linhas == 9
    assert cov.total_por_componente["salario"] == 4
    assert cov.total_por_componente["assessores"] == 1
    assert cov.total_por_componente["ceap"] == 3
    assert cov.total_por_componente["auxilio_moradia"] == 1
    assert cov.total_por_casa.get("camara", 0) == 0
    assert cov.total_por_casa.get("senado") == 9

    custo = pl.read_parquet(tmp_path / "gold" / "custo_erario" / "*.parquet")
    assert set(custo["casa"].unique()) == {"senado"}
    assert set(custo["componente"].unique()) == {"salario", "assessores", "ceap", "auxilio_moradia"}

    obs = pl.read_parquet(tmp_path / "gold" / "observacoes_metricas" / "*.parquet")
    chaves = set(obs["chave"].unique())
    assert "fonte_nao_ingerida_folha_pagamento" in chaves
    assert "fonte_nao_ingerida_funcionarios" in chaves
    assert "fonte_nao_ingerida_despesas" in chaves
    assert "fonte_nao_ingerida_deputados" in chaves
    assert "beneficios_indiretos" in chaves

    # Append-only: 1 lote na primeira execução; segunda execução não sobrescreve.
    assert len(list((tmp_path / "gold" / "custo_erario").glob("*.parquet"))) == 1
    CustoErarioBuilder(base_dir=str(tmp_path)).build()
    assert len(list((tmp_path / "gold" / "custo_erario").glob("*.parquet"))) == 2


def test_builder_folha_presente_sem_periodo_registra_observacao(tmp_path):
    """
    Folha ingerida mas sem ``ano``/``mes`` no contrato não vira zero silencioso.

    Os mappers Câmara exigem referência temporal; sem ela produzem zero linhas.
    O builder deve registrar a observação ``folha_pagamento_sem_periodo`` (e
    NÃO a ``fonte_nao_ingerida_folha_pagamento``, pois a fonte existe).
    """
    folha_sem_periodo = _folha_pagamento().drop("ano", "mes")
    _salvar_silver(tmp_path, DomainType.FOLHA_PAGAMENTO, folha_sem_periodo)
    _salvar_aliases(tmp_path, _aliases())

    builder = CustoErarioBuilder(base_dir=str(tmp_path))
    builder.build()
    cov = builder.cobertura()

    assert cov.total_por_casa.get("camara", 0) == 0
    chaves = set(
        pl.read_parquet(tmp_path / "gold" / "observacoes_metricas" / "*.parquet")["chave"].unique()
    )
    assert "folha_pagamento_sem_periodo" in chaves
    assert "fonte_nao_ingerida_folha_pagamento" not in chaves


def test_builder_sem_silver_nao_crasha_e_somente_observacoes(tmp_path):
    _salvar_aliases(tmp_path, _aliases())

    builder = CustoErarioBuilder(base_dir=str(tmp_path))
    builder.build()
    cov = builder.cobertura()

    assert cov.total_linhas == 0
    assert cov.total_por_componente == {}
    assert cov.total_observacoes > 0
    assert not (tmp_path / "gold" / "custo_erario").exists()
