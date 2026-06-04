---
Status: ready-for-agent
Date: 2026-06-04
Area: ferramentas
Fase: 2
---

# Ferramenta swagger_codegen.py para geração de stubs de novas rotas

## Parent

[PRD: iPolitico ETL — Roadmap de Expansão](../PRD.md)

## What to build

Criar script em `tools/swagger_codegen.py` que lê o arquivo Swagger local
(`docs/camara_swagger.json`) e gera blocos de configuração e stubs de código
para rotas da API Câmara ainda não implementadas.

Funcionalidades:

1. **Scan**: percorre todas as `paths` do Swagger
2. **Match**: compara com `DomainType` existente e com o YAML para identificar
   rotas não mapeadas
3. **Generate**: para cada rota não mapeada, gera:
   - Bloco de configuração YAML (pronto para colar em `camara_pipeline.yaml`)
   - Stub de entrada em `DomainSpec` (constantes.py + domain_spec.py)
   - Stub de `SILVER_SCHEMA` (schemas.py)
   - Nome do extrator e transformer sugerido
4. **Output**: texto formatado para stdout (o desenvolvedor revisa e copia)

O script NÃO sobrescreve arquivos automaticamente — é um assistente, não um
gerador headless.

Testar com fixture do Swagger local.

## Acceptance criteria

- [ ] Script `tools/swagger_codegen.py` implementado
- [ ] Lê `docs/camara_swagger.json` e lista rotas não mapeadas
- [ ] Gera blocos de YAML, DomainSpec e SILVER_SCHEMA para cada rota faltante
- [ ] Teste unitário com fixture Swagger
- [ ] Documentação básica na CLI do script (`python -m tools.swagger_codegen --help`)

## Blocked by

None — independente das issues 04 e 05 (pode rodar em paralelo).
