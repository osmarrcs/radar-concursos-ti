# Telegram

## Secrets

No GitHub:

`Settings → Secrets and variables → Actions`

Crie:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Rotina

O workflow consulta os órgãos selecionados a cada seis horas. A primeira execução cria a linha de base. As seguintes enviam apenas URLs novas.

O resumo pode conter itens analisados, relevantes, oficiais, novidades, erros e duração.
