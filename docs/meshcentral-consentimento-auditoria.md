# Requisitos de privacidade para acesso remoto

## Estado atual

O painel React exibe uma janela de consentimento quando o colaborador estiver
logado na seção **Meus chamados**. Ela mostra o supervisor solicitante, o
computador, o chamado e a descrição do problema. A decisão e seus autores ficam
registrados no banco. Expirações continuam sendo avaliadas nas chamadas da API.

**Este pop-up NÃO é um aviso do sistema operacional.** A janela só existe com
o painel aberto e não impede acesso por um MeshCentral configurado fora deste
sistema. O produto mantém acesso remoto real desabilitado, inclusive após uma
autorização no React. O atributo `sessao_remota_ativa` é falso neste estágio.

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
        "consentTimeout": 60,
        "autoAcceptOnTimeout": false,
        "autoAcceptIfNoUser": false
      }
    }
  }
}
```

Esses valores são referência **para configuração futura**, não estão aplicados
pelo Docker Compose deste repositório. Conferir compatibilidade e
comportamento com a versão instalada antes de usar em ambiente real.

## Auditoria atual vs. futura

A tabela `acessos_remotos` guarda solicitante, PC, chamado, horário do pedido
(`inicio_em`), resultado, expiração, decisão (`respondido_por_id`,
`respondido_em`), aprovação (`autorizado_por_id`, `autorizado_em`),
fim/encerramento do fluxo (`fim_em`, `encerrado_por_id`).
O motivo é a descrição vinculada ao chamado.

**Nenhum desses horários comprova uma sessão de desktop iniciada.** Campos
próprios de sessão real e confirmação de encerramento devem ser introduzidos
quando houver integração MeshCentral. Os logs atuais são registros no banco
operacional; ainda não são imutáveis nem equivalem a prova pericial.

## Privacidade e comunicação interna

Solicitar ciência dos funcionários sobre a finalidade de suporte, controles de
acesso, prazos de retenção e canais de contestação. Revisar as regras com o
responsável de TI/privacidade da organização e manter o tratamento proporcional
à finalidade profissional.
