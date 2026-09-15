# Painel Sangria x Extrato

Página única, sem servidor: tudo roda no navegador de quem abre. Os arquivos
que a pessoa sobe **não saem do computador dela** — a leitura do `.xlsx` é
feita ali mesmo, e o que fica guardado (arquivos lidos, flags, observações,
vínculos de loja) vive no `localStorage` daquele navegador.

## Publicar no GitHub Pages

1. No repositório: **Settings → Pages**
2. Em *Build and deployment · Source*, escolher **Deploy from a branch**
3. Branch: `main` · pasta `/ (root)` — e salvar

O endereço fica `https://hylaryfarias.github.io/relatorio-diario/painel/`.

Para ficar só `https://hylaryfarias.github.io/relatorio-diario/`, mover o
`painel/index.html` para a raiz do repositório.

## Dependências

- **SheetJS** (leitura de xlsx) vem do cdnjs, versão fixada em 0.18.5.
- **Instrument Sans** vem do Google Fonts.
- As quatro logos estão embutidas no HTML como data URI — nada carrega de fora.

## O que falta

A **Dotties Vanilla Heavy** (display, só no H1) é da Lost Type e não está no
Google Fonts. Enquanto o arquivo não for embutido como `@font-face` data URI,
o H1 cai em Instrument Sans 700. O CSS já aponta para ela em `--display`.
