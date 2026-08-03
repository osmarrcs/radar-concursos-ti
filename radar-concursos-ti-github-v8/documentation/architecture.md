# Arquitetura e DFD

## Componentes

- **Colab:** interface administrativa e pesquisa pontual.
- **JSON:** armazenamento versionado.
- **Python:** regras, importação de PDF, pesquisa, validação e alertas.
- **GitHub Actions:** CI/CD e pesquisa agendada.
- **GitHub Pages:** portal estático.
- **Telegram:** notificações.

## DFD — consulta histórica

```mermaid
flowchart LR
  U[Usuário] --> A[Âmbito]
  A --> C[Carreira]
  C --> O[Órgão]
  O --> E[3 últimos concursos ou todos]
  E --> P[Todos os cargos]
  P --> D[Detalhes e fontes]
```

## DFD — edital aberto

```mermaid
flowchart LR
  U[Usuário] --> E[Escolhe edital]
  E --> P[Seleciona até 2 cargos]
  P --> R[Pesquisa automática]
  R --> F[Fontes oficiais/GDELT/Querido Diário]
  F --> M[Vacância, convocação e resultado]
  M --> V[Valores confirmados ou revisão manual]
```

## DFD — alertas

```mermaid
flowchart LR
  G[GitHub Actions] --> O[Órgãos selecionados]
  O --> S[Provedores]
  S --> D[Deduplicação]
  D --> T[Telegram]
  D --> U[updates.json]
  U --> P[GitHub Pages]
```

## Decisão de segurança

A pesquisa automática não inventa valores. Se localizar documentos, mas não conseguir extrair métricas de forma confiável, retorna `MANUAL_REVIEW_REQUIRED` e preserva os links.
