# Auditoria somente leitura — Atendimento FortGiro

**Repositório:** `JanGustavo/atendimento_whatsapp`  
**Snapshot auditado:** branch `main`, commit `569e125`  
**Data:** 02/11/2026  
**Escopo:** revisão estática de frontend, API, operação e documentação, conforme o prompt fornecido. Nenhum arquivo do repositório foi alterado; o clone permaneceu limpo (`git status --short` sem saída).

## A. Resumo

Estado geral: há cobertura de funcionalidades e documentação consideráveis, mas a validação dinâmica não foi possível neste ambiente sem instalar dependências.  
Pontos fortes: verificações de identidade/role em `deps.py`; deduplicação de eventos recebidos; backup com cópia consistente do SQLite e verificação por manifesto.  
Maiores riscos observados: foco de teclado removido em partes do gestor e do formulário público; diálogo de imagem sem gerenciamento/confinamento do foco; agendamento do backup não reproduzível a partir do repositório, embora o README afirme que existe.  
O risco do backup é de configuração/operação: não foi possível confirmar se há um crontab configurado no host de produção.

## B. Testes, build e lint

As verificações foram tentadas numa cópia descartável dos arquivos versionados para não gerar artefatos no clone auditado. Não foram instaladas dependências, conforme a instrução de auditoria somente leitura.

| Verificação | Resultado |
|---|---|
| Suíte Python (`python3 -m pytest -q`) | **Não executada:** `No module named pytest`. |
| Build frontend (`npm run build`) | **Não executado:** `vite: not found`; `frontend/node_modules` não existe. |
| Lint Biome (`npm run lint`) | **Não executado:** `biome: not found`; dependências do frontend ausentes. |
| Ruff (`ruff check .`) | **Não executado:** `ruff: command not found`. |

## C. Achados

Ordenados por severidade e, dentro da severidade, por esforço.

| ID | Tipo | Severidade | Esforço | Local | Problema | Correção sugerida |
|---|---|---:|:---:|---|---|---|
| A-01 | ACESSIBILIDADE | média | P | `frontend/src/styles.css:1119-1131, 1209-1219`; `frontend/src/App.jsx:1117-1132, 1177-1199, 1226-1255` | Os `select` de filtro/transferência e campos do cadastro no painel de gestão definem `outline: none`, mas os estilos de foco visível existentes não cobrem `.manager-page`. Ao navegar por teclado, esses controles podem não mostrar onde está o foco. **Reprodução:** percorra com Tab os filtros, transferência e formulário de equipe. | Adicionar `:focus-visible` para botões, campos e seletores do painel gestor, com contorno de contraste adequado e `outline-offset`. |
| A-02 | ACESSIBILIDADE | média | P | `frontend/src/styles.css:2107-2115`; `frontend/src/ChamadoPublico.jsx:75-105` | `select` e `textarea` do formulário público removem o contorno padrão com `outline: none` e não têm estilo substituto local. O foco pode ficar sem indicação visível ao navegar por teclado. **Reprodução:** abrir o formulário e percorrer os campos com Tab. | Definir `:focus-visible` (ou `:focus`) para esses campos, preservando um contorno claramente visível. |
| A-03 | INCONSISTÊNCIA | média | P | `README.md:3-10`; `app/scripts/backup_dados.sh:1-27` | O README afirma que o crontab executa o script às 02:00, mas o repositório contém apenas um script sob demanda e não fornece uma entrada ou procedimento para configurar o agendamento. Isso impede reproduzir a configuração seguindo somente as instruções versionadas. **Não verificado:** se existe crontab configurado externamente no host. | Documentar a entrada de crontab e os requisitos de caminho, variáveis e usuário; ou explicar que o agendamento é configurado fora do repositório e como validá-lo. |
| A-04 | ACESSIBILIDADE | média | M | `frontend/src/ModalImagem.jsx:14-31, 48-55` | O diálogo anuncia `aria-modal="true"` e fecha com Escape, mas não move o foco para dentro, não o confina enquanto aberto e não o restaura ao fechar. Assim, o teclado pode alcançar controles da tela que fica atrás do modal. **Reprodução:** abrir uma imagem e pressionar Tab repetidamente. | Ao abrir, focar o botão Fechar ou o contêiner; confinar Tab/Shift+Tab ao diálogo e devolver o foco ao elemento que o abriu. |
| A-05 | BUG | baixa | P | `app/api/gestor.py:99-134, 137-160`; `app/models.py:24-26` | As rotas de criação e edição aplicam `strip()` ao nome, mas não rejeitam o resultado vazio nem o limitam aos 120 caracteres definidos em `Usuario.nome`. SQLite não impõe o tamanho de `VARCHAR`, então um cliente direto à API pode gravar nome vazio ou maior que o limite esperado. **Reprodução:** enviar à rota de criação um formulário com `nome=   ` ou um nome com mais de 120 caracteres. | Validar após `strip()` que o nome não está vazio e tem até 120 caracteres, tanto na criação quanto na edição; retornar 422 antes de persistir. |
| A-06 | ACESSIBILIDADE | baixa | P | `frontend/biome.json:12-28`; `frontend/package.json:6-10` | A configuração desativa todas as regras recomendadas de acessibilidade do Biome (`a11y.recommended: false`), enquanto `npm run lint` executa `biome check src`. O lint, portanto, não cobre esse conjunto de verificações estáticas de acessibilidade. | Habilitar as regras recomendadas, ou selecionar explicitamente regras a11y após revisar exceções e falsos positivos. |

