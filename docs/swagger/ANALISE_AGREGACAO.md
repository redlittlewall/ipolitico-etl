# Análise de Agregação: Câmara + Senado + Portal da Transparência

> **Data:** 2026-06-27
> **Autor:** iPolitico ETL — Análise automatizada dos Swaggers

---

## Sumário

1. [Visão Geral das APIs](#1-visão-geral-das-apis)
2. [API do Senado — Análise Detalhada](#2-api-do-senado--análise-detalhada)
3. [API do Portal da Transparência — Análise Detalhada](#3-api-do-portal-da-transparência--análise-detalhada)
4. [Matriz de Mapeamento Câmara ↔ Senado](#4-matriz-de-mapeamento-câmara--senado)
5. [O que o Portal da Transparência Agrega](#5-o-que-o-portal-da-transparência-agrega)
6. [Estratégia de Integração no ETL](#6-estratégia-de-integração-no-etl)
7. [Estimativa de Esforço](#7-estimativa-de-esforço)
8. [Riscos e Pontos de Atenção](#8-riscos-e-pontos-de-atenção)

---

## 1. Visão Geral das APIs

| Característica | Câmara | Senado | Portal Transparência |
|---|---|---|---|
| **Endpoints** | 78 | 157 | 106 |
| **Autenticação** | Nenhuma | Nenhuma | API Key (header `chave-api-dados`) |
| **Rate limit** | ~30 req/s (empírico, não documentado) | 10 req/s (documentado) | Não documentado |
| **Formatos** | JSON | JSON / XML / CSV / NDJSON | JSON |
| **Paginação** | `pagina` + `itens` | Desconhecida (não documentada no spec) | `pagina` (obrigatório) |
| **Endpoints deprecated** | 0 | ~42 (27%) | 0 |
| **Cobertura temporal** | 1826- | ~1988- | ~2006- |
| **Dados principais** | Deputados, proposições, votações, eventos, gastos CEAP | Senadores, processos legislativos, comissões, discursos, orçamento | Gastos federais, contratos, licitações, servidores, benefícios sociais, emendas |

---

## 2. API do Senado — Análise Detalhada

### 2.1 Tags e Domínios Identificados

| Tag | Qtde Endpoints | Descrição | Status |
|---|---|---|---|
| **Parlamentar** | 16 | Senadores — lista, detalhes, cargos, comissões, filiações, mandatos, profissões | ✅ Core |
| **Comissão** | 14 | Colegiados, agenda, reuniões, CPIs, tipos | ✅ Core |
| **Composição** | 15 | Blocos, lideranças, mesas, composição de comissões | ✅ Core |
| **Plenário** | 24 | Agenda, votações, resultados, sessões, orientação de bancada | ✅ Core |
| **Votação** | 12 | Votos nominais, votações em comissão | ✅ Core |
| **Processo** | 28 | Processos legislativos (nova API) — filtros avançados | ⭐ Essencial |
| **Discurso** | 9 | Discursos, notas taquigráficas, apartes | ✅ Core |
| **Legislação** | 9 | Normas jurídicas, classificação, pesquisa | ✅ Core |
| **Orçamento** | 3 | Emendas ao orçamento, ofícios | 💎 Valor agregado |
| ~~Matéria~~ | 28 | **(DEPRECATED)** — substituído por `/processo` | ❌ Ignorar |

### 2.2 Observações Críticas

1. **42 endpoints deprecated (27%)** — A API do Senado está em migração do sistema legado `MATE` para o novo sistema de processos. O spec já lista os substitutos via cabeçalhos `Deprecation` / `Sunset` / `Link`.
2. **Sem autenticação** — Igual à Câmara. Pode ser consumida livremente dentro do rate limit de 10 req/s.
3. **Múltiplos formatos** — Diferente da Câmara (só JSON), o Senado aceita `Accept: application/json`, `application/xml`, `text/csv`, `application/x-ndjson`. O JSON é o padrão moderno.
4. **Rate limit explícito: 10 req/s** — A documentação avisa que acima disso retorna HTTP 429. Comparado com os ~30 req/s empíricos da Câmara, é mais restritivo.
5. **Sem Bulk/CSV dump** — Diferente da Câmara (que oferece ZIPs anuais de deputados, despesas, proposições), o Senado **não** parece oferecer dados granulares em bulk. Tudo via API REST.

---

## 3. API do Portal da Transparência — Análise Detalhada

### 3.1 Tags e Domínios

| Tag | Qtde | Descrição | Relevância para iPolitico |
|---|---|---|---|
| **Emendas parlamentares** | 2 | Emendas parlamentares e seus documentos | 🔥 **ALTA** — diretamente ligado ao mandato |
| **Despesas Públicas** | 14 | Documentos de despesas, empenhos, favorecidos, plano orçamentário | 🔥 **ALTA** — gasto público federal |
| **Contratos do Poder Executivo** | 8 | Contratos, apostilamentos, itens, fornecedores | 🔥 **ALTA** — fiscalização |
| **Licitações** | 10 | Licitações, participantes, modalidades, UGs | 🔥 **ALTA** — transparência |
| **Servidores** | 5 | Servidores federais, remunerações, cargos | 🔥 **ALTA** — gasto com pessoal |
| **Convênios** | 5 | Convênios, instrumentos | 🔥 **ALTA** — transferências |
| **Órgãos** | 2 | Órgãos SIAFI e SIAPE | 🟡 Média — tabela auxiliar |
| **Sanções** | 10 | CEIS, CNEP, CEPIM, CEAF, acordos de leniência | 🟡 Média — integridade |
| **Viagens** | 3 | Viagens a serviço | 🟡 Média |
| **Benefícios** | 22 | Bolsa Família, Auxílio Brasil, BPC, seguro-defeso | 🟡 Média — social |
| **Cartões** | 1 | Gastos com cartão de pagamento | 🟡 Média |
| **Renúncias Fiscais** | 3 | Benefícios fiscais, empresas isentas | 🟡 Média |
| **Notas Fiscais** | 2 | NFe do Executivo Federal | 🟢 Baixa |
| **Pessoas** | 2 | PF e PJ cadastradas | 🟢 Baixa — auxiliar |
| **Imóveis** | 3 | Imóveis funcionais e permissionários | 🟢 Baixa |

### 3.2 Observações Críticas

1. **Requer API Key** — É necessário se cadastrar em https://www.portaldatransparencia.gov.br/api-de-dados/cadastrar-email para obter uma chave.
2. **Paginação obrigatória** — O parâmetro `pagina` é obrigatório em praticamente todos os endpoints. Sem página, a requisição falha.
3. **Sem bulk download** — Diferente da Câmara, o Portal da Transparência não oferece dumps ZIP. Tudo via API REST paginada.
4. **Dados federais, não legislativos** — Enquanto Câmara e Senado tratam do processo legislativo, o Portal cobre o **Poder Executivo Federal** (execução orçamentária, contratos, servidores).
5. **Endpoints de alta cardinalidade** — Endpoints como `despesas/documentos` e `contratos` exigem janelas temporais ou filtros específicos para não serem proibitivos.

---

## 4. Matriz de Mapeamento Câmara ↔ Senado

A tabela abaixo mapeia domínios equivalentes entre as duas casas legislativas:

### 4.1 Parlamentares

| Domínio | Câmara (existente) | Senado (a implementar) | Mapeamento |
|---|---|---|---|
| Lista de parlamentares | `GET /deputados` | `GET /senador/lista/atual` | `deputados` ↔ `senadores` |
| Detalhes | `GET /deputados/{id}` | `GET /senador/{codigo}` | Similar, IDs diferentes |
| Mandatos anteriores | `GET /deputados/{id}/mandatosExternos` | `GET /senador/{codigo}/mandatos` | Similar |
| Profissões | `GET /deputados/{id}/profissoes` | `GET /senador/{codigo}/profissao` | Idêntico |
| Partido atual | Embutido em `/deputados/{id}` | `GET /senador/{codigo}/filiacoes` | Histórico no Senado |
| Discursos | `GET /deputados/{id}/discursos` | `GET /senador/{codigo}/discursos` | Idêntico |
| Órgãos/Comissões | `GET /deputados/{id}/orgaos` | `GET /senador/{codigo}/comissoes` | Idêntico (nomenclatura diferente) |
| Cargos | Embutido em `/deputados/{id}` | `GET /senador/{codigo}/cargos` | Similar |
| Histórico acadêmico | Não existe | `GET /senador/{codigo}/historicoAcademico` | **Exclusivo Senado** |
| Licenças | Não existe | `GET /senador/{codigo}/licencas` | **Exclusivo Senado** |
| Afastados | Não existe | `GET /senador/afastados` | **Exclusivo Senado** |

### 4.2 Proposições / Processos Legislativos

| Domínio | Câmara | Senado | Mapeamento |
|---|---|---|---|
| Lista de proposições | `GET /proposicoes` | `GET /processo` | Diferente (Senado é mais rico: sigla, classe, assunto, situação) |
| Detalhes | `GET /proposicoes/{id}` | `GET /processo/{id}` | Similar |
| Autores | `GET /proposicoes/{id}/autores` | Embutido em `/processo` | Senado tem embutido |
| Tramitação | `GET /proposicoes/{id}/tramitacoes` | `GET /processo/{id}` (embutido?) | A verificar |
| Relatorias | `GET /proposicoes/{id}/autores` | `GET /processo/relatoria` | **Exclusivo Senado** |
| Emendas | Não existe | `GET /processo/emenda` | **Exclusivo Senado** |
| Documentos | Não existe | `GET /processo/documento` | **Exclusivo Senado** |
| Prazos | Não existe | `GET /processo/prazo` | **Exclusivo Senado** |
| Votações da matéria | `GET /proposicoes/{id}/votacoes` | `GET /dadosabertos/votacao` (filtro por processo) | Similar |
| Vetos | Não existe | `GET /materia/vetos/{ano}` | **Exclusivo Senado** |

### 4.3 Votações e Plenário

| Domínio | Câmara | Senado | Mapeamento |
|---|---|---|---|
| Votações | `GET /votacoes` | `GET /dadosabertos/votacao` | Similar |
| Votos | `GET /votacoes/{id}/votos` | Embutido em `/dadosabertos/votacao` | A verificar |
| Orientações de bancada | `GET /votacoes/{id}/orientacoes` | `GET /plenario/votacao/orientacaoBancada/{inicio}/{fim}` | Similar |
| Sessões plenárias | `GET /eventos` | `GET /plenario/agenda/dia/{data}` | Estrutura diferente |
| Resultado de sessão | Não existe | `GET /plenario/resultado/{data}` | **Exclusivo Senado** |

### 4.4 Comissões e Órgãos

| Domínio | Câmara | Senado | Mapeamento |
|---|---|---|---|
| Lista de órgãos/comissões | `GET /orgaos` | `GET /comissao/lista/{tipo}` | Similar |
| Detalhes | `GET /orgaos/{id}` | `GET /comissao/{codigo}` | Similar |
| Membros | `GET /orgaos/{id}/membros` | Embutido em composição | Composição mais rica no Senado |
| Eventos/Reuniões |  `GET /orgaos/{id}/eventos` | `GET /comissao/agenda/{inicio}/{fim}` | Similar |
| Votações no órgão | `GET /orgaos/{id}/votacoes` | `GET /votacaoComissao/comissao/{sigla}` | Similar |
| Notas taquigráficas | Não existe | `GET /comissao/reuniao/notas/{codigo}` | **Exclusivo Senado** |
| CPIs | Não existe | `GET /comissao/cpi/{codigo}/requerimentos` | **Exclusivo Senado** |
| Tipos de colegiado | Não existe | `GET /comissao/lista/tiposColegiado` | Senado mais rico |

### 4.5 Blocos, Frentes, Lideranças

| Domínio | Câmara | Senado | Mapeamento |
|---|---|---|---|
| Blocos parlamentares | `GET /blocos` | `GET /composicao/bloco/{codigo}` | Similar |
| Partidos do bloco | `GET /blocos/{id}/partidos` | Embutido em `composicao/bloco` | Similar |
| Frentes parlamentares | `GET /frentes` | Não encontrado | ❌ **Não existe no Senado** |
| Lideranças | `GET /legislaturas/{id}/lideres` | `GET /composicao/lideranca` | Similar |
| Mesa diretora | `GET /legislaturas/{id}/mesa` | `GET /composicao/mesaCN` e `mesaSF` | Similar |

### 4.6 Domínios Exclusivos do Senado

Domínios que **não existem** na Câmara e agregariam valor significativo:

| Domínio | Endpoint | Valor Agregado |
|---|---|---|
| **Orçamento / Emendas** | `GET /dadosabertos/orcamento/lista` | Emendas parlamentares dos senadores ao orçamento |
| **Vetos presidenciais** | `GET /dadosabertos/materia/vetos/{ano}` | Histórico completo de vetos |
| **Notas taquigráficas** | `GET /dadosabertos/comissao/reuniao/notas/{codigo}` | Transcrição literal de reuniões |
| **Processo completo** | `GET /dadosabertos/processo/{id}` | Visão holística com emendas, documentos, relatorias, prazos |
| **Histórico acadêmico** | `GET /dadosabertos/senador/{codigo}/historicoAcademico` | Formação dos senadores |
| **Licenças** | `GET /dadosabertos/senador/{codigo}/licencas` | Transparência sobre afastamentos |
| **Distribuição de autoria/relatoria** | `GET /dadosabertos/materia/distribuicao/autoria` | Métricas de produtividade por comissão |

---

## 5. O que o Portal da Transparência Agrega

### 5.1 Complementaridade com Câmara

O Portal da Transparência **não compete** com Câmara ou Senado — ele **complementa** o retrato da atividade parlamentar sob o ângulo da execução orçamentária:

| Fonte atual | O que falta | Portal da Transparência preenche? |
|---|---|---|
| CEAP (Cota parlamentar) — Câmara | Só mostra gastos da cota, não o orçamento total | 🔥 **Sim** — despesas públicas federais completas |
| Licitações — Câmara (bulk) | Só da Câmara, não do Executivo | 🔥 **Sim** — licitações e contratos de todo o Executivo Federal |
| Servidores — Câmara (funcionarios) | Só servidores da Câmara | 🔥 **Sim** — servidores de **todo** o Executivo Federal |
| Sem fonte de emendas | Não temos emendas parlamentares | 🔥 **Sim** — emendas com documentos relacionados |
| Sem fonte de sanções | Não temos dados de integridade | 🟡 **Sim** — CEIS, CNEP, CEPIM, CEAF |

### 5.2 Conexão com dados legislativos

O Portal da Transparência **não se conecta diretamente** com IDs da Câmara ou do Senado. Não há chave estrangeira entre `deputados.id` (Câmara) e `emendas.codigoAutor` (Portal). A conexão teria que ser:

- **Por CPF** — O Portal retorna CPF de servidores (em `/servidores`). Se tivermos CPF dos deputados/senadores, podemos cruzar.
- **Por CNPJ** — Contratos e convênios têm CNPJ de fornecedores.
- **Por nome** — Fallback frágil, mas usável para emendas (nome do autor).

### 5.3 Restrições

1. **Apenas Poder Executivo Federal** — Dados do Judiciário, Legislativo e estados **não** estão cobertos (exceto onde o Executivo é o gestor, como convênios).
2. **API Key necessária** — A chave deve ser obtida via cadastro online.
3. **Alta cardinalidade** — Endpoints como `despesas/documentos` sem filtro podem demandar milhões de páginas.
4. **Paginação eterna** — Diferente da Câmara (que limita a 100 itens/página), o Portal não documenta limite de itens — a implosão de páginas é um risco real.

---

## 6. Estratégia de Integração no ETL

### 6.1 Arquitetura Proposta

```
┌────────────────────────────────────────────────────────────┐
│                  PipelineOrchestrator                       │
│  (coordena fontes, barreira semântica de concorrência)     │
└────┬──────────┬────────────┬───────────────────────────────┘
     │          │            │
┌────▼────┐ ┌──▼──────┐ ┌──▼──────────────────┐
│ Camara │ │ Senado  │ │ Portal Transparencia │
│ 78 endp│ │ 115 endp│ │ 106 endp             │
│ 30 rps │ │ 10 rps  │ │ ? rps (API Key)      │
│ no auth│ │ no auth │ │ auth: header key     │
└────────┘ └─────────┘ └──────────────────────┘
     │          │            │
     └──────────┴────────────┘
               │
        ┌──────▼──────┐
        │ Data Lake   │
        │ (Bronze →   │
        │  Silver →   │
        │  Gold)      │
        └─────────────┘
```

### 6.2 Princípios de Integração

1. **Fontes como `SourceProvider`** — Cada fonte implementa `SourceProvider` (padrão já definido em `sources/camara_provider.py`). O `PipelineManager` passa a aceitar uma lista de providers.

2. **Semáforo de concorrência por fonte** — Já que cada API tem rate limits diferentes:
   - Câmara: `CAMARA_HTTP_CONCURRENCY = 10` (já implementado)
   - Senado: `SENADO_HTTP_CONCURRENCY = 5` (10 req/s → 5 simultâneas seguras)
   - Portal: `PORTAL_HTTP_CONCURRENCY = 3` (conservador até documentar)

3. **Barreira semântica de federação** — Onde Câmara e Senado têm domínios equivalentes (ex: `deputados` ↔ `senadores`), o Gold Layer unifica ambos em visões como `parlamentares`, `proposicoes_federais`, `votacoes_plenario`.

4. **Padrão de implementação** — Mesma arquitetura de Camada (base: `Extractor → Transformer → Sink`):
   - `extractors/senado/` — Extratores seguindo `BaseExtractor`
   - `extractors/portaldatransparencia/` — Idem
   - `transformers/senado/` — Transformers puros (sem I/O)
   - `sinks/datalake_sink.py` — Reutilizado (já genérico)

### 6.3 Plano de Fases

#### Fase A — Senado (Core, ~115 endpoints não-deprecados)

| Prioridade | Domínio | Endpoints | Dependência | Esforço |
|---|---|---|---|---|
| P0 | **Senadores** (lista, detalhes) | 2 | Nenhuma | 1 dia |
| P0 | **Processos legislativos** (proposições) | 28 | Senadores? | 3 dias |
| P0 | **Votações** (nominais, comissão) | 12 | Processos | 2 dias |
| P0 | **Comissões** (lista, detalhes, membros) | 14 | Senadores | 2 dias |
| P1 | **Discursos** (senador, período) | 9 | Senadores | 1 dia |
| P1 | **Composição** (blocos, lideranças, mesas) | 15 | Senadores | 2 dias |
| P1 | **Plenário** (agenda, resultados) | 24 | Votações | 2 dias |
| P2 | **Orçamento** (emendas) | 3 | Senadores | 1 dia |
| P2 | **Legislação** (normas) | 9 | Nenhuma | 1 dia |
| **Total** | | **115** | | **~15 dias** |

#### Fase B — Portal da Transparência

| Prioridade | Domínio | Endpoints | Esforço |
|---|---|---|---|
| P0 | **Emendas parlamentares** | 2 | 1 dia |
| P0 | **Contratos federais** | 8 | 2 dias |
| P0 | **Licitações federais** | 10 | 2 dias |
| P1 | **Despesas públicas** | 14 | 3 dias |
| P1 | **Servidores federais** | 5 | 1 dia |
| P1 | **Convênios** | 5 | 1 dia |
| P2 | **Sanções** (CEIS, CNEP) | 10 | 2 dias |
| P2 | **Viagens** | 3 | 1 dia |
| **Total** | | **57** | **~12 dias** |

#### Fase C — Federação Gold

| Tarefa | Descrição | Esforço |
|---|---|---|
| Gold `parlamentares` | Unificar deputados + senadores (schema comum com CPF) | 2 dias |
| Gold `proposicoes_federais` | Unificar proposições Câmara + processos Senado | 2 dias |
| Gold `votacoes_plenario` | Unificar votações Câmara + Senado | 2 dias |
| Gold `gastos_parlamentares` | CEAP + emendas parlamentares + dados Portal | 3 dias |
| Gold `contratos_licitacoes` | Contratos e licitações (Câmara + Portal) | 2 dias |
| Gold `servidores_federais` | Servidores Câmara + Executivo Federal | 1 dia |
| **Total** | | **~12 dias** |

### 6.4 Schema de Domínios do Senado no DomainType

Seguindo o padrão existente (acentuação mantida por consistência):

```python
# ── Senado: Parlamentares ──────────────────────────────────────
SENADORES = "senadores"               # Lista de senadores (equivalente a deputados)
SENADORES_DETALHE = "senadores_detalhe"
SENADORES_MANDATOS = "senadores_mandatos"
SENADORES_FILIACOES = "senadores_filiacoes"
SENADORES_CARGOS = "senadores_cargos"
SENADORES_COMISSOES = "senadores_comissoes"
SENADORES_PROFISSOES = "senadores_profissoes"
SENADORES_DISCURSOS = "senadores_discursos"
SENADORES_HISTORICO_ACADEMICO = "senadores_historico_academico"
SENADORES_LICENCAS = "senadores_licencas"

# ── Senado: Processos Legislativos ─────────────────────────────
PROCESSOS = "processos"               # Lista de processos (equivalente a proposicoes)
PROCESSOS_DETALHE = "processos_detalhe"
PROCESSOS_EMENDAS = "processos_emendas"
PROCESSOS_DOCUMENTOS = "processos_documentos"
PROCESSOS_RELATORIAS = "processos_relatorias"
PROCESSOS_PRAZOS = "processos_prazos"

# ── Senado: Votações ───────────────────────────────────────────
VOTACOES_SENADO = "votacoes_senado"
VOTOS_SENADO = "votos_senado"
ORIENTACOES_SENADO = "orientacoes_senado"
VOTACOES_COMISSAO_SENADO = "votacoes_comissao_senado"

# ── Senado: Comissões ──────────────────────────────────────────
COMISSOES_SENADO = "comissoes_senado"
COMISSOES_MEMBROS = "comissoes_membros"
COMISSOES_REUNIOES = "comissoes_reunioes"
COMISSOES_NOTAS = "comissoes_notas_taquigrafia"

# ── Senado: Composição ─────────────────────────────────────────
BLOCOS_SENADO = "blocos_senado"
LIDERANCAS_SENADO = "liderancas_senado"
MESA_SENADO = "mesa_senado"

# ── Senado: Plenário ───────────────────────────────────────────
PLENARIO_AGENDA = "plenario_agenda"
PLENARIO_RESULTADOS = "plenario_resultados"
PLENARIO_SESSOES = "plenario_sessoes"
VETOS = "vetos_presidenciais"

# ── Portal Transparência ───────────────────────────────────────
EMENDAS_PARLAMENTARES = "emendas_parlamentares"
CONTRATOS_FEDERAIS = "contratos_federais"
LICITACOES_FEDERAIS = "licitacoes_federais"
DESPESAS_FEDERAIS = "despesas_federais"
SERVIDORES_FEDERAIS = "servidores_federais"
CONVENIOS_FEDERAIS = "convenios_federais"
ORGAOS_SIAFI = "orgaos_siafi"
SANCOES_CEIS = "sancoes_ceis"
SANCOES_CNEP = "sancoes_cnep"
```

---

## 7. Estimativa de Esforço

| Fase | Dias | Dependências | Entregas |
|---|---|---|---|
| **Fase A — Senado Core** | ~15 dias | Nenhuma (pode rodar em paralelo) | 115 endpoints, ~20 novos DomainTypes |
| **Fase B — Portal** | ~12 dias | Obter API Key (1h) | ~57 endpoints de alto valor |
| **Fase C — Federação Gold** | ~12 dias | Fase A + B completas | 6 visões Gold federadas |
| **Total estimado** | **~39 dias** | | |

### 7.1 Paralelismo

- **Fase A (Senado)** pode começar imediatamente — não depende de nada.
- **Fase B (Portal)** pode começar assim que a API Key for obtida.
- **Fase C (Federação Gold)** só faz sentido após ambas as fases A e B estarem em Silver.

---

## 8. Riscos e Pontos de Atenção

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| **42 endpoints deprecated no Senado** | Certo | Médio | Ignorar os 42 deprecated; focar nos 115 ativos + os novos `/processo` |
| **Senado sem bulk download** | Certo | Alto | FULL_LOAD via API (lento para processos e votações). Necessário planejar job incremental robusto |
| **Rate limit Senado 10 req/s** | Certo | Médio | Semáforo `SENADO_HTTP_CONCURRENCY=5` + backoff exponencial (igual Câmara) |
| **Portal sem bulk download** | Certo | Alto | FULL_LOAD via API paginada. Para `despesas/documentos` pode ser inviável sem filtro temporal agressivo |
| **Portal sem documentação de rate limit** | Alto | Médio | Começar conservador (conc=3), escalar empiricamente igual fizemos com Câmara |
| **Portal sem chave estrangeira com Câmara/Senado** | Certo | Alto | Federação Gold terá que usar CPF/CNPJ como ponte, não IDs |
| **Portal: alta cardinalidade** | Alto | Alto | FULL_LOAD só viável com janelas anuais+mensais. INCREMENTAL via data |
| **Senado migrando de API** | Médio | Alto | Monitorar headers `Deprecation`/`Sunset` nos endpoints novos — podem ser descontinuados |
| **Volume de dados estimado** | Médio | Baixo | Senado: ~500MB-1GB (projeção). Portal: ~5-10GB (muito maior por ser Executivo Federal) |

---

## Swaggers Baixados

Os arquivos foram salvos em:

| API | Arquivo | Tamanho | Fonte |
|---|---|---|---|
| Câmara (já existia) | `docs/camara_swagger.json` | 408 KB | `https://dadosabertos.camara.leg.br/swagger` |
| Senado (novo) | `docs/swagger/senado_swagger.json` | 168 KB | `https://legis.senado.leg.br/dadosabertos/v3/api-docs` |
| Portal Transparência (novo) | `docs/swagger/portal_transparencia_swagger.json` | 164 KB | `https://api.portaldatransparencia.gov.br/v3/api-docs` |
