# Atendimento WhatsApp — alpha

## Backup diário

`app/scripts/backup_dados.sh` copia o SQLite com `sqlite3.Connection.backup()`
(equivalente a `.backup`) e a pasta `/data/media` para
`../atendimento_whatsapp-backups`. Cada cópia é restaurada em pasta temporária
e conferida. O crontab do usuário executa o script às 02:00, no horário de
São Paulo. `BACKUP_KEEP_DAYS` controla a retenção; o padrão é 30 dias. Guarde
também uma cópia em outro disco para proteção contra falha do disco principal.

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


## Consentimento remoto (em desenvolvimento)

Quando `REMOTO_PROVIDER=meshcentral`, a solicitação de suporte começa em `pendente` por 60 segundos. O colaborador autenticado, vinculado ao PC de grupo `empresa`, pode autorizar ou recusar na tela Meus chamados. Solicitações pendentes expiram ao consultar o painel ou tentar uma resposta; não existe tarefa de expiração em segundo plano. Depois de autorizada, a autorização permanece registrada até ser encerrada pelo colaborador ou pelo fechamento do chamado. Uma nova solicitação para o mesmo PC é bloqueada enquanto a anterior estiver pendente.

**Importante:** esta etapa registra o consentimento no aplicativo, mas ainda não estabelece, libera ou revoga sessões MeshCentral. Nenhuma URL remota é entregue pela API, inclusive para solicitações autorizadas. Não confundir o estado `autorizado` com uma sessão ativa. A etapa seguinte deverá conectar a API à política de consentimento e encerramento do MeshCentral/agent antes de disponibilizar controle remoto. O atalho compartilhado de abertura de chamados não concede permissão de acesso remoto.


As regras para pop-up no sistema operacional, barra de privacidade durante uma sessão real e auditoria completa estão descritas em [Consentimento e auditoria MeshCentral](docs/meshcentral-consentimento-auditoria.md). A janela atual de autorização é exibida apenas no painel React aberto; não substitui o consentimento nativo do agente.


## Eventos reais do MeshCentral (integração opt-in)

Na aba **Chamados**, gestor e supervisor encontram **Abrir MeshCentral**. O botão
abre `MESHCENTRAL_URL` em outra aba e exige autenticação própria no MeshCentral;
ele não concede acesso a um PC. No ambiente atual, `REMOTO_PROVIDER=simulado`,
então **Solicitar acesso** registra apenas uma simulação. A interface
`mesh.jangustavo.me` exige Cloudflare Access e depois login no MeshCentral.
Para acessar um PC fora da rede, tanto o operador quanto o agente instalado no
PC precisam alcançar o servidor pela Internet. A política Access interativa
atual protege a interface, mas impede o MeshAgent de se conectar; uma rota de
agente separada e validada ainda é necessária. O PC cadastrado como grupo
`dono` continua bloqueado para solicitações da administração pelo painel.
Uso pessoal do próprio PC de casa exige conta e permissões específicas no
MeshCentral, sem passar por esse fluxo de chamado.

A FortGiro pode observar o WebSocket autenticado do MeshCentral para identificar
**início e fim reais do relay de desktop** (`relaylog`, protocolo 2), registrar
ID da sessão, computador, técnico e horários na tabela `sessoes_meshcentral`.
Sessões sem correspondência a consentimento ficam sinalizadas na auditoria.

A funcionalidade inicia **desativada** e só funciona com servidor MeshCentral
acessível, agente oficial instalado no PC, conta de auditoria e vínculos de
identidade configurados. O banner React reflete os últimos eventos observados,
podendo estar desatualizado em caso de desconexão do monitor.

Consulte [Instalação, vínculo de agentes e auditoria de eventos](docs/meshcentral-integracao-eventos.md)
antes de ativar. **Ainda não há disparo nem encerramento de conexão real pela
FortGiro, nem enforcement do consentimento React no servidor MeshCentral.**
A confirmação de acesso nativa e a barra de privacidade devem ser configuradas
e verificadas no agente. Não exponha acesso remoto em produção sem essa etapa.
