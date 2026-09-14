# Relatório diário de vendas — Grupo Ragga

São **dois envios** por dia, e cada um tem seu script:

| Envio | Quando | Script | Saída |
|---|---|---|---|
| **1. Venda bruta + entrada prevista** | de manhã, quando ela manda os PDFs | `gerar_relatorio.py` | quadrinho PNG + `texto_whatsapp.txt` |
| **2. Entradas do dia (recebimento real)** | depois, quando ela passa o que entrou | `gerar_entradas.py` | `texto_entradas.txt` |

O envio 2 é o **complemento** do 1: ele confronta o que entrou de verdade
contra a previsão que foi mandada no envio 1.

# Envio 1 — venda bruta e entrada prevista

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
| **Cartão + Pix** | `TEF - CREDITO` + `TEF - DEBITO` + `PIX MAQUININHA` do período atual, **já agrupados** (ou seja, com CARTAO CREDITO e CARTAO DEBITO dentro), **líquidos de taxa**. |
| **Voucher D+30** | soma de `VOUCHER` + `TEF - VOUCHER` + `TEF - TICKET` do PDF de `--mes-anterior`. Voucher liquida em 30 dias, então o previsto de hoje é a venda de voucher de um mês atrás. |
| **Repasse do iFood** | **valor informado na mão** em `--ifood-valor`, já líquido, por entidade (Grupo Ragga, Dell Iris). Cai na quarta, referente à semana segunda a domingo anterior. |
| **Vendas a prazo** | `vendas_a_prazo.csv`, só os títulos cujo `VENCIMENTO` é **exatamente** a data prevista. Fora dessa data a parcela não entra. |
| **B2B iKI** | ainda **sem base**. Entra só quando vier `--b2b`. |

`PAGAMENTO ONLINE` **é o iFood** e fica fora da parcela diária de cartão + Pix
porque tem repasse próprio, semanal. Isso confere com o modelo dela: no print
de 27/08 o previsto (R$ 101.481,14) bate com crédito + débito + Pix
(R$ 102.999,18) e não com nada que inclua o pagamento online.

### A regra do iFood

O fechamento do iFood é de **segunda a domingo**, e isso abre **duas** datas em
que a parcela entra:

| Dia previsto | O que é | Entra no total? | De onde |
|---|---|---|---|
| **Segunda** | **prévia**: a semana fechou domingo, então o valor já dá para calcular | **NÃO** — sai num bloco à parte do texto | faturado do Cloudfy (`--ifood`) com as taxas |
| **Quarta** | o repasse **entra de verdade** | **SIM**, é parcela do total | valor na mão (`--ifood-valor`), já líquido |

**A regra que resolve tudo: a semana fecha no domingo e o dinheiro entra na
quarta.** Segunda é só quando já dá para saber o número — não é entrada de
segunda. Por isso a prévia fica **fora do total do dia** e vai no texto como
bloco separado (`🛵 REPASSE DO IFOOD — ENTRA QUARTA dd/mm`). Somar a prévia no
total de segunda contaria o mesmo dinheiro duas vezes, já que segunda 14/09 e
quarta 16/09 apontam ambas para a semana 07/09 a 13/09.

Nos outros dias da semana não há janela, e os PDFs de `--ifood` são ignorados
com aviso.

### O relatório de pedidos do iFood (fonte certa da prévia)

A Hylary exporta toda segunda o `relatorio-pedidos_*.xlsx` do iFood, cobrindo
a semana seg–dom. **Ele traz o `VALOR LIQUIDO (R$)` pronto, por pedido** — é a
fonte da prévia de segunda, muito melhor que estimar taxa sobre o Cloudfy.

Regra de limpeza: **descartar só os `CANCELADO`**. Manter `CONCLUIDO`,
`CANCELAMENTO PARCIAL` e `CONFIRMED`.

Identidade validada em 96,3% das linhas:

```
VALOR LIQUIDO = VALOR DOS ITENS − INCENTIVO PROMOCIONAL DA LOJA + TAXAS E COMISSOES
```

#### A estrutura real de taxa (medida, não estimada)

Ajuste sobre 3.189 pedidos, erro médio de R$ 0,004:

```
TAXAS E COMISSOES = 10,600% × VALOR DOS ITENS + taxa fixa por pedido
```

- **10,600%** = comissão 8% + transação 2,60%. Bate exatamente com as taxas
  que ela passou.
- **taxa fixa por pedido**: R$ 3,46 / R$ 3,99 / R$ 5,46 / R$ 5,99 conforme a
  faixa. Média R$ 4,46. **Ela não sabia dessa taxa** — e ela é quase metade do
  que o iFood cobra (R$ 63.648,41 de R$ 133.503,77 na semana 07–13/09).
