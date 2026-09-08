# relatorio-diario

Gera o quadrinho de vendas por forma de pagamento e o texto do WhatsApp a
partir do PDF `Vendas por forma de pagamento - por dia` do Cloud Commerce.

## Uso

```bash
# uso normal: PDF do periodo + PDF do mesmo intervalo do mes anterior
python3 gerar_relatorio.py setembro.pdf --mes-anterior agosto.pdf --saida saida

# apenas um dia
python3 gerar_relatorio.py setembro.pdf --dia 04/09/2026 --saida saida

# forcando a data da entrada prevista e informando o B2B
python3 gerar_relatorio.py setembro.pdf --mes-anterior agosto.pdf \
    --dia-previsto 14/09/2026 --b2b 1177.80 --saida saida
```

O `--mes-anterior` alimenta a parcela de voucher (liquida em D+30). A data
prevista e, por padrao, o dia seguinte ao ultimo dia do relatorio.

Saidas em `saida/`: `vendas_card.png`, `texto_whatsapp.txt` e
`formas_agrupadas.csv`.

## Entrada prevista

Quatro parcelas, somadas no total:

| Parcela | Origem |
|---|---|
| Cartao + Pix | credito + debito + pix do periodo atual (venda bruta) |
| Voucher D+30 | voucher do PDF de `--mes-anterior` |
| Vendas a prazo | titulos de `vendas_a_prazo.csv` que vencem na data prevista |
| B2B iKI | so com `--b2b` (sem base ainda) |

`PAGAMENTO ONLINE` fica fora de proposito: e app/marketplace, com repasse
proprio.

## vendas_a_prazo.csv

Recebiveis B2B a prazo, no formato
`RAZAO SOCIAL;CNPJ;VALOR;VENCIMENTO;ORIGEM DO CONSUMO`. Cada titulo entra na
entrada prevista apenas no dia do seu vencimento. Para forcar outra data de
apuracao, use `--dia-previsto`.

## Requisitos

```bash
pip install pdfplumber pillow
```

Mais Chromium para o PNG (opcional: sem ele o script salva um `.html`).

As regras de agrupamento estao no dicionario `GRUPOS`, no topo de
`gerar_relatorio.py`. Detalhes do processo em [CLAUDE.md](CLAUDE.md).
