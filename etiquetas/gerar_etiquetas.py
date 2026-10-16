#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera as folhas de QR da Coleta de Campo (FIS/IPÊ, Projeto Amazônia Bee):

  acesso-android-ios.pdf        uma folha A4 com o QR de instalação no Android (APK) e o de acesso no
                                iPhone (aplicativo web), com os passos de cada um
  etiquetas-colonias-kits.pdf   etiquetas para colar nas colmeias (G01-C1 a G04-C4, pares P01 a P08) e
                                nos kits (K01 a K12); o aplicativo lê em Hoje → Ler etiqueta QR

Conteúdo das etiquetas: "CCAMPO:COL:G01-C2" (colônia) e "CCAMPO:KIT:K01" (kit), com correção de erro
alta (nível H), para continuar legível com sujeira ou desgaste.

Uso:  python gerar_etiquetas.py [--saida pasta] [--kits 12] [--pares 8]
Requer: pip install segno reportlab
"""
import argparse
import os
from pathlib import Path

import segno
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

URL_APK = "https://github.com/andersonsakuma/beemeter-coleta/releases/latest/download/coleta-de-campo.apk"
URL_WEB = "https://andersonsakuma.github.io/beemeter-coleta/"
GRUPOS = [("G01", "M. interrupta", "Rio/igapó"), ("G02", "M. interrupta", "Terra firme"),
          ("G03", "M. seminigra", "Rio/igapó"), ("G04", "M. seminigra", "Terra firme")]
VERDE = HexColor("#2B654A")
TINTA = HexColor("#15231C")
CINZA = HexColor("#67776D")
LINHA = HexColor("#C2CDC4")


def fontes():
    """DejaVu (Linux) ou Arial (Windows); sem nenhuma, usa Helvetica."""
    candidatos = [("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
                  (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
                  ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf")]
    for normal, negrito in candidatos:
        if os.path.exists(normal) and os.path.exists(negrito):
            pdfmetrics.registerFont(TTFont("Texto", normal))
            pdfmetrics.registerFont(TTFont("Texto-B", negrito))
            return "Texto", "Texto-B"
    return "Helvetica", "Helvetica-Bold"


F, FB = fontes()


def qr(c, conteudo, x, y, lado, erro="h"):
    """Desenha o QR com quadrados (vetorial, imprime nítido em qualquer tamanho). (x, y) = canto inferior esquerdo."""
    q = segno.make(conteudo, error=erro, micro=False)
    m = q.matrix
    n = len(m) + 8                      # 4 módulos de margem de cada lado
    mod = lado / n
    c.setFillColor(white)
    c.rect(x, y, lado, lado, stroke=0, fill=1)
    c.setFillColor(TINTA)
    for i, linha in enumerate(m):
        for j, v in enumerate(linha):
            if v:
                c.rect(x + (j + 4) * mod, y + lado - (i + 5) * mod, mod * 1.02, mod * 1.02, stroke=0, fill=1)


def marca(c, x, y, s=1.0):
    """Hexágono da marca IPÊ/FIS com a marca de conferência."""
    import math
    c.saveState()
    c.setStrokeColor(VERDE)
    c.setLineWidth(1.6 * s)
    def hexa(r):
        p = c.beginPath()
        for k in range(7):
            a = math.radians(-90 + 60 * k)
            px, py = x + r * math.cos(a), y - r * math.sin(a)
            (p.moveTo if k == 0 else p.lineTo)(px, py)
        return p
    c.drawPath(hexa(8 * s), stroke=1, fill=0)
    c.setLineWidth(1.1 * s)
    c.drawPath(hexa(4.6 * s), stroke=1, fill=0)
    c.setLineWidth(1.3 * s)
    c.line(x - 2.2 * s, y - 0.1 * s, x - 0.6 * s, y - 1.7 * s)
    c.line(x - 0.6 * s, y - 1.7 * s, x + 2.4 * s, y + 1.6 * s)
    c.restoreState()


def folha_acesso(arq):
    c = canvas.Canvas(str(arq), pagesize=A4)
    W, H = A4
    c.setTitle("Coleta de Campo — instalação no Android e no iPhone")
    c.setAuthor("Anderson Cardoso Sakuma — IPÊ/FIS")
    marca(c, 22 * mm, H - 22 * mm, 1.6)
    c.setFillColor(TINTA); c.setFont(FB, 20); c.drawString(36 * mm, H - 24 * mm, "Coleta de Campo")
    c.setFillColor(CINZA); c.setFont(F, 10.5)
    c.drawString(36 * mm, H - 30 * mm, "Experimento de meliponicultura · Cametá do Ramos · IPÊ/FIS · Projeto Amazônia Bee")
    c.setStrokeColor(VERDE); c.setLineWidth(1.2); c.line(15 * mm, H - 36 * mm, W - 15 * mm, H - 36 * mm)

    colunas = [
        ("ANDROID", "Aplicativo (APK)", URL_APK, "github.com/andersonsakuma/beemeter-coleta/releases", [
            "Aponte a câmera para o QR e abra o link.",
            "Baixe o arquivo coleta-de-campo.apk.",
            "Toque no arquivo. Na primeira vez, permita instalar apps desta origem.",
            "Abra Coleta de Campo.",
        ], "Android 7.0 ou superior. Não usa internet."),
        ("IPHONE", "Aplicativo web", URL_WEB, "andersonsakuma.github.io/beemeter-coleta", [
            "Aponte a câmera para o QR e abra no Safari.",
            "Toque em Compartilhar (quadrado com seta).",
            "Toque em Adicionar à Tela de Início → Adicionar.",
            "Abra sempre pelo ícone Coleta na tela de início.",
        ], "Abra uma vez com internet; depois funciona sem sinal."),
    ]
    larg = (W - 30 * mm - 10 * mm) / 2
    base = 96 * mm
    for k, (plat, tipo, url, url_curta, passos, nota) in enumerate(colunas):
        x0 = 15 * mm + k * (larg + 10 * mm)
        topo = H - 46 * mm
        c.setStrokeColor(LINHA); c.setLineWidth(0.8); c.roundRect(x0, base, larg, topo - base, 4 * mm, stroke=1, fill=0)
        c.setFillColor(VERDE); c.setFont(FB, 11); c.drawString(x0 + 7 * mm, topo - 9 * mm, plat)
        c.setFillColor(TINTA); c.setFont(FB, 16); c.drawString(x0 + 7 * mm, topo - 17 * mm, tipo)
        lado = larg - 24 * mm
        qr(c, url, x0 + (larg - lado) / 2, topo - 22 * mm - lado, lado, erro="m")
        y = topo - 30 * mm - lado
        c.setFont(F, 10.5)
        for i, p in enumerate(passos, 1):
            c.setFillColor(VERDE); c.setFont(FB, 10.5); c.drawString(x0 + 7 * mm, y, f"{i}.")
            c.setFillColor(TINTA); c.setFont(F, 10.5)
            linhas = quebrar(p, F, 10.5, larg - 20 * mm)
            for ln in linhas:
                c.drawString(x0 + 13 * mm, y, ln); y -= 5.2 * mm
            y -= 1.4 * mm
        c.setFillColor(CINZA); c.setFont(F, 9)
        for ln in quebrar(nota, F, 9, larg - 14 * mm):
            c.drawString(x0 + 7 * mm, y - 1 * mm, ln); y -= 4.4 * mm
        c.setFont(F, 8)
        c.drawString(x0 + 7 * mm, base + 4 * mm, url_curta)

    c.setFillColor(TINTA); c.setFont(FB, 11.5); c.drawString(15 * mm, 84 * mm, "Depois de instalar")
    c.setFont(F, 10.5)
    itens = ["Informe o seu nome em Enviar → Este aparelho: ele vai em todas as fichas.",
             "Na colmeia, use Hoje → Ler etiqueta QR: a ficha abre já com a colônia ou o kit.",
             "Todo mês, toque em Enviar planilha e mande para a coordenação."]
    y = 77 * mm
    for t in itens:
        c.setFillColor(VERDE); c.circle(17 * mm, y + 1.2 * mm, 0.9 * mm, stroke=0, fill=1)
        c.setFillColor(TINTA); c.drawString(21 * mm, y, t); y -= 6 * mm
    c.setFillColor(CINZA); c.setFont(F, 8)
    c.drawString(15 * mm, 14 * mm, "https://github.com/andersonsakuma/beemeter-coleta · FIS/IPÊ")
    c.showPage(); c.save()


def quebrar(texto, fonte, tam, largura):
    palavras, linhas, atual = texto.split(), [], ""
    for p in palavras:
        teste = (atual + " " + p).strip()
        if pdfmetrics.stringWidth(teste, fonte, tam) <= largura:
            atual = teste
        else:
            linhas.append(atual); atual = p
    if atual:
        linhas.append(atual)
    return linhas


def etiquetas(arq, n_kits=12, n_pares=8):
    itens = []
    for g, esp, amb in GRUPOS:
        for i in range(1, 5):
            itens.append(("COL", f"{g}-C{i}", "COLÔNIA", f"{esp} · {amb}"))
    for p in range(1, n_pares + 1):
        for i in (1, 2):
            itens.append(("COL", f"P{p:02d}-C{i}", "COLÔNIA · PAR ADICIONAL", "espécie: _____________"))
    for k in range(1, n_kits + 1):
        itens.append(("KIT", f"K{k:02d}", "KIT DE MONITORAMENTO", "colônia: _____________"))
    c = canvas.Canvas(str(arq), pagesize=A4)
    c.setTitle("Coleta de Campo — etiquetas QR das colônias e dos kits")
    c.setAuthor("Anderson Cardoso Sakuma — IPÊ/FIS")
    W, H = A4
    cols, linhas = 2, 5
    mx, my = 10 * mm, 12 * mm
    lw, lh = (W - 2 * mx) / cols, (H - 2 * my) / linhas
    for n, (tipo, cod, rotulo, sub) in enumerate(itens):
        pos = n % (cols * linhas)
        if n and pos == 0:
            c.showPage()
        if pos == 0:
            c.setFillColor(CINZA); c.setFont(F, 7.5)
            c.drawString(mx, H - 7 * mm, "Coleta de Campo · etiquetas QR · recortar nas linhas · plastificar ou usar papel adesivo à prova d'água")
        col, lin = pos % cols, pos // cols
        x, y = mx + col * lw, H - my - (lin + 1) * lh
        c.setStrokeColor(LINHA); c.setDash(2, 2); c.setLineWidth(0.5); c.rect(x, y, lw, lh, stroke=1, fill=0); c.setDash()
        lado = lh - 10 * mm
        qr(c, f"CCAMPO:{tipo}:{cod}", x + 5 * mm, y + 5 * mm, lado)
        tx = x + 9 * mm + lado
        c.setFillColor(VERDE); c.setFont(FB, 7.5); c.drawString(tx, y + lh - 11 * mm, rotulo)
        c.setFillColor(TINTA); c.setFont(FB, 25 if len(cod) <= 6 else 21); c.drawString(tx, y + lh - 22 * mm, cod)
        c.setFillColor(TINTA); c.setFont(F, 8.5); c.drawString(tx, y + lh - 29 * mm, sub)
        marca(c, tx + 3.4 * mm, y + 9.5 * mm, 0.62)
        c.setFillColor(CINZA); c.setFont(F, 7)
        c.drawString(tx + 8 * mm, y + 10.5 * mm, "Coleta de Campo · IPÊ/FIS")
        c.drawString(tx + 8 * mm, y + 7.2 * mm, "Hoje → Ler etiqueta QR")
    c.showPage(); c.save()
    return len(itens)


def main():
    ap = argparse.ArgumentParser(description="QR de acesso e etiquetas da Coleta de Campo")
    ap.add_argument("--saida", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--kits", type=int, default=12)
    ap.add_argument("--pares", type=int, default=8)
    a = ap.parse_args()
    out = Path(a.saida); out.mkdir(parents=True, exist_ok=True)
    folha_acesso(out / "acesso-android-ios.pdf")
    n = etiquetas(out / "etiquetas-colonias-kits.pdf", a.kits, a.pares)
    print(f"Gerados em {out}: acesso-android-ios.pdf e etiquetas-colonias-kits.pdf ({n} etiquetas)")


if __name__ == "__main__":
    main()
