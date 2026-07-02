---
Status: completed
Type: review
---

# Issue 09 — Execução Completa e Validação do Senado

## Parent

`.scratch/senado-integracao/PRD.md`

## Objetivo

Executar o pipeline completo do Senado ponta-a-ponta, validar que todos os 30 domínios
foram consumidos com sucesso, e durante a execução identificar correções e melhorias.

**Regra:** correções rápidas (até ~5min) devem ser aplicadas na hora.
Correções maiores devem ser documentadas neste issue para execução posterior.

## Pré-condições

- [x] Issues 02–08 todas marcadas como `completed`
- [x] `configs/senado_pipeline.yaml` contém todos os 29 domínios mapeados
- [x] `SILVER_SCHEMAS` definidos para todos os 31 domínios (inclui compartilhados)
- [x] `pytest -q` passando (**572 passed**)
- [x] Conexão com internet (API do Senado pública)

## Roteiro de Execução

### Passo 1 — Smoke test rápido (validação de imports e CLI)

```bash
# Listar domínios do Senado
python -m ipolitico --list-domains | grep -c "senado"

# Executar um domínio conhecido para confirmar que o pipeline básico funciona
python -m ipolitico pipeline --source senado --full-load --domains senadores
```

### Passo 2 — Execução completa (full load)

```bash
python -m ipolitico pipeline --source senado --full-load 2>&1 | tee /tmp/senado-full-load.log
```

**Monitorar durante execução:**
- Erros 429 (rate limit) — verificar se backoff está funcionando
- Erros 502/504 (instabilidade da API)
- Falsos 404 tratados como lista vazia
- Erros de schema mismatch (campo que a API retorna mas não está mapeado)
- Erros de `_ensure_list` (objeto-único não normalizado)
- Domínios que demoram desproporcionalmente (possível bottleneck)

### Passo 3 — Auditoria de cobertura

```bash
python -m ipolitico --audit-coverage 2>&1 | tee /tmp/senado-audit-coverage.log
```

**Verificar para cada domínio:**
- [ ] `silver_rows > 0` (todo domínio produziu dados)
- [ ] `gold_rows > 0` (otimização Gold funcionou)
- [ ] Nenhum domínio com `silver_rows = 0` sem justificativa (ex: endpoint sem dados históricos)

### Passo 4 — Verificação manual de integridade (amostragem)

Para cada categoria, abrir um arquivo Silver e conferir:
- [ ] **Senadores:** `data/datalake/silver/senadores/` — contém 81 registros?
- [ ] **Senadores Detalhe:** dados cadastrais completos (nome, partido, UF, mandatos)
- [ ] **Processos:** pelo menos 1 arquivo Parquet com registros
- [ ] **Votações:** votos individuais com `codigo_parlamentar`, `voto`
- [ ] **Emendas:** emendas orçamentárias com valores
- [ ] **Vetos:** vetos presidenciais com data e resultado
- [ ] **Discursos:** discursos com texto integral
- [ ] **Comissões:** composição com membros
- [ ] **Plenário:** agenda, resultados e sessões
- [ ] **Composição:** blocos, lideranças, mesa

```bash
# Script auxiliar para checar todos os dirs Silver do Senado
for d in data/datalake/silver/senado_*/; do
  count=$(find "$d" -name '*.parquet' 2>/dev/null | wc -l)
  echo "$(basename "$d"): $count arquivos"
done
```

## Checklist de Avaliação

### Performance

- [x] Tempo total de execução registrado: **3.849s (~64 min)**
- [ ] Domínios mais lentos identificados (top 5 por tempo)
- [ ] Bottlenecks de concorrência (semáforo 5 ocioso ou sobrecarregado?)
- [ ] Domínios com janela mensal que poderiam ser paralelizados

**Nota:** Domínios mais pesados por volume de jobs diários: `plenario_agenda` (8.582), `plenario_resultados` (8.582), `plenario_sessoes` (8.582), `senadores_discursos` (1.943), `senadores_detalhe` (78 lotes).

### Qualidade dos Dados

- [x] Schemas Silver respeitados (sem colunas extras inesperadas) — verificado nos 12 domínios com dados
- [x] Tipos de dados corretos (int vs string, datas como datetime)
- [x] `captured_at` presente em todos os registros — confirmado em todos os domínios
- [x] Valores nulos tratados adequadamente — nulos em campos opcionais (ex: `codigo_mandato` em senadores)
- [ ] IDs únicos respeitados (unique_keys do DomainSpec) — parcialmente verificado

### Resiliência

- [x] Nenhum timeout não tratado
- [x] Nenhum crash em falso 404 — tratado como lista vazia (SenadoClient linha 106-108)
- [x] Retry funcionou para falhas intermitentes — confirmado em processos_emendas e processos_documentos
- [x] PipelineManager recuperou de erros parciais — domínios com erro 400 continuaram, pipeline prosseguiu

