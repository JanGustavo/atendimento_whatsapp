# Plano futuro: banco operacional e primeiro acesso

**Decisão atual:** reconstruir o cadastro da FortGiro do zero. Não importar nem sincronizar a tabela antiga `funcionarios` do SQL Server. O sistema continua em SQLite até a escolha e implantação de um banco operacional definitivo.

## Cadastro de pessoas

O gestor cadastrará cada colaborador individualmente, com nome, e-mail de login, papel e setor. A aplicação deve impedir e-mails duplicados e manter auditoria de criação, alteração e desativação. Não usar CPF, matrícula ou data de nascimento como senha.

## Primeiro acesso por e-mail

Implementar um serviço de envio de e-mail antes de ativar o cadastro em produção. Ao criar a conta, gerar uma credencial aleatória individual e temporária, com validade curta e troca obrigatória no primeiro login. Preferir link de definição de senha de uso único: guardar só o hash do token, invalidá-lo após uso e permitir reenvio controlado. Se for exigido o envio literal de senha temporária, guardar só o hash da senha, exigir troca antes de acessar qualquer outra rota e nunca registrar a senha em logs ou relatórios. Confirmar o endereço de e-mail antes do envio; tratar falha de entrega sem deixar a conta acessível com uma credencial desconhecida pelo usuário.

Antes da entrega, testar expiração, tentativas excessivas, reenvio, revogação de sessão, conta desativada e recuperação de acesso. O cadastro atual em Equipe, no qual o gestor define a senha inicial, ainda não implementa esse fluxo.

## Escolha do banco

PostgreSQL e SQL Server são opções a avaliar; nenhuma foi escolhida. Comparar hospedagem, custo, operação, backup, restauração, suporte a índices e transações, driver SQLAlchemy async e equipe responsável. Manter o SQLite atual até a decisão. A adoção de outro banco deve começar por schema vazio e migrações testadas; se houver dados reais a preservar no momento da troca, planejar sua migração com backup, validação e rollback. Não criar dois bancos graváveis concorrentes.

Arquivos de mídia ficam em armazenamento privado; o banco guarda apenas a chave do arquivo. Definir retenção, controle de acesso e restauração junto com o novo banco.

## Etapas

1. Fechar campos, papéis e setores do cadastro manual.
2. Escolher banco e serviço de e-mail, sem adicionar dependências antes dessa decisão.
3. Implementar schema/migrações e serviço de primeiro acesso com testes de segurança.
4. Testar backup, restauração, login, isolamento de conversas, chatbot, chamados e envio Meta no novo ambiente.
5. Liberar o cadastro gradual de colaboradores, um a um.

Nenhuma importação do SQL Server ou rotina de e-mail foi implementada nesta etapa.
