from enum import Enum
from typing import Dict


class LoadStrategy(str, Enum):
    """Estratégias de carga de dados gerenciadas pelo Orquestrador."""

    FULL_LOAD = "full_load"
    INCREMENTAL = "incremental"


class SourceType(str, Enum):
    """Tipos de fontes de origem dos dados suportadas pelo ETL."""

    API = "api"
    BULK = "bulk"


class SinkType(str, Enum):
    """Tipos de destinos de armazenamento (Sinks) para a persistência."""

    DATALAKE = "datalake"


class SourceSystem(str, Enum):
    """Sistemas de origem dos dados (casas do Congresso Nacional e órgãos do Executivo).

    Usado como fonte única da coluna "sistema/API de origem" do documento de
    cobertura de dados (issue 03) — nunca derivar do nome do domínio.
    """

    CAMARA = "camara"
    SENADO = "senado"
    # Poder Executivo Federal via Portal da Transparência (CGU) — ticket 02
    # (tracer bullet cg_orgaos). Consumo total decidido no survey de 18/08.
    PORTAL_TRANSPARENCIA = "portal_transparencia"
    # Tribunal Superior Eleitoral (TSE) — Eixo canônico eleitoral e patrimonial
    TSE = "tse"


class ApiRoutes(str, Enum):
    """Mapeamento oficial dos endpoints raiz da API da Câmara."""

    BLOCOS = "blocos"
    DEPUTADOS = "deputados"
    EVENTOS = "eventos"
    FRENTES = "frentes"
    GRUPOS = "grupos"
    LEGISLATURAS = "legislaturas"
    ORGAOS = "orgaos"
    PARTIDOS = "partidos"
    PROPOSICOES = "proposicoes"
    VOTACOES = "votacoes"
    VOTOS = "votos"


class ApiParams(str, Enum):
    """Mapeamento oficial dos parâmetros e colunas da API."""

    ID = "id"
    DATA_INICIO = "dataInicio"
    DATA_FIM = "dataFim"
    ID_LEGISLATURA = "idLegislatura"
    ORDEM = "ordem"
    ORDENAR_POR = "ordenarPor"
    PAGINA = "pagina"
    ITENS = "itens"
    ANO = "ano"
    MES = "mes"
    SIGLA_UF = "siglaUf"
    SIGLA_PARTIDO = "siglaPartido"
    DATA_DOCUMENTO = "dataDocumento"
    # Valores comuns de retorno (Ajudam nos Transformers)
    DEPUTADO_ID = "id_deputado"
    PARTIDO_NO_VOTO = "partido_no_voto"
    UF_NO_VOTO = "uf_no_voto"
    # Orquestração
    ORDEM_ASC = "ASC"
    ORDEM_DESC = "DESC"


