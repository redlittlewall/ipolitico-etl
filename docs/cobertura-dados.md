# Cobertura de Dados — iPolitico ETL

> Documento gerado automaticamente a partir do registry de cobertura do código
> (`EARLIEST_DATE_MAP`, `COVERAGE_GAPS`, `DOMAIN_SOURCE_SYSTEM`). Não edite à mão.
> Para regenerar: `ipolitico --generate-coverage-doc`.

A **data de início** indica quando o órgão passou a disponibilizar dados para o
domínio — não há registros anteriores por ausência na fonte, e o full load não
faz requisições em períodos sem dados. As **lacunas** são ausências permanentes
conhecidas no meio da série (a fonte responde vazio/404 para o período).

## Sistemas de origem

| Sistema | API |
|---|---|
| Câmara dos Deputados | https://dadosabertos.camara.leg.br |
| Senado Federal | https://legis.senado.leg.br |
| Portal da Transparência (CGU) | https://portaldatransparencia.gov.br |

## Câmara dos Deputados

API: https://dadosabertos.camara.leg.br

| Domínio | Início dos dados | Lacunas no meio da série |
|---|---|---|
| `deputados` | 1826-04-29 | — |
| `deputados_detalhe` | 1826-04-29 | — |
| `legislaturas` | 1826-04-29 | — |
| `legislaturas_detalhe` | 1826-04-29 | — |
| `legislaturas_lideres` | 1826-04-29 | — |
| `legislaturas_mesa` | 1826-04-29 | — |
| `blocos` | 1826-04-29 | — |
| `blocos_partidos` | 1826-04-29 | — |
| `frentes` | 2003-01-01 | — |
| `frentes_detalhe` | 2003-01-01 | — |
| `frentes_membros` | 2003-01-01 | — |
| `grupos` | 1826-04-29 | — |
| `grupos_detalhe` | 1826-04-29 | — |
| `grupos_membros` | 1826-04-29 | — |
| `grupos_historico` | 1826-04-29 | — |
| `orgaos` | 1946-02-01 | — |
| `orgaos_detalhe` | 1946-02-01 | — |
| `orgaos_membros` | 1946-02-01 | — |
| `orgaos_eventos` | 1946-02-01 | — |
| `orgaos_votacoes` | 1946-02-01 | — |
| `partidos` | 1946-02-01 | — |
| `partidos_detalhe` | 1946-02-01 | — |
| `partidos_membros` | 1946-02-01 | — |
| `partidos_lideres` | 1946-02-01 | — |
| `despesas` | 2009-01-01 | — |
| `proposicoes` | 1988-01-01 | — |
| `tramitacoes` | 1988-01-01 | — |
| `autores` | 1988-01-01 | — |
| `relacionadas` | 1988-01-01 | — |
| `temas` | 1988-01-01 | — |
| `proposicoes_votacoes` | 1988-01-01 | — |
| `deputados_historico` | 1826-04-29 | — |
| `discursos` | 1995-01-01 | — |
| `deputados_frentes` | 1826-04-29 | — |
| `deputados_orgaos` | 1826-04-29 | — |
| `deputados_eventos` | 1826-04-29 | — |
| `mandatos_externos` | 1826-04-29 | — |
| `profissoes` | 1826-04-29 | — |
| `ocupacoes` | 1826-04-29 | — |
| `votacoes` | 1991-01-01 | — |
| `votacoes_detalhe` | 1991-01-01 | — |
| `votos` | 1991-01-01 | — |
| `orientacoes` | 1991-01-01 | — |
| `eventos` | 1991-01-01 | — |
| `eventos_detalhe` | 1991-01-01 | — |
| `eventos_deputados` | 1991-01-01 | — |
| `eventos_votacoes` | 1991-01-01 | — |
| `eventos_pauta` | 1991-01-01 | — |
| `eventos_orgaos` | 1991-01-01 | — |
| `referencias` | 1826-04-29 | — |
| `funcionarios` | 1826-04-29 | — |
| `tecad_categorias` | 1826-04-29 | — |
| `tecad_termos` | 1826-04-29 | — |
| `licitacoes` | 1999-01-01 | — |
| `licitacoes_contratos` | 1999-01-01 | — |
| `licitacoes_itens` | 1999-01-01 | — |
| `licitacoes_pedidos` | 1999-01-01 | — |
| `licitacoes_propostas` | 1999-01-01 | — |
| `eventos_presenca_deputados` | 1991-01-01 | — |
| `eventos_requerimentos` | 1991-01-01 | — |
| `votacoes_objetos` | 1991-01-01 | — |
| `votacoes_proposicoes` | 1991-01-01 | — |
| `folha_pagamento` | 2012-01-01 | 2011, 2015 e 2022 não publicados (HTTP 404) — ausência, não erro |
| `blocos_detalhe` | 1826-04-29 | — |
| `proposicoes_detalhe` | 1988-01-01 | — |

