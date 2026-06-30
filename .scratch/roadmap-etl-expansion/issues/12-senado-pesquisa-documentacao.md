---
Status: completed
Date: 2026-06-04
Area: senado
Fase: 4
Completed: 2026-06-30
---

# Pesquisar e documentar a API de Dados Abertos do Senado Federal

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Etapa prévia à implementação do adapter do Senado. Requer pesquisa manual para
mapear a API antes de qualquer codificação.

Atividades:

1. **Buscar documentação oficial da API de Dados Abertos do Senado Federal**
   (provável URL: `https://legis.senado.leg.br/dadosabertos/`)
2. **Baixar spec OpenAPI/Swagger** se disponível, salvar em
   `docs/senado_swagger.json`
3. **Analisar endpoints disponíveis** e mapear para domínios iPolitico:
   - Quais endpoints têm equivalente direto na Câmara (senadores ↔ deputados,
     proposicoes, votacoes, despesas)?
   - Quais endpoints são exclusivos do Senado?
4. **Documentar diferenças** de schema entre Câmara e Senado para domínios
   equivalentes
5. **Planejar a implementação**: quais domínios implementar primeiro, quais
   extratores/transformers podem ser reusados vs criados do zero

Output esperado:
- `docs/senado_swagger.json` (ou nota de indisponibilidade)
- Seção "Senado Federal" em `docs/api-comparison.md` com análise de endpoints
- Esboço dos primeiros 3-5 domínios a implementar

**Esta issue REQUER PESQUISA HUMANA** para buscar a documentação da API do
Senado. Um agente automatizado pode tentar buscar online, mas a validação
precisa ser feita por um humano.

## Acceptance criteria

- [ ] API do Senado localizada e documentação baixada
- [ ] `docs/senado_swagger.json` criado (ou nota explicando impossibilidade)
- [ ] Análise de endpoints publicada em `docs/api-comparison.md`
- [ ] Plano de implementação (primeiros domínios) documentado
- [ ] Issue 13 atualizada com o plano

## Blocked by

None — esta é a primeira etapa da Fase 4.
