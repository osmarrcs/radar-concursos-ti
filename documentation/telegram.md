# Alertas no Telegram

O monitor consulta apenas os órgãos selecionados em `data/alert_config.json` e somente as fontes oficiais cadastradas no órgão.

## Secrets

Crie em **Settings → Secrets and variables → Actions**:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

O endereço `t.me/osmarcs` não substitui o Chat ID de uma conversa privada. Envie `/start` ao bot e consulte `getUpdates` para obter o número.

## Persistência

- `alert_state.json` muda apenas ao criar a linha de base ou registrar links novos.
- `alert_last_run.json` é local e ignorado pelo Git.
- O workflow só cria commit quando o estado realmente muda.

## Fontes

Prefira, nesta ordem: RSS/Atom, API oficial e HTML. URLs são normalizadas e parâmetros `utm_*`, `fbclid` e `gclid` são removidos.
