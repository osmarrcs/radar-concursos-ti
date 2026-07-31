# Radar de Concursos de TI

Portal estático gratuito para consultar concursos na ordem:

1. selecionar o órgão;
2. escolher um dos três concursos mais recentes ou clicar em **Ver todos**;
3. selecionar o cargo/especialidade de TI daquele edital;
4. consultar vagas, validade, vacância, último chamado, nota e links oficiais.

O filtro de TI contempla segurança, governança, dados, banco de dados, infraestrutura, redes, suporte, desenvolvimento, sistemas, técnico de TI e laboratórios de informática/redes.

## Google Colab

O notebook já está na raiz e em `notebooks/Radar_Concursos_TI_Colab.ipynb`. Ele clona este repositório, permite cadastrar órgão com apenas nome e sigla, adicionar cargos, atualizar vacância separadamente, validar o portal e exportar um novo ZIP.

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/osmarrcs/radar-concursos-ti/blob/main/Radar_Concursos_TI_Colab.ipynb)

## Publicação sem Git

Extraia o ZIP e envie seu conteúdo pelo botão **Add file → Upload files** do repositório. Em **Settings → Pages**, selecione **GitHub Actions**.

## Dados

- `data/competitions.json`: base editável.
- `docs/data.json`: base publicada.
- `docs/index.html`: portal.
- `src/build_site.py`: valida e atualiza o portal.
- `src/test_examples.py`: testa IFPE e Dataprev.

A vacância é armazenada dentro do registro em um bloco próprio, com quantidade, data, fonte e código de coleta. Ela não é confundida com vagas do edital.
