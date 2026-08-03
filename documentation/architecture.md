# Arquitetura e DFD

## Decisões

- **HTML/CSS/JavaScript puro:** pequeno, sem build front-end e compatível com GitHub Pages.
- **Python:** valida dados, gera o portal e executa monitoramentos no Colab e Actions, sem dependências externas.
- **JSON normalizado:** três arquivos evitam repetir órgão e concurso em cada cargo.
- **GitHub Actions:** CI/CD gratuito; nenhum servidor fica ligado permanentemente.

## Modelo

```mermaid
erDiagram
  ORGAN ||--o{ CONTEST : possui
  CONTEST ||--o{ POSITION : oferece
  POSITION ||--|| VACANCY : possui_apuracao
  ORGAN ||--o{ ALERT_SOURCE : monitora
```

## DFD nível 0

```mermaid
flowchart LR
  U[Administrador] --> C[Google Colab]
  C --> D[(JSON normalizado)]
  D --> G[GitHub]
  G --> A[GitHub Actions]
  A --> P[GitHub Pages]
  P --> V[Visitante]
  A --> T[Telegram Bot API]
```

## DFD do portal

```mermaid
flowchart TD
  J[data.json] --> O[Selecionar órgão]
  O --> E[Selecionar concurso]
  E --> R[Listar todos os cargos]
  R --> X[Detalhe do cargo]
  X --> F[Fontes e vacância]
```

## DFD de último chamado

```mermaid
flowchart LR
  RF[Resultado final] --> N[Normalização]
  NM[Nomeações/convocações] --> N
  N --> C[Cruzamento por inscrição/nome]
  C --> Q[Filtro por cargo, localidade e modalidade]
  Q --> L[Última classificação e nota]
```
