# Arquitetura, APIs e fluxo de busca

## Estado atual
O portal não usa uma API geral do Google. A base principal é `data/competitions.json`; por isso ele continua funcionando gratuitamente mesmo se fontes externas ficarem indisponíveis.

## Componentes
1. `data/organs.json`: catálogo editável de órgãos.
2. `data/competitions.json`: concursos, notas, vacância, fontes e status da coleta.
3. `src/build_site.py`: valida a base e copia os dados para `docs/data.json`.
4. `docs/index.html`, CSS e JavaScript: interface estática e filtros no navegador.
5. GitHub Actions: executa a validação e publica `docs/` no GitHub Pages.
6. Colab: interface administrativa para cadastrar órgãos e concursos e gerar ZIP.

## API implementada
`src/collectors/querido_diario.py` consulta a API Pública do Querido Diário para diários oficiais municipais. Ela é útil principalmente para prefeituras e empresas municipais. Não cobre automaticamente DOU, DOE, tribunais, universidades ou todas as páginas de bancas.

## O que não está automatizado
IFPE e Dataprev ainda precisam de adaptadores próprios para suas páginas, resultados e atos de convocação. Os testes incluídos validam filtros e apresentação com dados fictícios; não afirmam notas reais.

## Códigos de retorno
Consulte `src/collectors/status.py`. O portal mostra o código e o motivo em cada registro.
