#!/usr/bin/env python3
"""Gera o quadrinho de vendas por forma de pagamento + o texto do WhatsApp.

Entrada : o PDF "Vendas por forma de pagamento - por dia" do Cloud Commerce.
Saidas  : vendas_card.png, texto_whatsapp.txt e formas_agrupadas.csv.

Uso:
    python3 gerar_relatorio.py relatorio.pdf
    python3 gerar_relatorio.py relatorio.pdf --dia 04/09/2026
    python3 gerar_relatorio.py relatorio.pdf --entrada entrada.json
"""

import argparse
import csv as csvmod
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict

# ---------------------------------------------------------------------------
# Regras de agrupamento pedidas pela Hylary. A chave e o nome que fica na
# linha final (o nome do primeiro da dupla); os valores sao as formas que
# entram nela. Para desfazer um agrupamento, apague a linha correspondente.
# ---------------------------------------------------------------------------
GRUPOS = OrderedDict([
    ('TEF - DEBITO',             ['TEF - DEBITO', 'CARTAO DEBITO']),
    ('TEF - CREDITO',            ['TEF - CREDITO', 'CARTAO CREDITO']),
    ('VOUCHER IFOOD (DESCONTO)', ['VOUCHER IFOOD (DESCONTO)', 'IFOOD']),
])

# VOUCHER, TEF - VOUCHER e TEF - TICKET ficam separados de proposito.

# ---------------------------------------------------------------------------
# Entrada prevista. Nomes JA AGRUPADOS (portanto 'TEF - CREDITO' ja carrega
# CARTAO CREDITO dentro dele).
#
# Cartao + Pix: o que liquida rapido e entra na previsao do proximo dia.
# PAGAMENTO ONLINE fica fora daqui porque tem repasse proprio -- ver IFOOD.
CARTAO_E_PIX = ['TEF - CREDITO', 'TEF - DEBITO', 'PIX MAQUININHA']

# PAGAMENTO ONLINE e o iFood. O repasse cai na QUARTA, referente a semana
# fechada de segunda a domingo anterior (quarta 09/09 -> 31/08 a 06/09). Entao
# so entra na previsao quando o dia previsto e uma quarta-feira.
# O recebimento do iFood NAO da para tirar do Cloudfy: o PAGAMENTO ONLINE de
# lá é a venda, não o repasse, e a diferença medida foi de 24,72% (bem mais que
# a taxa). Então o valor vem NA MAO, em --ifood-valor, e chega por entidade
# (Grupo Ragga, Dell Iris). Valor informado assim JA E LIQUIDO: nao aplicar
# taxa de novo. A janela seg-dom e a regra da quarta continuam valendo para
# dizer a que semana o repasse se refere.
IFOOD_FORMA = 'PAGAMENTO ONLINE'
QUARTA = 2  # datetime.date.weekday(): segunda=0

# ---------------------------------------------------------------------------
# Taxas para estimar o LIQUIDO da entrada prevista. Sao estimativas, nao a
# taxa real de cada transacao -- a taxa real sai do EDI (skill ragga-conciliacao).
# Aplicadas sobre o bruto de cada forma. Para mudar uma taxa, e aqui.
# ---------------------------------------------------------------------------
TAXAS = {
    'TEF - CREDITO': 0.0263,   # 2,63%
    'TEF - DEBITO': 0.0099,    # 0,99%
    'PIX MAQUININHA': 0.0000,  # sem taxa
}

# iFood em DOIS ESTAGIOS, e nao numa soma simples:
#   1) comissao (8%) + transacao (2,60%) incidem sobre o BRUTO;
#   2) antecipacao (1,59%) incide sobre o LIQUIDO que sobrou do estagio 1.
# Taxa efetiva resultante: 12,0215%.
IFOOD_SOBRE_BRUTO = 0.0800 + 0.0260
IFOOD_ANTECIPACAO = 0.0159


def liquido_ifood(bruto):
    """Aplica os dois estagios da taxa do iFood."""
    return bruto * (1 - IFOOD_SOBRE_BRUTO) * (1 - IFOOD_ANTECIPACAO)


def taxa_efetiva_ifood():
    """Taxa efetiva equivalente dos dois estagios, para exibir."""
    return 1 - (1 - IFOOD_SOBRE_BRUTO) * (1 - IFOOD_ANTECIPACAO)