- **A antecipação de 1,59% NÃO está nessa coluna** (a inclinação medida é
  10,600%, não 12,19%). Se for cobrada depois, incide sobre o líquido.
- A taxa de entrega paga pelo cliente **não entra** no cálculo: pedidos com os
  mesmos itens e entregas diferentes têm taxa idêntica.

#### O desconto real é ~40%, não 12%

Semana 07–13/09, pedidos liquidados:

| | | % dos itens |
|---|---:|---:|
| Valor dos itens | R$ 659.012,79 | 100% |
| − Incentivo promocional da **loja** | −R$ 110.321,83 | 16,74% |
| − Comissão + transação | −R$ 69.855,36 | 10,60% |
| − Taxa fixa por pedido | −R$ 63.648,41 | 9,66% |
| **= Valor líquido** | **R$ 397.039,13** | **60,25%** |

O incentivo promocional da loja é desconto que o Grupo banca, não taxa, mas
sai do líquido igual — e é a maior das deduções.

> **Cuidado: o último dia da semana costuma vir incompleto.** Em 07–13/09,
> **803 dos 1.603 pedidos de domingo** estavam com taxa e líquido zerados (não
> liquidados). Os outros seis dias vieram completos. **Sempre conferir quantas
> linhas têm `VALOR LIQUIDO = 0` e em que dia caem**; se houver, estimar o que
> falta pela razão líquido/itens dos liquidados e avisar no chat.

#### Cloudfy × relatório de pedidos

`PAGAMENTO ONLINE` do Cloudfy espelha **`VALOR DOS ITENS − INCENTIVO DA LOJA`**
do iFood — não o valor líquido, e não o valor dos itens puro.

A virada de dia é às **02h**, não à meia-noite: agrupar os pedidos por
`DATA E HORA DO PEDIDO − 2h` reduz o erro diário de R$ 3.877 para R$ 2.861.

Semana 07–13/09: Cloudfy R$ 555.505,94 × iFood R$ 579.344,26 → Cloudfy fica
**4,1% abaixo**. A **Dell'iris está nos dois** (4 lojas no relatório de
pedidos, 988 pedidos, R$ 32.559,78) — não procurar um relatório separado dela.

> **Por que a estimativa por taxa dava errado:** aplicar 12,02% sobre o
> faturado do Cloudfy deu R$ 488.726,02 para 07–13/09, contra um líquido real
> de ~R$ 422 mil. **Erro de R$ 66 mil.** Por isso a prévia de segunda passa a
> sair do `VALOR LIQUIDO` do relatório de pedidos, não de taxa sobre o Cloudfy.

**O valor NÃO sai do Cloudfy.** O `PAGAMENTO ONLINE` do relatório é a *venda*,
não o *repasse* — medido em 09/09, a diferença foi de **24,72%**, muito acima
da taxa. Ela passa o valor na mão:

```bash
python3 gerar_relatorio.py 08-09.pdf --mes-anterior 08-08.pdf \
    --ifood-valor "Grupo Ragga=401827.58" --ifood-valor "Dell Iris=22224.02" \
    --saida saida
```

- `--ifood-valor` aceita `[ROTULO=]VALOR`, pode repetir e soma tudo. O rótulo
  aparece na abertura do console. Aceita `401827.58` e `401.827,58`.
- **O valor informado assim JÁ É LÍQUIDO — nunca aplicar taxa em cima.**
  Aplicar os 12,02% de novo tiraria uns R$ 51 mil de um repasse de R$ 424 mil.
- Chega **por entidade**: Grupo Ragga e Dell Iris são CNPJs diferentes e vêm
  em valores separados. Passar cada um com seu rótulo.
- **A Dell Iris é só iFood.** Ela não tem cartão, voucher nem venda a prazo
  para entrar no previsto — o relatório do Cloudfy (CNPJ 52.934.334/0001-36)
  cobre tudo o que não é iFood. Não procurar venda da Dell Iris.
- Se a data prevista é quarta e o valor não veio, o script avisa e diz a janela
  — aí é pedir o valor antes de mandar o texto.

`--ifood <pdf>` continua existindo como **estimativa** a partir do Cloudfy (aí
sim com a taxa de 12,02%), mas `--ifood-valor` tem precedência e o script avisa
quando os dois vêm juntos. Para o número que vai para a diretoria, usar sempre
o valor informado.

### As taxas (entrada prevista LÍQUIDA)

A entrada prevista sai **líquida de taxa**, como estimativa. As taxas vivem em
`TAXAS` e `TAXA_IFOOD` no topo de `gerar_relatorio.py` — mudança de taxa se faz
lá:

