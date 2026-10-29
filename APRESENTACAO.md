# FortGiro · Atendimento e suporte (demo)

## O que funciona hoje

- **Atendimento:** painel web com login por papéis, conversas isoladas por atendente, gestão e transferência.
- **Bot:** menu de setores, escolha do vendedor ou distribuição pelo menos ocupado, aviso e transferência por tempo de espera.
- **Chamados:** formulário por computador, fila para gestor/supervisor, solução registrada e auditoria de acesso remoto **simulado**. O PC do dono é bloqueado para acesso remoto.
- **WhatsApp:** adaptador da Cloud API oficial da Meta implementado; o número de teste, credenciais e webhook público ainda precisam ser configurados. A demo usa o simulador.

## Stack

React (painel) · FastAPI (API e páginas) · SQLAlchemy async + SQLite (dados) · Alembic (migrações) · httpx (Meta Cloud API) · Docker Compose · pytest.

## Árvore resumida

```text
frontend/src/       painel React
app/api/            rotas de atendimento, chamados e webhook
app/services/       regras do bot, timer e acesso remoto
app/providers/     simulador e Meta Cloud API
app/models.py       usuários, conversas, computadores, chamados e auditoria
migrations/         evolução do banco
app/scripts/seed.py dados iniciais para a demo
tests/              testes das regras principais
compose.yaml        app com banco SQLite em volume
```

## Próximos passos

1. **WhatsApp real:** configurar o número de teste da Meta, credenciais e webhook HTTPS; validar o fluxo completo com mensagens de teste.
2. **Acesso remoto real:** conectar MeshCentral ao `RemotoProvider`; pedir consentimento do usuário do PC, permitir cancelamento e registrar início/fim reais.
3. **Uso nos PCs:** publicar o app na rede interna com segurança, instalar os atalhos de chamado e testar com a equipe.

**Roteiro de demo:** abrir chamado de um PC da empresa → ver na fila → solicitar acesso simulado → registrar a solução. Depois mostrar bot e distribuição no simulador WhatsApp.
