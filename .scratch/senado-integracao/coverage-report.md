# Relatório de Cobertura — Senado Full Load

> Data: 2026-06-30
> Execução: `--source senado --strategy full_load`
> Duração: **3.849s (~64 min)**

## Resumo

| Categoria | Qtde |
|---|---|
| Domínios configurados | 29 |
| Com dados Silver ✅ | 12 |
| Sem dados — erro API ❌ | 7 |
| Sem dados — investigar ⚠️ | 6 |
| Skipados (dependência) | 4 |

## Domínios por status

### Dados OK ✅

| Domínio | Silver | Gold | Amostra |
|---|---|---|---|
| senadores | 10.822 | — | 1.943 códigos únicos |
| senadores_detalhe | 1.943 | — | Nome, sexo, UF, data_nascimento |
| processos | 10.709 | — | id, ementa, autoria, situação |
| votacoes_senado | 9.372 | — | votacao_id, codigo_materia, resultado |
| votos_senado | 759.132 | — | codigo_parlamentar, voto, partido |
| orcamento_emendas | 186.872 | — | autor, emendas, ano |
| orcamento_oficios | 41.804 | — | id, nome, protocolo |
| comissoes_senado | 654 | — | codigo, sigla, nome, tipo |
| blocos_senado | 12 | — | codigo, nome, membros |
| liderancas_senado | 604 | — | parlamentar, cargo, bloco, partido |
| mesa_senado | 22 | — | colegiado, cargo, parlamentar |
| mesa_congresso | 14 | — | colegiado, cargo, parlamentar |

### Sem dados — investigação necessária ⚠️

| Domínio | Jobs executados | Causa provável |
|---|---|---|
| vetos_presidenciais | 32 (anos) | API mudou envelope para `ListaVetosAnoCN` |
| processos_emendas | 1 | API limita janela a 1 ano |
| processos_documentos | 1 | API limita janela a 6 meses |
| plenario_agenda | 8.582 (dias) | Endpoint 404 |
| plenario_resultados | 8.582 (dias) | Endpoint 400 |
| plenario_sessoes | 8.582 (dias) | Endpoint 404 |
| senadores_discursos | 1.943 (senadores) | Endpoint/transformer |
| discursos_plenario | 378 (meses) | Endpoint/transformer |
| processos_detalhe | 1 | Endpoint 404 |
| votacoes_comissao | 1 | Endpoint 404 |
| comissoes_detalhe | 1 | Transformer/endpoint |
| comissoes_reunioes | 1 | Transformer/endpoint |
| comissoes_membros | 1 | Transformer/endpoint |
| vetos_detalhe | skip | Pai sem dados |
| discursos_texto | skip | Pai sem dados |
| notas_taquigrafia_sessao | skip | Pai sem dados |
| notas_taquigrafia_reuniao | skip | Pai sem dados |

## Qualidade dos Dados (domínios com dados)

- ✅ Schemas Silver respeitados
- ✅ `captured_at` presente em todos os registros
- ✅ Chaves de negócio íntegras (codigo, id, codigo_parlamentar)
- ✅ Cobertura histórica desde 1949 (senadores) até 2026

## Correções Aplicadas

1. **warmup_for_domain**: no-op adicionado ao SenadoClient (compatibilidade com PipelineManager)

## Pendências

1. Re-mapear extratores de vetos_presidenciais (envelope API mudou)
2. Criar planners anuais para processos_emendas
3. Criar planners semestrais para processos_documentos
4. Corrigir endpoints de plenario_*, discursos_*, comissoes_*
5. Validar extratores/transformers de processos_detalhe e votacoes_comissao
6. Rodar Gold optimization (`--optimize`)
