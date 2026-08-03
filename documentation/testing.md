# TDD e testes

O ciclo recomendado é **Red → Green → Refactor**.

## Camadas

- Unitários: slug, inferência, validação, parser e normalização de URL.
- Integração: referências órgão/concurso/cargo, build e persistência.
- Amostra: fluxo IFPE e Dataprev, separado das regras estruturais.

## Executar

```bash
python -m unittest discover -s tests -v
```

O CI interrompe a publicação quando qualquer teste falha.
