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

| Dia previsto | O que entra | De onde |
|---|---|---|
| **Segunda** | **estimativa** do repasse: a semana fechou no domingo | faturado do Cloudfy (`--ifood`) **com as taxas aplicadas** |
| **Quarta** | o repasse **real**, que cai nesse dia | valor na mão (`--ifood-valor`), já líquido |

O script calcula a janela sozinho e **as duas datas apontam para a mesma
semana**: segunda 14/09 e quarta 16/09 dão ambas 07/09 a 13/09. Nos outros dias
da semana não há janela, e os PDFs de `--ifood` são ignorados com aviso.

> **PENDÊNCIA EM ABERTO — não resolver sozinho, perguntar.**
> Como segunda e quarta apontam para o mesmo dinheiro, incluir a parcela nas
> duas mensagens conta o repasse **duas vezes**. Falta a Hylary decidir se, na
> quarta, o valor real substitui a estimativa, se repete, ou se fica de fora.

> **PENDÊNCIA EM ABERTO — a taxa não explica a diferença medida.**
> Único par medido (semana 31/08–06/09): faturado do Cloudfy R$ 563.296,83 →
> repasse real R$ 424.051,60, ou seja **24,72% abaixo**, contra os 12,02% da
> taxa. Se essa razão se repetir, a estimativa de segunda sai **alta em uns
> R$ 70 mil** por semana. Com um só ponto de comparação não dá para concluir
> que 75,28% é a regra — **acumular os pares faturado × repasse real toda
> semana** e, quando houver amostra, decidir entre aplicar a taxa ou a razão
> observada. Ao mandar a estimativa de segunda, **sempre avisar no chat** que
> ela pode estar otimista.

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