# Voucher (Alelo, Pluxee, Ticket, Fepas): 5% FICTICIO, so para ter uma base.
# Nao e taxa negociada -- trocar quando a real aparecer.
TAXA_VOUCHER = 0.05

# Venda a prazo e B2B entram BRUTOS: sao boleto, sem adquirente no meio.

# Voucher: liquida em D+30, entao o previsto de hoje sai das vendas de voucher
# do mesmo periodo do mes anterior (--mes-anterior).
FORMAS_VOUCHER = ['VOUCHER', 'TEF - VOUCHER', 'TEF - TICKET']

# Venda a prazo (B2B das BGs, Casaria etc.): tabela de recebiveis com data de
# vencimento em vendas_a_prazo.csv. Cada titulo entra na entrada prevista so no
# dia do seu vencimento -- nao no dia da venda, que ja foi na venda bruta.
A_PRAZO_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'vendas_a_prazo.csv')

ROW_RE = re.compile(r'^(.+?)\s+R\$\s*([\d\.]+,\d{2})\s+([\d\.]+,?\d*)\s+R\$\s*([\d\.]+,\d{2})$')
DAY_RE = re.compile(r'^Data:\s*(\d{2}/\d{2}/\d{4})')
CNPJ_RE = re.compile(r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$')

CHROME_CANDIDATES = [
    os.environ.get('CHROME_PATH', ''),
    '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    '/opt/pw-browsers/chromium/chrome-linux/chrome',
]


def brl(valor, casas=2):
    """1234.5 -> '1.234,50' (padrao brasileiro)."""
    return f"{valor:,.{casas}f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def to_float(texto):
    """'1.234,50' -> 1234.5"""
    return float(texto.replace('.', '').replace(',', '.'))


def achar_chrome():
    for caminho in CHROME_CANDIDATES:
        if caminho and os.path.isfile(caminho):
            return caminho
    for nome in ('chromium', 'chromium-browser', 'google-chrome', 'chrome'):
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    return None


def ler_pdf(caminho):
    """Devolve (dias, cnpj). dias = {'04/09/2026': {forma: total}}.

    O nome da loja no cabecalho do PDF ("ROBS") e erro do relatorio: o valor e
    de todas as filiais. Por isso nao e lido nem usado no quadrinho.
    """
    import pdfplumber

    linhas = []
    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            linhas.extend((pagina.extract_text() or '').splitlines())

    dias, dia_atual, cnpj = OrderedDict(), None, ''
    for linha in linhas:
        linha = linha.strip()
        if not cnpj and CNPJ_RE.match(linha):
            cnpj = linha
        achou_dia = DAY_RE.match(linha)
        if achou_dia:
            dia_atual = achou_dia.group(1)
            dias.setdefault(dia_atual, OrderedDict())
            continue
        achou_linha = ROW_RE.match(linha)
        if achou_linha and dia_atual:
            forma = achou_linha.group(1).strip()
            # a coluna 2 e o TOTAL; qtde. clientes e ticket medio sao descartados
            valor = to_float(achou_linha.group(2))
            dias[dia_atual][forma] = dias[dia_atual].get(forma, 0.0) + valor
    return dias, cnpj


def ler_ifood_manual(entradas):
    """Le os --ifood-valor no formato "[ROTULO=]VALOR". Valores JA LIQUIDOS."""
    itens = []
    for bruto in entradas:
        rotulo, _, texto = bruto.rpartition('=')
        texto = texto.strip()
        try:
            valor = to_float(texto) if ',' in texto else float(texto)
        except ValueError:
            raise SystemExit(f'ERRO: valor invalido em --ifood-valor: {bruto!r}')
        itens.append((rotulo.strip() or 'repasse', valor))
    return itens


def janela_ifood(dia_previsto):
    """Semana de referencia do repasse do iFood para uma data prevista.

    Devolve (segunda, domingo) como date, ou None se a data nao for quarta.
    """
    data = datetime.datetime.strptime(dia_previsto, '%d/%m/%Y').date()
    if data.weekday() != QUARTA:
        return None
    domingo = data - datetime.timedelta(days=3)
    return domingo - datetime.timedelta(days=6), domingo


def somar_ifood(pdfs, janela):
    """Soma PAGAMENTO ONLINE dos dias dentro da janela. Devolve (total, faltando)."""
    esperados = [janela[0] + datetime.timedelta(days=n) for n in range(7)]
    por_dia = {}
    for caminho in pdfs:
        dias, _ = ler_pdf(caminho)
        for texto_dia, formas in dias.items():
            data = datetime.datetime.strptime(texto_dia, '%d/%m/%Y').date()
            if janela[0] <= data <= janela[1]:
                por_dia[data] = formas.get(IFOOD_FORMA, 0.0)
            else:
                print(f'AVISO: {texto_dia} esta fora da janela do iFood '
                      f'({janela[0]:%d/%m} a {janela[1]:%d/%m}) e foi ignorado.',
                      file=sys.stderr)
    faltando = [d for d in esperados if d not in por_dia]
    return sum(por_dia.values()), faltando


def ler_a_prazo(caminho):
    """Le a tabela de vendas a prazo. Devolve [] se o arquivo nao existir."""
    if not caminho or not os.path.isfile(caminho):
        return []
    titulos = []
    with open(caminho, newline='', encoding='utf-8') as arquivo:
        for numero, linha in enumerate(csvmod.DictReader(arquivo, delimiter=';'), start=2):
            valor = (linha.get('VALOR') or '').strip()
            vencimento = (linha.get('VENCIMENTO') or '').strip()
            if not valor or not vencimento:
                continue
            try:
                titulos.append({
                    'razao': (linha.get('RAZAO SOCIAL') or '').strip(),
                    'valor': to_float(valor),
                    'vencimento': vencimento,
                    'origem': (linha.get('ORIGEM DO CONSUMO') or '').strip(),
                })
            except ValueError:
                print(f'AVISO: valor invalido na linha {numero} de {caminho}: {valor!r}',
                      file=sys.stderr)
    return titulos


def agrupar(dias, rotulo='PDF do periodo'):
    """Consolida os dias num bloco unico e aplica GRUPOS. Valida a soma."""
    membro_para_grupo = {m: destino for destino, ms in GRUPOS.items() for m in ms}
    bruto, agrupado, composicao = OrderedDict(), OrderedDict(), OrderedDict()

    for formas in dias.values():
        for forma, valor in formas.items():
            bruto[forma] = bruto.get(forma, 0.0) + valor
            destino = membro_para_grupo.get(forma, forma)
            agrupado[destino] = agrupado.get(destino, 0.0) + valor
            composicao.setdefault(destino, OrderedDict())
            composicao[destino][forma] = composicao[destino].get(forma, 0.0) + valor

    # trava de seguranca: agrupar nao pode criar nem perder dinheiro
    if abs(sum(bruto.values()) - sum(agrupado.values())) > 0.005:
        raise SystemExit('ERRO: a soma mudou depois do agrupamento.')

    ignorados = [m for ms in GRUPOS.values() for m in ms if m not in bruto]
    if ignorados:
        print(f'AVISO: {rotulo}: formas de GRUPOS que nao aparecem nele: '
              f'{", ".join(ignorados)}', file=sys.stderr)

    return agrupado, composicao


def montar_html(linhas, total, subtitulo):
    corpo = '\n'.join(
        f'      <tr><td class="f">{forma}</td>'
        f'<td class="v">R$ {brl(valor)}</td>'
        f'<td class="p">{brl(valor / total * 100)}%</td></tr>'
        for forma, valor in linhas
    )
    return f"""<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 18px; background: #ffffff;
          font-family: "Segoe UI", Calibri, Arial, Helvetica, sans-serif; }}
  table {{ border-collapse: collapse; width: 620px; }}
  caption {{ background: #E4DDF6; border: 1px solid #8B76C4; border-bottom: none;
             padding: 7px 10px 8px; }}
  .t1 {{ font-size: 16px; font-weight: 700; color: #2B2140; }}
  .t2 {{ font-size: 12px; color: #6B5E8A; margin-top: 2px; }}
  th {{ background: #EDE8F9; border: 1px solid #8B76C4; color: #2B2140;
        font-size: 12.5px; font-weight: 700; padding: 6px 10px; line-height: 1.25;
        vertical-align: bottom; }}
  th.c1 {{ text-align: left; }}
  th.c2 {{ text-align: right; width: 165px; }}
  th.c3 {{ text-align: right; width: 120px; }}
  td {{ border: 1px solid #8B76C4; font-size: 13.5px; color: #1B1B1B; padding: 5px 10px; }}
  td.f {{ text-align: left; }}
  td.v, td.p {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tbody tr:nth-child(even) td {{ background: #FAF8FE; }}
  tfoot td {{ background: #EDE8F9; font-weight: 700; font-size: 14px; }}
</style>
<table>
  <caption>
    <div class="t1">Composi&ccedil;&atilde;o da venda &mdash; por forma de pagamento</div>
    <div class="t2">{subtitulo}</div>
  </caption>
  <thead>
    <tr>
      <th class="c1">Forma de Pagamento</th>
      <th class="c2">Composi&ccedil;&atilde;o de Venda</th>
      <th class="c3">% Venda por<br>Forma de Pag.</th>
    </tr>
  </thead>
  <tbody>
{corpo}
  </tbody>
  <tfoot>
    <tr><td class="f">Total</td><td class="v">R$ {brl(total)}</td><td class="p">100,00%</td></tr>
  </tfoot>
</table>
"""


def renderizar_png(html, destino):
    chrome = achar_chrome()
    if not chrome:
        print('AVISO: Chromium nao encontrado; gerei so o .html.', file=sys.stderr)
        return False

    with tempfile.TemporaryDirectory() as tmp:
        pagina = os.path.join(tmp, 'card.html')
        with open(pagina, 'w') as arquivo:
            arquivo.write(html)
        subprocess.run(
            [chrome, '--headless', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
             '--force-device-scale-factor=2', '--window-size=660,900',
             f'--screenshot={destino}', f'file://{pagina}'],
            check=True, capture_output=True,
        )

    try:  # recorta a sobra branca para o print sair justo
        from PIL import Image, ImageChops
        imagem = Image.open(destino).convert('RGB')
        caixa = ImageChops.difference(imagem, Image.new('RGB', imagem.size, (255, 255, 255))).getbbox()
        if caixa:
            pad, (esq, topo, dir_, baixo) = 32, caixa
            imagem.crop((max(0, esq - pad), max(0, topo - pad),
                         min(imagem.width, dir_ + pad),
                         min(imagem.height, baixo + pad))).save(destino)
    except ImportError:
        pass
    return True


PARCELAS = ('vendas', 'voucher', 'ifood', 'a_prazo', 'b2b')


def calcular_entrada(agrupado, agrupado_anterior, titulos, dia_previsto,
                     ifood=None, b2b=None, override=None, liquido=True,
                     ifood_manual=None):
    """Monta as parcelas da entrada prevista.

    vendas   -> credito + debito + pix do periodo atual (venda bruta)
    voucher  -> voucher do mesmo periodo do mes anterior (D+30)
    ifood    -> PAGAMENTO ONLINE da semana seg-dom anterior, so nas quartas

    Com liquido=True (padrao) cartao, voucher e a estimativa de iFood saem
    liquidos das taxas. Venda a prazo e B2B saem brutos (boleto).
    a_prazo  -> titulos a prazo que vencem exatamente em dia_previsto
    b2b      -> iKI Produtos Alimenticios; None enquanto nao houver base
    """
    vencendo = [t for t in titulos if t['vencimento'] == dia_previsto]

    # detalhe por forma, para poder auditar bruto -> taxa -> liquido
    detalhe = []
    for forma in CARTAO_E_PIX:
        bruto = agrupado.get(forma, 0.0)
        taxa = TAXAS.get(forma, 0.0) if liquido else 0.0
        detalhe.append((forma, bruto, taxa, bruto * (1 - taxa)))

    # valor informado na mao ja vem liquido: taxa zero, sem bruto de referencia
    if ifood_manual:
        taxa_ifood, ifood_bruto = 0.0, None
        ifood_valor = sum(valor for _, valor in ifood_manual)
    else:
        taxa_ifood, ifood_bruto = (taxa_efetiva_ifood() if liquido else 0.0), ifood
        ifood_valor = None if ifood is None else (liquido_ifood(ifood) if liquido else ifood)
    entrada = {
        'vendas': sum(item[3] for item in detalhe),
        'detalhe_vendas': detalhe,
        'ifood_bruto': ifood_bruto,
        'taxa_ifood': taxa_ifood,
        'ifood_manual': ifood_manual or [],
        'voucher': (sum(agrupado_anterior.get(f, 0.0) for f in FORMAS_VOUCHER)
                    * (1 - (TAXA_VOUCHER if liquido else 0.0))
                    if agrupado_anterior is not None else None),
        'taxa_voucher': TAXA_VOUCHER if liquido else 0.0,
        'ifood': ifood_valor,
        'a_prazo': sum(t['valor'] for t in vencendo) if vencendo else None,
        'b2b': b2b,
        'titulos_a_prazo': vencendo,
    }
    if override:
        entrada.update({k: v for k, v in override.items() if k in PARCELAS})
    entrada['total'] = sum(entrada[p] for p in PARCELAS if entrada[p] is not None)
    return entrada


def montar_texto(dias_usados, total, entrada, dia_previsto):
    """Texto pronto para colar no WhatsApp.

    So entram no texto as parcelas que tem numero. O que falta sai no console,
    para nao mandar "[PREENCHER]" para a diretoria.
    """
    primeiro, ultimo = dias_usados[0], dias_usados[-1]

    if primeiro == ultimo:
        cabecalho = f'📊 *VENDA BRUTA DO DIA | {primeiro[:5]}*'
        referencia = 'do dia'
    else:
        cabecalho = f'📊 *VENDA BRUTA | {primeiro[:5]} a {ultimo[:5]}*'
        referencia = 'do período'

    partes = [cabecalho, '', f'R$ {brl(total)}', '',
              f'💰 *ENTRADA PREVISTA PRO DIA {dia_previsto[:5]}*', '',
              f'*R$ {brl(entrada["total"])}*', '']

    partes.append(f'· R$ {brl(entrada["vendas"])} são referentes às vendas '
                  f'{referencia} (Crédito, Débito e Pix);')

    if entrada['voucher'] is not None:
        partes.append(f'· R$ {brl(entrada["voucher"])} de recebimento de períodos '
                      f'anteriores (Voucher D+30);')

    if entrada['ifood'] is not None:
        janela = entrada['janela_ifood']
        referencia = (f', referente a {janela[0]:%d/%m} a {janela[1]:%d/%m}'
                      if janela else '')
        partes.append(f'· R$ {brl(entrada["ifood"])} de repasse do iFood'
                      f'{referencia};')

    if entrada['a_prazo'] is not None:
        quantos = len(entrada['titulos_a_prazo'])
        partes.append(f'· R$ {brl(entrada["a_prazo"])} de vendas a prazo com '
                      f'vencimento em {dia_previsto[:5]} ({quantos} títulos);')

    if entrada['b2b'] is not None:
        partes.append(f'· R$ {brl(entrada["b2b"])} referente a iKI Produtos '
                      f'Alimentícios – B2B.')

    partes[-1] = partes[-1].rstrip(';') + '.'  # a ultima linha fecha com ponto
    return '\n'.join(partes) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('pdf', help='PDF de vendas por forma de pagamento')
    parser.add_argument('--dia', help='usar so este dia (dd/mm/aaaa); padrao: todos somados')
    parser.add_argument('--saida', default='.', help='pasta de saida (padrao: atual)')
    parser.add_argument('--mes-anterior', dest='mes_anterior',
                        help='PDF do MESMO periodo do mes anterior, para o voucher D+30')
    parser.add_argument('--ifood', action='append', default=[], metavar='PDF',
                        help='PDF(s) cobrindo a semana seg-dom do repasse do iFood; '
                             'pode repetir a flag. So vale quando a data prevista e quarta')
    parser.add_argument('--ifood-valor', dest='ifood_valores', action='append',
                        default=[], metavar='[ROTULO=]VALOR',
                        help='repasse do iFood JA LIQUIDO, informado na mao; pode repetir '
                             '(ex.: --ifood-valor "Grupo Ragga=401827.58"). Tem precedencia '
                             'sobre --ifood')
    parser.add_argument('--b2b', type=float, help='valor do B2B da iKI, quando houver base')
    parser.add_argument('--a-prazo', dest='a_prazo', default=A_PRAZO_PADRAO,
                        help='CSV de vendas a prazo (padrao: vendas_a_prazo.csv do projeto)')
    parser.add_argument('--dia-previsto', dest='dia_previsto',
                        help='data da entrada prevista (dd/mm/aaaa); padrao: dia seguinte')
    parser.add_argument('--bruto', action='store_true',
                        help='nao aplicar taxas: entrada prevista no bruto')
    parser.add_argument('--entrada', help='JSON para forcar vendas, voucher, a_prazo ou b2b')
    args = parser.parse_args()

    dias, cnpj = ler_pdf(args.pdf)
    if not dias:
        raise SystemExit('ERRO: nenhum dia encontrado no PDF. O layout mudou?')

    if args.dia:
        if args.dia not in dias:
            raise SystemExit(f'ERRO: {args.dia} nao esta no PDF. '
                             f'Dias disponiveis: {", ".join(dias)}')
        dias = OrderedDict([(args.dia, dias[args.dia])])

    agrupado, composicao = agrupar(dias)
    total = sum(agrupado.values())
    linhas = sorted(agrupado.items(), key=lambda item: -item[1])  # maior -> menor
    dias_usados = list(dias)

    periodo = (f'{dias_usados[0]}' if len(dias_usados) == 1
               else f'{dias_usados[0][:5]} a {dias_usados[-1]}')
    subtitulo = f'Vendas de {periodo} &middot; Todas as filiais'

    os.makedirs(args.saida, exist_ok=True)
    png = os.path.join(args.saida, 'vendas_card.png')
    html = montar_html(linhas, total, subtitulo)
    if not renderizar_png(html, png):
        with open(os.path.join(args.saida, 'vendas_card.html'), 'w') as arquivo:
            arquivo.write(html)

    agrupado_anterior = None
    if args.mes_anterior:
        dias_ant, _ = ler_pdf(args.mes_anterior)
        if not dias_ant:
            raise SystemExit('ERRO: nenhum dia no PDF do mes anterior.')
        agrupado_anterior, _ = agrupar(dias_ant, 'PDF do mes anterior')
        dias_ant_usados = list(dias_ant)
        if len(dias_ant_usados) != len(dias_usados):
            print(f'AVISO: o periodo atual tem {len(dias_usados)} dia(s) e o do mes '
                  f'anterior {len(dias_ant_usados)}. O voucher D+30 fica desproporcional.',
                  file=sys.stderr)

    if args.dia_previsto:
        dia_previsto = args.dia_previsto
    else:  # dia seguinte ao ultimo do relatorio, respeitando virada de mes
        ultimo = datetime.datetime.strptime(dias_usados[-1], '%d/%m/%Y').date()
        dia_previsto = (ultimo + datetime.timedelta(days=1)).strftime('%d/%m/%Y')

    janela = janela_ifood(dia_previsto)
    ifood_manual = ler_ifood_manual(args.ifood_valores)
    ifood, ifood_faltando = None, []
    if ifood_manual and args.ifood:
        print('AVISO: --ifood-valor tem precedencia; os PDFs de --ifood foram ignorados.',
              file=sys.stderr)
    elif ifood_manual:
        pass
    elif args.ifood and janela is None:
        print(f'AVISO: {dia_previsto} nao e quarta-feira, entao nao ha repasse de '
              f'iFood nesse dia. Os PDFs de --ifood foram ignorados.', file=sys.stderr)
    elif args.ifood:
        ifood, ifood_faltando = somar_ifood(args.ifood, janela)
        if ifood_faltando:
            print(f'AVISO: faltam dias na janela do iFood '
                  f'({janela[0]:%d/%m} a {janela[1]:%d/%m}): '
                  f'{", ".join(f"{d:%d/%m}" for d in ifood_faltando)}. '
                  f'O repasse esta SUBESTIMADO.', file=sys.stderr)
    elif janela is not None:
        print(f'AVISO: {dia_previsto} e quarta-feira, entao tem repasse de iFood '
              f'de {janela[0]:%d/%m} a {janela[1]:%d/%m}. Informe o valor em '
              f'--ifood-valor (o Cloudfy nao serve para isso).', file=sys.stderr)

    titulos = ler_a_prazo(args.a_prazo)
    override = json.load(open(args.entrada)) if args.entrada else None
    entrada = calcular_entrada(agrupado, agrupado_anterior, titulos, dia_previsto,
                               ifood, args.b2b, override, liquido=not args.bruto,
                               ifood_manual=ifood_manual)
    entrada['janela_ifood'] = janela

    txt = os.path.join(args.saida, 'texto_whatsapp.txt')
    with open(txt, 'w') as arquivo:
        arquivo.write(montar_texto(dias_usados, total, entrada, dia_previsto))

    csv = os.path.join(args.saida, 'formas_agrupadas.csv')
    with open(csv, 'w') as arquivo:
        arquivo.write('FORMA DE PAGAMENTO;TOTAL;% DO TOTAL;COMPOSICAO\n')
        for forma, valor in sorted(agrupado.items(), key=lambda item: -item[1]):
            partes = composicao[forma]
            comp = (' + '.join(f'{s} R$ {brl(v)}'
                               for s, v in sorted(partes.items(), key=lambda i: -i[1]))
                    if len(partes) > 1 else '')
            arquivo.write(f'{forma};{brl(valor)};{brl(valor / total * 100)};{comp}\n')
        arquivo.write(f'TOTAL GERAL;{brl(total)};100,00;\n')

    print(f'Dias no PDF: {", ".join(dias_usados)}')
    for dia, formas in dias.items():
        print(f'  {dia}: R$ {brl(sum(formas.values()))}')
    print(f'\n{len(linhas)} linhas apos o agrupamento | VENDA BRUTA R$ {brl(total)}')

    rotulo = 'BRUTA' if args.bruto else 'LIQUIDA (estimativa)'
    print(f'\nENTRADA PREVISTA PARA {dia_previsto} -- {rotulo}')
    print(f'  {"":28} {"bruto":>14} {"taxa":>7} {"liquido":>14}')
    for forma, bruto, taxa, liq in entrada['detalhe_vendas']:
        print(f'  {forma:<28} {brl(bruto):>14} {brl(taxa * 100)+"%":>7} {brl(liq):>14}')
    print(f'  {"= cartao + pix":<28} {"":>14} {"":>7} {brl(entrada["vendas"]):>14}')

    if agrupado_anterior is None:
        print('  voucher D+30                 FALTA --mes-anterior')
    else:
        print(f'  voucher D+30 ({dias_ant_usados[0]} a {dias_ant_usados[-1]})')
        bruto_voucher = sum(agrupado_anterior.get(f, 0.0) for f in FORMAS_VOUCHER)
        for forma in FORMAS_VOUCHER:
            if forma in agrupado_anterior:
                print(f'    {forma:<26} {brl(agrupado_anterior[forma]):>14}')
        print(f'  {"= voucher D+30":<28} {brl(bruto_voucher):>14} '
              f'{brl(entrada["taxa_voucher"] * 100)+"%":>7} {brl(entrada["voucher"]):>14}')

    if entrada['ifood'] is None:
        print('  repasse iFood                '
              + ('nao e quarta-feira' if janela is None else 'FALTA --ifood'))
    elif entrada['ifood_manual']:
        print(f'  repasse iFood (na mao, ja liquido)')
        for rotulo, valor in entrada['ifood_manual']:
            print(f'    {rotulo:<26} {"":>14} {"":>7} {brl(valor):>14}')
        print(f'  {"= repasse iFood":<28} {"":>14} {"":>7} {brl(entrada["ifood"]):>14}')
        if janela is not None:
            print(f'    referente a {janela[0]:%d/%m} a {janela[1]:%d/%m}')
    else:
        print(f'  {"repasse iFood":<28} {brl(entrada["ifood_bruto"]):>14} '
              f'{brl(entrada["taxa_ifood"] * 100)+"%":>7} {brl(entrada["ifood"]):>14}')
        print(f'    {janela[0]:%d/%m} a {janela[1]:%d/%m}'
              + (f', faltam {len(ifood_faltando)} dia(s)' if ifood_faltando else ''))

    if entrada['a_prazo'] is None:
        proximos = sorted({t['vencimento'] for t in titulos})
        print(f'  vendas a prazo               nenhum titulo vence em {dia_previsto}')
        if proximos:
            print(f'    proximos vencimentos: {", ".join(proximos)}')
    else:
        print(f'  {"vendas a prazo":<28} R$ {brl(entrada["a_prazo"]):>13} '
              f'({len(entrada["titulos_a_prazo"])} titulos)')

    print(f'  {"B2B iKI":<28} '
          f'{"SEM BASE" if entrada["b2b"] is None else "R$ " + brl(entrada["b2b"])}')
    print(f'  {"TOTAL PREVISTO":<28} {"":>14} {"":>7} {brl(entrada["total"]):>14}')

    print(f'\nGerado:\n  {png}\n  {txt}\n  {csv}')


if __name__ == '__main__':
    main()