## Senado Federal

API: https://legis.senado.leg.br

| Domínio | Início dos dados | Lacunas no meio da série |
|---|---|---|
| `senadores` | 1949-01-01 | — |
| `senadores_detalhe` | 1949-01-01 | — |
| `processos` | 1949-01-01 | — |
| `processos_detalhe` | 1949-01-01 | — |
| `processos_emendas` | 1949-01-01 | — |
| `processos_documentos` | 1949-01-01 | — |
| `votacoes_senado` | 1991-01-01 | — |
| `votos_senado` | 1991-01-01 | — |
| `votacoes_comissao` | 1991-01-01 | — |
| `orcamento_emendas` | 2000-01-01 | — |
| `orcamento_oficios` | 2000-01-01 | — |
| `vetos_presidenciais` | 1995-01-01 | — |
| `vetos_detalhe` | 1995-01-01 | — |
| `senadores_discursos` | 1995-01-01 | — |
| `discursos_plenario` | 1995-01-01 | — |
| `discursos_texto` | 1995-01-01 | — |
| `notas_taquigrafia_sessao` | 2003-01-01 | — |
| `notas_taquigrafia_reuniao` | 2003-01-01 | — |
| `comissoes_senado` | 1949-01-01 | — |
| `comissoes_detalhe` | 1949-01-01 | — |
| `comissoes_reunioes` | 2003-01-01 | — |
| `comissoes_membros` | 1949-01-01 | — |
| `plenario_agenda` | 2003-01-01 | — |
| `plenario_resultados` | 2003-01-01 | — |
| `plenario_sessoes` | 2003-01-01 | — |
| `blocos_senado` | 1995-01-01 | — |
| `liderancas_senado` | 1995-01-01 | — |
| `mesa_senado` | 1995-01-01 | — |
| `mesa_congresso` | 1995-01-01 | — |
| `senadores_mandatos` | 1949-01-01 | — |
| `senadores_filiacoes` | 1949-01-01 | — |
| `orientacao_bancada` | 1991-01-01 | — |
| `servidores` | 1826-04-29 | — |
| `remuneracoes` | 2013-01-01 | 404 para 2012 e anteriores (início da série 2013-01) — ausência permanente; mês corrente não publicado = HTTP 200 com lista vazia (ausência temporária) |
| `despesas_ceaps` | 2008-01-01 | 404 para 2007 e anteriores (início da série 2008) — ausência permanente |

## Portal da Transparência (CGU)

API: https://portaldatransparencia.gov.br

| Domínio | Início dos dados | Lacunas no meio da série |
|---|---|---|
| `cg_orgaos` | 1826-04-29 | — |
| `cg_servidores` | 1826-04-29 | — |
| `cg_remuneracoes` | 2017-01-01 | — |
| `cg_pep` | 2013-01-01 | — |
| `cg_viagens` | 2013-01-01 | — |
| `cg_cartoes` | 2014-01-01 | — |
| `cg_imoveis_funcionais` | 1826-04-29 | — |
| `cg_emendas` | 2012-01-01 | — |
| `cg_ceis` | 1826-04-29 | — |
| `cg_cnep` | 1826-04-29 | — |
| `cg_cepim` | 1826-04-29 | — |
| `cg_ceaf` | 1826-04-29 | — |
| `cg_acordos_leniencia` | 1826-04-29 | — |
| `cg_licitacoes` | 1826-04-29 | — |
| `cg_contratos` | 1826-04-29 | — |
| `cg_contratos_aditivos` | 1826-04-29 | — |
| `cg_convenios` | 1826-04-29 | — |
| `cg_convenios_aditivos` | 1826-04-29 | — |
