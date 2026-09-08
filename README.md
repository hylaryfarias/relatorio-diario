# relatorio-diario

Gera o quadrinho de vendas por forma de pagamento e o texto do WhatsApp a
partir do PDF `Vendas por forma de pagamento - por dia` do Cloud Commerce.

## Uso

```bash
# todos os dias do PDF somados num bloco unico
python3 gerar_relatorio.py relatorio.pdf --saida saida

# apenas um dia
python3 gerar_relatorio.py relatorio.pdf --dia 04/09/2026 --saida saida

# com a entrada prevista preenchida
python3 gerar_relatorio.py relatorio.pdf --entrada entrada.json --saida saida
```

Saidas em `saida/`: `vendas_card.png`, `texto_whatsapp.txt` e
`formas_agrupadas.csv`.

## entrada.json

```json
{
  "vendas_dia": 101481.14,
  "periodos_anteriores": 5789.23,
  "b2b": 1177.80
}
```

O total e a soma dos tres. Passe `"total"` para forcar outro valor.

## Requisitos

```bash
pip install pdfplumber pillow
```

Mais Chromium para o PNG (opcional: sem ele o script salva um `.html`).

As regras de agrupamento estao no dicionario `GRUPOS`, no topo de
`gerar_relatorio.py`. Detalhes do processo em [CLAUDE.md](CLAUDE.md).
