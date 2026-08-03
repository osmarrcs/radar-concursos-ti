# Radar de Concursos

Sistema gratuito para acompanhar concursos públicos por **âmbito, carreira, órgão, edital e cargo**, com portal no GitHub Pages, administração pelo Google Colab, pesquisa automática e alertas no Telegram.

## Links do projeto

Depois de enviar os arquivos para o GitHub e ativar o GitHub Pages:

- Repositório: `https://github.com/osmarrcs/radar-concursos-ti`
- Portal: `https://osmarrcs.github.io/radar-concursos-ti/`
- Abrir o painel no Colab: `https://colab.research.google.com/github/osmarrcs/radar-concursos-ti/blob/main/Radar_Concursos_TI_Colab.ipynb`

O endereço do portal só funciona depois da primeira publicação concluída pelo workflow **CI e GitHub Pages**. Se o endereço retornar 404, confirme em **Settings → Pages** que a fonte está definida como **GitHub Actions** e confira a execução mais recente na aba **Actions**.

---

## O que mudou nesta versão

O PDF voltou a ser apenas uma alternativa. O fluxo principal é automatizado e começa pelo órgão.

### Histórico

```text
Nacional
  → carreira
  → órgão
  → três concursos mais recentes ou todos
  → todos os cargos e especialidades do edital
  → vagas, validade, vacância, último convocado, nota e fontes

Estados
  → estado
  → carreira
  → órgão
  → três concursos mais recentes ou todos
  → todos os cargos e especialidades do edital
```

Exemplo nacional:

```text
Nacional
→ Carreiras Policiais e Inteligência
→ Polícia Federal, PRF ou ABIN
→ concursos mais recentes
→ cargo/especialidade
```

Exemplo estadual/regional:

```text
Estados
→ Pernambuco
→ Tribunais
→ TJPE
→ concursos mais recentes
→ cargo/especialidade
```

Se o órgão tiver menos de três concursos estruturados na base, a opção **Buscar automaticamente quando houver menos de 3 concursos** consulta as fontes online cadastradas. O botão **Atualizar histórico e publicações** permite repetir a pesquisa e salvar editais, resultados, homologações, convocações e nomeações encontrados como evidências do órgão.
A tela informa quantos concursos ainda faltam. Os achados online só viram um concurso estruturado depois que o edital e seus dados forem confirmados; o sistema não cria três registros fictícios apenas para preencher a lista.

### Editais em aberto

A aba **Editais em aberto** permite escolher um edital por vez e comparar no máximo dois cargos/especialidades. Ela apresenta três informações principais:

1. vacância do cargo;
2. nome e classificação do último convocado;
3. nota do último convocado.

Antes da escolha do edital, o botão **Buscar editais abertos agora** consulta as fontes dos órgãos filtrados. Um PDF encontrado pode ser encaminhado diretamente para a aba de importação.

Depois de escolher o edital e até dois cargos, a pesquisa automática procura documentos de vacância, resultado, convocação e nomeação. Quando o formato da fonte não permite extração confiável, o sistema mostra os links e o código `MANUAL_REVIEW_REQUIRED`, em vez de inventar um valor. Não existe uma seção manual obrigatória para “procurar vacância”: a busca é iniciada nessa própria aba.

### Pesquisa automática

A aba **Pesquisa automática** pode consultar:

- um órgão específico;
- todos os órgãos de uma carreira;
- vários órgãos cadastrados;
- âmbito nacional ou estados;
- um estado específico;
- qualquer termo livre.

Provedores disponíveis:

- páginas HTML, RSS ou Atom cadastradas no órgão;
- GDELT para descoberta de notícias;
- Querido Diário para órgãos municipais com código IBGE configurado.

### Adicionar por PDF

Use esta aba somente quando o edital ainda não estiver na base ou quando precisar corrigir uma importação incompleta.

O sistema:

1. recebe o PDF pelo computador ou por URL;
2. extrai os dados do edital;
3. verifica se o concurso parece já existir;
4. mostra todos os cargos reconhecidos;
5. permite importar os cargos selecionados.

O PDF não substitui a pesquisa de vacância, chamadas e notas, porque essas informações normalmente estão em documentos posteriores ao edital.

---

## Primeira instalação sem Git no computador

1. Baixe e extraia o ZIP do projeto.
2. Acesse `https://github.com/osmarrcs/radar-concursos-ti`.
3. Clique em **Add file → Upload files**.
4. Envie o conteúdo extraído, não o ZIP fechado.
5. Confirme o commit na branch `main`.
6. Acesse **Settings → Pages**.
7. Em **Source**, selecione **GitHub Actions**.
8. Acesse **Actions → CI e GitHub Pages** e confirme a execução.

Após a publicação, o portal ficará em:

`https://osmarrcs.github.io/radar-concursos-ti/`

---

## Como abrir no Google Colab

Você não cria um notebook novo. O notebook já está no repositório.

Abra:

`https://colab.research.google.com/github/osmarrcs/radar-concursos-ti/blob/main/Radar_Concursos_TI_Colab.ipynb`

Execute a única célula. Ela:

1. instala somente os pacotes ausentes;
2. clona ou atualiza o repositório;
3. carrega o código Python;
4. abre o painel administrativo.

