# Plano futuro: SQL Server e provisionamento de contas a partir de `funcionarios`

**Status:** planejamento; não altera o backend atual, não conecta ao SQL Server e não cria usuários automaticamente. A aplicação continua em SQLite até uma etapa aprovada de migração.

## Objetivo e limites

A futura integração deverá receber/importar a tabela corporativa `funcionarios` e as tabelas necessárias ao atendimento, mantendo o vínculo do funcionário à conta de acesso FortGiro. O esquema real do SQL Server ainda precisa ser levantado com o responsável pelo banco: nomes de colunas, tipos, chave primária, regras de desligamento, setores e qualidade de e-mails. Não presumir que o ERP possui senha reutilizável ou que CPF pode virar senha.

A proposta separa três coisas:

1. **Cadastro funcional de origem** (`funcionarios`): nome, identificador estável, e-mail corporativo, situação e código do setor. A integração deve ler somente as colunas necessárias e não copiar CPF, documentos ou dados pessoais sem necessidade formal.
2. **Conta de aplicação** (`usuarios`): identidade de login, hash de senha, papel de acesso, status, presença e preferências. Cada conta terá vínculo imutável ao identificador do funcionário de origem. Papel de acesso não será inferido apenas pelo nome do setor; um gestor autorizado confirma o papel e o setor antes da ativação.
3. **Vínculos e auditoria**: o primeiro desenho atual suporta um setor interno por usuário (`usuarios.setor_interno_id`). Se o cadastro corporativo permitir múltiplos setores, criar uma tabela associativa `usuario_setores` com unicidade `(usuario_id, setor_id)` e definir um setor principal para distribuição. Registrar a origem e o horário de cada sincronização sem gravar cópias de campos sensíveis desnecessários.

## Tabelas a avaliar no SQL Server

A decisão final deve seguir o modelo oficial do banco corporativo, sem duplicar tabelas existentes. No mínimo, mapear:

| Entidade | Uso na aplicação | Chave/regra planejada |
|---|---|---|
| `funcionarios` (origem já existente) | Identidade e situação do colaborador | ID estável da origem; e-mail normalizado apenas como atributo, pois pode mudar |
| `setores` ou tabela equivalente (origem, se existir) | Departamento funcional | Código estável; mapear para setor interno da aplicação |
| `usuarios` | Login e autorização | ID próprio; `funcionario_id_externo` único e nullable para contas técnicas/serviço |
| `setores_internos` | Grupos de chat e organização da operação | ID próprio; vínculo explícito com código do setor de origem quando aplicável |
| `usuario_setores` (se múltiplos setores) | Associação usuário/setor | Chave composta única `(usuario_id, setor_id)` |
| `credenciais_temporarias` ou `tokens_redefinicao` | Primeiro acesso/redefinição | Token de uso único armazenado somente como hash, expiração e `usado_em` |
| `auditoria_provisionamento` | Rastrear criação, atualização, desativação e conflito | ID da origem, ação, data, resultado e operador/job; sem senha/token em log |

Também revisar chaves estrangeiras e índices para conversas, mensagens, chamados, computadores, acessos remotos, sessões MeshCentral, histórico de atribuições, leituras, grupos e mídias. A pasta de mídia deve permanecer em storage de arquivos; no banco guarda-se apenas a chave privada, sem URL pública.

## Importação e sincronização

1. Fazer inventário do SQL Server e aprovar as colunas permitidas, a finalidade e a retenção. A credencial técnica será somente leitura para a origem; segredos vão em secret manager/`.env` fora do Git.
2. Importar primeiro para staging com `funcionario_id_externo`, e-mail normalizado, setor, status e `sincronizado_em`. Rejeitar ou colocar em quarentena linhas sem ID, e-mail inválido, ID duplicado ou setor sem mapeamento.
3. Fazer *upsert* idempotente pelo ID externo. Mudança de nome/e-mail atualiza os dados descritivos, sem criar conta duplicada. E-mail em uso por outro ID externo vira conflito para revisão, nunca fusão automática de contas.
4. Funcionário desligado/inativo deixa a conta `ativo=false`, revoga sessões/cookies ao próximo mecanismo de versão de credenciais e impede novos logins. Não apagar conversas nem atribuir o mesmo login a outro funcionário. Reativação exige conferência do ID externo.
5. Não copiar senhas do SQL Server e não usar CPF, matrícula, data de nascimento ou senha padrão compartilhada como credencial inicial. Papéis `gestor`, `supervisor` e `colaborador` são aprovados explicitamente por um gestor.
6. Rodar sincronização em modo de prévia, apresentar contagens de criar/atualizar/desativar/conflitos e exigir aprovação antes do primeiro lote real. Guardar log de auditoria minimizado, sem telefone, senha temporária ou token.

