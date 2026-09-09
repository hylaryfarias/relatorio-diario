# relatorio-diario

Os dois envios diarios do financeiro do Grupo Ragga, no WhatsApp:

1. **`gerar_relatorio.py`** — venda bruta por forma de pagamento (quadrinho em
   PNG) e a entrada prevista, a partir do PDF `Vendas por forma de pagamento -
   por dia` do Cloud Commerce.
2. **`gerar_entradas.py`** — o recebimento real do dia contra aquela previsao.

## Envio 1 — venda bruta e entrada prevista

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
| Cartao + Pix | credito + debito + pix do periodo atual, liquidos de taxa |
| Voucher D+30 | voucher do PDF de `--mes-anterior` |
| Repasse do iFood | valor informado em `--ifood-valor`, ja liquido, por entidade; cai na quarta |
| Vendas a prazo | titulos de `vendas_a_prazo.csv` que vencem na data prevista |
| B2B iKI | so com `--b2b` (sem base ainda) |

`PAGAMENTO ONLINE` e o iFood: fica fora da parcela diaria de cartao + Pix
porque o repasse e semanal. Ele cai na **quarta-feira**, referente a semana
fechada de **segunda a domingo anterior** (quarta 09/09 -> 31/08 a 06/09):

```bash
python3 gerar_relatorio.py setembro.pdf --mes-anterior agosto.pdf \
    --dia-previsto 09/09/2026 --ifood semana1.pdf --ifood semana2.pdf
```

**O valor do repasse nao sai do Cloudfy**: o `PAGAMENTO ONLINE` de la e a
venda, nao o repasse (diferenca medida de 24,72%). Informe na mao:

```bash
python3 gerar_relatorio.py 08-09.pdf --mes-anterior 08-08.pdf \
    --ifood-valor "Grupo Ragga=401827.58" --ifood-valor "Dell Iris=22224.02"
```

`--ifood-valor` aceita `[ROTULO=]VALOR`, pode repetir e soma. **Esse valor ja
e liquido** — o script nao aplica taxa em cima. O repasse chega por entidade
(Grupo Ragga, Dell Iris), com CNPJs diferentes.

A flag `--ifood <pdf>` continua servindo como estimativa a partir do Cloudfy,
com a taxa de 12,02%, mas `--ifood-valor` tem precedencia. O script calcula a
janela seg-dom a partir da data prevista de qualquer jeito.

## Taxas

A entrada prevista sai **liquida**, como estimativa. As taxas estao em `TAXAS`
e `TAXA_IFOOD`, no topo de `gerar_relatorio.py`:

| Forma | Taxa |
|---|---:|
| Credito | 2,63% |
| Debito | 0,99% |
| Pix | 0% |
| iFood | 12,0215% efetivos, em dois estagios |

A taxa do iFood nao e uma soma: comissao (8%) e transacao (2,60%) incidem
sobre o bruto, e a antecipacao (1,59%) incide sobre o liquido que sobra —
`bruto x (1 - 0,1060) x (1 - 0,0159)`.

Voucher, venda a prazo e B2B saem brutos: ainda nao ha taxa definida para
essas. Use `--bruto` para desligar as taxas e comparar.

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

## Envio 2 — entradas do dia

```bash
python3 gerar_entradas.py --data 04/09/2026 --previsao 110000 \
    --pix 24739.28 --debito 44730.61 --credito 46217.25 \
    --voucher 6730.53 --b2b 1045.86 --saida saida
```

Gera `saida/texto_entradas.txt`. A `--previsao` e a que foi mandada para aquele
dia no envio 1. Formas: `--pix`, `--debito`, `--credito`, `--voucher`, `--b2b`,
`--dinheiro`, `--online` — so as informadas aparecem no texto.

O `VALOR RECEBIDO` e sempre a soma das formas. Se voce tiver o total na mao,
passe em `--total-informado`: o script confere e avisa quando nao fecha, em vez
de mandar um numero que nao soma.

Tambem aceita `--dados recebimentos.json`:

```json
{
  "data": "04/09/2026",
  "previsao": 110000.00,
  "recebido": {"PIX": 24739.28, "Débito": 44730.61, "Crédito": 46217.25,
               "Voucher": 6730.53, "B2B": 1045.86},
  "total_informado": 128115.36
}
```
