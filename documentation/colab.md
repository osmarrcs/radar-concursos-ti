# Google Colab

O notebook da raiz é uma interface fina: ele chama funções do pacote Python, em vez de duplicar regras.

## Abrir

`https://colab.research.google.com/github/osmarrcs/radar-concursos-ti/blob/main/Radar_Concursos_TI_Colab.ipynb`

## Fluxo

1. Clonar o repositório e adicionar `src/` ao caminho do Python. Nenhuma biblioteca é instalada.
2. Cadastrar ou atualizar órgão.
3. Cadastrar concurso uma vez.
4. Cadastrar todos os cargos do edital.
5. Atualizar vacância separadamente.
6. Selecionar órgãos para alertas.
7. Rodar testes e gerar `dist/`.
8. Visualizar o portal.
9. Exportar ZIP limpo, sem `.git`, caches ou `dist/` antigo.

## Publicar sem Git local

Extraia o ZIP exportado e use **Add file → Upload files** no GitHub. Envie o conteúdo extraído, não o ZIP fechado.
