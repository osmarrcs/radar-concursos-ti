# Testes e TDD

A suíte usa `unittest` e cobre:

- validação e relacionamentos dos JSONs;
- build do portal;
- importação do PDF;
- classificação de eventos;
- detecção de domínios oficiais;
- deduplicação de resultados;
- métricas do orquestrador;
- criação da linha de base dos alertas;
- execução repetida sem falsa novidade.

Execução:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Ciclo recomendado:

1. escrever teste que falha;
2. implementar o comportamento mínimo;
3. refatorar;
4. executar a suíte completa.
