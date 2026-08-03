# Telegram e métricas

## Configuração única

1. Crie o bot no `@BotFather`.
2. Envie `/start` ao bot.
3. Obtenha o `chat.id` com `getUpdates`.
4. Crie no GitHub Actions os Secrets `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.
5. No painel do Colab, selecione os órgãos e salve.

## Funcionamento

- varredura de novidades: a cada seis horas;
- resumo de métricas: diariamente às 08:30 no fuso de Recife;
- primeira execução: cria a linha de base e não envia links antigos;
- novidades: são enviadas e salvas em `data/updates.json`;
- relatório de cada execução: armazenado como artifact do GitHub Actions por 30 dias.

## Métricas

O resumo informa órgãos, provedores, itens analisados, relevantes, oficiais, novidades, erros e duração. O arquivo `data/alert_last_run.json` não é versionado.
