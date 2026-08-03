# Radar de Concursos de TI

Portal e painel administrativo em nuvem para acompanhar concursos nacionais e dos estados de PE, PB, AL, RN, SE, CE e MA.

## O que esta versão faz de verdade

Há dois tipos de informação:

1. **Concurso estruturado** — possui edital, cargos, vagas e campos próprios. Fica em `data/contests.json` e `data/positions.json`.
2. **Descoberta automática** — publicação localizada na internet, ainda sem cargos estruturados. Fica em `data/discovered_contests.json` e aparece no portal com o link da fonte.

A pesquisa automática agora **persiste** os resultados. Ela não apenas mostra links temporariamente no Colab.

O processo diário:

```text
105 órgãos cadastrados
        ↓
fontes oficiais + GDELT + Querido Diário
        ↓
data/updates.json
        ↓
data/discovered_contests.json
        ↓
PDF oficial direto, quando reconhecido
        ↓
importação automática de todos os cargos compatíveis com o parser
        ↓
GitHub Pages e Telegram
```

Não é tecnicamente seguro inventar vacância, nota ou último convocado quando a fonte não traz esses dados em formato relacionável. Nesses casos, o sistema mantém os documentos encontrados e marca revisão necessária.

## Links

- Repositório: `https://github.com/osmarrcs/radar-concursos-ti`
- Portal: `https://osmarrcs.github.io/radar-concursos-ti/`
- Colab: `https://colab.research.google.com/github/osmarrcs/radar-concursos-ti/blob/main/Radar_Concursos_TI_Colab.ipynb`

## Primeira publicação

Envie todo o conteúdo do ZIP para a raiz do repositório, inclusive a pasta oculta `.github`.

A raiz precisa conter:

```text
.github/
data/
documentation/
documents/
src/
tests/
web/
README.md
Radar_Concursos_TI_Colab.ipynb
```

Em `Settings → Pages`, escolha **GitHub Actions**.

Depois execute manualmente uma vez:

```text
Actions → Sincronização automática da base → Run workflow
```

A partir daí a sincronização executará diariamente e poderá ser iniciada manualmente a qualquer momento.

## Colab

O Colab não executa nada no seu computador. O código roda em uma máquina virtual do Google.

1. Abra o link do Colab.
2. Execute a única célula.
3. Na primeira aba, escolha âmbito → carreira → órgão.
4. Clique em **Sincronizar todos os órgãos agora** para atualizar imediatamente.
5. Use **Salvar direto no GitHub** para publicar sem baixar ZIP.

Para o botão de publicação, crie no Colab o Secret:

```text
GH_TOKEN
```

Use um Fine-grained Personal Access Token limitado ao repositório, com `Contents: Read and write`.

## Automação no GitHub

### `sync.yml`

- pesquisa todos os órgãos diariamente;
- grava atualizações e descobertas;
- tenta importar PDFs oficiais diretos;
- executa testes;
- gera e publica o portal;
- salva métricas como artifact.

### `alerts.yml`

- monitora apenas os órgãos escolhidos pelo usuário;
- envia novidades e métricas ao Telegram;
- usa `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` nos Secrets do GitHub.

### `ci-pages.yml`

- executa os testes em alterações do código;
- gera e publica o portal.

## Organização dos dados

- `data/organs.json`: catálogo de órgãos e carreiras;
- `data/contests.json`: concursos confirmados/estruturados;
- `data/positions.json`: cargos e especialidades;
- `data/updates.json`: publicações coletadas automaticamente;
- `data/discovered_contests.json`: candidatos a concursos extraídos das publicações;
- `data/alert_config.json`: órgãos e regras do Telegram;
- `data/alert_state.json`: links já conhecidos pelo monitor.

## Limitações reais

A automação consegue descobrir publicações, persistir links, classificar eventos e importar alguns editais tabulares. Não existe uma API pública única que forneça, para todos os órgãos:

- três concursos históricos completos;
- vacância atual por cargo;
- nome do último convocado;
- nota correspondente;
- separação correta por localidade e modalidade.

Essas métricas dependem de documentos distintos. O sistema pesquisa e organiza as evidências; a extração automática só é aplicada quando o parser consegue relacionar os dados sem ambiguidade.

## Testes

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m radar_concursos.build
```

A versão inclui testes para garantir que uma publicação de um órgão sem concurso pré-carregado seja persistida como atualização e descoberta automática, sem duplicação em execuções posteriores.
