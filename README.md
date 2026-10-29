# Atendimento WhatsApp — alpha

1. Copie `.env.example` para `.env` e troque `JWT_SECRET` e as três senhas `SEED_*_PASSWORD`. O banco do contêiner usa `/data/atendimento.db` no volume do Compose.
2. Suba o app em segundo plano: `docker compose up -d --build`. O serviço está configurado para reiniciar automaticamente após a inicialização do Docker, salvo se tiver sido parado explicitamente.
3. Em outro terminal, crie os usuários e setores: `docker compose exec app python -m app.scripts.seed`. O seed pode ser executado novamente sem duplicar os registros.
4. Abra [http://127.0.0.1:18087/login](http://127.0.0.1:18087/login). O login abre o painel React em `/painel`. Entre como `gestor@demo.local` com a senha definida em `SEED_GESTOR_PASSWORD`.

O React é compilado dentro do Docker e servido pelo próprio FastAPI; não há outro serviço de frontend. A demo inicia com `WHATSAPP_PROVIDER=simulador`. Para testar pela Cloud API oficial da Meta, crie um app na Meta for Developers com o número de teste, preencha `META_*` no `.env`, mude para `WHATSAPP_PROVIDER=meta` e reinicie com `docker compose up -d --build`. A configuração do webhook está em `NOTAS.md`.

Para receber mensagens da Meta, crie um Cloudflare Tunnel dedicado, copie seu token para `CLOUDFLARE_TUNNEL_TOKEN` no `.env` e inicie `docker compose --profile webhook up -d`. Na rota publicada do túnel, use o hostname desejado, o caminho `^/webhook/whatsapp$` e o serviço `http://app:8000`. Na Meta, configure `https://<hostname>/webhook/whatsapp`, o valor de `META_VERIFY_TOKEN` e assine o campo `messages`.

## Painel HTTPS

O painel está publicado em [https://painel.jangustavo.me](https://painel.jangustavo.me) por Cloudflare Tunnel, com **Protect with Access** e política **Allow** para `jeeh2200@gmail.com` e `jandersongustavo1@gmail.com`. Após a autenticação por código enviado ao e-mail, faça o login próprio do painel. A rota `wpp.jangustavo.me/webhook/whatsapp` continua separada e sem Access, pois a Meta precisa alcançá-la.

`PANEL_HTTPS_HOST=painel.jangustavo.me` no `.env` ativa cookie `Secure` e exige `Origin: https://painel.jangustavo.me` nos POSTs para `/api/`. O acesso HTTP local continua disponível para testes na rede.

O painel e o formulário de chamados usam React. A API JSON fica em `/api`; os testes rodam com `pytest tests/ -v` em um ambiente Python com as dependências de desenvolvimento instaladas.

## Lint e Formatação

- **Backend (Python):** Usando [Ruff](https://docs.astral.sh/ruff/) para lint e formatação.
  - Verificar: `ruff check app tests` e `ruff format --check app tests`
  - Formatar/corrigir: `ruff check --fix app tests` e `ruff format app tests`
- **Frontend (JavaScript/React):** Usando [Biome](https://biomejs.dev/) para lint e formatação.
  - Verificar: `npm run lint` (dentro de `frontend/`)
  - Formatar: `npm run format` (dentro de `frontend/`)

## Equipes e imagens internas

O gestor cria equipes internas em **Visão do gestor → Setores** e vincula usuários em **Equipe**. Um grupo de chat aparece automaticamente para os membros quando há pelo menos dois usuários ativos no setor. Mensagens do grupo e conversas individuais são privadas para seus participantes.

No chat interno, o navegador reduz imagens para até 1600 px e converte para WebP antes do envio. O servidor limita cada arquivo a 2 MB, guarda o WebP em `MEDIA_DIR` (use `/data/media` no Docker) e grava no SQLite somente uma chave. A imagem é entregue por rota autenticada, com autorização por conversa; não existe link público direto ao arquivo. Mantenha o volume `atendimento_data` nos backups junto com o banco.

## Chamados de computador

O gestor cadastra os PCs na aba **Chamados** do painel. A equipe abre pedidos em `/chamado?token=<CHAMADO_INSTALL_TOKEN>`; o token vem do `.env` e pode ser colocado em um favorito/atalho do navegador de cada PC. O seed também cria quatro PCs de demonstração, incluindo o PC do dono. Gestor e supervisor veem todos os pedidos, registram uma solicitação remota **simulada** e fecham o chamado com a solução.

As permissões são **gestor**, **supervisor** e **colaborador**. O setor/equipe é configurado separadamente por usuário; somente colaboradores da equipe Vendas participam da distribuição do bot. O painel registra por usuário quando uma conversa foi aberta. Para respostas enviadas pela Meta, mostra enviada, entregue ou lida quando a Cloud API informar o status; mensagens antigas sem ID de envio não recebem esse acompanhamento retroativo. Depois da migração de papéis, entre novamente no painel.

Por padrão, a porta continua restrita a `127.0.0.1`. Para abrir o formulário a partir de outros PCs, configure `APP_BIND_HOST` com o IP local da máquina que roda o Docker e use esse IP no atalho. O acesso remoto real via MeshCentral ainda não está conectado.

## Teste no celular

Na mesma rede Wi-Fi, configure `APP_BIND_HOST=0.0.0.0` no `.env` e reinicie o app. Abra `http://<IP-do-computador>:18087/painel` no celular. Isso libera a porta na rede local; o túnel Cloudflare atual publica apenas o webhook da Meta, não o painel. Para uso pela Internet, o painel precisa de uma rota HTTPS separada e controle de acesso antes da publicação.
