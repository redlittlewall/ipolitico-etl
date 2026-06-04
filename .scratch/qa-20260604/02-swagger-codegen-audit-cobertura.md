---
Status: resolved
Date: 2026-06-04
Area: ferramentas
Severity: low
Source: qa-skill
---

# swagger_codegen: modo `--audit` para relatório de cobertura e validação de schemas

## Finding

Atualmente o `swagger_codegen` só tem um modo de operação: encontrar
rotas não mapeadas. Com todas as 78 rotas da Câmara já mapeadas, a
ferramenta perde utilidade para o provider `camara` — não há mais o que
descobrir.

Porém, a ferramenta poderia evoluir para oferecer valor contínuo via
um modo `--audit`:

1. **Relatório de cobertura**: Para cada rota Swagger, mostrar qual
   DomainType mapeia, qual extrator/transformer é usado, se tem testes
2. **Validação de schemas**: Comparar as `properties` definidas no
   Swagger para cada rota com as colunas do `SILVER_SCHEMAS`
   correspondente — detectar colunas faltantes, tipos divergentes,
   campos novos não mapeados
3. **Detecção de drift**: Após atualizar `docs/camara_swagger.json`,
   apontar endpoints existentes que tiveram o schema de resposta alterado

## Impact

- A ferramenta atualmente só serve para "primeiro contato" com uma nova API
- Não ajuda na manutenção contínua contra mudanças na API da Câmara
- Perde a oportunidade de validar automaticamente os contracts de dados
  (SILVER_SCHEMAS vs Swagger real)

## Suggested fix

Adicionar flag `--audit` que, em vez de gerar stubs, produz um relatório
tabular:

```
Rota                  DomainType          Coberto?   Schema OK?
/deputados            deputados           ✅         ✅
/deputados/{id}       deputados_detalhe   ✅         ⚠ campos extras: 'ultimoStatus'
/blocos/{id}/partidos blocos_partidos     ✅         ❌ coluna 'sigla' ausente no Silver
```

A validação de schema exigiria parser das `properties` do Swagger para
extrair nomes e tipos das colunas de resposta.

## Location

`src/ipolitico/tools/swagger_codegen.py` — nova função `audit_coverage()`
