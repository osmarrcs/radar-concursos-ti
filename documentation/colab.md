# Google Colab — painel único

Não crie outro notebook e não execute células em sequência.

1. Suba o projeto no GitHub.
2. Abra `Radar_Concursos_TI_Colab.ipynb` pelo botão **Open in Colab** ou pelo endereço do README.
3. Execute a única célula.
4. Use o menu exibido.

A célula executa `git pull` quando o projeto já existe na sessão ou `git clone` quando é a primeira abertura. Em seguida chama `radar_concursos.colab_app.launch()`.

## Opções

### Concurso na base

Consulta sem alterar dados. Mostra as atualizações automáticas mais recentes do órgão.

### Buscar por órgão

Informe estado e sigla/nome. Um órgão já existente usa nome, sigla, fontes e domínios cadastrados. Um nome ainda inexistente é usado temporariamente e só é salvo quando você decide persistir os resultados ou importar um PDF.

A busca mostra métricas, erros por provedor e resultados selecionáveis. PDFs localizados podem ser encaminhados diretamente para o importador.

### Adicionar por PDF

Aceita upload ou URL. Mostra todos os cargos reconhecidos, sem filtro por TI. Vagas são extraídas do edital; vacância e histórico de chamadas continuam separados.

### Alertas e métricas

Seleciona órgãos, provedores, período e palavras-chave. O botão de teste executa uma simulação sem Telegram e sem alterar o estado.

### Gerar e exportar

Executa testes, gera o portal, abre uma prévia e exporta um ZIP limpo.
