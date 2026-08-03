# Testes e TDD

## Execução

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Cobertura

- integridade das referências órgão → concurso → cargo;
- hierarquia âmbito → carreira → órgão;
- três concursos mais recentes;
- editais em aberto;
- limite de dois cargos na pesquisa de métricas;
- busca geral local;
- pesquisa automática e deduplicação;
- importação de PDF;
- alertas e linha de base;
- build do GitHub Pages;
- notebook com uma única célula executável.

## Ciclo recomendado

1. escrever teste que falha;
2. implementar o mínimo;
3. refatorar mantendo os testes aprovados.
