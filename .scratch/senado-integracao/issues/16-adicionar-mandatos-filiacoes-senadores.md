---
Status: ready
Priority: P2
Type: feature
---

# Issue 16 — Adicionar Dados de Mandatos e Filiações de Senadores

## Parent

`.scratch/senado-integracao/PRD.md`

## What to build

Dois endpoints novos de alto valor que expandem o domínio `senadores_detalhe`:

- **`senador/{codigo}/mandatos`**: Histórico completo de mandatos parlamentares do senador (legislaturas, partido, UF, período)
- **`senador/{codigo}/filiacoes`**: Histórico de filiações partidárias (datas de filiação e desfiliação)

Estes dados permitem rastrear a carreira política de cada senador — quais partidos já passou, quantos mandatos exerceu, etc.

### Implementação

Pode ser:
- **Opção A**: Dois novos domínios (`senadores_mandatos`, `senadores_filiacoes`) com extratores, transformers e schemas próprios
- **Opção B**: Expandir o extrator/transformer de `senadores_detalhe` para incluir mandatos e filiações como sub-listas

Recomendação: **Opção A** (SRP — Single Responsibility), pois mandatos e filiações são listas independentes que mudam em frequências diferentes.

## Acceptance criteria

- [ ] Novos extratores para `senador/{codigo}/mandatos` e `senador/{codigo}/filiacoes`
- [ ] Transformers normalizam para snake_case Silver
- [ ] Schemas Silver definidos
- [ ] Mapeados no `senado_pipeline.yaml`
- [ ] `pytest -q` passando

## Blocked by

Issue 10 — depende do padrão de extrator/transformer consolidado
