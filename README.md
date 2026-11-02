# Atendimento WhatsApp — alpha

## Backup diário

`app/scripts/backup_dados.sh` copia o SQLite com `sqlite3.Connection.backup()`
(equivalente a `.backup`) e a pasta `/data/media` para
`../atendimento_whatsapp-backups`. Cada cópia é restaurada em pasta temporária
e conferida. O agendamento do host não pode ser confirmado pelo repositório. Configure-o uma vez no usuário que executa Docker com `crontab -e`, usando a entrada abaixo (substitua pelo caminho absoluto do clone):

```cron
0 2 * * * cd /caminho/absoluto/atendimento_whatsapp && ./app/scripts/backup_dados.sh >> ../atendimento_whatsapp-backups/cron.log 2>&1
```

Verifique com `crontab -l` e confirme a execução olhando o horário e o conteúdo mais recente em `../atendimento_whatsapp-backups/`. `BACKUP_KEEP_DAYS` controla a retenção; o padrão é 30 dias. Guarde também uma cópia em outro disco para proteção contra falha do disco principal. Se o computador ficar desligado às 02:00, cron pode não executar o trabalho perdido; use `anacron` ou um agendador equivalente se isso for necessário.

Após um backup bem-sucedido, a mesma rotina exclui conversas encerradas há
`RETENCAO_CONVERSAS_DIAS` (padrão: 180) e suas mensagens e mídias sem outras
referências. Conversas abertas não entram na exclusão. Para registros encerrados
antes da migração 0022, a contagem começa na data da migração, pois a data real
de encerramento não era armazenada. Backups anteriores ainda podem conter esses
dados por até 30 dias adicionais. O prazo foi escolhido para este projeto;
[a ANPD esclarece que a LGPD não fixa um prazo universal](https://www.gov.br/anpd/pt-br/acesso-a-informacao/perguntas-frequentes).

1. Copie `.env.example` para `.env` e troque `JWT_SECRET` e as três senhas `SEED_*_PASSWORD`. O banco do contêiner usa `/data/atendimento.db` no volume do Compose.
2. Suba o app em segundo plano: `docker compose up -d --build`. O serviço está configurado para reiniciar automaticamente após a inicialização do Docker, salvo se tiver sido parado explicitamente.
3. Em outro terminal, crie os usuários e setores: `docker compose exec app python -m app.scripts.seed`. O seed pode ser executado novamente sem duplicar os registros.
4. Abra [http://127.0.0.1:18087/login](http://127.0.0.1:18087/login). O login abre o painel React em `/painel`. Entre como `gestor@demo.local` com a senha definida em `SEED_GESTOR_PASSWORD`.

O React é compilado dentro do Docker e servido pelo próprio FastAPI; não há outro serviço de frontend. A demo inicia com `WHATSAPP_PROVIDER=simulador`. Para testar pela Cloud API oficial da Meta, crie um app na Meta for Developers com o número de teste, preencha `META_*` no `.env`, mude para `WHATSAPP_PROVIDER=meta` e reinicie com `docker compose up -d --build`. A configuração do webhook está em `NOTAS.md`.

Para apresentar sem exibir nomes, números, e-mails, fotos e textos reais, abra `/painel?apresentacao=1` ou use **Modo apresentação** no cabeçalho. O modo vale somente para a aba atual do navegador, substitui dados pessoais por exemplos na interface e bloqueia ações de gravação. Desative-o para voltar ao atendimento. Os registros reais continuam protegidos pelo login e pelas permissões normais; o modo de apresentação não é uma rotina de anonimização do banco.

Em **Minha conta → Papel de parede**, escolha ou recorte uma imagem com zoom e posição horizontal/vertical. A prévia mostra o escurecimento imediatamente; **Aplicar recorte** salva a versão WebP localmente no navegador. Nos dois chats, o menu da mensagem oferece **Copiar** para mensagens de texto.

Para receber mensagens da Meta, crie um Cloudflare Tunnel dedicado, copie seu token para `CLOUDFLARE_TUNNEL_TOKEN` no `.env` e inicie `docker compose --profile webhook up -d`. Na rota publicada do túnel, use o hostname desejado, o caminho `^/webhook/whatsapp$` e o serviço `http://app:8000`. Na Meta, configure `https://<hostname>/webhook/whatsapp`, o valor de `META_VERIFY_TOKEN` e assine o campo `messages`.

## Plano de migração SQL Server e funcionários

A migração está documentada em [`docs/migracao-sql-server-funcionarios.md`](docs/migracao-sql-server-funcionarios.md). Ela define a leitura da tabela `funcionarios`, o mapeamento para contas e setores, sincronização idempotente e provisionamento de credenciais temporárias sem usar CPF como senha. A aplicação continua em SQLite até uma etapa separada de migração, testes e aprovação operacional.

## Painel HTTPS

O painel está publicado em [https://painel.jangustavo.me](https://painel.jangustavo.me) por Cloudflare Tunnel, com **Protect with Access** e política **Allow** para `jeeh2200@gmail.com` e `jandersongustavo1@gmail.com`. Após a autenticação por código enviado ao e-mail, faça o login próprio do painel. A rota `wpp.jangustavo.me/webhook/whatsapp` continua separada e sem Access, pois a Meta precisa alcançá-la.

`PANEL_HTTPS_HOST=painel.jangustavo.me` no `.env` ativa cookie `Secure` e exige `Origin: https://painel.jangustavo.me` nos POSTs para `/api/`. O acesso HTTP local continua disponível para testes na rede.

O painel e o formulário de chamados usam React. A API JSON fica em `/api`; os testes rodam com `pytest tests/ -v` em um ambiente Python com as dependências de desenvolvimento instaladas.

## Lint e Formatação

- **Backend (Python):** Usando [Ruff](https://docs.astral.sh/ruff/) para lint e formatação.
  - Verificar: `ruff check app tests` e `ruff format --check app tests`
  - Formatar/corrigir: `ruff check --fix app tests` e `ruff format app tests`
- **Frontend (JavaScript/React):** Usando [Biome](https://biomejs.dev/) para lint e formatação.
  - Verificar: `npm run lint` (dentro de `frontend/`); o Biome habilita as regras de acessibilidade `useAltText` e `useValidAnchor`.
  - Formatar: `npm run format` (dentro de `frontend/`)

## Equipes e imagens internas

O gestor cria equipes internas em **Visão do gestor → Setores** e vincula usuários em **Equipe**. Um grupo de chat aparece automaticamente para os membros quando há pelo menos dois usuários ativos no setor. Mensagens do grupo e conversas individuais são privadas para seus participantes.

No chat interno, o navegador reduz imagens para até 1600 px e converte para WebP antes do envio. O servidor limita cada arquivo a 2 MB, guarda o WebP em `MEDIA_DIR` (use `/data/media` no Docker) e grava no SQLite somente uma chave. A imagem é entregue por rota autenticada, com autorização por conversa; não existe link público direto ao arquivo. Mantenha o volume `atendimento_data` nos backups junto com o banco.

## Automação e expediente

O gestor configura em **Gestão → Automação** os horários de cada dia da semana, datas fechadas e três textos do bot: fora do expediente, retorno e espera sem atendente. A configuração fica no SQLite e vale para mensagens novas e para o loop do timer. Antes do primeiro salvamento, os horários e textos do `.env` continuam sendo o padrão. O fuso é `EXPEDIENTE_FUSO` (padrão `America/Sao_Paulo`). Um dia marcado como fechado prevalece sobre o horário semanal; o bot responde a primeira mensagem fora do expediente e retoma a conversa quando o expediente abrir. Intervalos que atravessam a meia-noite não são aceitos no formulário atual.

## Chamados de computador

O gestor cadastra os PCs na aba **Chamados** do painel. A equipe abre pedidos em `/chamado?token=<CHAMADO_INSTALL_TOKEN>`; o token vem do `.env` e pode ser colocado em um favorito/atalho do navegador de cada PC. O seed também cria quatro PCs de demonstração, incluindo o PC do dono. Gestor e supervisor veem todos os pedidos, registram solicitações remotas e fecham o chamado com a solução.

As permissões são **gestor**, **supervisor** e **colaborador**. O setor/equipe é configurado separadamente por usuário; somente colaboradores da equipe Vendas participam da distribuição do bot. O painel registra por usuário quando uma conversa foi aberta. Para respostas enviadas pela Meta, mostra enviada, entregue ou lida quando a Cloud API informar o status; mensagens antigas sem ID de envio não recebem esse acompanhamento retroativo. Depois da migração de papéis, entre novamente no painel.

Por padrão, a porta continua restrita a `127.0.0.1`. Para abrir o formulário a partir de outros PCs, configure `APP_BIND_HOST` com o IP local da máquina que roda o Docker e use esse IP no atalho. No modo MeshCentral, o link do PC aparece no chamado após registrar o pedido e abre diretamente a aba Área de Trabalho do dispositivo; a conexão exige login no MeshCentral e consentimento no próprio computador.

## Teste no celular

Na mesma rede Wi-Fi, configure `APP_BIND_HOST=0.0.0.0` no `.env` e reinicie o app. Abra `http://<IP-do-computador>:18087/painel` no celular. Isso libera a porta na rede local; o túnel Cloudflare atual publica apenas o webhook da Meta, não o painel. Para uso pela Internet, o painel precisa de uma rota HTTPS separada e controle de acesso antes da publicação.


## Consentimento remoto pelo MeshCentral

Com `REMOTO_PROVIDER=meshcentral`, gestor ou supervisor clica **Solicitar acesso** no chamado de um PC da empresa. O pedido fica válido por cinco minutos e o link desse PC aparece apenas para a equipe de suporte. O colaborador vê o pedido em **Meus chamados** e pode cancelá-lo no painel antes da conexão. Ao iniciar o desktop no MeshCentral, o agente pede a única confirmação de consentimento no próprio computador. O PC de grupo `dono` permanece bloqueado para pedidos da administração.

O pedido registrado no painel não comprova que a sessão começou. Cancelar o pedido, fechar o chamado ou fechar a aba não desconecta uma sessão ativa; use a barra de privacidade do MeshCentral no computador. O atalho público de abertura de chamados não concede acesso remoto.

O aviso de encerramento no painel depende do monitor de eventos do MeshCentral. Com `MESHCENTRAL_EVENT_MONITOR=false`, o painel mostra que o monitor está desligado e não afirma que a sessão terminou. Ative-o somente após configurar uma conta de auditoria e o vínculo `mesh_user_id` dos técnicos, conforme a documentação da integração.

As regras de consentimento, barra de privacidade e auditoria estão em [Consentimento e auditoria MeshCentral](docs/meshcentral-consentimento-auditoria.md).


## Eventos reais do MeshCentral (integração opt-in)

Na aba **Chamados**, gestor e supervisor encontram **Abrir MeshCentral**. O botão
abre `MESHCENTRAL_URL` em outra aba e exige autenticação própria no MeshCentral;
ele não concede acesso a um PC. O link do computador aparece no histórico do
chamado durante um pedido válido. Neste ambiente, `REMOTO_PROVIDER=meshcentral`.
A interface `mesh.jangustavo.me` exige Cloudflare Access e depois login no MeshCentral.
Para acessar um PC fora da rede, tanto o operador quanto o agente instalado no
PC precisam alcançar o servidor pela Internet. A política Access interativa
atual protege a interface; os agentes usam a rota separada
`mesh-agent.jangustavo.me`. O PC cadastrado como grupo
`dono` continua bloqueado para solicitações da administração pelo painel.
Uso pessoal do próprio PC de casa exige conta e permissões específicas no
MeshCentral, sem passar por esse fluxo de chamado.

A FortGiro pode observar o WebSocket autenticado do MeshCentral para identificar
**início e fim reais do relay de desktop** (`relaylog`, protocolo 2), registrar
ID da sessão, computador, técnico e horários na tabela `sessoes_meshcentral`.
Sessões sem correspondência a um pedido ficam sinalizadas na auditoria.

A funcionalidade inicia **desativada** e só funciona com servidor MeshCentral
acessível, agente oficial instalado no PC, conta de auditoria e vínculos de
identidade configurados. O banner React reflete os últimos eventos observados,
podendo estar desatualizado em caso de desconexão do monitor.

Consulte [Instalação, vínculo de agentes e auditoria de eventos](docs/meshcentral-integracao-eventos.md)
para configurar o monitor. Neste ambiente, `MESHCENTRAL_EVENT_MONITOR=false` e
a conta de auditoria ainda não está configurada; o painel não confirma início
ou fim das sessões reais. A confirmação e a barra de privacidade nativas foram
conferidas na configuração do servidor e devem ser validadas em cada agente.