class DomainType(str, Enum):
    """Domínios principais suportados pelo iPolitico."""

    DEPUTADOS = "deputados"
    DESPESAS = "despesas"
    PROPOSICOES = "proposicoes"
    VOTACOES = "votacoes"
    VOTOS = "votos"
    PROFISSÕES = "profissoes"
    OCUPACOES = "ocupacoes"
    ORGAOS = "orgaos"
    PARTIDOS = "partidos"
    EVENTOS = "eventos"
    BLOCOS = "blocos"
    FRENTES = "frentes"
    GRUPOS = "grupos"
    LEGISLATURAS = "legislaturas"
    DISCURSOS = "discursos"
    TRAMITACOES = "tramitacoes"
    AUTORES = "autores"
    ORIENTACOES = "orientacoes"
    ORGAOS_MEMBROS = "orgaos_membros"
    FRENTES_MEMBROS = "frentes_membros"
    RELACIONADAS = "relacionadas"
    TEMAS = "temas"
    DEPUTADOS_FRENTES = "deputados_frentes"
    DEPUTADOS_ORGAOS = "deputados_orgaos"
    DEPUTADOS_EVENTOS = "deputados_eventos"
    DEPUTADOS_HISTORICO = "deputados_historico"
    MANDATOS_EXTERNOS = "mandatos_externos"
    EVENTOS_DEPUTADOS = "eventos_deputados"
    EVENTOS_VOTACOES = "eventos_votacoes"
    EVENTOS_PAUTA = "eventos_pauta"
    PARTIDOS_MEMBROS = "partidos_membros"
    PARTIDOS_LIDERES = "partidos_lideres"
    PROPOSICOES_VOTACOES = "proposicoes_votacoes"
    BLOCOS_PARTIDOS = "blocos_partidos"
    REFERENCIAS = "referencias"
    DEPUTADOS_DETALHE = "deputados_detalhe"
    ORGAOS_DETALHE = "orgaos_detalhe"
    EVENTOS_DETALHE = "eventos_detalhe"
    VOTACOES_DETALHE = "votacoes_detalhe"
    FRENTES_DETALHE = "frentes_detalhe"
    PARTIDOS_DETALHE = "partidos_detalhe"
    GRUPOS_DETALHE = "grupos_detalhe"
    LEGISLATURAS_DETALHE = "legislaturas_detalhe"
    BLOCOS_DETALHE = "blocos_detalhe"
    PROPOSICOES_DETALHE = "proposicoes_detalhe"
    EVENTOS_ORGAOS = "eventos_orgaos"
    ORGAOS_EVENTOS = "orgaos_eventos"
    ORGAOS_VOTACOES = "orgaos_votacoes"
    GRUPOS_MEMBROS = "grupos_membros"
    GRUPOS_HISTORICO = "grupos_historico"
    LEGISLATURAS_LIDERES = "legislaturas_lideres"
    LEGISLATURAS_MESA = "legislaturas_mesa"
    # Domínios bulk-only (sem rota API REST)
    FUNCIONARIOS = "funcionarios"
    TECAD_CATEGORIAS = "tecad_categorias"
    TECAD_TERMOS = "tecad_termos"
    # Domínios bulk-only de eventos/votações (dumps CSV anuais)
    EVENTOS_PRESENCA_DEPUTADOS = "eventos_presenca_deputados"
    EVENTOS_REQUERIMENTOS = "eventos_requerimentos"
    VOTACOES_OBJETOS = "votacoes_objetos"
    VOTACOES_PROPOSICOES = "votacoes_proposicoes"
    # Domínios bulk-only de licitações (dumps CSV anuais)
    LICITACOES = "licitacoes"
    LICITACOES_CONTRATOS = "licitacoes_contratos"
    LICITACOES_ITENS = "licitacoes_itens"
    LICITACOES_PEDIDOS = "licitacoes_pedidos"
    LICITACOES_PROPOSTAS = "licitacoes_propostas"
    # Domínio bulk-only mensal (folha de pagamento consolidada por ano/mês)
    FOLHA_PAGAMENTO = "folha_pagamento"
    # Domínio de pessoal de gabinete (extraído via scraper HTML)
    CAMARA_GABINETE_ASSESSORES = "camara_gabinete_assessores"

    # ── Domínios do Senado ───────────────────────────────────────────────
    SENADORES = "senadores"
    SENADORES_DETALHE = "senadores_detalhe"
    PROCESSOS = "processos"
    PROCESSOS_DETALHE = "processos_detalhe"
    PROCESSOS_EMENDAS = "processos_emendas"
    PROCESSOS_DOCUMENTOS = "processos_documentos"
    VOTACOES_SENADO = "votacoes_senado"
    VOTOS_SENADO = "votos_senado"
    VOTACOES_COMISSAO = "votacoes_comissao"
    ORCAMENTO_EMENDAS = "orcamento_emendas"
    ORCAMENTO_OFICIOS = "orcamento_oficios"
    VETOS_PRESIDENCIAIS = "vetos_presidenciais"
    VETOS_DETALHE = "vetos_detalhe"
    SENADORES_DISCURSOS = "senadores_discursos"
    DISCURSOS_PLENARIO = "discursos_plenario"
    DISCURSOS_TEXTO = "discursos_texto"
    NOTAS_TAQUIGRAFIA_SESSAO = "notas_taquigrafia_sessao"
    NOTAS_TAQUIGRAFIA_REUNIAO = "notas_taquigrafia_reuniao"
    COMISSOES_SENADO = "comissoes_senado"
    COMISSOES_DETALHE = "comissoes_detalhe"
    COMISSOES_REUNIOES = "comissoes_reunioes"
    COMISSOES_MEMBROS = "comissoes_membros"
    PLENARIO_AGENDA = "plenario_agenda"
    PLENARIO_RESULTADOS = "plenario_resultados"
    PLENARIO_SESSOES = "plenario_sessoes"
    BLOCOS_SENADO = "blocos_senado"
    LIDERANCAS_SENADO = "liderancas_senado"
    MESA_SENADO = "mesa_senado"
    MESA_CONGRESSO = "mesa_congresso"
    SENADORES_MANDATOS = "senadores_mandatos"
    SENADORES_FILIACOES = "senadores_filiacoes"
    ORIENTACAO_BANCADA = "orientacao_bancada"
    # ── Senado — API administrativa (adm-dadosabertos, issues 07-09) ──────────
    SERVIDORES = "servidores"
    REMUNERACOES = "remuneracoes"
    DESPESAS_CEAPS = "despesas_ceaps"
    # ── Portal da Transparência (CGU) — Poder Executivo (tickets 02/03) ─────
    # Domínios com prefixo ``cg_`` (namespace próprio) — não colidem com os
    # homônimos da Câmara (``orgaos``). O tracer bullet é o primeiro.
    CG_ORGAOS = "cg_orgaos"
    # Ticket 03: snapshot agregado por órgão (API v3, validado real) +
    # remunerações mensais (bulk, WAF bloqueado na validação real).
    CG_SERVIDORES = "cg_servidores"
    CG_REMUNERACOES = "cg_remuneracoes"
    # Ticket 04 — Onda 1 restante (validação real corrigiu premissas):
    #   cg_pep  → PEPs = Pessoas Expostas Politicamente (ocupantes de cargo
    #             público — NÃO patrimônio; a API exige filtro, bulk anual).
    #   cg_viagens → bulk ANUAL (o ticket previa mensal; não há dumps {YYYYMM}).
    #   cg_cartoes → rota dupla: bulk mensal (cpgf/cpcc/cpdc) + API ≤12 meses.
    #   cg_imoveis_funcionais → API snapshot (dump indisponível hoje).
    #   cg_emendas → API por ano (dump único re-publica o histórico inteiro).
    CG_PEP = "cg_pep"
    CG_VIAGENS = "cg_viagens"
    CG_CARTOES = "cg_cartoes"
    CG_IMOVEIS_FUNCIONAIS = "cg_imoveis_funcionais"
    CG_EMENDAS = "cg_emendas"
    # ── Portal da Transparência (CGU) — Fatia 1 (Sanções e Integridade) ────────
    CG_CEIS = "cg_ceis"
    CG_CNEP = "cg_cnep"
    CG_CEPIM = "cg_cepim"
    CG_CEAF = "cg_ceaf"
    CG_ACORDOS_LENIENCIA = "cg_acordos_leniencia"
    # ── Portal da Transparência (CGU) — Fatia 2 (Compras Públicas) ────────────
    CG_LICITACOES = "cg_licitacoes"
    CG_CONTRATOS = "cg_contratos"
    CG_CONTRATOS_ADITIVOS = "cg_contratos_aditivos"
    # ── Portal da Transparência (CGU) — Fatia 3 (Convênios e Repasses) ────────
    CG_CONVENIOS = "cg_convenios"
    CG_CONVENIOS_ADITIVOS = "cg_convenios_aditivos"
    # ── Portal da Transparência (CGU) — Fatia 4 (Despesas Públicas) ───────────
    CG_DESPESAS_EMPENHOS = "cg_despesas_empenhos"
    CG_DESPESAS_PAGAMENTOS = "cg_despesas_pagamentos"
    # ── Tribunal Superior Eleitoral (TSE) — Eixo Canônico Eleitoral ───────────
    TSE_CANDIDATOS = "tse_candidatos"
    TSE_BENS = "tse_bens"
    TSE_VOTACAO_MUNZONA = "tse_votacao_munzona"
    TSE_RECEITAS_CAMPANHA = "tse_receitas_campanha"
    TSE_DESPESAS_CAMPANHA = "tse_despesas_campanha"
    # ── Dimensões Canônicas de Identidade e Mandato (Gold / Star Schema) ──────
    DIM_POLITICO = "dim_politico"
    DIM_MANDATO = "dim_mandato"


