# Radar de Concursos

Portal estático e painel administrativo no Google Colab para acompanhar concursos por órgão, edital e cargo.

## Fluxo do Colab

O notebook possui **uma única célula executável**. Ela baixa/atualiza o repositório e abre um painel com cinco opções independentes:

1. **Concurso na base** — órgão → três concursos mais recentes ou todos → cargo → detalhes.
2. **Buscar por órgão** — estado + sigla/nome; consulta fontes oficiais cadastradas, GDELT e Querido Diário quando aplicável.
3. **Adicionar por PDF** — anexa ou baixa um edital, reconhece todos os cargos e permite escolher quais importar.
4. **Alertas e métricas** — escolhe órgãos, provedores, período e palavras-chave.
5. **Gerar e exportar** — testa, gera, visualiza e baixa o ZIP.

Abrir no Colab:

`https://colab.research.google.com/github/osmarrcs/radar-concursos-ti/blob/main/Radar_Concursos_TI_Colab.ipynb`

## Busca automática

A busca usa provedores independentes:

- páginas HTML/RSS oficiais cadastradas no órgão;
- GDELT DOC 2.0 para descoberta de notícias;
- Querido Diário para órgãos municipais que possuam `territory_id` (código IBGE);
- PDF anexado ou localizado por URL.

Os resultados são classificados como edital, retificação, inscrição, resultado, homologação, convocação, nomeação, prorrogação, banca, comissão, autorização, vacância ou notícia.

Resultados oficiais podem atualizar automaticamente o status do concurso correspondente, preservando o link como evidência. A atualização aparece em `data/updates.json` e no portal.

## Alertas

O GitHub Actions faz uma varredura a cada seis horas e um resumo diário às 08:30 no fuso `America/Recife`.

Métricas enviadas:

- órgãos consultados;
- provedores executados e com sucesso;
- itens analisados;
- itens relevantes e oficiais;
- novidades;
- erros;
- duração.

Secrets necessários:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Dados

- `data/organs.json`: órgãos, domínios e fontes oficiais.
- `data/contests.json`: concursos.
- `data/positions.json`: cargos/especialidades.
- `data/updates.json`: atualizações descobertas.
- `data/alert_config.json`: seleção e regras dos alertas.
- `data/alert_state.json`: URLs já conhecidas.

## Testes e build

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m radar_concursos.build
```

O portal é gerado em `dist/` e publicado automaticamente no GitHub Pages.
