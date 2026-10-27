# Notas do alpha

- O projeto é criado em `Concursos/atendimento_whatsapp` para não alterar o KanbanDoro.
- O simulador oferece três números fictícios fixos e usa `receber_mensagem`, que também será a entrada do webhook no M3.
- O gestor pode responder a qualquer conversa; vendedor e responsável só podem responder à própria. A primeira resposta enviada pelo vendedor atribuído cancela o timer.
- `online` é um estado explícito do vendedor, inicialmente verdadeiro; o gestor pode alterá-lo. Conversa ativa é a que tem `status=aberta`.
- Transferências e atribuições usam `UPDATE` condicional pelo estado e responsável atual. O histórico registra toda atribuição, inclusive a inicial.
- O login usa formulário HTML simples e cookie JWT HttpOnly. As bibliotecas `python-jose`, `passlib` e `bcrypt` vêm estritamente do hash/JWT reaproveitado de `auth_service.py`.
- Os quatro setores mantêm as opções 1–4 do fluxo especificado. O gestor pode editar seus nomes e responsáveis; o menu enviado pelo serviço usa os nomes do banco.
- O timer considera Vendas pela ordem do setor, não pelo ID. Sem outro vendedor online no vencimento, a conversa fica com o vendedor atual e o loop tenta novamente a cada 5 s.
- Após uma transferência automática, começa um novo prazo para a primeira resposta do novo vendedor. O limite de 150 s vale para cada atribuição.
- O M3a usa um único processo Uvicorn para que exista apenas um loop de timer. O SQLite fica no volume `atendimento_data` em `/data/atendimento.db`; a porta publicada é `127.0.0.1:18087` (a porta interna permanece 8000).
- `TIMER_ESPERA_SEGUNDOS`, `TIMER_AVISO_SEGUNDOS`, `TIMER_MAXIMO_SEGUNDOS` e `WHATSAPP_PROVIDER` são lidos pelo `Settings` do `.env`. O provider pode ser `simulador` ou `evolution`; os números fictícios do simulador permanecem locais em ambos os modos.
- Evolution API v2.3.7 usa PostgreSQL e Redis no perfil opcional `evolution` do Compose. A API não é publicada na máquina; configure e pareie a instância na rede do Compose.
- Configure o webhook por instância em `POST http://evolution:8080/webhook/set/fortgiro` com header `apikey: <EVOLUTION_API_KEY>` e JSON `{"webhook":{"enabled":true,"url":"http://app:8000/webhook/whatsapp","headers":{"X-Webhook-Secret":"<EVOLUTION_WEBHOOK_SECRET>"},"events":["MESSAGES_UPSERT"],"byEvents":false}}`. Substitua `fortgiro` se mudar `EVOLUTION_INSTANCIA`. O segredo via header é obrigatório; o webhook global não tem esse header customizado.
- Em `APP_LOG_LEVEL=DEBUG`, o primeiro payload recebido pelo webhook aparece apenas no log padrão do contêiner. Pode conter número e texto de cliente; não ative debug em produção.
- O estado no cartão do gestor vem de `/instance/connectionState/{instancia}`. `open` aparece como conectado; os demais estados ou falha de rede aparecem como desconectado.
- Falhas de envio ficam no histórico como `falhou`. O operador pode reenviar o texto pelo painel; o timer só é cancelado após sucesso da primeira resposta humana.
- O aviso de transferência manual usa `AVISO_TRANSFERENCIA_ATIVO` e `AVISO_TRANSFERENCIA_TEXTO` no `.env`; `{nome}` é substituído pelo atendente de destino.
- O painel principal agora é React em `/painel`, com uma única compilação estática no Docker. As rotas HTML anteriores continuam disponíveis como apoio aos testes e às mutações existentes; o React usa leituras JSON em `/api` e as rotas POST já protegidas pelo servidor.
- A foto da fachada inspirou as cores grafite e dourado e um símbolo vetorial simples. Para reproduzir exatamente o desenho original, será preciso um arquivo de marca em boa resolução ou vetorial.

## Chamados e acesso remoto

- O papel `responsavel` representa o supervisor de suporte; `gestor` representa o ADM. Ambos veem todos os chamados. Vendedores só podem abrir chamados pelo formulário com token; não veem a lista interna.
- `dono_id` liga o PC a um usuário cadastrado. `grupo=dono` impede **no servidor** solicitações de acesso remoto para aquele computador, tanto por gestor quanto por responsável. Ainda é possível abrir e fechar chamados desse PC sem acesso remoto.
- O `RemotoProvider` tem implementação simulada. Cada clique permitido em **Solicitar acesso** grava solicitante, PC, chamado, início, fim e resultado `simulado`. Não há conexão nem controle remoto nesta etapa; `mesh_node_id` já pode ser cadastrado para a futura integração.
- O fechamento exige um relato da solução em `chamados.solucao`. Cancelamento pelo usuário do PC e sessão MeshCentral real ficam para uma etapa posterior. Também não há atalho global Ctrl+Shift+H; nesta versão usa-se favorito/atalho do navegador.
- `CHAMADO_INSTALL_TOKEN` é um segredo compartilhado entre os atalhos. O formulário valida o token na abertura e no envio. A URL com token deve permanecer restrita à equipe; trocar o token invalida atalhos antigos. A resposta usa `Cache-Control: no-store`.
- `APP_BIND_HOST` mantém `127.0.0.1` na demonstração local. Para uso na rede interna, ajuste para o IP local do host Docker e atualize o link dos atalhos.
