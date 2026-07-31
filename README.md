# Radar de Concursos Públicos de TI

Portal HTML estático, gratuito e open source para acompanhar concursos exclusivamente da área de Tecnologia da Informação.

## Funcionalidades

- filtros por âmbito, estado, carreira, órgão e especialidade;
- separação entre Nordeste/capitais e concursos federais nacionais;
- carreiras como Tribunais, Ministérios Públicos, Empresas Públicas de TI, Controle, Educação e Executivo;
- exibição dos três concursos mais recentes por órgão;
- vagas imediatas, vacância, validade, total de nomeados e lotação;
- nota e classificação do último chamado;
- modalidade de concorrência e nível de confiança;
- índice de previsibilidade de 0 a 100;
- fontes oficiais vinculadas em cada registro;
- publicação gratuita pelo GitHub Pages;
- nenhuma dependência de banco, servidor ou API paga.

## Estrutura

```text
data/competitions.json        base principal editável
docs/index.html               página publicada
docs/assets/                  CSS e JavaScript
docs/data.json                cópia publicada da base
src/build_site.py             valida e prepara a publicação
.github/workflows/pages.yml   publicação automática
```

## Como cadastrar dados reais

Edite `data/competitions.json`. Cada objeto representa um concurso/cargo/localidade/modalidade. Não misture ampla concorrência, PcD e cotas no mesmo registro.

Campos mais importantes:

- `scope`: `regional`, `regional_federal` ou `national`;
- `career`: Tribunais, Ministérios Públicos, Empresas Públicas de TI etc.;
- `last_called_rank` e `last_called_score`;
- `current_vacancy`;
- `predictability_score`;
- `is_official`: use `true` somente após confirmar as fontes;
- `sources`: links oficiais de edital, resultado e nomeações.

Exemplo de fonte:

```json
"sources": [
  {"label": "Edital", "url": "https://..."},
  {"label": "Resultado final", "url": "https://..."},
  {"label": "Última nomeação", "url": "https://..."}
]
```

## Publicar sem Git instalado

1. Baixe e extraia o ZIP.
2. Abra o repositório no GitHub.
3. Clique em **Add file → Upload files**.
4. Arraste todos os arquivos e pastas extraídos, inclusive `.github`.
5. Clique em **Commit changes**.
6. Acesse **Settings → Pages** e selecione **GitHub Actions** em Source.
7. Abra **Actions → Publicar portal → Run workflow**.

A página ficará em:

```text
https://xxxxx.github.io/radar-concursos-ti/
```


## Atualização dos dados

Após editar `data/competitions.json`, execute:

```bash
python src/build_site.py
```

No GitHub, o workflow faz isso automaticamente em cada envio para a branch `main`.

## Observação sobre a demonstração

Os registros incluídos são fictícios e possuem `is_official: false`. Eles servem para demonstrar filtros e layout. Substitua-os progressivamente por dados oficiais.

## Licença

MIT.
