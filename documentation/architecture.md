# Arquitetura e DFD

## Componentes

```mermaid
flowchart LR
    U[Usuário no Colab] --> UI[colab_app.py]
    UI --> S[Serviços de domínio]
    UI --> O[Orquestrador de busca]
    UI --> P[Importador de PDF]
    O --> F[Fontes oficiais HTML/RSS]
    O --> G[GDELT]
    O --> Q[Querido Diário]
    S --> D[(JSON normalizado)]
    P --> D
    O --> D
    D --> B[Build estático]
    B --> W[GitHub Pages]
    A[GitHub Actions] --> O
    A --> T[Telegram]
```

## Busca manual por órgão

```mermaid
flowchart TD
    A[Estado + órgão] --> B[Resolver órgão existente ou temporário]
    B --> C[Executar provedores habilitados]
    C --> D[Normalizar URLs]
    D --> E[Classificar eventos]
    E --> F[Deduplicar e pontuar oficialidade]
    F --> G[Mostrar resultados e métricas]
    G --> H{Usuário salva?}
    H -- Sim --> I[data/updates.json]
    I --> J[Vincular ao concurso mais recente/ano encontrado]
    J --> K[Atualizar status quando fonte oficial]
    H -- PDF --> L[Importador de edital]
```

## Automação

```mermaid
flowchart TD
    C[GitHub Actions cron] --> S[Órgãos selecionados]
    S --> P[Provedores]
    P --> M[Métricas]
    P --> N[Novidades]
    N --> T[Telegram]
    N --> U[updates.json]
    U --> G[Commit automático]
    G --> B[Build do GitHub Pages]
    M --> R[Artifact de 30 dias]
    M --> D[Resumo diário no Telegram]
```

## Regra de segurança dos dados

A busca automática não inventa vacância, nota ou último chamado. Ela registra publicações e pode atualizar o status geral do concurso quando a URL é oficial. Vacância e histórico de chamadas exigem fonte específica ligada ao cargo.
