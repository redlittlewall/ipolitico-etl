---
Status: needs-triage
Date: 2026-06-04
Area: ferramentas
Severity: medium
Source: qa-skill
---

# swagger_codegen: parametrizar templates por provider (Câmara ↔ Senado)

## Finding

O `tools/swagger_codegen.py` atual tem templates de geração de código
hardcoded para o ecossistema Câmara:

```python
# Hardcoded:
extractor: "ipolitico.extractors.camara.api.{domain}.{class_name}Extractor"
transformer: "ipolitico.transformers.camara.{domain}_transformer.Camara{class_name}Transformer"
DomainType = from ipolitico.core.constants.DomainType
```

Isso impede o uso da ferramenta para gerar stubs para a API do Senado
(Issue #13) ou qualquer outro provider futuro.

## Impact

- Bloqueia reúso da ferramenta na Fase 4 (Senado)
- Desenvolvedor teria que editar manualmente os stubs gerados para usar
  os caminhos e prefixos corretos do Senado
- Difícil manter duas versões da ferramenta

## Suggested fix

Adicionar `--provider {camara,senado}` à CLI que alterna entre templates
definidos num dict `PROVIDER_TEMPLATES`:

```python
PROVIDER_TEMPLATES = {
    "camara": ProviderTemplate(
        extractor_tpl="ipolitico.extractors.camara.api.{domain}.{class_name}Extractor",
        transformer_tpl="ipolitico.transformers.camara.{domain}_transformer.Camara{class_name}Transformer",
        domain_type_module="ipolitico.core.constants",
        domain_type_class="DomainType",
        sink_tpl="ipolitico.sinks.datalake_sink.DataLakeSink",
    ),
    "senado": ProviderTemplate(
        extractor_tpl="ipolitico.extractors.senado.{domain}.{class_name}Extractor",
        transformer_tpl="ipolitico.transformers.senado.{domain}_transformer.Senado{class_name}Transformer",
        domain_type_module="ipolitico.core.senado_constants",
        domain_type_class="SenadoDomainType",
        sink_tpl="ipolitico.sinks.datalake_sink.DataLakeSink",
    ),
}
```

As funções `generate_yaml_block`, `generate_domain_spec_stub` e
`generate_silver_schema_stub` receberiam o provider ativo e usariam
os templates correspondentes.

## Location

`src/ipolitico/tools/swagger_codegen.py` — funções `generate_*` e `main()`