O painel possui seis abas independentes:

1. **Histórico por órgão**;
2. **Editais em aberto**;
3. **Pesquisa automática**;
4. **Adicionar PDF faltante**;
5. **Alertas**;
6. **Gerar/Publicar**.

Não é necessário executar células em uma ordem específica.

### Como devolver as alterações ao GitHub

Na aba **Gerar/Publicar**:

1. clique em **Testar e gerar portal**;
2. clique em **Visualizar portal** para conferir;
3. clique em **Exportar ZIP**;
4. extraia o ZIP baixado;
5. envie o conteúdo ao repositório usando **Add file → Upload files**.

O notebook não faz `push` automático para evitar guardar token do GitHub no Colab.

---

## Telegram

### Configuração inicial

1. Crie um bot pelo `@BotFather` usando `/newbot`.
2. Abra o bot criado e envie `/start`.
3. Obtenha o `chat.id` com `getUpdates`.
4. No GitHub, acesse **Settings → Secrets and variables → Actions**.
5. Cadastre:
   - `TELEGRAM_BOT_TOKEN`;
   - `TELEGRAM_CHAT_ID`.
6. No Colab, abra a aba **Alertas** e selecione os órgãos desejados.

### Funcionamento automático

O workflow `alerts.yml` executa a pesquisa a cada seis horas. O Colab não precisa permanecer aberto.

Os alertas podem incluir:

- novo edital;
- retificação;
- inscrições;
- resultado;
- homologação;
- convocação;
- nomeação;
- prorrogação;
- vacância;
- métricas e erros da pesquisa.

A primeira execução cria uma linha de base e não envia notícias antigas.

---

## Estrutura de dados

- `data/organs.json`: órgãos, carreira, âmbito, estado, domínios e fontes oficiais;
- `data/contests.json`: editais e informações comuns ao concurso;
- `data/positions.json`: cargos e especialidades;
- `data/updates.json`: publicações encontradas pela pesquisa automática;
- `data/alert_config.json`: órgãos e regras dos alertas;
- `data/alert_state.json`: links já conhecidos pelo monitor.

A separação evita repetir validade e fontes do mesmo edital em todos os cargos.

---

## Arquitetura

```text
Google Colab
  → consulta e administração interativa
  → arquivos JSON do repositório

GitHub Actions
  → testes
  → pesquisa periódica
  → Telegram
  → geração do portal

GitHub Pages
  → consulta pública estática
```

O Colab é opcional para o funcionamento contínuo. O portal, a pesquisa agendada e os alertas continuam funcionando mesmo com o computador desligado.

---

## Testes e geração local

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m radar_concursos.build
```

O portal é gerado em `dist/`.

---

## Limitação importante

Não existe uma API pública única e padronizada que forneça, para todos os órgãos, vacância, último convocado e nota. O sistema automatiza a descoberta das fontes e preserva evidências, mas só preenche uma métrica quando ela já está estruturada ou pode ser extraída com segurança. Caso contrário, mostra o motivo e os links para conferência.

## Observação sobre o repositório atual

Ao substituir uma versão anterior pelo conteúdo deste ZIP, envie os arquivos para a **raiz** do repositório. Apague pastas antigas que contenham outra cópia inteira do projeto, como `radar-concursos-ti-github-v6/`, para evitar duas versões concorrentes.

## Onde encontrar cada função no Colab

| Objetivo | Aba | Ação |
|---|---|---|
| Ver os últimos concursos de um órgão | Histórico por órgão | Âmbito → estado, quando aplicável → carreira → órgão |
| Completar um histórico com menos de três concursos | Histórico por órgão | Deixe a busca automática marcada ou clique em **Atualizar histórico e publicações** |
| Procurar qualquer termo em toda a base já cadastrada | Histórico por órgão | Use **Busca geral na base** |
| Descobrir um edital aberto ainda não cadastrado | Editais em aberto | Aplique os filtros e clique em **Buscar editais abertos agora** |
| Ver todos os cargos de um edital | Histórico por órgão ou Editais em aberto | Selecione o concurso; nenhum cargo é filtrado |
| Pesquisar vacância, último convocado e nota | Editais em aberto | Selecione um edital, marque um ou dois cargos e clique em **Pesquisar vacância, chamadas e notas** |
| Fazer uma pesquisa livre na internet | Pesquisa automática | Escolha âmbito/estado/carreira/órgão, escreva o termo e pesquise |
| Importar um edital que não foi localizado | Adicionar PDF faltante | Envie o PDF ou informe a URL; esta é a alternativa final |
| Escolher órgãos dos alertas | Alertas | Marque os órgãos e salve |
| Publicar as alterações | Gerar/Publicar | Teste, visualize e exporte o ZIP |

### O que a automação faz e o que exige confirmação

A automação descobre e classifica links, mede a busca, identifica PDFs e preserva evidências. Ela também pode associar uma atualização ao concurso quando a correspondência é segura. Nome do último convocado, classificação, nota e vacância só são gravados como valores estruturados quando a fonte pode ser relacionada com segurança ao mesmo órgão, concurso, cargo, especialidade, localidade e modalidade. Nos demais casos, o sistema entrega os links e o motivo técnico para revisão, sem inventar dados.
