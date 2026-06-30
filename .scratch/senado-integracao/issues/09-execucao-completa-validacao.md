---
Status: pending
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

- [ ] Issues 02–08 todas marcadas como `completed`
- [ ] `configs/senado_pipeline.yaml` contém todos os 30 domínios mapeados
- [ ] `SILVER_SCHEMAS` definidos para todos os 30 domínios
- [ ] `pytest -q` passando (nenhum domínio quebra testes existentes)
- [ ] Conexão com internet (API do Senado pública)

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

- [ ] Tempo total de execução registrado
- [ ] Domínios mais lentos identificados (top 5 por tempo)
- [ ] Bottlenecks de concorrência (semáforo 5 ocioso ou sobrecarregado?)
- [ ] Domínios com janela mensal que poderiam ser paralelizados

### Qualidade dos Dados

- [ ] Schemas Silver respeitados (sem colunas extras inesperadas)
- [ ] Tipos de dados corretos (int vs string, datas como datetime)
- [ ] `captured_at` presente em todos os registros
- [ ] Valores nulos tratados adequadamente
- [ ] IDs únicos respeitados (unique_keys do DomainSpec)

### Resiliência

- [ ] Nenhum timeout não tratado
- [ ] Nenhum crash em falso 404
- [ ] Retry funcionou para falhas intermitentes
- [ ] PipelineManager recuperou de erros parciais (domínio falhou, outros continuaram)

### Pipeline

- [ ] Dependências entre domínios respeitadas (ex: processos_detalhe depois de processos)
- [ ] Watermark columns funcionando (incremental não reprocessa tudo)
- [ ] FederationOrchestrator executou Câmara e Senado sem conflito (se `--source all`)

## Registro de Correções e Achados

| # | Categoria | Descrição | Gravidade | Correção imediata? | Resolução |
|---|---|---|---|---|---|
|   |           |           |           |                    |           |

**Gravidade:** blocker / alta / média / baixa / melhoria
**Correção imediata:** sim / não

### Achados da execução

(Preencher durante a execução — cada achado vira uma linha na tabela acima)

**Template para cada achado:**
```markdown
#### [GRAVIDADE] Título do achado

**O quê:** descrição concisa do problema observado.

**Evidência:** log ou output que comprova.

**Causa:** análise da causa raiz.

**Correção imediata:** sim/não. Se sim, descrever o fix aplicado. Se não, documentar o que precisa ser feito.
```

## Pós-Execução

### Se correções imediatas foram aplicadas

- [ ] `pytest -q` passa após as correções
- [ ] Nova execução confirmou que correções resolveram o problema

### Se correções diferidas foram documentadas

- [ ] Cada correção não-imediata virou uma sub-issue ou entrada no PRD
- [ ] Achados documentados em `.scratch/senado-integracao/findings/` (se aplicável)

### Final

- [ ] Relatório de cobertura salvo em `.scratch/senado-integracao/coverage-report.md`
- [ ] Status geral documentado: quantos domínios ok, quantos com ressalvas, quantos falharam
- [ ] PRD atualizado com o status pós-execução
