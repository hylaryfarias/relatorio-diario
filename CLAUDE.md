# Relatório diário de vendas — Grupo Ragga

A Hylary manda **todo dia** o PDF `Vendas por forma de pagamento - por dia`
(Cloud Commerce) neste chat. O trabalho é sempre o mesmo: agrupar as formas de
pagamento, gerar o quadrinho e o texto para ela mandar no WhatsApp.

## O que fazer quando o PDF chegar

```bash
python3 gerar_relatorio.py <pdf-do-periodo> --mes-anterior <pdf-de-um-mes-atras> --saida saida
```

Ela manda **dois** PDFs: o do período atual e o do **mesmo intervalo do mês
anterior** (ex.: 04-07/09 + 04-07/08). O segundo serve só para o voucher D+30.

Isso entrega os três arquivos em `saida/`:

| Arquivo | O que é |
|---|---|
| `vendas_card.png` | o quadrinho roxo pronto para o print do WhatsApp |
| `texto_whatsapp.txt` | o texto de venda bruta + entrada prevista |
| `formas_agrupadas.csv` | a tabela em CSV (`;` e decimal BR, abre no Excel) |

Depois: mandar o PNG e o texto no chat, com a tabela também em markdown na
resposta, e o fechamento (soma dos dias) conferido.

Flags úteis:

- `--dia 04/09/2026` — usa só aquele dia. **Sem a flag, todos os dias do PDF
  são somados num bloco único** (foi o que ela pediu: "em um dia só").
- `--mes-anterior <pdf>` — PDF do mesmo intervalo do mês anterior, de onde sai
  o voucher D+30. Sem ele, a parcela de voucher não entra.
- `--dia-previsto dd/mm/aaaa` — força a data da entrada prevista (o padrão é o
  dia seguinte ao último dia do relatório, já tratando virada de mês).
- `--b2b 1177.80` — valor do B2B da iKI, quando a base existir.
- `--a-prazo outro.csv` — outra tabela de recebíveis (padrão: `vendas_a_prazo.csv`).
- `--entrada forcar.json` — sobrescreve na mão qualquer parcela:
  `{"vendas": 0, "voucher": 0, "a_prazo": 0, "b2b": 0}`

## Regras que ela já definiu (não perguntar de novo)

1. **Descartar** as colunas `QTDE. CLIENTES` e `TICKET MÉDIO`. A tabela final
   tem só **FORMA DE PAGAMENTO · TOTAL · % DO TOTAL**.
2. **Agrupar mantendo o nome do primeiro da dupla:**
   - `TEF - DEBITO` + `CARTAO DEBITO` → **TEF - DEBITO**
   - `TEF - CREDITO` + `CARTAO CREDITO` → **TEF - CREDITO**
   - `VOUCHER IFOOD (DESCONTO)` + `IFOOD` → **VOUCHER IFOOD (DESCONTO)**
3. **Deixar separados:** `VOUCHER`, `TEF - VOUCHER` e `TEF - TICKET`. Ela
   desfez esse agrupamento de propósito — não juntar de novo.
4. Ordenar o quadrinho **do maior para o menor percentual**, com linha `Total`
   no pé.
5. Valores em **padrão brasileiro** (`R$ 1.089.716,13`).
6. **Não usar o nome da loja do cabeçalho do PDF.** O PDF vem com "ROBS", mas
   isso é erro do relatório — o valor é de **todas as filiais**. O subtítulo do
   quadrinho é sempre `Vendas de <período> · Todas as filiais`.

As regras 2 e 3 vivem no dicionário `GRUPOS` no topo de `gerar_relatorio.py`.
Mudança de agrupamento se faz lá, não na mão na resposta.

## Entrada prevista — como cada parcela é calculada

| Parcela | De onde sai |
|---|---|
| **Cartão + Pix** | `TEF - CREDITO` + `TEF - DEBITO` + `PIX MAQUININHA` do período atual, **já agrupados** (ou seja, com CARTAO CREDITO e CARTAO DEBITO dentro). Soma da venda **bruta**, como ela pediu. |
| **Voucher D+30** | soma de `VOUCHER` + `TEF - VOUCHER` + `TEF - TICKET` do PDF de `--mes-anterior`. Voucher liquida em 30 dias, então o previsto de hoje é a venda de voucher de um mês atrás. |
| **Vendas a prazo** | `vendas_a_prazo.csv`, só os títulos cujo `VENCIMENTO` é **exatamente** a data prevista. Fora dessa data a parcela não entra. |
| **B2B iKI** | ainda **sem base**. Entra só quando vier `--b2b`. |

`PAGAMENTO ONLINE` fica **fora** da entrada prevista de propósito — é
app/marketplace, com repasse próprio. Isso confere com o modelo que ela usa: no
print de 27/08 o previsto (R$ 101.481,14) bate com crédito + débito + Pix
(R$ 102.999,18) e não com nada que inclua o pagamento online.

Aquele print de 27/08 saiu **1,47% abaixo** da soma bruta, o que tem cara de
líquido de MDR. O script entrega o **bruto**, que foi a instrução dela. Se
algum dia ela quiser o líquido, é aplicar a régua de taxas — aí é a skill
`ragga-conciliacao`.

O texto do WhatsApp só mostra as parcelas que têm número; o que está faltando
sai como aviso no console, para não mandar `[PREENCHER]` para a diretoria.
**Sempre avisar no chat o que ficou de fora.**

## vendas_a_prazo.csv

Tabela de recebíveis B2B a prazo (BGs, Casaria etc.) que ela manda de vez em
quando. Formato: `RAZAO SOCIAL;CNPJ;VALOR;VENCIMENTO;ORIGEM DO CONSUMO`, com
valor em padrão BR e vencimento `dd/mm/aaaa`.

Estado atual: 22 títulos, todos vencendo **14/09/2026**, somando
**R$ 38.482,02** (confere com o total da planilha dela). Quando ela mandar
títulos novos, acrescentar linhas no arquivo e commitar.

Cuidado para **não contar em dobro**: a venda a prazo já entrou na venda bruta
no dia da venda; o que entra aqui é o **caixa** no dia do vencimento. São
coisas diferentes, e é por isso que `VENDA A PRAZO` não está em `CARTAO_E_PIX`.

## Conferências que o script já faz

- A soma antes e depois do agrupamento tem de ser idêntica (erro se divergir).
- Avisa se alguma forma de `GRUPOS` não apareceu no PDF do dia.
- Imprime o total de cada dia para bater com o rodapé do PDF.
- Avisa quando o período do mês anterior tem número de dias diferente do atual
  (aí o voucher D+30 sai desproporcional).
- Mostra os próximos vencimentos a prazo quando nenhum cai na data prevista.

Se o PDF vier sem nenhum dia reconhecido, o layout do Cloud Commerce mudou —
conferir `ROW_RE` e `DAY_RE`.

## Ambiente

- `pdfplumber` para ler o PDF. Se der `ModuleNotFoundError: _cffi_backend`,
  rodar `pip install --force-reinstall cffi`.
- Chromium para o PNG (usa `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`
  ou o que estiver no PATH; dá para apontar com `CHROME_PATH`). Sem Chromium o
  script salva `vendas_card.html` em vez do PNG.
- `pillow` (opcional) para recortar a sobra branca do print.

## Conciliação

Pergunta sobre **por que** o dinheiro entra assim (taxas, prazos, EDI, vales,
Sicredi/Fiserv) não é este relatório — usar a skill `ragga-conciliacao`.