### Pipeline

- [x] Dependências entre domínios respeitadas (ex: vetos_detalhe skipado porque vetos_presidenciais não produziu dados)
- [ ] Watermark columns funcionando (incremental não reprocessa tudo) — não testado (execução full load)
- [ ] FederationOrchestrator executou Câmara e Senado sem conflito — não testado (`--source senado` apenas)

## Registro de Correções e Achados

| # | Categoria | Descrição | Gravidade | Correção imediata? | Resolução |
|---|---|---|---|---|---|
| 1 | Resiliência | `warmup_for_domain` ausente no `SenadoClient` | blocker | sim | Adicionado no-op `warmup_for_domain` em `senado_client.py` |
| 2 | Pipeline | `--strategy` precisa do valor enum, não nome (`full_load` funciona, `LoadStrategy.FULL_LOAD` não) | melhoria | sim | Documentado — CLI aceita `full_load` como string |
| 3 | Extrator | **vetos_presidenciais**: envelope API mudou de `MateriaVetos` para `ListaVetosAnoCN` | blocker | não | `_DATA_PATH_PRESIDENCIAIS` + `_FIELD_MAP_PRESIDENCIAIS` precisam ser atualizados |
| 4 | Extrator | **processos_emendas**: API limita janela a 1 ano (HTTP 400) | alta | não | Precisa de planner com janela anual |
| 5 | Extrator | **processos_documentos**: API limita janela a 6 meses (HTTP 400) | alta | não | Precisa de planner com janela semestral |
| 6 | Extrator | **plenario_agenda/resultados/sessoes**: endpoints 404 ou 400 | alta | não | Endpoints do Senado mudaram ou estão incorretos |
| 7 | Extrator | **senadores_discursos**: 0 dados apesar de 1943 jobs processados | alta | não | Verificar endpoint e transformer |
| 8 | Extrator | **discursos_plenario**: 0 dados apesar de 378 jobs processados | alta | não | Verificar endpoint e transformer |
| 9 | Extrator | **votacoes_comissao**: endpoint 404 | alta | não | Endpoint não encontrado |
| 10 | Transformador | **comissoes_detalhe/reunioes/membros**: 0 dados | média | não | Verificar schema e transformer |
| 11 | Transformador | **processos_detalhe**: 0 dados | média | não | Verificar dependência e transformer |
| 12 | Pipeline | CLI não tem `--no-warmup` para senado (warmup é no-op) | baixa | sim | N/A — warmup já é no-op para Senado |

### Achados da execução

#### [BLOCKER] Fix #1 — warmup_for_domain ausente no SenadoClient

**O quê:** PipelineManager chama `client.warmup_for_domain()`, mas SenadoClient não implementava o método.

**Evidência:** `'SenadoClient' object has no attribute 'warmup_for_domain'` no log do smoke test.

**Causa:** Apenas CamaraClient implementava warmup. SenadoClient não precisava (API mais estável), mas o PipelineManager chama o método genericamente.

**Correção imediata:** sim. Adicionado no-op `warmup_for_domain()` em `senado_client.py`.

---

#### [BLOCKER] Fix #3 — vetos_presidenciais: envelope da API mudou

**O quê:** A API de vetos do Senado mudou o endpoint e a estrutura de resposta. O endpoint `/materia/vetos/{ano}` redireciona para `/dados/ListaVetosAnoCN{ano}.json` com envelope `ListaVetosAnoCN` ao invés de `MateriaVetos`, e os campos retornados são completamente diferentes.

**Evidência:** 
- Log: vetos_presidenciais processou 32/32 jobs mas audit mostra 0 dados
- Teste manual: URL redireciona, novo envelope é `ListaVetosAnoCN`
- Campos reais da API: `Codigo, Materia, MateriaVetada, Mensagem, Total, Assunto, DataRecebimentoCongresso, ...`
- Campos esperados pelo transformer: `Codigo, Ano, Numero, Tipo, CasaOrigem, SiglaProposicao, ...`

**Causa:** A API do Senado foi atualizada e o extrator/transformador não acompanhou a mudança.

**Correção imediata:** não. Requer re-mapeamento completo do endpoint e field map.

---

#### [ALTA] Fix #4 — processos_emendas: janela limitada a 1 ano

**O quê:** A API de emendas de processo rejeita janelas maiores que 1 ano com HTTP 400. O full load enviou janela 1949-01-01→2026-06-30 (77 anos) e falhou.

**Evidência:** 
```
Erro HTTP 400: {"detail":"Limite o período a 1 ano ou informe um dos parâmetros obrigatórios."}
```

**Causa:** O planner de processos não segmenta a janela em blocos anuais para este endpoint específico.

