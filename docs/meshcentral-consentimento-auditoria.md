# Requisitos de privacidade para acesso remoto

## Estado atual

Com `REMOTO_PROVIDER=meshcentral`, o gestor ou supervisor registra um pedido no
chamado. O painel mostra a ele um link para o computador por cinco minutos. O
colaborador vê o pedido no painel, mas **não precisa aprová-lo no React**: ao
iniciar a conexão, o MeshCentral pede consentimento no próprio computador. A
solicitação e seu cancelamento ficam registrados em `acessos_remotos`.

O link temporário controla a interface FortGiro, não as permissões internas
do MeshCentral. Se o técnico já abriu a página do dispositivo, cancelar o
pedido no painel não encerra uma sessão. O colaborador deve usar a barra de
privacidade do agente para interromper uma conexão ativa.

## Proteções exigidas antes de habilitar MeshCentral real

1. Instalar agente oficial do MeshCentral nos equipamentos autorizados e
   vincular a identidade do agente ao equipamento (não a um favorito
   com token compartilhado).
2. Configurar o consentimento **no próprio MeshCentral/agente** para desktop,
   terminal e arquivos. Jamais aceitar automaticamente em caso de timeout ou
   ausência de usuário. O funcionário deve ter opção de recusar.
3. Exibir notificação do sistema operacional e barra de privacidade visível
   durante **toda a conexão real**. A barra deve ser acionada pelo evento
   de conexão real do agente, não pelo estado de consentimento no React.
4. Impedir conexões não supervisionadas por outros caminhos, inclusive contas
   de gestor que tenham permissões diretas no MeshCentral. Aplicar o princípio
   do menor privilégio e autenticação forte.
5. Receber do MeshCentral eventos confiáveis de **início e fim efetivos**
   da sessão, contendo ID de sessão, técnico, nó, horário e motivo/chamado.
   Reconciliar desconexões inesperadas; nunca presumir que fechar o chamado
   ou fechar a aba remota encerra a conexão efetiva sem confirmação do agente.
6. Persistir log auditável e resistente a alteração, com UTC, controle de
   retenção, acesso restrito e exportação para apuração. Separar os eventos
   'pedido', 'decisão', 'autorização encerrada' dos eventos de conexão efetiva.
7. Validar aviso, recusa, timeout, logout, desconexão, queda de rede,
   revogação e tentativas fora do expediente com dois computadores reais.

## Exemplo de configuração a avaliar em MeshCentral

O [exemplo avançado oficial](https://github.com/Ylianst/MeshCentral/blob/master/sample-config-advanced.json)
documenta `userConsentFlags` e a barra de privacidade. Adaptar ao
`config.json` do domínio da versão efetivamente instalada:

```json
{
  "domains": {
    "": {
      "userConsentFlags": {
        "desktopnotify": true,
        "desktopprompt": true,
        "desktopprivacybar": true,
        "terminalnotify": true,
        "terminalprompt": true,
        "filenotify": true,
        "fileprompt": true
      },
      "consentMessages": {
        "Title": "FortGiro - autorização de acesso remoto",
        "Desktop": "{0} solicita acesso à área de trabalho deste computador para atendimento. Autorizar?",
        "Terminal": "{0} solicita acesso ao terminal deste computador para atendimento. Autorizar?",
        "Files": "{0} solicita acesso aos arquivos deste computador para atendimento. Autorizar?",
        "consentTimeout": 60,
        "autoAcceptOnTimeout": false,
        "autoAcceptIfNoUser": false
      }
    }
  }
}
```

Em 02/11/2026, esses valores foram conferidos no `config.json` do MeshCentral
em execução. O arquivo fica no volume do MeshCentral e não é gerado pelo
Compose; uma instalação nova precisa configurá-los e validar o comportamento
com um computador real.

O aviso nativo aceita título e texto personalizados, mas seu desenho pertence
ao agente/sistema operacional. Os textos em português foram aplicados ao
servidor em 02/11/2026, mantendo as opções de aceite existentes. No painel
FortGiro, avisos destacados de início e fim dependem do monitor de eventos
conectado; `MESHCENTRAL_EVENT_MONITOR=false` ou a ausência de uma conta de
auditoria impedem confirmar esses eventos automaticamente.

## Auditoria atual vs. futura

A tabela `acessos_remotos` guarda solicitante, PC, chamado, horário do pedido
(`inicio_em`), resultado, expiração, decisão (`respondido_por_id`,
`respondido_em`), aprovação (`autorizado_por_id`, `autorizado_em`),
fim/encerramento do fluxo (`fim_em`, `encerrado_por_id`).
O motivo é a descrição vinculada ao chamado.

**O pedido pendente não comprova uma sessão de desktop iniciada.** A tabela
`sessoes_meshcentral` recebe eventos de início e fim somente quando o monitor
de eventos está configurado. Neste ambiente, `MESHCENTRAL_EVENT_MONITOR=false`;
o painel ainda não confirma o resultado da sessão real. Os registros SQLite
não são imutáveis nem equivalem a prova pericial.

## Privacidade e comunicação interna

Solicitar ciência dos funcionários sobre a finalidade de suporte, controles de
acesso, prazos de retenção e canais de contestação. Revisar as regras com o
responsável de TI/privacidade da organização e manter o tratamento proporcional
à finalidade profissional.