class MedallionLayer(str, Enum):
    """Camadas da Arquitetura Medallion."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class EarliestDates:
    """Datas mínimas de dados por domínio para evitar loops infinitos."""

    # DEPUTADOS = "1826-04-29" é a data de fundação da Câmara — o limite real
    # para mandatos históricos, NÃO um default. Manter quando a disponibilidade
    # for igual à existência do órgão (issue 02).
    DEPUTADOS = "1826-04-29"
    PROPOSICOES = "1988-01-01"
    VOTACOES = "1991-01-01"
    DESPESAS = "2009-01-01"
    ORGAOS = "1946-02-01"
    PARTIDOS = "1946-02-01"
    EVENTOS = "1991-01-01"
    FRENTES = "2003-01-01"
    FUNCIONARIOS = "1826-04-29"
    TECAD_CATEGORIAS = "1826-04-29"
    TECAD_TERMOS = "1826-04-29"
    EVENTOS_PRESENCA_DEPUTADOS = "1991-01-01"
    EVENTOS_REQUERIMENTOS = "1991-01-01"
    VOTACOES_OBJETOS = "1991-01-01"
    VOTACOES_PROPOSICOES = "1991-01-01"
    LICITACOES = "1999-01-01"
    CAMARA_GABINETE_ASSESSORES = "1826-04-29"
    # ── Domínios confirmados (PRD Consumo Absoluto) ───────────────────────
    # Datas reais de disponibilidade levantadas na pesquisa. Ainda sem
    # DomainType/EARLIEST_DATE_MAP (o extrator chega na issue própria); quando
    # o domínio for criado, o map deve apontar para estes valores.
    FOLHA_PAGAMENTO = "2012-01-01"  # consolidado da folha da Câmara (issue 02/04)
    REMUNERACOES = "2013-01-01"  # remunerações do Senado, adm (issue 08)
    DESPESAS_CEAPS = "2008-01-01"  # despesas CEAPs do Senado, adm (issue 09)
    # ── Senado ──────────────────────────────────────────────────────────
    SENADORES = "1949-01-01"
    SENADORES_DETALHE = "1949-01-01"
    PROCESSOS = "1949-01-01"
    PROCESSOS_DETALHE = "1949-01-01"
    PROCESSOS_EMENDAS = "1949-01-01"
    PROCESSOS_DOCUMENTOS = "1949-01-01"
    VOTACOES_SENADO = "1991-01-01"
    VOTOS_SENADO = "1991-01-01"
    VOTACOES_COMISSAO = "1991-01-01"
    ORCAMENTO_EMENDAS = "2000-01-01"
    ORCAMENTO_OFICIOS = "2000-01-01"
    VETOS_PRESIDENCIAIS = "1995-01-01"
    VETOS_DETALHE = "1995-01-01"
    SENADORES_DISCURSOS = "1995-01-01"
    DISCURSOS_PLENARIO = "1995-01-01"
    DISCURSOS_TEXTO = "1995-01-01"
    NOTAS_TAQUIGRAFIA_SESSAO = "2003-01-01"
    NOTAS_TAQUIGRAFIA_REUNIAO = "2003-01-01"
    COMISSOES_SENADO = "1949-01-01"
    COMISSOES_DETALHE = "1949-01-01"
    COMISSOES_REUNIOES = "2003-01-01"
    COMISSOES_MEMBROS = "1949-01-01"
    PLENARIO_AGENDA = "2003-01-01"
    PLENARIO_RESULTADOS = "2003-01-01"
    PLENARIO_SESSOES = "2003-01-01"
    BLOCOS_SENADO = "1995-01-01"
    LIDERANCAS_SENADO = "1995-01-01"
    MESA_SENADO = "1995-01-01"
    MESA_CONGRESSO = "1995-01-01"
    SENADORES_MANDATOS = "1949-01-01"
    SENADORES_FILIACOES = "1949-01-01"
    ORIENTACAO_BANCADA = "1991-01-01"
    # SERVIDORES (issue 07): snapshot do roster — disponibilidade = existência
    # do órgão (mesma convenção de FUNCIONARIOS na Câmara), não série temporal.
    SERVIDORES = "1826-04-29"
    # CG_ORGAOS (ticket 02): snapshot de órgãos do SIAPE — disponibilidade =
    # existência do órgão (mesma convenção de SERVIDORES), não série temporal.
    # Fonte: API v3 /api-de-dados/orgaos-siape (não existe bulk de órgãos).
    CG_ORGAOS = "1826-04-29"
    # CG_SERVIDORES (ticket 03): snapshot do agregado /servidores/por-orgao —
    # disponibilidade = existência do órgão (mesma convenção de CG_ORGAOS).
    CG_SERVIDORES = "1826-04-29"
    # CG_REMUNERACOES (ticket 03): PLACEHOLDER documentado (2017-01-01). O dump
    # mensal está BLOQUEADO pelo WAF/CAPTCHA (validação real) — validar quando
    # o WAF liberar (a CGU publica remunerações do Executivo desde ~2017).
    CG_REMUNERACOES = "2017-01-01"
    # CG_PEP (ticket 04): PLACEHOLDER (2013-01-01). Dump `pep` indisponível hoje
    # (403 AccessDenied no host S3) — validar quando o arquivo publicar (o portal
    # expõe PEPs do Executivo desde ~2013).
    CG_PEP = "2013-01-01"
    # CG_VIAGENS (ticket 04): 2013-01-01 CONFIRMADO — arquivos anuais do módulo
    # `viagens` existem de 2013 em diante (nomes {YYYY}_{data}_Viagens.zip).
    CG_VIAGENS = "2013-01-01"
    # CG_CARTOES (ticket 04): PLACEHOLDER (2014-01-01). Validar pelo mesExtrato
    # mais antigo na validação real (cartões de pagamento do Executivo desde
    # ~2013/2014 — a probe encontrou dados de 2016).
    CG_CARTOES = "2014-01-01"
    # CG_IMOVEIS_FUNCIONAIS (ticket 04): snapshot (relação de imóveis funcionais
    # via API v3) — disponibilidade = existência do órgão (convenção CG_ORGAOS).
    CG_IMOVEIS_FUNCIONAIS = "1826-04-29"
    # CG_EMENDAS (ticket 04): PLACEHOLDER (2012-01-01). API por ano — validar
    # pelo ano mais antigo na validação real (emendas parlamentares no portal
    # desde ~2012).
    CG_EMENDAS = "2012-01-01"
    # ── Fatia 1 (Sanções e Integridade — snapshot de cadastros) ──────────────
    CG_CEIS = "1826-04-29"
    CG_CNEP = "1826-04-29"
    CG_CEPIM = "1826-04-29"
    CG_CEAF = "1826-04-29"
    CG_ACORDOS_LENIENCIA = "1826-04-29"
    # ── Fatia 2 (Compras Públicas — snapshot de licitações e contratos) ──────
    CG_LICITACOES = "1826-04-29"
    CG_CONTRATOS = "1826-04-29"
    CG_CONTRATOS_ADITIVOS = "1826-04-29"
    # ── Fatia 3 (Convênios e Repasses — snapshot de transferências) ───────────
    CG_CONVENIOS = "1826-04-29"
    CG_CONVENIOS_ADITIVOS = "1826-04-29"
    # ── Fatia 4 (Despesas Públicas — snapshot de empenhos e pagamentos) ───────
    CG_DESPESAS_EMPENHOS = "1826-04-29"
    CG_DESPESAS_PAGAMENTOS = "1826-04-29"
    # ── Tribunal Superior Eleitoral (TSE) e Dimensões Canônicas ───────────────
    TSE_CANDIDATOS = "1994-01-01"
    TSE_BENS = "2006-01-01"
    TSE_VOTACAO_MUNZONA = "1994-01-01"
    TSE_RECEITAS_CAMPANHA = "2002-01-01"
    TSE_DESPESAS_CAMPANHA = "2002-01-01"
    DIM_POLITICO = "1949-01-01"
    DIM_MANDATO = "1949-01-01"


# Facilita o acesso dinâmico: EarliestDateMap[DomainType.DESPESAS]
EARLIEST_DATE_MAP: Dict[DomainType, str] = {
    DomainType.DEPUTADOS: EarliestDates.DEPUTADOS,
    DomainType.PROPOSICOES: EarliestDates.PROPOSICOES,
    DomainType.VOTACOES: EarliestDates.VOTACOES,
    # VOTOS compartilha o piso de VOTACOES (só existem votos onde há votação).
    # Sem esta entrada, caía no fallback silencioso 1826-04-29 (issue 02).
    DomainType.VOTOS: EarliestDates.VOTACOES,
    DomainType.DESPESAS: EarliestDates.DESPESAS,
    DomainType.PROFISSÕES: EarliestDates.DEPUTADOS,
    DomainType.OCUPACOES: EarliestDates.DEPUTADOS,
    DomainType.ORGAOS: EarliestDates.ORGAOS,
    DomainType.PARTIDOS: EarliestDates.PARTIDOS,
    DomainType.EVENTOS: EarliestDates.EVENTOS,
    DomainType.BLOCOS: EarliestDates.DEPUTADOS,
    DomainType.FRENTES: EarliestDates.FRENTES,
    DomainType.GRUPOS: EarliestDates.DEPUTADOS,
    DomainType.LEGISLATURAS: EarliestDates.DEPUTADOS,
    # DISCURSOS usa 1995-01-01 (e não DEPUTADOS/1826) porque:
    # 1) A API rejeita janelas >4 anos (HTTP 400)
    # 2) Discursos digitalizados existem a partir de ~1999
    # 3) Evita 51 chunks/deputado × 7275 = 371K requisições desnecessárias
    DomainType.DISCURSOS: "1995-01-01",
    DomainType.TRAMITACOES: EarliestDates.PROPOSICOES,
    DomainType.AUTORES: EarliestDates.PROPOSICOES,
    DomainType.ORIENTACOES: EarliestDates.VOTACOES,
    DomainType.ORGAOS_MEMBROS: EarliestDates.ORGAOS,
    DomainType.FRENTES_MEMBROS: EarliestDates.FRENTES,
    DomainType.RELACIONADAS: EarliestDates.PROPOSICOES,
    DomainType.TEMAS: EarliestDates.PROPOSICOES,
    DomainType.DEPUTADOS_FRENTES: EarliestDates.DEPUTADOS,
    DomainType.DEPUTADOS_ORGAOS: EarliestDates.DEPUTADOS,
    DomainType.DEPUTADOS_EVENTOS: EarliestDates.DEPUTADOS,
    DomainType.DEPUTADOS_HISTORICO: EarliestDates.DEPUTADOS,
    DomainType.MANDATOS_EXTERNOS: EarliestDates.DEPUTADOS,
    DomainType.EVENTOS_DEPUTADOS: EarliestDates.EVENTOS,
    DomainType.EVENTOS_VOTACOES: EarliestDates.EVENTOS,
    DomainType.EVENTOS_PAUTA: EarliestDates.EVENTOS,
    DomainType.PARTIDOS_MEMBROS: EarliestDates.PARTIDOS,
    DomainType.PARTIDOS_LIDERES: EarliestDates.PARTIDOS,
    DomainType.PROPOSICOES_VOTACOES: EarliestDates.PROPOSICOES,
    DomainType.BLOCOS_PARTIDOS: EarliestDates.DEPUTADOS,
    DomainType.REFERENCIAS: EarliestDates.DEPUTADOS,
    DomainType.DEPUTADOS_DETALHE: EarliestDates.DEPUTADOS,
    DomainType.ORGAOS_DETALHE: EarliestDates.ORGAOS,
    DomainType.EVENTOS_DETALHE: EarliestDates.EVENTOS,
    DomainType.VOTACOES_DETALHE: EarliestDates.VOTACOES,
    DomainType.FRENTES_DETALHE: EarliestDates.FRENTES,
    DomainType.PARTIDOS_DETALHE: EarliestDates.PARTIDOS,
    DomainType.GRUPOS_DETALHE: EarliestDates.DEPUTADOS,
    DomainType.LEGISLATURAS_DETALHE: EarliestDates.DEPUTADOS,
    DomainType.BLOCOS_DETALHE: EarliestDates.DEPUTADOS,
    DomainType.PROPOSICOES_DETALHE: EarliestDates.PROPOSICOES,
    DomainType.EVENTOS_ORGAOS: EarliestDates.EVENTOS,
    DomainType.ORGAOS_EVENTOS: EarliestDates.ORGAOS,
    DomainType.ORGAOS_VOTACOES: EarliestDates.ORGAOS,
    DomainType.GRUPOS_MEMBROS: EarliestDates.DEPUTADOS,
    DomainType.GRUPOS_HISTORICO: EarliestDates.DEPUTADOS,
    DomainType.LEGISLATURAS_LIDERES: EarliestDates.DEPUTADOS,
    DomainType.LEGISLATURAS_MESA: EarliestDates.DEPUTADOS,
    # Domínios bulk-only
    DomainType.FUNCIONARIOS: EarliestDates.FUNCIONARIOS,
    DomainType.TECAD_CATEGORIAS: EarliestDates.TECAD_CATEGORIAS,
    DomainType.TECAD_TERMOS: EarliestDates.TECAD_TERMOS,
    # Domínios bulk-only de eventos/votações
    DomainType.EVENTOS_PRESENCA_DEPUTADOS: EarliestDates.EVENTOS_PRESENCA_DEPUTADOS,
    DomainType.EVENTOS_REQUERIMENTOS: EarliestDates.EVENTOS_REQUERIMENTOS,
    DomainType.VOTACOES_OBJETOS: EarliestDates.VOTACOES_OBJETOS,
    DomainType.VOTACOES_PROPOSICOES: EarliestDates.VOTACOES_PROPOSICOES,
    # Domínios bulk-only de licitações
    DomainType.LICITACOES: EarliestDates.LICITACOES,
    DomainType.LICITACOES_CONTRATOS: EarliestDates.LICITACOES,
    DomainType.LICITACOES_ITENS: EarliestDates.LICITACOES,
    DomainType.LICITACOES_PEDIDOS: EarliestDates.LICITACOES,
    DomainType.LICITACOES_PROPOSTAS: EarliestDates.LICITACOES,
    DomainType.FOLHA_PAGAMENTO: EarliestDates.FOLHA_PAGAMENTO,
    DomainType.CAMARA_GABINETE_ASSESSORES: EarliestDates.CAMARA_GABINETE_ASSESSORES,
    # ── Domínios do Senado ──────────────────────────────────────────────
    DomainType.SENADORES: EarliestDates.SENADORES,
    DomainType.SENADORES_DETALHE: EarliestDates.SENADORES_DETALHE,
    DomainType.PROCESSOS: EarliestDates.PROCESSOS,
    DomainType.PROCESSOS_DETALHE: EarliestDates.PROCESSOS_DETALHE,
    DomainType.PROCESSOS_EMENDAS: EarliestDates.PROCESSOS_EMENDAS,
    DomainType.PROCESSOS_DOCUMENTOS: EarliestDates.PROCESSOS_DOCUMENTOS,
    DomainType.VOTACOES_SENADO: EarliestDates.VOTACOES_SENADO,
    DomainType.VOTOS_SENADO: EarliestDates.VOTOS_SENADO,
    DomainType.VOTACOES_COMISSAO: EarliestDates.VOTACOES_COMISSAO,
    DomainType.ORCAMENTO_EMENDAS: EarliestDates.ORCAMENTO_EMENDAS,
    DomainType.ORCAMENTO_OFICIOS: EarliestDates.ORCAMENTO_OFICIOS,
    DomainType.VETOS_PRESIDENCIAIS: EarliestDates.VETOS_PRESIDENCIAIS,
    DomainType.VETOS_DETALHE: EarliestDates.VETOS_DETALHE,
    DomainType.SENADORES_DISCURSOS: EarliestDates.SENADORES_DISCURSOS,
    DomainType.DISCURSOS_PLENARIO: EarliestDates.DISCURSOS_PLENARIO,
    DomainType.DISCURSOS_TEXTO: EarliestDates.DISCURSOS_TEXTO,
    DomainType.NOTAS_TAQUIGRAFIA_SESSAO: EarliestDates.NOTAS_TAQUIGRAFIA_SESSAO,
    DomainType.NOTAS_TAQUIGRAFIA_REUNIAO: EarliestDates.NOTAS_TAQUIGRAFIA_REUNIAO,
    DomainType.COMISSOES_SENADO: EarliestDates.COMISSOES_SENADO,
    DomainType.COMISSOES_DETALHE: EarliestDates.COMISSOES_DETALHE,
    DomainType.COMISSOES_REUNIOES: EarliestDates.COMISSOES_REUNIOES,
    DomainType.COMISSOES_MEMBROS: EarliestDates.COMISSOES_MEMBROS,
    DomainType.PLENARIO_AGENDA: EarliestDates.PLENARIO_AGENDA,
    DomainType.PLENARIO_RESULTADOS: EarliestDates.PLENARIO_RESULTADOS,
    DomainType.PLENARIO_SESSOES: EarliestDates.PLENARIO_SESSOES,
    DomainType.BLOCOS_SENADO: EarliestDates.BLOCOS_SENADO,
    DomainType.LIDERANCAS_SENADO: EarliestDates.LIDERANCAS_SENADO,
    DomainType.MESA_SENADO: EarliestDates.MESA_SENADO,
    DomainType.MESA_CONGRESSO: EarliestDates.MESA_CONGRESSO,
    DomainType.SENADORES_MANDATOS: EarliestDates.SENADORES_MANDATOS,
    DomainType.SENADORES_FILIACOES: EarliestDates.SENADORES_FILIACOES,
    DomainType.ORIENTACAO_BANCADA: EarliestDates.ORIENTACAO_BANCADA,
    # ── Senado — API administrativa (adm-dadosabertos) ───────────────────────
    DomainType.SERVIDORES: EarliestDates.SERVIDORES,
    DomainType.REMUNERACOES: EarliestDates.REMUNERACOES,
    DomainType.DESPESAS_CEAPS: EarliestDates.DESPESAS_CEAPS,
    # ── Portal da Transparência (CGU) — Poder Executivo (tickets 02/03) ─────
    DomainType.CG_ORGAOS: EarliestDates.CG_ORGAOS,
    DomainType.CG_SERVIDORES: EarliestDates.CG_SERVIDORES,
    DomainType.CG_REMUNERACOES: EarliestDates.CG_REMUNERACOES,
    # ── Portal da Transparência (CGU) — Poder Executivo (ticket 04) ───────────
    DomainType.CG_PEP: EarliestDates.CG_PEP,
    DomainType.CG_VIAGENS: EarliestDates.CG_VIAGENS,
    DomainType.CG_CARTOES: EarliestDates.CG_CARTOES,
    DomainType.CG_IMOVEIS_FUNCIONAIS: EarliestDates.CG_IMOVEIS_FUNCIONAIS,
    DomainType.CG_EMENDAS: EarliestDates.CG_EMENDAS,
    # ── Portal da Transparência (CGU) — Fatia 1 (Sanções e Integridade) ────────
    DomainType.CG_CEIS: EarliestDates.CG_CEIS,
    DomainType.CG_CNEP: EarliestDates.CG_CNEP,
    DomainType.CG_CEPIM: EarliestDates.CG_CEPIM,
    DomainType.CG_CEAF: EarliestDates.CG_CEAF,
    DomainType.CG_ACORDOS_LENIENCIA: EarliestDates.CG_ACORDOS_LENIENCIA,
    # ── Portal da Transparência (CGU) — Fatia 2 (Compras Públicas) ────────────
    DomainType.CG_LICITACOES: EarliestDates.CG_LICITACOES,
    DomainType.CG_CONTRATOS: EarliestDates.CG_CONTRATOS,
    DomainType.CG_CONTRATOS_ADITIVOS: EarliestDates.CG_CONTRATOS_ADITIVOS,
    # ── Portal da Transparência (CGU) — Fatia 3 (Convênios e Repasses) ────────
    DomainType.CG_CONVENIOS: EarliestDates.CG_CONVENIOS,
    DomainType.CG_CONVENIOS_ADITIVOS: EarliestDates.CG_CONVENIOS_ADITIVOS,
    # ── Portal da Transparência (CGU) — Fatia 4 (Despesas Públicas) ───────────
    DomainType.CG_DESPESAS_EMPENHOS: EarliestDates.CG_DESPESAS_EMPENHOS,
    DomainType.CG_DESPESAS_PAGAMENTOS: EarliestDates.CG_DESPESAS_PAGAMENTOS,
    # ── Tribunal Superior Eleitoral (TSE) e Dimensões Canônicas ───────────────
    DomainType.TSE_CANDIDATOS: EarliestDates.TSE_CANDIDATOS,
    DomainType.TSE_BENS: EarliestDates.TSE_BENS,
    DomainType.TSE_VOTACAO_MUNZONA: EarliestDates.TSE_VOTACAO_MUNZONA,
    DomainType.TSE_RECEITAS_CAMPANHA: EarliestDates.TSE_RECEITAS_CAMPANHA,
    DomainType.TSE_DESPESAS_CAMPANHA: EarliestDates.TSE_DESPESAS_CAMPANHA,
    DomainType.DIM_POLITICO: EarliestDates.DIM_POLITICO,
    DomainType.DIM_MANDATO: EarliestDates.DIM_MANDATO,
}


# ── Lacunas de cobertura no meio da série (issue 02) ────────────────────────
# Notas de ausência PERMANENTE no meio da série, chaveadas pelo nome do domínio
# (domain.value). Chave por nome — e não por DomainType — para registrar fatos
# confirmados na pesquisa antes de o domínio existir no enum (ex: FOLHA_PAGAMENTO
# chega na issue 04). Quando o DomainType for criado, spec_for/coverage_gaps
# passa a consumir esta entrada automaticamente.
COVERAGE_GAPS: Dict[str, tuple[str, ...]] = {
    "folha_pagamento": ("2011, 2015 e 2022 não publicados (HTTP 404) — ausência, não erro",),
    # Regra dupla de cobertura da remuneração do Senado (issue 08): 404 = mês
    # anterior ao início da série (pré-2013, ausência PERMANENTE); 200 com lista
    # vazia = mês corrente ainda não publicado (ausência TEMPORÁRIA, não 404).
    "remuneracoes": (
        "404 para 2012 e anteriores (início da série 2013-01) — ausência permanente; "
        "mês corrente não publicado = HTTP 200 com lista vazia (ausência temporária)",
    ),
    # Início da série 2008: anos anteriores (2007/2006/2005) respondem 404 —
    # ausência permanente, não erro (issue 09).
    "despesas_ceaps": ("404 para 2007 e anteriores (início da série 2008) — ausência permanente",),
}


# ── Anos de lacuna por domínio (issue 04) ──────────────────────────────────────
# Anos inteiros em que a fonte não publicou arquivo (404) — usados pelo planner
# mensal (MonthlyBulkStrategy) para pular jobs em vez de fazer requisições que
# retornam vazio. Chaveado pelo nome do domínio (domain.value), mesma convenção
# de COVERAGE_GAPS; a versão legível ao leitor vive em COVERAGE_GAPS.
COVERAGE_GAP_YEARS: Dict[str, tuple[int, ...]] = {
    "folha_pagamento": (2011, 2015, 2022),
}


# ── Sistema de origem por domínio (issue 03) ──────────────────────────────────
# Chaveado pelo nome (domain.value) — mesma convenção de COVERAGE_GAPS — para
# registrar fatos antes de o DomainType existir no enum (ex: FOLHA_PAGAMENTO
# chega na issue 04). É a fonte única da coluna "sistema/API de origem" do
# documento de cobertura (docs/cobertura-dados.md).
DOMAIN_SOURCE_SYSTEM: Dict[str, SourceSystem] = {
    "deputados": SourceSystem.CAMARA,
    "despesas": SourceSystem.CAMARA,
    "proposicoes": SourceSystem.CAMARA,
    "votacoes": SourceSystem.CAMARA,
    "votos": SourceSystem.CAMARA,
    "profissoes": SourceSystem.CAMARA,
    "ocupacoes": SourceSystem.CAMARA,
    "orgaos": SourceSystem.CAMARA,
    "partidos": SourceSystem.CAMARA,
    "eventos": SourceSystem.CAMARA,
    "blocos": SourceSystem.CAMARA,
    "frentes": SourceSystem.CAMARA,
    "grupos": SourceSystem.CAMARA,
    "legislaturas": SourceSystem.CAMARA,
    "discursos": SourceSystem.CAMARA,
    "tramitacoes": SourceSystem.CAMARA,
    "autores": SourceSystem.CAMARA,
    "orientacoes": SourceSystem.CAMARA,
    "orgaos_membros": SourceSystem.CAMARA,
    "frentes_membros": SourceSystem.CAMARA,
    "relacionadas": SourceSystem.CAMARA,
    "temas": SourceSystem.CAMARA,
    "deputados_frentes": SourceSystem.CAMARA,
    "deputados_orgaos": SourceSystem.CAMARA,
    "deputados_eventos": SourceSystem.CAMARA,
    "deputados_historico": SourceSystem.CAMARA,
    "mandatos_externos": SourceSystem.CAMARA,
    "eventos_deputados": SourceSystem.CAMARA,
    "eventos_votacoes": SourceSystem.CAMARA,
    "eventos_pauta": SourceSystem.CAMARA,
    "partidos_membros": SourceSystem.CAMARA,
    "partidos_lideres": SourceSystem.CAMARA,
    "proposicoes_votacoes": SourceSystem.CAMARA,
    "blocos_partidos": SourceSystem.CAMARA,
    "referencias": SourceSystem.CAMARA,
    "deputados_detalhe": SourceSystem.CAMARA,
    "orgaos_detalhe": SourceSystem.CAMARA,
    "eventos_detalhe": SourceSystem.CAMARA,
    "votacoes_detalhe": SourceSystem.CAMARA,
    "frentes_detalhe": SourceSystem.CAMARA,
    "partidos_detalhe": SourceSystem.CAMARA,
    "grupos_detalhe": SourceSystem.CAMARA,
    "legislaturas_detalhe": SourceSystem.CAMARA,
    "blocos_detalhe": SourceSystem.CAMARA,
    "proposicoes_detalhe": SourceSystem.CAMARA,
    "eventos_orgaos": SourceSystem.CAMARA,
    "orgaos_eventos": SourceSystem.CAMARA,
    "orgaos_votacoes": SourceSystem.CAMARA,
    "grupos_membros": SourceSystem.CAMARA,
    "grupos_historico": SourceSystem.CAMARA,
    "legislaturas_lideres": SourceSystem.CAMARA,
    "legislaturas_mesa": SourceSystem.CAMARA,
    "funcionarios": SourceSystem.CAMARA,
    "tecad_categorias": SourceSystem.CAMARA,
    "tecad_termos": SourceSystem.CAMARA,
    "eventos_presenca_deputados": SourceSystem.CAMARA,
    "eventos_requerimentos": SourceSystem.CAMARA,
    "votacoes_objetos": SourceSystem.CAMARA,
    "votacoes_proposicoes": SourceSystem.CAMARA,
    "licitacoes": SourceSystem.CAMARA,
    "licitacoes_contratos": SourceSystem.CAMARA,
    "licitacoes_itens": SourceSystem.CAMARA,
    "licitacoes_pedidos": SourceSystem.CAMARA,
    "licitacoes_propostas": SourceSystem.CAMARA,
    # ── Senado ────────────────────────────────────────────────────────────
    "senadores": SourceSystem.SENADO,
    "senadores_detalhe": SourceSystem.SENADO,
    "processos": SourceSystem.SENADO,
    "processos_detalhe": SourceSystem.SENADO,
    "processos_emendas": SourceSystem.SENADO,
    "processos_documentos": SourceSystem.SENADO,
    "votacoes_senado": SourceSystem.SENADO,
    "votos_senado": SourceSystem.SENADO,
    "votacoes_comissao": SourceSystem.SENADO,
    "orcamento_emendas": SourceSystem.SENADO,
    "orcamento_oficios": SourceSystem.SENADO,
    "vetos_presidenciais": SourceSystem.SENADO,
    "vetos_detalhe": SourceSystem.SENADO,
    "senadores_discursos": SourceSystem.SENADO,
    "discursos_plenario": SourceSystem.SENADO,
    "discursos_texto": SourceSystem.SENADO,
    "notas_taquigrafia_sessao": SourceSystem.SENADO,
    "notas_taquigrafia_reuniao": SourceSystem.SENADO,
    "comissoes_senado": SourceSystem.SENADO,
    "comissoes_detalhe": SourceSystem.SENADO,
    "comissoes_reunioes": SourceSystem.SENADO,
    "comissoes_membros": SourceSystem.SENADO,
    "plenario_agenda": SourceSystem.SENADO,
    "plenario_resultados": SourceSystem.SENADO,
    "plenario_sessoes": SourceSystem.SENADO,
    "blocos_senado": SourceSystem.SENADO,
    "liderancas_senado": SourceSystem.SENADO,
    "mesa_senado": SourceSystem.SENADO,
    "mesa_congresso": SourceSystem.SENADO,
    "senadores_mandatos": SourceSystem.SENADO,
    "senadores_filiacoes": SourceSystem.SENADO,
    "orientacao_bancada": SourceSystem.SENADO,
    "servidores": SourceSystem.SENADO,
    # ── Portal da Transparência (CGU) — Poder Executivo (tickets 02/03) ─────
    "cg_orgaos": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_servidores": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_remuneracoes": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_pep": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_viagens": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_cartoes": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_imoveis_funcionais": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_emendas": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_ceis": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_cnep": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_cepim": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_ceaf": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_acordos_leniencia": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_licitacoes": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_contratos": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_contratos_aditivos": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_convenios": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_convenios_aditivos": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_despesas_empenhos": SourceSystem.PORTAL_TRANSPARENCIA,
    "cg_despesas_pagamentos": SourceSystem.PORTAL_TRANSPARENCIA,
    # ── Tribunal Superior Eleitoral (TSE) e Dimensões Canônicas ───────────────
    "tse_candidatos": SourceSystem.TSE,
    "tse_bens": SourceSystem.TSE,
    "tse_votacao_munzona": SourceSystem.TSE,
    "tse_receitas_campanha": SourceSystem.TSE,
    "tse_despesas_campanha": SourceSystem.TSE,
    "dim_politico": SourceSystem.TSE,
    "dim_mandato": SourceSystem.TSE,
    "camara_gabinete_assessores": SourceSystem.CAMARA,
    # ── Domínios documentados no registry, ainda sem DomainType ─────────────
    "folha_pagamento": SourceSystem.CAMARA,
    "remuneracoes": SourceSystem.SENADO,
    "despesas_ceaps": SourceSystem.SENADO,
}


# ── Labels amigaveis para exibicao (CLI --list-domains, dashboards) ──────────
DOMAIN_LABELS: dict[DomainType, str] = {
    # ── Entidades principais ───────────────────────────────────────────────────
    DomainType.DEPUTADOS: "Deputados federais (mandato ativo e historico)",
    DomainType.CAMARA_GABINETE_ASSESSORES: "Assessores de gabinete dos deputados",
    DomainType.PROPOSICOES: "Proposicoes legislativas",
    DomainType.VOTACOES: "Votacoes em plenario",
    DomainType.ORGAOS: "Orgaos e comissoes da Camara",
    DomainType.PARTIDOS: "Partidos politicos com representacao na Camara",
    DomainType.EVENTOS: "Eventos da Camara dos Deputados",
    DomainType.BLOCOS: "Blocos parlamentares",
    DomainType.FRENTES: "Frentes parlamentares",
    DomainType.GRUPOS: "Grupos parlamentares",
    DomainType.LEGISLATURAS: "Legislaturas (mandatos de 4 anos)",
    # ── Filhos de DEPUTADOS ─────────────────────────────────────────────────────
    DomainType.DESPESAS: "Cota para Exercicio da Atividade Parlamentar (CEAP)",
    DomainType.DISCURSOS: "Discursos em plenario",
    DomainType.DEPUTADOS_DETALHE: "Dados cadastrais detalhados dos deputados",
    DomainType.DEPUTADOS_FRENTES: "Frentes parlamentares por deputado",
    DomainType.DEPUTADOS_ORGAOS: "Orgaos e comissoes por deputado",
    DomainType.DEPUTADOS_EVENTOS: "Eventos por deputado",
    DomainType.DEPUTADOS_HISTORICO: "Historico do mandato do deputado",
    DomainType.MANDATOS_EXTERNOS: "Mandatos externos anteriores dos deputados",
    DomainType.PROFISSÕES: "Profissões declaradas pelos deputados",
    DomainType.OCUPACOES: "Ocupacoes declaradas pelos deputados",
    # ── Filhos de PROPOSICOES ──────────────────────────────────────────────────
    DomainType.TRAMITACOES: "Historico de tramitacao de proposicoes",
    DomainType.AUTORES: "Autores de proposicoes legislativas",
    DomainType.RELACIONADAS: "Proposicoes relacionadas",
    DomainType.TEMAS: "Temas (assuntos) das proposicoes",
    DomainType.PROPOSICOES_VOTACOES: "Votacoes de proposicoes",
    DomainType.PROPOSICOES_DETALHE: "Detalhes de proposicoes legislativas",
    # ── Filhos de VOTACOES ──────────────────────────────────────────────────────
    DomainType.VOTOS: "Votos individuais dos deputados",
    DomainType.ORIENTACOES: "Orientacoes de bancada nas votacoes",
    DomainType.VOTACOES_DETALHE: "Detalhes de votacoes",
    # ── Filhos de EVENTOS ───────────────────────────────────────────────────────
    DomainType.EVENTOS_DETALHE: "Detalhes de eventos",
    DomainType.EVENTOS_DEPUTADOS: "Deputados presentes em eventos",
    DomainType.EVENTOS_VOTACOES: "Votacoes ocorridas em eventos",
    DomainType.EVENTOS_PAUTA: "Pauta dos eventos",
    DomainType.EVENTOS_ORGAOS: "Orgaos responsaveis por eventos",
    # ── Filhos de ORGAOS ────────────────────────────────────────────────────────
    DomainType.ORGAOS_DETALHE: "Detalhes de orgaos e comissoes",
    DomainType.ORGAOS_MEMBROS: "Membros de orgaos e comissoes",
    DomainType.ORGAOS_EVENTOS: "Eventos de orgaos e comissoes",
    DomainType.ORGAOS_VOTACOES: "Votacoes em orgaos e comissoes",
    # ── Filhos de PARTIDOS ──────────────────────────────────────────────────────
    DomainType.PARTIDOS_DETALHE: "Detalhes de partidos politicos",
    DomainType.PARTIDOS_MEMBROS: "Membros de partidos politicos",
    DomainType.PARTIDOS_LIDERES: "Liderancas partidarias",
    # ── Filhos de LEGISLATURAS ─────────────────────────────────────────────────
    DomainType.LEGISLATURAS_DETALHE: "Detalhes de legislaturas",
    DomainType.LEGISLATURAS_LIDERES: "Liderancas da legislatura",
    DomainType.LEGISLATURAS_MESA: "Mesa diretora da legislatura",
    # ── Filhos de BLOCOS ────────────────────────────────────────────────────────
    DomainType.BLOCOS_DETALHE: "Detalhes de blocos parlamentares",
    DomainType.BLOCOS_PARTIDOS: "Partidos integrantes de blocos",
    # ── Filhos de FRENTES ──────────────────────────────────────────────────────
    DomainType.FRENTES_DETALHE: "Detalhes de frentes parlamentares",
    DomainType.FRENTES_MEMBROS: "Membros de frentes parlamentares",
    # ── Filhos de GRUPOS ────────────────────────────────────────────────────────
    DomainType.GRUPOS_DETALHE: "Detalhes de grupos parlamentares",
    DomainType.GRUPOS_MEMBROS: "Membros de grupos parlamentares",
    DomainType.GRUPOS_HISTORICO: "Historico de grupos parlamentares",
    # ── Referencias ─────────────────────────────────────────────────────────────
    DomainType.REFERENCIAS: "Tabelas de referencia (tipos, situacoes, etc.)",
    # ── Dominios bulk-only ──────────────────────────────────────────────────────
    DomainType.FUNCIONARIOS: "Servidores da Camara dos Deputados",
    DomainType.TECAD_CATEGORIAS: "Categorias do TECAD (gestao de conhecimento)",
    DomainType.TECAD_TERMOS: "Termos do TECAD (vocabulario controlado)",
    DomainType.EVENTOS_PRESENCA_DEPUTADOS: "Presenca de deputados em eventos",
    DomainType.EVENTOS_REQUERIMENTOS: "Requerimentos de eventos",
    DomainType.VOTACOES_OBJETOS: "Objetos de votacao",
    DomainType.VOTACOES_PROPOSICOES: "Proposicoes votadas",
    DomainType.LICITACOES: "Licitacoes da Camara dos Deputados",
    DomainType.LICITACOES_CONTRATOS: "Contratos de licitacao",
    DomainType.LICITACOES_ITENS: "Itens de licitacao",
    DomainType.LICITACOES_PEDIDOS: "Pedidos de licitacao",
    DomainType.LICITACOES_PROPOSTAS: "Propostas de licitacao",
    DomainType.FOLHA_PAGAMENTO: "Folha de pagamento consolidada (Camara, por ano/mes)",
    # ── Senado ──────────────────────────────────────────────────────────────────
    DomainType.SENADORES: "Senadores (mandato ativo e historico)",
    DomainType.SENADORES_DETALHE: "Dados cadastrais detalhados dos senadores",
    DomainType.PROCESSOS: "Processos legislativos do Senado",
    DomainType.PROCESSOS_DETALHE: "Detalhes de processos legislativos",
    DomainType.PROCESSOS_EMENDAS: "Emendas a processos legislativos",
    DomainType.PROCESSOS_DOCUMENTOS: "Documentos de processos legislativos",
    DomainType.VOTACOES_SENADO: "Votacoes nominais no plenario do Senado",
    DomainType.VOTOS_SENADO: "Votos individuais dos senadores",
    DomainType.VOTACOES_COMISSAO: "Votacoes em comissoes do Senado",
    DomainType.ORCAMENTO_EMENDAS: "Emendas ao orcamento (exclusivo Senado)",
    DomainType.ORCAMENTO_OFICIOS: "Oficios orcamentarios (exclusivo Senado)",
    DomainType.VETOS_PRESIDENCIAIS: "Vetos presidenciais (exclusivo Senado)",
    DomainType.VETOS_DETALHE: "Detalhes de vetos presidenciais",
    DomainType.SENADORES_DISCURSOS: "Discursos de senadores",
    DomainType.DISCURSOS_PLENARIO: "Discursos em plenario do Senado",
    DomainType.DISCURSOS_TEXTO: "Texto integral de discursos",
    DomainType.NOTAS_TAQUIGRAFIA_SESSAO: "Notas taquigraficas de sessoes",
    DomainType.NOTAS_TAQUIGRAFIA_REUNIAO: "Notas taquigraficas de reunioes",
    DomainType.COMISSOES_SENADO: "Comissoes do Senado Federal",
    DomainType.COMISSOES_DETALHE: "Detalhes de comissoes do Senado",
    DomainType.COMISSOES_REUNIOES: "Reunioes de comissoes do Senado",
    DomainType.COMISSOES_MEMBROS: "Membros de comissoes do Senado",
    DomainType.PLENARIO_AGENDA: "Agenda do plenario do Senado",
    DomainType.PLENARIO_RESULTADOS: "Resultados de votacoes em plenario",
    DomainType.PLENARIO_SESSOES: "Sessoes do plenario do Senado",
    DomainType.BLOCOS_SENADO: "Blocos parlamentares do Senado",
    DomainType.LIDERANCAS_SENADO: "Liderancas no Senado",
    DomainType.MESA_SENADO: "Mesa diretora do Senado",
    DomainType.MESA_CONGRESSO: "Mesa diretora do Congresso Nacional",
    DomainType.SENADORES_MANDATOS: "Histórico de mandatos dos senadores",
    DomainType.SENADORES_FILIACOES: "Histórico de filiações partidárias dos senadores",
    DomainType.ORIENTACAO_BANCADA: "Orientação de bancada nas votações do Senado",
    # ── Senado — API administrativa (adm-dadosabertos) ───────────────────────
    DomainType.SERVIDORES: "Servidores do Senado Federal (roster)",
    DomainType.REMUNERACOES: "Remunerações individuais de servidores do Senado (mensal)",
    DomainType.DESPESAS_CEAPS: "Despesas de cotas parlamentares (CEAP) do Senado (anual)",
    # ── Portal da Transparência (CGU) — Poder Executivo (tickets 02/03) ─────
    DomainType.CG_ORGAOS: "Órgãos do Poder Executivo (SIAPE, snapshot do portal)",
    DomainType.CG_SERVIDORES: "Servidores do Poder Executivo (SIAPE, agregado por órgão)",
    DomainType.CG_REMUNERACOES: "Remunerações individuais de servidores do Executivo "
    "(mensal, WAF bloqueado)",
    # ── Portal da Transparência (CGU) — Poder Executivo (ticket 04) ──────────
    DomainType.CG_PEP: "Pessoas Expostas Politicamente do Executivo (cargos públicos, bulk anual)",
    DomainType.CG_VIAGENS: "Viagens de servidores do Executivo (bulk anual)",
    DomainType.CG_CARTOES: "Cartões de pagamento do Executivo (CPGF/CPCC/CPDC — "
    "bulk mensal + API ≤12 meses)",
    DomainType.CG_IMOVEIS_FUNCIONAIS: "Imóveis funcionais da União (API v3, snapshot)",
    DomainType.CG_EMENDAS: "Emendas parlamentares (API v3, por ano)",
    # ── Portal da Transparência (CGU) — Fatia 1 (Sanções e Integridade) ────────
    DomainType.CG_CEIS: "Cadastro de Empresas Inidôneas e Suspensas (CEIS, API v3)",
    DomainType.CG_CNEP: "Cadastro Nacional de Empresas Punidas (CNEP, API v3)",
    DomainType.CG_CEPIM: "Entidades Privadas Sem Fins Lucrativos Impedidas (CEPIM, API v3)",
    DomainType.CG_CEAF: "Cadastro de Expulsões da Administração Federal (CEAF, API v3)",
    DomainType.CG_ACORDOS_LENIENCIA: "Acordos de Leniência da CGU (API v3)",
    # ── Portal da Transparência (CGU) — Fatia 2 (Compras Públicas) ────────────
    DomainType.CG_LICITACOES: "Licitações do Poder Executivo Federal (API v3)",
    DomainType.CG_CONTRATOS: "Contratos do Poder Executivo Federal (API v3)",
    DomainType.CG_CONTRATOS_ADITIVOS: "Termos Aditivos de Contratos (API v3)",
    # ── Portal da Transparência (CGU) — Fatia 3 (Convênios e Repasses) ────────
    DomainType.CG_CONVENIOS: "Convênios do Poder Executivo Federal (API v3)",
    DomainType.CG_CONVENIOS_ADITIVOS: "Termos Aditivos de Convênios (API v3)",
    # ── Portal da Transparência (CGU) — Fatia 4 (Despesas Públicas) ───────────
    DomainType.CG_DESPESAS_EMPENHOS: "Empenhos de Despesas do Poder Executivo Federal (API v3)",
    DomainType.CG_DESPESAS_PAGAMENTOS: "Pagamentos de Despesas do Poder Executivo Federal (API v3)",
    # ── Tribunal Superior Eleitoral (TSE) e Dimensões Canônicas ───────────────
    DomainType.TSE_CANDIDATOS: "Candidaturas eleitorais oficiais (TSE)",
    DomainType.TSE_BENS: "Bens e patrimônio declarados por candidatos (TSE)",
    DomainType.TSE_VOTACAO_MUNZONA: "Votação nominal de candidatos por município e zona (TSE)",
    DomainType.TSE_RECEITAS_CAMPANHA: "Receitas e doações de campanha eleitoral (TSE)",
    DomainType.TSE_DESPESAS_CAMPANHA: "Despesas e prestação de contas de campanha eleitoral (TSE)",
    DomainType.DIM_POLITICO: "Dimensão canônica mestre de políticos (Gold Star Schema)",
    DomainType.DIM_MANDATO: (
        "Dimensão temporal de mandatos e desempenho eleitoral (Gold Star Schema)"
    ),
}
