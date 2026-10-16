# Coleta de Campo — iPhone e iPad

O mesmo `index.html` da coleta, instalado como **aplicativo web** a partir do GitHub Pages: ícone na
tela de início, tela cheia e funcionamento sem internet depois da primeira abertura. Não passa pela
App Store e não precisa de conta de desenvolvedor da Apple.

## Instalar

Escaneie com a câmera do iPhone:

![QR de acesso](qr-acesso.png)

Link direto: <https://andersonsakuma.github.io/beemeter-coleta/>

1. Abra o link no **Safari** (com internet, só desta vez).
2. Toque em **Compartilhar** (quadrado com seta para cima).
3. Toque em **Adicionar à Tela de Início** → **Adicionar**.
4. Abra sempre pelo ícone **Coleta** e informe o seu nome em **Enviar → Este aparelho**.

Requer iOS 15 ou superior.

## Importante no iPhone

- **Use sempre pelo ícone.** Os dados do aplicativo instalado e os da aba do Safari ficam separados.
  Pelo ícone, o iOS não aplica a limpeza automática que o Safari faz em sites sem uso por 7 dias.
- **Envio dos arquivos:** a planilha, as fotos e a cópia de segurança saem pelo menu **Compartilhar**
  do iOS (WhatsApp, Arquivos, AirDrop, e-mail). **Salvar no aparelho** grava em **Arquivos**.
- **Etiquetas QR:** em **Hoje → Ler etiqueta QR** a câmera lê a etiqueta da colmeia ao vivo; a primeira vez
  o iOS pede permissão de câmera.
- **GPS e fotos** funcionam como no Android; o iOS pede permissão na primeira vez.
- Desinstalar (remover o ícone) apaga os registros: faça **Enviar → Salvar cópia** antes.

## Como funciona

- `manifest.webmanifest` e `apple-touch-icon.png` (raiz do repositório) dão nome, ícone e tela cheia.
- `sw.js` guarda a página no aparelho: com sinal, busca a versão nova; sem sinal, usa a guardada.
  Os registros não passam por ele — ficam no armazenamento do próprio aplicativo.
- Toda atualização publicada no `main` chega ao iPhone na próxima abertura com internet.