| Forma | Taxa |
|---|---:|
| Crédito (`TEF - CREDITO`) | 2,63% |
| Débito (`TEF - DEBITO`) | 0,99% |
| Pix maquininha | 0% |
| Voucher | **5% fictício** — ver abaixo |
| iFood (`PAGAMENTO ONLINE`) | **12,02% efetivos** — só na estimativa por `--ifood`; o valor de `--ifood-valor` já vem líquido |

Regras de uso:

- **Não descrever as taxas no texto do WhatsApp.** Ela pediu explicitamente:
  o texto mostra só o valor líquido. A abertura bruto → taxa → líquido sai no
  console, e vale reportar no chat.
- São **estimativas**, não a taxa real de cada transação. A taxa real sai do
  EDI — isso é a skill `ragga-conciliacao`.
- A taxa do iFood tem **dois estágios**, não é uma soma:
  1. comissão (8%) + transação (2,60%) incidem sobre o **bruto**;
  2. antecipação (1,59%) incide sobre o **líquido** que sobrou do estágio 1.

  `líquido = bruto × (1 − 0,1060) × (1 − 0,0159)`, o que dá **12,0215%**
  efetivos. Somar as três daria 12,19% e desconta R$ 949,38 a mais numa
  semana de R$ 563 mil — por isso a composição importa. Está em
  `liquido_ifood()`.
- **A taxa do voucher (5%) é FICTÍCIA.** Ela não tem a taxa real e pediu os 5%
  só para ter uma base. Está em `TAXA_VOUCHER`. Consequências:
  - **não tratar esse número como taxa negociada** em nenhuma análise;
  - **não perguntar a taxa real a cada envio** — ela sabe que é estimativa;
  - quando a real aparecer (contrato de Alelo, Pluxee, Ticket, Fepas, ou o
    EDI), é trocar uma linha.

  Como o voucher é parcela pequena (uns R$ 10 mil num previsto de R$ 517 mil),
  o erro dessa estimativa não move o total de forma relevante.
- **Venda a prazo e B2B saem brutos** — são boleto, sem adquirente no meio.
- `--bruto` desliga tudo e devolve a entrada prevista no bruto, para comparar.

Confere com o modelo dela: aquele print de 27/08 saiu 1,47% abaixo da soma
bruta, que era justamente o desconto de taxa.

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

# Envio 2 — entradas do dia (recebimento real)

Quando ela passar os valores que entraram:

```bash
python3 gerar_entradas.py --data 04/09/2026 --previsao 110000 \
    --pix 24739.28 --debito 44730.61 --credito 46217.25 \
    --voucher 6730.53 --b2b 1045.86 --saida saida
```

Ou com `--dados recebimentos.json`:

```json
{
  "data": "04/09/2026",
  "previsao": 110000.00,
  "recebido": {"PIX": 24739.28, "Débito": 44730.61, "Crédito": 46217.25,
               "Voucher": 6730.53, "B2B": 1045.86},
  "total_informado": 128115.36
}
```

Formas disponíveis, na ordem em que saem no texto: `--pix`, `--debito`,
`--credito`, `--voucher`, `--b2b`, `--dinheiro`, `--online`. Só as que forem
passadas aparecem na mensagem.

## Regras do envio 2

1. **`--previsao` é a previsão que foi mandada para aquele dia** no envio 1 —
   não recalcular por outro caminho. Sem ela o script para: comparar
   recebimento com uma previsão inventada é pior do que não mandar nada.
2. **O `VALOR RECEBIDO` é sempre a soma das formas.** Nunca digitar um total à
   parte. Se ela informar um total, passar em `--total-informado`: o script
   confere e avisa se não fechar, mas o texto sai com a soma.
3. O tom muda sozinho conforme o resultado: acima da previsão sai `✅` +
   `🟢 ... ACIMA` + 🚀 no resumo; abaixo sai `⚠️` + `🔴 ... ABAIXO` e um resumo
   sem comemoração; empate sai `⚪ EM LINHA COM A PREVISÃO`.
4. **Sempre reportar no chat** a diferença entre previsto e recebido, e por
   forma quando der, para ela ver de onde veio o desvio.

## Sobre o exemplo de 04/09

Os valores daquele modelo **não são reais** — ela confirmou que era só para
mostrar o formato. Por isso a soma das formas (R$ 123.463,53) não fechava com
o total do texto (R$ 128.115,36). Não é para caçar essa diferença.

A trava do `--total-informado` continua valendo para os envios de verdade: se
a soma não fechar com o total que ela passar, avisar antes de mandar.

## Conciliação

Pergunta sobre **por que** o dinheiro entra assim (taxas, prazos, EDI, vales,
Sicredi/Fiserv) não é este relatório — usar a skill `ragga-conciliacao`.
