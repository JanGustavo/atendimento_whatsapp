# Notas do alpha

- O projeto é criado em `Concursos/atendimento_whatsapp` para não alterar o KanbanDoro.
- O simulador oferece três números fictícios fixos e usa `receber_mensagem`, a mesma entrada de negócio do webhook da Meta.
- O gestor pode responder a qualquer conversa; colaborador e supervisor só podem responder à própria. A primeira resposta enviada pelo colaborador de Vendas atribuído cancela o timer.
- `online` é um estado explícito do usuário, inicialmente verdadeiro; o gestor pode alterá-lo. Conversa ativa é a que tem `status=aberta`.
- Transferências e atribuições usam `UPDATE` condicional pelo estado e responsável atual. O histórico registra toda atribuição, inclusive a inicial.
- O login do React usa `/api/auth/login` e cookie JWT HttpOnly. As bibliotecas `python-jose`, `passlib` e `bcrypt` vêm do hash/JWT reaproveitado de `auth_service.py`.
- Os quatro setores mantêm as opções 1–4 do fluxo especificado. O gestor pode editar seus nomes e responsáveis; o menu enviado pelo serviço usa os nomes do banco.
- O timer considera Vendas pela ordem do setor, não pelo ID. Sem outro vendedor online no vencimento, a conversa fica com o vendedor atual e o loop tenta novamente a cada 5 s.
- Após uma transferência automática, começa um novo prazo para a primeira resposta do novo vendedor. O limite de 150 s vale para cada atribuição.
- O M3a usa um único processo Uvicorn para que exista apenas um loop de timer. O SQLite fica no volume `atendimento_data` em `/data/atendimento.db`; a porta publicada é `127.0.0.1:18087` (a porta interna permanece 8000).
- `TIMER_ESPERA_SEGUNDOS`, `TIMER_AVISO_SEGUNDOS`, `TIMER_MAXIMO_SEGUNDOS` e `WHATSAPP_PROVIDER` são lidos pelo `Settings` do `.env`. O provider pode ser `simulador` ou `meta`; os três números fictícios continuam locais em ambos os modos.
- A integração Meta usa a Cloud API diretamente; o Compose não precisa da Evolution, PostgreSQL ou Redis. Em Meta for Developers, obtenha o número de teste, `Phone Number ID`, token de acesso e App Secret. Informe a versão da Graph API exibida no painel em `META_GRAPH_VERSION`.
- O `MetaProvider` repõe o nono dígito no envio quando o `wa_id` de um celular brasileiro chega com 12 dígitos. O número original recebido continua na conversa para que as próximas mensagens entrem na mesma conversa.
- Configure o webhook no produto WhatsApp do app Meta: URL pública HTTPS `https://<dominio>/webhook/whatsapp`, Verify Token igual a `META_VERIFY_TOKEN` e inscrição no campo `messages`. O GET de verificação devolve `hub.challenge`; o POST exige `X-Hub-Signature-256` calculado com `META_APP_SECRET`.
- O Compose inclui o conector Cloudflare no perfil `webhook`. Seu token fica apenas em `CLOUDFLARE_TUNNEL_TOKEN` no `.env`; inicie com `docker compose --profile webhook up -d`. Crie no túnel uma rota publicada com `hostname: <dominio>`, caminho `^/webhook/whatsapp$` e serviço `http://app:8000`. O caminho é preservado pela Cloudflare. O painel permanece na porta local `127.0.0.1:18087`.
- Em `APP_LOG_LEVEL=DEBUG`, o primeiro payload Meta validado aparece apenas no log padrão do contêiner. Pode conter número e texto de cliente; não ative debug em produção.
- O log de acesso do Uvicorn fica desligado para não registrar `META_VERIFY_TOKEN` na URL de verificação enviada pela Meta.
- O cartão do gestor consulta a Graph API pelo `Phone Number ID`: `conectado` significa que as credenciais responderam, não garante entrega de mensagens. O simulador aparece como `simulado`.
- Falhas de envio ficam no histórico como `falhou`. O operador pode reenviar o texto pelo painel; o timer só é cancelado após sucesso da primeira resposta humana.
- O aviso de transferência manual usa `AVISO_TRANSFERENCIA_ATIVO` e `AVISO_TRANSFERENCIA_TEXTO` no `.env`; `{nome}` é substituído pelo atendente de destino.
- O painel e o formulário público `/chamado` usam React, compilado dentro do Docker e servido pelo FastAPI. Leituras e mutações estão em `/api`; as antigas rotas HTML, Jinja2 e HTMX foram removidas. O polling continua a cada 3 s.
- O painel usa a marca FortGiro fornecida pelo usuário e as cores grafite e dourado da fachada.

## Chamados e acesso remoto

- O papel `supervisor` representa o suporte; `gestor` representa o ADM. Ambos veem todos os chamados. Colaboradores veem apenas seus chamados e também podem abrir pedidos pelo formulário com token.
- `dono_id` liga o PC a um usuário cadastrado. `grupo=dono` impede **no servidor** solicitações de acesso remoto para aquele computador, tanto por gestor quanto por responsável. Ainda é possível abrir e fechar chamados desse PC sem acesso remoto.
- O `RemotoProvider` tem implementação simulada. Cada clique permitido em **Solicitar acesso** grava solicitante, PC, chamado, início, fim e resultado `simulado`. Não há conexão nem controle remoto nesta etapa; `mesh_node_id` já pode ser cadastrado para a futura integração.
- O fechamento exige um relato da solução em `chamados.solucao`. Cancelamento pelo usuário do PC e sessão MeshCentral real ficam para uma etapa posterior. Também não há atalho global Ctrl+Shift+H; nesta versão usa-se favorito/atalho do navegador.
- `CHAMADO_INSTALL_TOKEN` é um segredo compartilhado entre os atalhos. A API valida o token ao listar PCs e ao abrir o chamado. A URL com token deve permanecer restrita à equipe; trocar o token invalida atalhos antigos.
- `APP_BIND_HOST` mantém `127.0.0.1` na demonstração local. Para uso na rede interna, ajuste para o IP local do host Docker e atualize o link dos atalhos.
## Chat interno ilustrativo