## Primeiro acesso e senha temporária

Preferir um **link de primeiro acesso de uso único**, com token aleatório de alta entropia enviado por canal corporativo verificado. Armazenar somente o hash do token, validade curta (sugestão inicial: 24 horas), data de uso e limite de tentativas. No primeiro acesso, exigir definição de senha própria antes de abrir o painel e invalidar o token imediatamente.

Se a operação exigir literalmente senha temporária, gerar uma senha aleatória diferente por pessoa usando gerador criptograficamente seguro; guardar apenas seu hash no campo de senha atual e `forcar_troca_senha=true`, com prazo curto e bloqueio das demais rotas até a troca. Entregar fora do sistema por canal aprovado, exigir troca no primeiro login, expirar e invalidar após uso. Nunca registrar ou exportar a senha em CSV, logs, relatórios, banco de origem, commit ou mensagem em grupo. Não gerar senha a partir de CPF nem reutilizar uma senha entre funcionários.

Antes de habilitar esse fluxo, implementar e testar login, troca obrigatória, expiração, revogação de sessão, política de tentativas e recuperação segura. Hoje a tela de gestão aceita que um gestor escolha uma senha inicial; isso não equivale ao fluxo temporário descrito aqui.

## Caminho de migração do banco da aplicação

A conexão de leitura de `funcionarios` e a migração do banco operacional são etapas separadas. Para mover as tabelas da aplicação de SQLite para SQL Server:

1. Definir qual SQL Server/instância, versão, disponibilidade, backup, RPO/RTO, TLS e dono operacional.
2. Aprovar o driver SQLAlchemy/ODBC e instalar dependências apenas nessa bateria futura; hoje o `migrations/env.py` rejeita intencionalmente qualquer URL que não seja SQLite.
3. Fazer inventário de tipos, `CHECK`, índices parciais, autoincremento, datas/UTC, textos, unicidade e consultas. Reescrever migrações específicas: por exemplo, o índice único parcial de conversas abertas por número precisa de estratégia compatível com SQL Server (índice filtrado), e SQLAlchemy `sqlite_insert/on_conflict` deve ser trocado por operações portáveis ou `MERGE` cuidadosamente transacional.
4. Criar schema SQL Server vazio e aplicar migrações adaptadas em ambiente de teste. Não apontar produção para o novo banco sem ensaio de restauração e compatibilidade.
5. Fazer cópia consistente SQLite, exportar/importar por lotes preservando IDs e dependências, validar contagens, chaves órfãs, amostras e anexos; pausar escritas ou definir uma janela curta de corte.
6. Fazer *cutover* reversível: manter backup SQLite imutável, validar login, papéis, isolamento, chatbot, envio Meta, leitura, grupos, chamados e backup no SQL Server. Ter procedimento e prazo de rollback.
7. Só depois de uma janela de observação, decidir quando encerrar SQLite. O projeto não deve manter dois bancos graváveis como fontes concorrentes.

## Decisões pendentes antes de implementar

- DDL/colunas reais de `funcionarios`, chave estável e se e-mail corporativo é confiável/verificado.
- Quais campos do funcionário podem ser armazenados e por qual finalidade.
- Mapeamento oficial entre cargos/departamentos de origem, papéis e setores internos.
- Quem aprova novos gestores/supervisores e desligamentos.
- Se o SQL Server será fonte somente de funcionários ou também o banco operacional da aplicação.
- Prazo e canal de entrega do primeiro acesso; política de senha, MFA/SSO e revogação.
- Driver, versão, ambiente de homologação, plano de backup e janela de migração.

Nenhuma tabela, credencial, driver ou conexão SQL Server foi adicionada nesta etapa.
