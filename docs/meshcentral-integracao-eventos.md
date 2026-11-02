# Integração de auditoria real com MeshCentral

Este módulo faz **ingestão de eventos reais do relay MeshCentral**. A aplicação
não implementa outro agente de controle remoto e não instala o executável em
computadores automaticamente. Para operar, instale o MeshAgent oficial em cada
PC pela interface de administração do MeshCentral, em equipamentos autorizados.

## Fonte verificada e limites

- O código upstream `meshrelay.js` registra `etype=relay`,
  `action=relaylog`, `protocol=2`, `msgid=15` ao iniciar o relay desktop
  e `msgid=11` ao encerrá-lo. `msgArgs[0]` é o ID da sessão;
  `nodeid` e `userid` identificam dispositivo e operador.
- O upstream `meshcentral.js` adiciona `time` antes de distribuir e
  persistir o evento. Horários são interpretados como UTC.
- O upstream `meshctrl.js` usa WebSocket TLS em `/control.ashx`, com
  cabeçalho de autenticação `x-meshauth`; o comando `events` lista histórico
  e o canal recebe notificações `action=event`.
- A FortGiro usa TLS validado, conexão de leitura autenticada e recuperação
  dos últimos 2.000 eventos após reconectar. `mesh_user_id` e
  `mesh_node_id` precisam coincidir com os IDs completos retornados pelo
  servidor de MeshCentral, não com nomes exibidos.
- Uma sessão sem consentimento correlacionado continua sendo auditada, marcada
  **sem vínculo com autorização**. A conexão real pode ter ocorrido diretamente
  pelo MeshCentral, fora da FortGiro.

Fontes upstream:
- https://github.com/Ylianst/MeshCentral/blob/master/meshrelay.js
- https://github.com/Ylianst/MeshCentral/blob/master/meshcentral.js
- https://github.com/Ylianst/MeshCentral/blob/master/meshctrl.js

## Provisionamento (homologação)

1. Configure o servidor MeshCentral a partir do serviço opcional já existente
   em `compose.yaml`: `docker compose --profile remoto up -d meshcentral`.
   O perfil **não publica** a interface diretamente na Internet; o
   mapeamento é local (127.0.0.1:18088). Configure HTTPS confiável,
   DNS e tunnel/proxy dedicado de modo compatível com os agentes.

   Na instalação FortGiro, `mesh.jangustavo.me` usa uma rota publicada pelo
   Cloudflare Tunnel para `https://meshcentral:443`, com `Origin Server Name`
   igual a `mesh.jangustavo.me` e `CA Pool` em
   `/meshcentral-certs/root-cert-public.crt`. O Compose monta esse certificado
   público no `cloudflared` somente para leitura. A aplicação Cloudflare Access
   desse host reutiliza a política de e-mails permitidos do painel. **Esta
   proteção também bloqueia o MeshAgent**, que não faz login interativo no
   Access. Para agentes externos, configure `agentPort=444`,
   `agentAliasDNS=mesh-agent.jangustavo.me`, `agentAliasPort=443` e
   `agentPortTls=true` em `settings` do `meshcentral-data/config.json`.
   Publique somente `mesh-agent.jangustavo.me` no Tunnel apontando para
   `https://meshcentral:444`, com `Origin Server Name` igual a
   `mesh.jangustavo.me`, `CA Pool` em
   `/meshcentral-certs/root-cert-public.crt` e verificação TLS ativa.
   No domínio padrão (`domains[""]`) do `config.json`, configure também
   `certUrl="https://mesh-agent.jangustavo.me/"`. O MeshCentral precisa
   reconhecer o certificado público apresentado pela Cloudflare aos agentes;
   sem isso, registra `Agent bad web cert hash` e não mostra o dispositivo.
   Após reiniciar, confira no log `Loaded web certificate` e compare o hash
   SHA384 com `Agent reported web cert hash`. Mantenha a verificação de hash
   ativa. A Cloudflare pode trocar o certificado público; se os agentes
   perderem conexão após uma troca, confira esses hashes e reinicie o
   MeshCentral para recarregar `certUrl`.
   A porta 444 aceita apenas agentes; ela não oferece a interface de
   administração. Não crie bypass para `mesh.jangustavo.me`. A rota do
   agente precisa ser validada com um PC real antes de considerá-la pronta.
2. Na interface MeshCentral, crie grupo de dispositivos e instale o agente
   oficial a partir da opção de adicionar dispositivos, **com consentimento
   dos usuários envolvidos**. Gere o instalador somente depois de configurar
   o endereço de agente: instaladores antigos podem apontar para o host da
   interface protegido pelo Cloudflare Access. Confira que o nó está online
   e anote seu identificador completo `node/<dominio>/<id>`.
3. Configure no `meshcentral-data/config.json` do servidor as políticas
   obrigatórias de prompt e barra de privacidade. Use o exemplo oficial
   `sample-config-advanced.json` para o domínio da sua versão:
   `userConsentFlags.desktopprompt=true`,
   `userConsentFlags.desktopnotify=true`,
   `userConsentFlags.desktopprivacybar=true`, além de
   `consentMessages.autoAcceptOnTimeout=false` e
   `consentMessages.autoAcceptIfNoUser=false`.
   Reinicie o MeshCentral e valide em dois PCs. Não desabilite o prompt
   para ajustar a integração.
