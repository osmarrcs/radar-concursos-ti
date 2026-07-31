# Utilização no Google Colab

Arquivo: `notebooks/Radar_Concursos_TI_Colab.ipynb`

## Primeira carga do repositório vazio

1. Entre em https://colab.research.google.com/.
2. Escolha **Upload** e envie o arquivo `Radar_Concursos_TI_Colab.ipynb`.
3. Execute a célula de configuração.
4. Na segunda célula, selecione **Enviar ZIP do computador**.
5. Envie `radar-concursos-ti-github-com-colab.zip`.
6. Execute a validação e abra a visualização do portal.
7. Use o formulário para cadastrar ou atualizar concursos.
8. Execute a célula de geração do ZIP.
9. Extraia o ZIP baixado e envie seu conteúdo ao repositório pelo menu **Add file → Upload files**.

## Atualizações futuras

Depois que os arquivos estiverem no GitHub:

1. abra novamente o notebook;
2. mantenha o modo **Clonar do GitHub**;
3. edite os dados pelo formulário;
4. baixe o ZIP atualizado; ou
5. habilite a última célula para enviar diretamente ao GitHub com um Personal Access Token.

## Segurança do token

O token é solicitado por `getpass`, portanto não aparece no notebook. Use um token com acesso apenas ao repositório `osmarrcs/radar-concursos-ti` e permissão de escrita em **Contents**. Revogue o token quando não precisar mais dele.

## Publicação

Após o envio para a branch `main`, o workflow **Publicar portal** valida `data/competitions.json`, atualiza `docs/data.json` e publica o GitHub Pages.
