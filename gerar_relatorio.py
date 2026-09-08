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


def agrupar(dias):
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
        print(f'AVISO: formas de GRUPOS ausentes neste PDF: {", ".join(ignorados)}',
              file=sys.stderr)

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


def montar_texto(dias_usados, total, entrada):
    """Texto pronto para colar no WhatsApp."""
    primeiro, ultimo = dias_usados[0], dias_usados[-1]
    dia_a, mes_a, ano_a = (int(p) for p in ultimo.split('/'))
    proximo = f'{dia_a + 1:02d}/{mes_a:02d}'  # ajuste na mao se cair virada de mes

    if primeiro == ultimo:
        cabecalho = f'📊 *VENDA BRUTA DO DIA | {primeiro[:5]}*'
    else:
        cabecalho = f'📊 *VENDA BRUTA | {primeiro[:5]} a {ultimo[:5]}*'

    partes = [cabecalho, '', f'R$ {brl(total)}', '',
              f'💰 *ENTRADA PREVISTA PRO DIA {proximo}*', '']

    if entrada:
        vendas = entrada.get('vendas_dia')
        anteriores = entrada.get('periodos_anteriores')
        b2b = entrada.get('b2b')
        itens = [v for v in (vendas, anteriores, b2b) if v is not None]
        soma = entrada.get('total') or (sum(itens) if itens else None)
        partes += [f'*R$ {brl(soma)}*' if soma is not None else '*R$ [PREENCHER]*', '']
        if vendas is not None:
            partes.append(f'· R$ {brl(vendas)} são referentes às vendas do dia '
                          f'(Crédito, Débito e Pix);')
        if anteriores is not None:
            partes.append(f'· R$ {brl(anteriores)} de recebimento de períodos '
                          f'anteriores (Voucher D+30);')
        if b2b is not None:
            partes.append(f'· R$ {brl(b2b)} referente a iKI Produtos Alimentícios – B2B.')
    else:
        partes += ['*R$ [PREENCHER]*', '',
                   '· R$ [PREENCHER] são referentes às vendas do dia (Crédito, Débito e Pix);',
                   '· R$ [PREENCHER] de recebimento de períodos anteriores (Voucher D+30);',
                   '· R$ [PREENCHER] referente a iKI Produtos Alimentícios – B2B.']

    return '\n'.join(partes) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('pdf', help='PDF de vendas por forma de pagamento')
    parser.add_argument('--dia', help='usar so este dia (dd/mm/aaaa); padrao: todos somados')
    parser.add_argument('--saida', default='.', help='pasta de saida (padrao: atual)')
    parser.add_argument('--entrada', help='JSON com vendas_dia, periodos_anteriores e b2b')
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

    entrada = json.load(open(args.entrada)) if args.entrada else None
    txt = os.path.join(args.saida, 'texto_whatsapp.txt')
    with open(txt, 'w') as arquivo:
        arquivo.write(montar_texto(dias_usados, total, entrada))

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
    print(f'\n{len(linhas)} linhas apos o agrupamento | TOTAL R$ {brl(total)}')
    print(f'\nGerado:\n  {png}\n  {txt}\n  {csv}')


if __name__ == '__main__':
    main()