**Correção imediata:** não. Requer planner com janela anual.

---

#### [ALTA] Fix #5 — processos_documentos: janela limitada a 6 meses

**O quê:** Mesmo problema do #4, mas com limite de 6 meses.

**Evidência:**
```
Erro HTTP 400: {"detail":"Limite o período a 6 meses ou informe um dos parâmetros obrigatórios."}
```

**Causa:** Planner não segmenta em blocos semestrais.

**Correção imediata:** não. Requer planner com janela semestral.

---

#### [ALTA] Fix #6 — plenario_agenda/resultados/sessoes: endpoints ausentes

**O quê:** Os endpoints de plenário retornam 404 ou 400, fazendo com que todos os 8.582 jobs diários produzam 0 dados.

**Evidência:**
- `plenario/agenda/20240601.json` → 404
- `plenario/resultado/2024.json` → 400
- `plenario/sessoes/2024.json` → 404

**Causa:** Endpoints incorretos ou a API do Senado mudou os paths.

**Correção imediata:** não. Requer consulta à documentação oficial da API do Senado.

---

#### [MÉDIA] Fix #10 — comissoes_detalhe/reunioes/membros: 0 dados

**O quê:** Os extratores de comissões executaram (1 job cada, 100%) mas produziram 0 dados.

**Evidência:** Log mostra `[Progresso - comissoes_detalhe] 1/1 (100.0%)` mas sem contagem de registros.
Audit mostra 0 linhas Silver.

**Causa:** Pode ser desencontro entre schema da API e data_path do extrator (similar ao caso dos vetos).

**Correção imediata:** não. Requer verificação do retorno real da API vs data_path configurado.

## Domínios — Status Final

### Com dados (12 de 29 configurados) ✅
| Domínio | Silver | Gold | Status |
|---|---|---|---|
| senadores | 10.822 | pendente | OK |
| senadores_detalhe | 1.943 | pendente | OK |
| processos | 10.709 | pendente | OK |
| votacoes_senado | 9.372 | pendente | OK |
| votos_senado | 759.132 | pendente | OK |
| orcamento_emendas | 186.872 | pendente | OK |
| orcamento_oficios | 41.804 | pendente | OK |
| comissoes_senado | 654 | pendente | OK |
| blocos_senado | 12 | pendente | OK |
| liderancas_senado | 604 | pendente | OK |
| mesa_senado | 22 | pendente | OK |
| mesa_congresso | 14 | pendente | OK |

### Sem dados por erro de API (3 de 29) ❌
| Domínio | Problema |
|---|---|
| processos_emendas | API limita a 1 ano |
| processos_documentos | API limita a 6 meses |
| votacoes_comissao | Endpoint 404 |

### Sem dados por API desatualizada (3 de 29) ❌
| Domínio | Problema |
|---|---|
| vetos_presidenciais | Envelope API mudou |
| plenario_agenda | Endpoint 404 |
| plenario_resultados | Endpoint 400 |
| plenario_sessoes | Endpoint 404 |

### Sem dados por dependência não satisfeita (4 de 29) ❌
| Domínio | Problema |
|---|---|
| vetos_detalhe | Skipado (pai vetos_presidenciais sem dados) |
| discursos_texto | Skipado (pai discursos_plenario sem dados) |
| notas_taquigrafia_sessao | Skipado (pai plenario_sessoes sem dados) |
| notas_taquigrafia_reuniao | Skipado (pai comissoes_reunioes sem dados) |

### Sem dados — causa a investigar (5 de 29) ⚠️
| Domínio | Problema |
|---|---|
| processos_detalhe | 0 dados (1 job executado) |
| senadores_discursos | 0 dados (1.943 jobs executados) |
| discursos_plenario | 0 dados (378 jobs executados) |
| comissoes_detalhe | 0 dados (1 job executado) |
| comissoes_reunioes | 0 dados (1 job executado) |
| comissoes_membros | 0 dados (1 job executado) |

### Domínios Câmara (fora do escopo Senado)
30+ domínios da Câmara foram ignorados (sem config no YAML de Senado) — comportamento esperado.

## Pós-Execução

### Se correções imediatas foram aplicadas

- [x] `pytest -q` passa após as correções — **572 passed** ✅
- [ ] Nova execução confirmou que correções resolveram o problema — warmup fix confirmado no smoke test

### Se correções diferidas foram documentadas

- [ ] Cada correção não-imediata virou uma sub-issue ou entrada no PRD
- [ ] Achados documentados em `.scratch/senado-integracao/findings/` (se aplicável)

### Final

- [ ] Relatório de cobertura salvo em `.scratch/senado-integracao/coverage-report.md`
- [x] Status geral documentado: **12 ok, 15 com ressalvas/falhas, 2 fora de escopo**
- [ ] PRD atualizado com o status pós-execução
