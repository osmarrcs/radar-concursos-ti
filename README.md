# Radar de Concursos

Portal gratuito para organizar concursos por **órgão → concurso → cargo/especialidade**, acompanhar validade, vagas, último chamado, nota, vacância e fontes oficiais. O projeto usa GitHub Pages, GitHub Actions, Python e Google Colab sem servidor permanente.

## Uso rápido

1. Envie o conteúdo deste projeto para `https://github.com/osmarrcs/radar-concursos-ti`.
2. Em **Settings → Pages**, selecione **GitHub Actions**.
3. Abra o notebook pelo botão abaixo para editar e exportar a base.

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/osmarrcs/radar-concursos-ti/blob/main/Radar_Concursos_TI_Colab.ipynb)

## Estrutura

- `data/organs.json`: órgãos e fontes de alerta.
- `data/contests.json`: dados comuns de cada edital.
- `data/positions.json`: cargos, especialidades, chamadas e vacância.
- `web/`: HTML, CSS e JavaScript-fonte.
- `dist/`: gerado automaticamente; não deve ser editado.
- `src/radar_concursos/`: pacote Python com regras, validação, build e alertas.

O projeto não instala bibliotecas: Colab e Actions adicionam `src/` ao caminho do Python.
- `tests/`: testes unitários e de integração.

## Comandos

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m radar_concursos.build
PYTHONPATH=src python -m radar_concursos.alerts.monitor --dry-run
```

## Documentação

- [Arquitetura e DFD](documentation/architecture.md)
- [Google Colab](documentation/colab.md)
- [Alertas Telegram](documentation/telegram.md)
- [TDD e testes](documentation/testing.md)