4. Crie usuário **dedicado de auditoria** no MeshCentral, com acesso só aos
   grupos necessários. Nunca compartilhe credenciais de administrador ou a
   chave mestra do servidor. Para o monitor histórico/stream, configure
   `MESHCENTRAL_AUDIT_USERNAME` e `MESHCENTRAL_AUDIT_PASSWORD` no
   `.env` (segredos nunca no repositório). Verifique que essa conta enxerga
   eventos de relay no ambiente de teste.
5. Configure:

   ```dotenv
   REMOTO_PROVIDER=meshcentral
   MESHCENTRAL_URL=https://mesh.seudominio.com
   MESHCENTRAL_EVENT_MONITOR=true
   MESHCENTRAL_AUDIT_USERNAME=conta-de-auditoria
   MESHCENTRAL_AUDIT_PASSWORD=senha-forte-secreta
   ```

   Garanta que o contêiner `app` consiga estabelecer WebSocket
   `wss://mesh.seudominio.com/control.ashx`, sem certificado inválido ou
   bloqueio de autenticação pelo proxy.
6. Use a interface do MeshCentral para obter o `nodeid` do agente e
   `userid` do técnico (ex.: `user//tecnico`). Vincule-os ao cadastro
   FortGiro usando as novas rotas abaixo, autenticado como gestor.

   ```text
   POST /api/computadores/{id}/mesh-node
        mesh_node_id=node//identificador
   POST /api/gestor/usuarios/{id}/meshcentral
        mesh_user_id=user//tecnico
   ```

   As rotas recebem formulário urlencoded e exigem autenticação/Origin
   corretos. Na abertura de PC novo, `mesh_node_id` também pode ser
   informado no formulário do gestor.
7. Reinicie o serviço da FortGiro e valide no painel:
   `GET /api/chamados/sessoes-remotas` (gestor/supervisor),
   `GET /api/meus-sessoes-remotas` (colaborador dono do PC).
   Uma sessão que já ocorreu e ainda está dentro da janela dos 2.000
   eventos mais recentes será recuperada no banco.

## Auditoria e correlação

`sessoes_meshcentral` possui ID do relay, computador, operador MeshCentral,
horário de início e término observado, estado e consentimento relacionado
(opcional). A correlação só ocorre se:

- o nó for idêntico ao `mesh_node_id` cadastrado;
- o `userid` for igual ao `mesh_user_id` de um técnico ativo;
- esse técnico for o solicitante do pedido para o PC;
- o relay iniciar durante os cinco minutos de validade do pedido. Ao observar
  o início, o pedido muda para `aceito`; ao observar o fim, muda para
  `encerrado`. Autorizações antigas do painel continuam correlacionáveis por
  até 30 minutos após o aceite.

Eventos duplicados são idempotentes. Um evento de fim recebido antes do
início deixa registro encerrado e não é reaberto durante replay. O estado
`ativa` significa que foi observado início sem fim correspondente;
**não é uma consulta instantânea ao agente**. Com falha ou interrupção do
monitor, o painel avisa que o estado pode estar desatualizado.

## Limitações de segurança que ainda bloqueiam produção

- O listener **não inicia** a sessão remota e **não encerra** conexões reais.
  Fechar autorização/chamado na FortGiro continua sem revogar uma conexão
  MeshCentral já ativa. A barra de privacidade/consentimento **nativos do
  agente** são fundamentais.
- No modo MeshCentral, o React registra o pedido; o único aceite é o aviso
  nativo no computador. A conta MeshCentral ainda pode ter permissões próprias
  fora do fluxo de chamados. Restrinja essas contas no servidor.
- Neste ambiente, `MESHCENTRAL_EVENT_MONITOR=false` e a conta de auditoria não
  está configurada. O histórico FortGiro mostra pedidos, mas ainda não
  comprova automaticamente início ou fim das sessões reais.
- O monitor recebe somente os eventos visíveis à conta de auditoria. Não há
  prova de completude em uma queda prolongada ou após mais de 2.000 eventos.
  Uma conciliação periódica pelo estado de sessões do servidor deve ser
  desenvolvida antes de tratar o painel como detector infalível.
- O banner React aparece só se o painel estiver aberto; apenas a barra
  nativa do MeshCentral cobre o desktop fora do navegador.
- Os registros SQLite não são à prova de adulteração. Para auditoria
  empresarial, aplicar armazenamento externo append-only, rotação,
  retenção, controle de acesso e sincronização de relógios.
- Testar versão do servidor, autenticação do proxy, prompt, aceitação,
  recusa, interrupção por usuário e descontinuidade de rede em **dois PCs
  reais** antes de liberar a ferramenta.

O projeto não fornece download do agente por link genérico nem distribui
credenciais de acesso. Faça o provisionamento pela console MeshCentral
autenticada do servidor que você controla.