O chat interno usa apenas o banco local, com mensagens entre dois usuários autenticados e atualização a cada 3 segundos. Os setores internos (Vendas, Estoque, Garantia e Administração) são separados dos quatro setores do bot. O gestor define o setor de cada usuário em Equipe. A árvore mostra todos os cadastrados, inclusive offline; contas inativas aparecem sem opção de envio. O indicador “online” ainda é o campo manual configurado pelo gestor; presença automática por sessão fica para a próxima etapa.

Cada usuário pode trocar a própria senha em Minha conta usando a senha atual. O gestor edita e-mail, setor e redefine senhas em Equipe. Integração com SQL Server, importação de usuários/CPF e geração de senhas temporárias dependem do esquema e acesso ao cadastro corporativo e ficam para uma etapa posterior. O CPF não deve ser usado diretamente como senha.
## Limite de mensagens do bot e expediente

Padrão: expediente diário de 07:00 a 18:30 no fuso America/Sao_Paulo; primeira espera de 90 s, aviso com prazo de 60 s e uma prorrogação de 60 s se o cliente responder 1. O máximo por atendente é 210 s. Há duas tentativas automáticas no total (atribuição original e uma transferência). Sem resposta, a conversa entra em standby e o bot para de enviar avisos; o atendente ainda pode responder. Todas as durações e mensagens ficam no .env.

Fora do expediente, conversas ainda sem primeira resposta humana recebem um único aviso. Mensagens seguintes ficam registradas sem nova resposta automática. Ao abrir o expediente, o loop envia uma mensagem de retorno com o menu uma vez e limpa a atribuição anterior para reiniciar a escolha. Conversas já atendidas por humano permanecem com o atendente. O horário é aplicado todos os dias nesta versão; dias da semana e feriados ainda não são configuráveis.
## Avisos na tela e simulador

O painel consulta `/api/eventos` a cada 3 s e mostra um aviso com prévia da mensagem. O status de leitura de conversas WhatsApp fica em `leituras_conversas`, por usuário, e é sincronizado entre dispositivos; a lista deriva seu contador do banco. O chat interno ainda usa contador local do navegador. Não são notificações nativas do Windows. A API filtra eventos pelo usuário autenticado e limita cada consulta a 100 mensagens.

A Meta devolve um ID para cada mensagem de saída; o painel guarda esse ID e processa os eventos `sent`, `delivered`, `read` e `failed` assinados no webhook. Estados atrasados não regridem uma mensagem já lida. O status `read` pode não ser enviado; ausência dele não comprova que o cliente não leu. Mensagens anteriores à migração não têm ID de saída e não podem receber status retroativo. Na migração, `vendedor` vira `colaborador` e `responsavel` vira `supervisor`; o setor interno permanece separado. Colaboradores do setor interno Vendas (ID 1 do seed) entram na distribuição de Vendas. Cookies antigos deixam de autenticar porque carregam o papel antigo; basta entrar novamente.

O simulador fica desativado e oculto por padrão. O gestor pode ativá-lo em Visão do gestor; quando desligado, as rotas de consulta e envio do simulador retornam 403. A integração da Meta continua independente desse controle.

Em 29/10/2026, a Graph API retornou HTTP 401, código 190/subcódigo 463 para o token configurado. Isso indica token expirado: o app não consegue entregar mensagens novas até atualizar `META_ACCESS_TOKEN` no `.env` e recriar o serviço. Falhas antigas ficam marcadas como `falhou`; não são reenviadas automaticamente para evitar duplicidade. O atendente pode clicar em **Reenviar** nas próprias mensagens humanas que falharam: o mesmo registro é atualizado, sem criar outra linha. Mensagens do bot que falharam não são reenviadas automaticamente. O cartão de status mostra `token expirado` e a tentativa de envio dá aviso específico.

Em 29/10/2026, o painel HTTPS foi publicado em `painel.jangustavo.me` pelo túnel `fortgiro-webhook`, com serviço `http://app:8000`, **Protect with Access** e AUD vinculado ao aplicativo Self-hosted `FortGiro · Painel`. A política Allow inclui somente `jeeh2200@gmail.com` e `jandersongustavo1@gmail.com`. O método One-time PIN foi adicionado e selecionado para esse aplicativo. Uma consulta anônima ao `/health` retornou 302 para o login Cloudflare Access; a entrada autenticada por código de e-mail ainda precisa ser conferida pelo titular da caixa postal. `PANEL_HTTPS_HOST` ativa cookie Secure e checagem de Origin nesse host; o HTTP local segue para teste. O Cloudflare Tunnel encerra TLS na borda e liga-se ao app pela rede interna do Compose. O webhook da Meta permanece no host separado `wpp.jangustavo.me`.

Para testar sem Internet, conecte computador e celular à mesma rede local (o hotspot do celular serve mesmo sem dados móveis), descubra o novo IP local do computador e abra `http://<IP>:18087/painel`. O chat interno usa apenas a rede local e o SQLite. O webhook e o envio pela Cloud API da Meta dependem de Internet; sem ela, mensagens reais de WhatsApp não chegam nem saem.
