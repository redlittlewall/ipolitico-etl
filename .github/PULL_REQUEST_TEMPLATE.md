## Descrição da Mudança
## Checklist de Engenharia
- [ ] **Testes:** Testes unitários/de integração foram implementados ou atualizados e estão passando.
- [ ] **Desacoplamento:** A arquitetura modular foi rigorosamente respeitada (ex: Extratores não instanciam Sinks).
- [ ] **Resiliência:** Tratamentos adequados para instabilidades de rede (retentativas, *timeouts*) foram aplicados, se pertinente.
- [ ] **Segurança:** Nenhuma credencial, URL sensível ou caminho de diretório local foi inserido diretamente no código (*hardcoded*).
- [ ] **Qualidade:** O código foi formatado e validado pelo linter (Ruff) via pre-commit localmente.
- [ ] **Governança:** A lógica adicionada mantém a neutralidade estrutural (apenas mapeamento de dados, sem algoritmos de juízo de valor).

## Tipo de Mudança
- [ ] 🐛 Correção de Bug (Fix)
- [ ] ✨ Nova Funcionalidade (Feat)
- [ ] ♻️ Refatoração (Refactor)
- [ ] 🧪 Adição/Ajuste de Testes (Test)
- [ ] 📚 Documentação (Docs)