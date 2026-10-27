# Atendimento WhatsApp — alpha

1. Copie `.env.example` para `.env` e troque `JWT_SECRET` e as três senhas `SEED_*_PASSWORD`. O banco do contêiner usa `/data/atendimento.db` no volume do Compose.
2. Suba o app: `docker compose up --build`.
3. Em outro terminal, crie os usuários e setores: `docker compose exec app python -m app.scripts.seed`. O seed pode ser executado novamente sem duplicar os registros.
4. Abra [http://127.0.0.1:18087/login](http://127.0.0.1:18087/login). O login abre o novo painel React em `/painel`. Entre como `gestor@demo.local` com a senha definida em `SEED_GESTOR_PASSWORD`. O simulador fica na navegação do painel.

O React é compilado dentro do Docker e servido pelo próprio FastAPI; não há outro serviço de frontend. Para WhatsApp real, configure as variáveis `EVOLUTION_*` no `.env`, mude `WHATSAPP_PROVIDER=evolution` e suba `docker compose --profile evolution up --build`. A instância e o webhook precisam ser criados/pareados conforme `NOTAS.md`.

## Chamados de computador

O gestor cadastra os PCs na aba **Chamados** do painel. A equipe abre pedidos em `/chamado?token=<CHAMADO_INSTALL_TOKEN>`; o token vem do `.env` e pode ser colocado em um favorito/atalho do navegador de cada PC. O seed também cria quatro PCs de demonstração, incluindo o PC do dono. Gestor e responsável veem todos os pedidos, registram uma solicitação remota **simulada** e fecham o chamado com a solução.

Por padrão, a porta continua restrita a `127.0.0.1`. Para abrir o formulário a partir de outros PCs, configure `APP_BIND_HOST` com o IP local da máquina que roda o Docker e use esse IP no atalho. O acesso remoto real via MeshCentral ainda não está conectado.