## D. Faça antes de entregar

1. **A-03 — Backup:** documentar/verificar a configuração do agendamento diário no ambiente de implantação. A documentação declara que o crontab existe; sua presença no host não foi verificada nesta auditoria.
2. **A-05 — Nome de usuário:** validar também no servidor o nome vazio e o limite de 120 caracteres para evitar registros inválidos por chamadas diretas à API.

## E. Melhorias rápidas

- **A-01 e A-02:** restaurar um indicador de foco visível nos controles do gestor e no formulário público.
- **A-06:** habilitar regras a11y escolhidas no Biome para que o lint ajude a detectar regressões acessíveis.
- **A-04** exige um pouco mais de trabalho que um ajuste CSS, mas é uma correção localizada no modal de imagem.

## F. Funcionalidades novas sugeridas

Estas são oportunidades, não correções de defeitos encontrados; não foram identificadas na busca estática por implementações existentes.

| FEATURE NOVA | Valor para o usuário | Esforço | Risco |
|---|---|:---:|---|
| Respostas rápidas configuráveis por setor | Reduz digitação repetitiva e padroniza respostas comuns de vendas, garantia e suporte. | M | Baixo; exigir revisão dos textos e inserção explícita pelo atendente para evitar envio acidental. |
| Exportação CSV de conversas/chamados filtrados para o gestor | Facilita acompanhamento operacional e preparação de relatórios sem copiar dados manualmente. | M | Médio; definir colunas, controle de acesso, escopo de filtros e cuidado com dados pessoais exportados. |
| Pesquisa curta de satisfação após encerramento do atendimento | Dá visibilidade à experiência do cliente e ajuda a detectar casos que precisam de retorno. | M | Médio; definir canal/janela de envio e consentimento, evitar múltiplas avaliações e limitar retenção/acesso às respostas. |
| Indicadores operacionais básicos no painel do gestor | Torna visíveis volume, tempo até primeira resposta e atendimentos por setor/vendedor. | M | Médio; explicitar definições e períodos para não comparar métricas inconsistentes nem incentivar comportamento inadequado. |

## G. Fase 2 e dívidas técnicas para depois

- A integração remota real do MeshCentral não foi tratada como defeito nesta auditoria: README/NOTAS descrevem o provider atual como simulado e esclarecem que autorização no painel ainda não abre nem encerra uma sessão real. A ativação operacional depende da integração e das políticas do agente/servidor.
- Itens explicitamente fora do escopo neste ciclo, conforme o prompt: edição/exclusão de mensagens, migração para SQL Server, importação do ERP, senhas temporárias e aplicativo desktop. Não foram propostos como correções.
- Executar a bateria de testes, build e lint em um ambiente de desenvolvimento preparado, antes da entrega, já que o ambiente desta auditoria não tinha as dependências disponíveis.

## H. O que não foi verificado e por quê

- Execução do aplicativo, testes automatizados, migrações, build e lint: as dependências necessárias não estavam instaladas; não foram instaladas por restrição expressa.
- Navegação real por browser e larguras de 1440, 1050, 850 e 390 px: não foi realizada. Responsividade foi considerada apenas por leitura estática, não como validação visual completa.
- Comportamento ponta a ponta de login, respostas, transferências, polling, estados de erro/sucesso, perda de rolagem ou texto digitado, chamados e cadastro de computadores.
- Chamadas reais à Meta, configuração de produção, persistência real no SQLite, execução/restauração operacional do backup, retenção em runtime e crontab externo.
- Integração efetiva com MeshCentral e política do agente remoto. O repositório documenta que o fluxo atual é parcial/simulado.
- Navegação com leitores de tela, testes automatizados de acessibilidade, contraste medido e comportamento em diferentes navegadores/temas.

**Limite desta revisão:** as conclusões de implementação são de análise estática do commit `569e125`; não equivalem a teste funcional ou auditoria de segurança completa.
