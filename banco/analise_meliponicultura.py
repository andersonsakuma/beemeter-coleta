#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise estatística do experimento de meliponicultura — Cametá do Ramos (FIS/IPÊ)
Anexo 05b. Autor: Anderson Cardoso Sakuma — versão 1.1, outubro de 2026 (lê as planilhas do app Coleta de Campo).

Compara caixas/melgueiras NOVAS (tecnologia implantada) com ANTIGAS (colônias-controle)
dentro de cada meliponário e estima o ganho das ações locais.

Uso (Windows: troque "python3" por "python"):
    python3 analise_meliponicultura.py poder
        Tabela de poder do estudo por simulação (efeito mínimo detectável).
    python3 analise_meliponicultura.py simular --saida teste
        Gera dados fictícios no formato da planilha (Anexo 05a) e dos arquivos dos kits,
        para testar a análise antes de existirem dados reais.
    python3 analise_meliponicultura.py analisar --planilha Anexo_05a.xlsx --kits pasta_csv --saida resultados
        Roda a análise completa. A pasta dos kits é opcional.
    python3 analise_meliponicultura.py analisar --planilha coleta-monitor1-*.xlsx coleta-monitor2-*.xlsx Anexo_05a.xlsx
        Junta as planilhas exportadas pelo aplicativo Coleta de Campo (uma por celular) e a do Anexo 05a
        (de onde vêm os parâmetros econômicos da aba F11_Ganhos). Registros repetidos entram uma vez.

Dependências: numpy, pandas, scipy, matplotlib, openpyxl (pip install ...).

Formato dos arquivos dos kits (CSV, um ou vários por kit, vírgula como separador):
    data_hora,kit,tc1_c,tc2_c,tc3_c,t_ar_c,ur_ar_pct,luz_lx,peso_g,bateria_mv
    2026-11-15T10:20:00,K01,30.25,29.50,28.75,29.8,78.5,12450,8423,3912
Leitura inválida = campo vazio (nunca zero).
"""
import argparse
import itertools
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COR_NOVA = "#2a78d6"
COR_ANTIGA = "#eb6834"
COR_GRADE = "#e4e3df"
COR_TEXTO = "#3b3a37"
ROTULO = {"NOVA": "Caixa/melgueira nova", "ANTIGA": "Caixa/melgueira antiga (controle)"}

ABAS = {
    "cad": "F01_Cadastro", "base": "F02_LinhaBase", "ocup": "F05_Ocupacao",
    "pes": "F06_PesagemAtividade", "chuva": "F07_Chuva", "manejo": "F08_Manejo",
    "extr": "F09_Extracao", "atend": "F10_Assistencia", "prat": "F10_Praticas",
    "prodass": "F10_ProducaoAssistidos", "ganhos": "F11_Ganhos",
}


# =============================================================================
# Teste de aleatorização em blocos (núcleo do estudo)
# =============================================================================
def matriz_pesos(blocos, n_ctrl_por_bloco, limite=20000, semente=1):
    """Todas as atribuições possíveis de controle dentro de cada bloco.

    blocos: lista com o rótulo do bloco de cada unidade (ordem das unidades).
    n_ctrl_por_bloco: dict bloco -> nº de controles sorteados naquele bloco.
    Devolve (W, T): W (atribuições x unidades) tal que W @ y = estatística
    (média, entre blocos, de [média das novas − média dos controles]);
    T (atribuições x unidades) com 1 = nova, 0 = controle.
    """
    blocos = list(blocos)
    rot = sorted(set(blocos))
    idx = {b: [i for i, x in enumerate(blocos) if x == b] for b in rot}
    opcoes = [list(itertools.combinations(idx[b], n_ctrl_por_bloco[b])) for b in rot]
    total = math.prod(len(o) for o in opcoes)
    if total <= limite:
        combos = itertools.product(*opcoes)
    else:
        rng = np.random.default_rng(semente)
        combos = (tuple(o[rng.integers(len(o))] for o in opcoes) for _ in range(limite))
        total = limite
    n = len(blocos)
    W = np.zeros((total, n))
    T = np.ones((total, n), dtype=np.int8)
    nb = len(rot)
    for a, comb in enumerate(combos):
        for b, ctrl in zip(rot, comb):
            ctrl = set(ctrl)
            novas = [i for i in idx[b] if i not in ctrl]
            for i in idx[b]:
                if i in ctrl:
                    W[a, i] = -1.0 / (len(ctrl) * nb)
                    T[a, i] = 0
                else:
                    W[a, i] = 1.0 / (len(novas) * nb)
    return W, T


def teste_aleatorizacao(y, trat, blocos, grade=None):
    """Efeito, valor-p exato (bicaudal) e IC 95% por inversão do teste.

    y: resposta por unidade; trat: 1 nova / 0 antiga; blocos: rótulo do bloco.
    O IC supõe efeito aditivo constante na escala de y.
    """
    y = np.asarray(y, float)
    trat = np.asarray(trat, int)
    ok = ~np.isnan(y)
    y, trat = y[ok], trat[ok]
    blocos = [b for b, k in zip(blocos, ok) if k]
    # só blocos com pelo menos uma nova e um controle
    validos = [b for b in set(blocos)
               if 0 < sum(t for t, x in zip(trat, blocos) if x == b) < sum(1 for x in blocos if x == b)]
    sel = np.array([b in validos for b in blocos])
    if sel.sum() < 2:
        return dict(efeito=np.nan, p=np.nan, ic_inf=np.nan, ic_sup=np.nan, n_blocos=len(validos), n_atrib=0)
    y, trat = y[sel], trat[sel]
    blocos = [b for b, k in zip(blocos, sel) if k]
    nctrl = {b: sum(1 for t, x in zip(trat, blocos) if x == b and t == 0) for b in set(blocos)}
    W, T = matriz_pesos(blocos, nctrl)
    # coluna observada: a linha de W que reproduz a atribuição real
    obs_w = np.array([(1.0 / (sum(1 for t2, x2 in zip(trat, blocos) if x2 == b and t2 == 1) * len(nctrl))) if t == 1
                      else (-1.0 / (nctrl[b] * len(nctrl))) for t, b in zip(trat, blocos)])
    efeito = float(obs_w @ y)

    def pval(delta):
        yy = y - delta * trat
        s_obs = obs_w @ yy
        s = W @ yy
        return float(np.mean(np.abs(s) >= abs(s_obs) - 1e-12))

    p = pval(0.0)
    if grade is None:
        amp = max(4 * np.nanstd(y), abs(efeito) * 3, 1e-6)
        grade = np.linspace(efeito - amp, efeito + amp, 801)
    aceitos = [d for d in grade if pval(d) > 0.05]
    ic_inf, ic_sup = (min(aceitos), max(aceitos)) if aceitos else (np.nan, np.nan)
    if aceitos and (ic_inf <= grade[0] + 1e-12 or ic_sup >= grade[-1] - 1e-12):
        # intervalo encostou na borda da grade: sem limite informativo
        ic_inf = -np.inf if ic_inf <= grade[0] + 1e-12 else ic_inf
        ic_sup = np.inf if ic_sup >= grade[-1] - 1e-12 else ic_sup
    return dict(efeito=efeito, p=p, ic_inf=ic_inf, ic_sup=ic_sup, n_blocos=len(nctrl), n_atrib=W.shape[0])


def _f(v, un="", casas=1):
    """Número com sinal; limite infinito = poucos meliponários para fechar o intervalo."""
    try:
        if v is None or not np.isfinite(v):
            return "sem limite"
    except TypeError:
        return "—"
    return f"{v:+.{casas}f}{un}"


def _ic(a, b, un="", casas=1):
    try:
        if not np.isfinite(a) and not np.isfinite(b):
            return "indeterminado (poucos meliponários com dados)"
    except TypeError:
        return "—"
    return f"{_f(a, un, casas)} a {_f(b, un, casas)}"


def holm(pvals):
    p = np.asarray(pvals, float)
    ordem = np.argsort(p)
    m = len(p)
    aj = np.empty(m)
    acum = 0.0
    for k, i in enumerate(ordem):
        acum = max(acum, (m - k) * p[i])
        aj[i] = min(1.0, acum)
    return aj


# =============================================================================
# Poder do estudo por simulação
# =============================================================================
def poder(reps=2000, semente=7, saida=None):
    """Efeito mínimo detectável (80% de poder, alfa 5%) na produção de mel.

    Modelo: ln(produção) = bloco + colônia + bloco×ano + efeito×nova×2027 + resíduo.
    Com a safra de 2026 como linha de base, a colônia sai da comparação; sobra o
    resíduo de um ano para o outro, cuja variância depende da correlação entre anos (rho).
    Cada desenho é uma lista de blocos (novas, antigas); o teste é o de aleatorização.
    """
    rng = np.random.default_rng(semente)
    desenhos = {
        "B: 4 × (3 novas + 1 antiga) = 16 colônias": [(3, 1)] * 4,
        "D: 4 × (3 novas + 2 antigas) = 20 colônias": [(3, 2)] * 4,
        "E: 4 × (2 novas + 2 antigas) = 16 colônias": [(2, 2)] * 4,
        "F: B + 8 pares (1 nova + 1 antiga) em meliponários assistidos = 32 colônias": [(3, 1)] * 4 + [(1, 1)] * 8,
    }
    cenarios = [(cv, rho) for cv in (0.4, 0.6, 0.8) for rho in (0.3, 0.6, None)]  # None = sem linha de base
    linhas = []
    for nome, spec in desenhos.items():
        nb = len(spec)
        blocos = [b for b, (nn, nc) in enumerate(spec) for _ in range(nn + nc)]
        trat = np.array([t for nn, nc in spec for t in [1] * nn + [0] * nc])
        W, _ = matriz_pesos(blocos, {b: nc for b, (nn, nc) in enumerate(spec)}, limite=5000, semente=semente)
        obs_w = np.array([(1.0 / (nn * nb)) if t == 1 else (-1.0 / (nc * nb))
                          for (nn, nc) in spec for t in [1] * nn + [0] * nc])
        for cv, rho in cenarios:
            s_tot = math.sqrt(math.log(1 + cv ** 2))
            sd = math.sqrt(2 * (1 - rho)) * s_tot if rho is not None else s_tot
            ruido = rng.normal(0, sd, size=(len(blocos), reps))
            ruido += rng.normal(0, 0.3, size=(nb, reps))[blocos, :]  # efeito do bloco (sai na comparação)

            def pod(delta):
                Y = ruido + delta * trat[:, None]
                s_obs = obs_w @ Y
                S = W @ Y
                p = np.mean(np.abs(S) >= np.abs(s_obs)[None, :] - 1e-12, axis=0)
                return float(np.mean(p <= 0.05))

            lo, hi = 0.0, 3.0
            if pod(hi) < 0.8:
                mde = np.inf
            else:
                for _ in range(18):
                    mid = (lo + hi) / 2
                    if pod(mid) >= 0.8:
                        hi = mid
                    else:
                        lo = mid
                mde = hi
            linhas.append(dict(desenho=nome, cv_entre_colonias=cv,
                               correlacao_entre_anos=rho if rho is not None else "sem linha de base",
                               efeito_minimo_ln=round(mde, 3),
                               efeito_minimo_pct=(round((math.exp(mde) - 1) * 100) if np.isfinite(mde) else None)))
    tab = pd.DataFrame(linhas)
    if saida:
        Path(saida).mkdir(parents=True, exist_ok=True)
        tab.to_csv(Path(saida) / "poder_efeito_minimo.csv", index=False, encoding="utf-8-sig")
    return tab


# =============================================================================
# Leitura da planilha de campo
# =============================================================================
def _ler(planilha, aba):
    try:
        df = pd.read_excel(planilha, sheet_name=aba)
    except ValueError:
        return pd.DataFrame()
    df = df.dropna(how="all")
    if df.empty:
        return df
    chave = df.iloc[:, 0]
    df = df[chave.notna() & (chave.astype(str).str.strip() != "")]
    for col in ("colonia", "meliponicultor", "kit", "grupo"):
        if col in df.columns:
            v = df[col].astype(str).str.strip().str.upper()
            df = df[~(v.str.startswith("EX-") | (v == "EXEMPLO"))]
    return df.reset_index(drop=True)


def _tempo(df):
    t = pd.Series("", index=df.index)
    for c in ("registrado_em", "editado_em"):
        if c in df.columns:
            v = df[c].fillna("").astype(str)
            t = t.where(t >= v, v)
    return t


def _juntar_cadastro(cad):
    """Uma linha por colônia; vale, campo a campo, o valor preenchido mais recente
    (cada celular cadastra as mesmas colônias e o sorteio pode ter sido feito em outro aparelho)."""
    if cad.empty or "colonia" not in cad.columns:
        return cad
    cad = cad.assign(_t=_tempo(cad)).sort_values("_t")
    linhas = []
    for _, g in cad.groupby("colonia", sort=True):
        reg = {}
        for _, r in g.iterrows():
            for k, v in r.items():
                if pd.notna(v) and str(v).strip() != "":
                    reg[k] = v
                elif k not in reg:
                    reg[k] = v
        linhas.append(reg)
    return pd.DataFrame(linhas).drop(columns="_t")


def ler_planilha(planilhas):
    """Lê uma ou mais planilhas: a do Anexo 05a e/ou as exportadas pelo aplicativo Coleta de Campo
    (uma por celular). Registros repetidos (mesmo id) entram uma vez só, na versão mais recente."""
    if isinstance(planilhas, (str, Path)):
        planilhas = [planilhas]
    d = {}
    for k, v in ABAS.items():
        if k == "ganhos":
            continue
        partes = [x for x in (_ler(p, v) for p in planilhas) if not x.empty]
        df = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
        if not df.empty and "id" in df.columns:
            com_id = df[df["id"].notna()].assign(_t=lambda x: _tempo(x)).sort_values("_t")
            com_id = com_id.drop_duplicates("id", keep="last").drop(columns="_t")
            df = pd.concat([df[df["id"].isna()], com_id], ignore_index=True)
        d[k] = df.reset_index(drop=True)
    cad = _juntar_cadastro(d["cad"])
    if cad.empty:
        sys.exit("Aba F01_Cadastro vazia: preencha o cadastro das colônias.")
    cad["tratamento"] = cad["tratamento"].astype(str).str.strip().str.upper()
    falta = cad[~cad["tratamento"].isin(["NOVA", "ANTIGA"])]
    if len(falta):
        print(f"Aviso: {len(falta)} colônia(s) sem tratamento NOVA/ANTIGA no cadastro — ficam fora das comparações.")
    d["cad"] = cad
    # parâmetros econômicos: da primeira planilha que tiver a aba F11_Ganhos preenchida
    d["par"] = {}
    for p in planilhas:
        try:
            g = pd.read_excel(p, sheet_name=ABAS["ganhos"], header=None)
        except ValueError:
            continue
        par = {}
        for _, r in g.iterrows():
            if len(r) > 3 and isinstance(r.iloc[3], str) and r.iloc[3].strip():
                par[r.iloc[3].strip()] = r.iloc[1]
        if par.get("preco_l") is not None and pd.notna(par.get("preco_l")):
            d["par"] = par
            break
        d["par"] = d["par"] or par
    return d


def ler_kits(pasta):
    arqs = sorted(Path(pasta).glob("*.csv")) if pasta else []
    if not arqs:
        return pd.DataFrame()
    df = pd.concat([pd.read_csv(a) for a in arqs], ignore_index=True)
    df["data_hora"] = pd.to_datetime(df["data_hora"], errors="coerce")
    df = df.dropna(subset=["data_hora"]).drop_duplicates(["kit", "data_hora"]).sort_values(["kit", "data_hora"])
    return df


# =============================================================================
# Indicadores
# =============================================================================
def producao(d):
    cad, ex = d["cad"], d["extr"].copy()
    if ex.empty:
        return pd.DataFrame()
    ex["safra"] = ex["safra"].astype(int)
    viva = (ex["colonia_viva"] if "colonia_viva" in ex.columns else pd.Series("S", index=ex.index))
    viva = viva.fillna("S").astype(str).str.strip().str.upper().str[:1]
    ex["mel_ml"] = pd.to_numeric(ex["mel_ml"], errors="coerce")
    ex.loc[viva == "N", "mel_ml"] = 0.0  # perda de colônia é resultado: produção zero
    tab = ex.pivot_table(index="colonia", columns="safra", values="mel_ml", aggfunc="sum")
    tab.columns = [f"mel_ml_{c}" for c in tab.columns]
    out = cad[["colonia", "grupo", "especie", "ambiente", "meliponicultor", "tratamento"]].merge(
        tab, left_on="colonia", right_index=True, how="left")
    if {"mel_ml_2026", "mel_ml_2027"} <= set(out.columns):
        a, b = out["mel_ml_2027"], out["mel_ml_2026"]
        out["razao_log"] = np.where((a > 0) & (b > 0), np.log(a.clip(lower=1e-9) / b.clip(lower=1e-9)), np.nan)
        out["variacao_ml"] = a - b
    for col in ("umidade_pct", "tempo_manejo_min", "praticidade_1a5", "sabura_g", "cerume_g"):
        if col in ex.columns:
            v = ex[ex["safra"] == ex["safra"].max()].groupby("colonia")[col].mean()
            out[col + "_final"] = out["colonia"].map(v)
    return out


def ocupacao(d):
    oc, cad = d["ocup"].copy(), d["cad"]
    if oc.empty:
        return pd.DataFrame()
    oc["data"] = pd.to_datetime(oc["data"], errors="coerce")
    base = d["base"].copy()
    if not base.empty:
        base["data"] = pd.to_datetime(base["data"], errors="coerce")
        inicio = base.groupby("colonia")["data"].min()   # mais de uma linha de base por colônia: vale a primeira
    else:
        inicio = pd.Series(dtype="datetime64[ns]")
    linhas = []
    for c, g in oc.groupby("colonia"):
        g = g.sort_values("data")
        t0 = inicio.get(c, g["data"].min())
        fim = (g["data"].max() - t0).days
        reg = dict(colonia=c)
        for nivel in (2, 4):
            atingiu = g[pd.to_numeric(g["nivel"], errors="coerce") >= nivel]
            if len(atingiu):
                reg[f"dias_ate_nivel{nivel}"] = (atingiu["data"].iloc[0] - t0).days
                reg[f"evento_nivel{nivel}"] = 1
            else:
                reg[f"dias_ate_nivel{nivel}"] = fim
                reg[f"evento_nivel{nivel}"] = 0
        linhas.append(reg)
    return cad[["colonia", "grupo", "tratamento"]].merge(pd.DataFrame(linhas), on="colonia", how="left")


def kaplan_meier(tempos, eventos):
    t = np.asarray(tempos, float)
    e = np.asarray(eventos, int)
    ordem = np.argsort(t)
    t, e = t[ordem], e[ordem]
    xs, ys, s = [0.0], [1.0], 1.0
    for tt in np.unique(t[e == 1]):
        em_risco = np.sum(t >= tt)
        d = np.sum((t == tt) & (e == 1))
        s *= 1 - d / em_risco
        xs.append(tt)
        ys.append(s)
    mediana = next((x for x, y in zip(xs, ys) if y <= 0.5), np.nan)
    return np.array(xs), np.array(ys), mediana


def pesagens(d):
    pe = d["pes"].copy()
    if pe.empty:
        return pd.DataFrame()
    pe["data"] = pd.to_datetime(pe["data"], errors="coerce")
    pe["peso_kg"] = pd.to_numeric(pe["peso_kg"], errors="coerce")
    linhas = []
    for c, g in pe.dropna(subset=["peso_kg"]).groupby("colonia"):
        if g["data"].nunique() >= 3:
            x = (g["data"] - g["data"].min()).dt.days / 30.44
            inc = stats.linregress(x, g["peso_kg"] * 1000).slope
            linhas.append(dict(colonia=c, ganho_peso_g_mes=inc,
                               entradas_5min_media=(pd.to_numeric(g["entradas_5min"], errors="coerce").mean()
                                                    if "entradas_5min" in g else np.nan)))
    return pd.DataFrame(linhas)


def termicos(kits, d):
    """Indicadores diários por colônia a partir dos arquivos dos kits."""
    if kits.empty:
        return pd.DataFrame(), pd.DataFrame()
    cad = d["cad"]
    ck = cad.dropna(subset=["kit"])
    mapa = dict(zip(ck["kit"].astype(str).str.strip(), ck["colonia"]))
    kits = kits.copy()
    kits["colonia"] = kits["kit"].astype(str).map(mapa)
    kits = kits.dropna(subset=["colonia"])
    man = d["manejo"].copy()
    dias_manejo = set()
    if not man.empty:
        man["data"] = pd.to_datetime(man["data"], errors="coerce").dt.normalize()
        for _, r in man.iterrows():
            for k in (-1, 0, 1):  # dia anterior, do dia e seguinte ficam fora do ganho de peso
                dias_manejo.add((r["colonia"], r["data"] + pd.Timedelta(days=k)))
    diarios = []
    for c, g in kits.groupby("colonia"):
        g = g.set_index("data_hora").sort_index()
        g = g[["tc1_c", "tc3_c", "t_ar_c", "peso_g"]].apply(pd.to_numeric, errors="coerce")
        g = g.resample("10min").mean()
        for dia, h in g.groupby(g.index.normalize()):
            if h["tc1_c"].notna().sum() < 100 or h["t_ar_c"].notna().sum() < 100:
                continue  # dia com menos de ~70 % das leituras
            amp_ar = h["t_ar_c"].max() - h["t_ar_c"].min()
            amp_tc1 = h["tc1_c"].max() - h["tc1_c"].min()
            # atraso: defasagem (0 a 6 h) que maximiza a correlação ar → ninho
            a = h["t_ar_c"].interpolate(limit=3)
            b = h["tc1_c"].interpolate(limit=3)
            melhor, atraso = -2, np.nan
            for lag in range(0, 37):
                r = a.corr(b.shift(-lag))
                if pd.notna(r) and r > melhor:
                    melhor, atraso = r, lag * 10 / 60
            madrugada = h.between_time("03:00", "05:00")["peso_g"].mean()
            diarios.append(dict(colonia=c, dia=dia, amortecimento=amp_tc1 / amp_ar if amp_ar > 0.5 else np.nan,
                                atraso_h=atraso if melhor > 0.3 else np.nan,
                                excesso_c=(h["tc1_c"] - h["t_ar_c"]).mean(),
                                gradiente_c=(h["tc3_c"] - h["tc1_c"]).mean(),
                                tc1_media_c=h["tc1_c"].mean(), peso_madrugada_g=madrugada,
                                manejo=(c, dia) in dias_manejo))
    dia = pd.DataFrame(diarios)
    if dia.empty:
        return dia, pd.DataFrame()
    dia = dia.sort_values(["colonia", "dia"])
    dia["ganho_liquido_g_dia"] = dia.groupby("colonia")["peso_madrugada_g"].shift(-1) - dia["peso_madrugada_g"]
    proximo_dia = dia.groupby("colonia")["dia"].shift(-1)
    dia.loc[(proximo_dia - dia["dia"]).dt.days != 1, "ganho_liquido_g_dia"] = np.nan
    dia.loc[dia["manejo"], "ganho_liquido_g_dia"] = np.nan
    col = ["amortecimento", "atraso_h", "excesso_c", "gradiente_c", "tc1_media_c", "ganho_liquido_g_dia"]
    resumo = dia.groupby("colonia")[col].mean().reset_index()
    resumo["dias_validos"] = dia.groupby("colonia").size().values
    return dia, cad[["colonia", "grupo", "tratamento"]].merge(resumo, on="colonia", how="inner")


def praticas(d):
    pr = d["prat"].copy()
    if pr.empty:
        return pd.DataFrame(), {}
    itens = [c for c in pr.columns if str(c).startswith("p") and str(c)[1:].isdigit()]
    pr["indice_calc"] = pr[itens].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)
    pr["momento"] = pr["momento"].astype(str).str.upper().str.strip()
    tab = pr.pivot_table(index="meliponicultor", columns="momento", values="indice_calc", aggfunc="mean")
    res = {}
    if {"ANTES", "DEPOIS"} <= set(tab.columns):
        tab = tab.dropna(subset=["ANTES", "DEPOIS"])
        dif = tab["DEPOIS"] - tab["ANTES"]
        res = dict(n=len(dif), media_antes=tab["ANTES"].mean(), media_depois=tab["DEPOIS"].mean(),
                   ganho_medio=dif.mean())
        if len(dif) >= 5 and (dif != 0).any():
            res["p_wilcoxon"] = float(stats.wilcoxon(dif).pvalue)
    return tab.reset_index(), res


def assistidos(d):
    pa = d["prodass"].copy()
    if pa.empty:
        return pd.DataFrame(), {}
    pa["safra"] = pd.to_numeric(pa["safra"], errors="coerce")
    pa["l_col"] = pd.to_numeric(pa["producao_total_l"], errors="coerce") / pd.to_numeric(pa["colonias_produtivas"], errors="coerce")
    tab = pa.pivot_table(index="meliponicultor", columns="safra", values="l_col", aggfunc="mean")
    res = {}
    anos = sorted(tab.columns)
    if len(anos) >= 2:
        a0, a1 = anos[0], anos[-1]
        t = tab.dropna(subset=[a0, a1])
        t = t[(t[a0] > 0) & (t[a1] > 0)]
        if len(t):
            r = np.log(t[a1] / t[a0])
            res = dict(n=len(t), ano_inicial=a0, ano_final=a1, l_col_inicial=t[a0].mean(), l_col_final=t[a1].mean(),
                       variacao_pct=(math.exp(r.mean()) - 1) * 100)
            if len(r) >= 5:
                res["p_wilcoxon"] = float(stats.wilcoxon(r).pvalue)
    return tab.reset_index(), res


# =============================================================================
# Ganhos econômicos
# =============================================================================
def ganhos(efeito_pct, ic, prod_antiga_l, dif_tempo_min, par):
    preco = float(par.get("preco_l", np.nan) or np.nan)
    custo = float(par.get("custo_tecnologia", np.nan) or np.nan)
    vida = float(par.get("vida_util_anos", np.nan) or np.nan)
    hora = float(par.get("valor_hora", 0) or 0)
    ncol = float(par.get("colonias_associacao", np.nan) or np.nan)
    linhas = []
    for nome, pct in (("pessimista (IC inferior)", ic[0]), ("central", efeito_pct), ("otimista (IC superior)", ic[1])):
        if pct is None or not np.isfinite(pct):
            continue
        dl = prod_antiga_l * pct / 100
        ganho = dl * preco + (-(dif_tempo_min or 0) / 60) * hora
        anual = custo / vida if vida else np.nan
        linhas.append(dict(cenario=nome, aumento_pct=pct, ganho_l_colonia_ano=dl, ganho_rs_colonia_ano=ganho,
                           custo_anual_rs=anual, beneficio_liquido_rs=ganho - anual,
                           relacao_beneficio_custo=ganho / anual if anual else np.nan,
                           retorno_anos=custo / ganho if ganho > 0 else np.nan,
                           beneficio_associacao_rs_ano=(ganho - anual) * ncol))
    eq = (custo / vida - (-(dif_tempo_min or 0) / 60) * hora) / preco if preco and vida else np.nan
    return pd.DataFrame(linhas), eq


# =============================================================================
# Gráficos
# =============================================================================
def _estilo(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(COR_GRADE)
    ax.grid(axis="y", color=COR_GRADE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=COR_TEXTO, labelsize=9)


def graf_producao(prod, arq):
    if "razao_log" not in prod:
        return
    p = prod.dropna(subset=["razao_log"])
    grupos = sorted(p["grupo"].unique())
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, g in enumerate(grupos):
        for trat, cor, dx in (("NOVA", COR_NOVA, -0.12), ("ANTIGA", COR_ANTIGA, 0.12)):
            v = (np.exp(p[(p["grupo"] == g) & (p["tratamento"] == trat)]["razao_log"]) - 1) * 100
            ax.scatter([i + dx] * len(v), v, s=60, color=cor, edgecolor="white", linewidth=1.5, zorder=3,
                       label=ROTULO[trat] if i == 0 else None)
    ax.axhline(0, color="#9b9a95", linewidth=1)
    ax.set_xticks(range(len(grupos)), grupos)
    ax.set_ylabel("Variação da produção 2027 × 2026 (%)", color=COR_TEXTO)
    ax.set_title("Produção de mel por colônia, por meliponário", loc="left", color=COR_TEXTO, fontsize=11)
    _estilo(ax)
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0, -0.12), ncol=2)
    fig.tight_layout()
    fig.savefig(arq, dpi=150)
    plt.close(fig)


def graf_ocupacao(oc, arq):
    if oc.empty or "dias_ate_nivel2" not in oc:
        return
    fig, ax = plt.subplots(figsize=(7, 4))
    for trat, cor in (("NOVA", COR_NOVA), ("ANTIGA", COR_ANTIGA)):
        g = oc[oc["tratamento"] == trat].dropna(subset=["dias_ate_nivel2"])
        if len(g) == 0:
            continue
        x, y, _ = kaplan_meier(g["dias_ate_nivel2"], g["evento_nivel2"])
        ax.step(x, (1 - y) * 100, where="post", color=cor, linewidth=2, label=ROTULO[trat])
    ax.set_xlabel("Dias desde a troca das melgueiras", color=COR_TEXTO)
    ax.set_ylabel("Colônias com potes na melgueira (%)", color=COR_TEXTO)
    ax.set_ylim(0, 105)
    ax.set_title("Tempo até a ocupação da melgueira (nível 2)", loc="left", color=COR_TEXTO, fontsize=11)
    _estilo(ax)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    fig.tight_layout()
    fig.savefig(arq, dpi=150)
    plt.close(fig)


def graf_pesagens(d, arq):
    pe = d["pes"].copy()
    if pe.empty:
        return
    pe["data"] = pd.to_datetime(pe["data"], errors="coerce")
    pe["peso_kg"] = pd.to_numeric(pe["peso_kg"], errors="coerce")
    pe = pe.merge(d["cad"][["colonia", "tratamento"]], on="colonia")
    pe["mes"] = pe["data"].dt.to_period("M").dt.to_timestamp()
    fig, ax = plt.subplots(figsize=(7, 4))
    for trat, cor in (("NOVA", COR_NOVA), ("ANTIGA", COR_ANTIGA)):
        g = pe[pe["tratamento"] == trat]
        if g.empty:
            continue
        # variação em relação à primeira pesagem de cada colônia
        g = g.sort_values("data")
        g["var_kg"] = g["peso_kg"] - g.groupby("colonia")["peso_kg"].transform("first")
        m = g.groupby("mes")["var_kg"].mean()
        ax.plot(m.index, m.values, color=cor, linewidth=2, marker="o", markersize=5,
                markeredgecolor="white", markeredgewidth=1.5, label=ROTULO[trat])
    ax.axhline(0, color="#9b9a95", linewidth=1)
    ax.set_ylabel("Variação média do peso (kg)", color=COR_TEXTO)
    ax.set_title("Peso das colmeias ao longo do ciclo", loc="left", color=COR_TEXTO, fontsize=11)
    _estilo(ax)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(arq, dpi=150)
    plt.close(fig)


def graf_ciclo_termico(kits, d, arq):
    if kits.empty:
        return
    cad = d["cad"]
    ck = cad.dropna(subset=["kit"])
    mapa = dict(zip(ck["kit"].astype(str).str.strip(), ck["tratamento"]))
    k = kits.copy()
    k["tratamento"] = k["kit"].astype(str).map(mapa)
    k["hora"] = k["data_hora"].dt.hour + k["data_hora"].dt.minute / 60
    k["hora"] = ((k["hora"] * 2).round() / 2) % 24
    fig, ax = plt.subplots(figsize=(7, 4))
    ar = k.groupby("hora")["t_ar_c"].mean()
    ax.plot(ar.index, ar.values, color="#9b9a95", linewidth=2, label="Ar junto às colmeias")
    for trat, cor in (("NOVA", COR_NOVA), ("ANTIGA", COR_ANTIGA)):
        g = k[k["tratamento"] == trat].groupby("hora")["tc1_c"].mean()
        if len(g):
            ax.plot(g.index, g.values, color=cor, linewidth=2, label="Ninho — " + ROTULO[trat].lower())
    ax.set_xlabel("Hora do dia", color=COR_TEXTO)
    ax.set_ylabel("Temperatura média (°C)", color=COR_TEXTO)
    ax.set_xticks(range(0, 25, 3))
    ax.set_title("Ciclo diário médio de temperatura", loc="left", color=COR_TEXTO, fontsize=11)
    _estilo(ax)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(arq, dpi=150)
    plt.close(fig)


# =============================================================================
# Análise completa
# =============================================================================
def analisar(planilha, pasta_kits, saida):
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    d = ler_planilha(planilha)
    kits = ler_kits(pasta_kits)
    cad = d["cad"]
    comp = cad[cad["tratamento"].isin(["NOVA", "ANTIGA"])]
    rel = ["RESULTADOS DO ESTUDO — caixas/melgueiras novas × antigas", "=" * 62, ""]
    res_sec = []

    def comparar(tab, col, rotulo, unidade, escala_log=False):
        t = tab.merge(comp[["colonia"]], on="colonia").dropna(subset=[col])
        if t.empty or t["tratamento"].nunique() < 2:
            return None
        r = teste_aleatorizacao(t[col].values, (t["tratamento"] == "NOVA").astype(int).values, t["grupo"].tolist())
        media_n = t.loc[t["tratamento"] == "NOVA", col].mean()
        media_a = t.loc[t["tratamento"] == "ANTIGA", col].mean()
        linha = dict(indicador=rotulo, unidade=unidade, n_novas=int((t["tratamento"] == "NOVA").sum()),
                     n_antigas=int((t["tratamento"] == "ANTIGA").sum()), media_novas=media_n, media_antigas=media_a,
                     efeito=r["efeito"], ic95_inf=r["ic_inf"], ic95_sup=r["ic_sup"], p=r["p"],
                     combinacoes=r["n_atrib"])
        if escala_log:
            for k in ("efeito", "ic95_inf", "ic95_sup"):
                linha[k + "_pct"] = (math.exp(linha[k]) - 1) * 100 if np.isfinite(linha[k]) else linha[k]
        return linha

    # --- 1. Produção (resultado principal)
    prod = producao(d)
    principal = None
    if not prod.empty:
        prod.to_csv(saida / "producao_por_colonia.csv", index=False, encoding="utf-8-sig")
        if "razao_log" in prod and prod["razao_log"].notna().sum() >= 4:
            principal = comparar(prod, "razao_log", "Produção de mel 2027/2026 (razão logarítmica)", "ln", escala_log=True)
            bloco = []
            for g, t in prod.dropna(subset=["razao_log"]).groupby("grupo"):
                n = t.loc[t["tratamento"] == "NOVA", "razao_log"].mean()
                a = t.loc[t["tratamento"] == "ANTIGA", "razao_log"].mean()
                bloco.append(dict(grupo=g, efeito_ln=n - a, efeito_pct=(math.exp(n - a) - 1) * 100 if pd.notna(n - a) else np.nan))
            pd.DataFrame(bloco).to_csv(saida / "efeito_producao_por_meliponario.csv", index=False, encoding="utf-8-sig")
        elif "mel_ml_2027" in prod:
            prod["ln_mel_2027"] = np.log(prod["mel_ml_2027"].where(prod["mel_ml_2027"] > 0))
            principal = comparar(prod, "ln_mel_2027", "Produção de mel 2027 (sem linha de base)", "ln", escala_log=True)
        if "variacao_ml" in prod:
            s = comparar(prod, "variacao_ml", "Variação da produção 2027 − 2026 (inclui colônias perdidas)", "mL")
            if s:
                res_sec.append(s)
        for col, rot, un in (("umidade_pct_final", "Umidade do mel na extração final", "%"),
                             ("tempo_manejo_min_final", "Tempo de manejo na extração final", "min/colônia"),
                             ("praticidade_1a5_final", "Praticidade percebida (1 a 5)", "pontos")):
            if col in prod:
                s = comparar(prod, col, rot, un)
                if s:
                    res_sec.append(s)
        graf_producao(prod, saida / "grafico_producao.png")

    if principal:
        rel += ["1. RESULTADO PRINCIPAL — PRODUÇÃO DE MEL",
                f"   Colônias: {principal['n_novas']} novas e {principal['n_antigas']} antigas; "
                f"{principal['combinacoes']} combinações de sorteio avaliadas.",
                f"   Efeito estimado da tecnologia nova: {principal['efeito_pct']:+.1f} % na produção",
                f"   IC 95 %: {_ic(principal['ic95_inf_pct'], principal['ic95_sup_pct'], ' %')}   "
                f"valor-p (aleatorização): {principal['p']:.3f}", ""]
    else:
        rel += ["1. RESULTADO PRINCIPAL — sem dados de extração suficientes.", ""]

    # --- 2. Ocupação
    oc = ocupacao(d)
    if not oc.empty:
        oc.to_csv(saida / "ocupacao_por_colonia.csv", index=False, encoding="utf-8-sig")
        for trat in ("NOVA", "ANTIGA"):
            g = oc[oc["tratamento"] == trat].dropna(subset=["dias_ate_nivel2"])
            if len(g):
                _, _, med = kaplan_meier(g["dias_ate_nivel2"], g["evento_nivel2"])
                rel.append(f"   Mediana de dias até potes na melgueira — {ROTULO[trat]}: {med if pd.notna(med) else 'não atingida'}")
        oc["ln_dias_n2"] = np.log(oc["dias_ate_nivel2"].clip(lower=1))
        s = comparar(oc[oc["evento_nivel2"] == 1], "ln_dias_n2", "Tempo até potes na melgueira (só colônias que ocuparam)", "ln", escala_log=True)
        if s:
            res_sec.append(s)
        graf_ocupacao(oc, saida / "grafico_ocupacao.png")
        rel.append("")

    # --- 3. Pesagens mensais (todas as colônias)
    pz = pesagens(d)
    if not pz.empty:
        pz = cad[["colonia", "grupo", "tratamento"]].merge(pz, on="colonia")
        pz.to_csv(saida / "pesagens_por_colonia.csv", index=False, encoding="utf-8-sig")
        for col, rot, un in (("ganho_peso_g_mes", "Ganho de peso (pesagens mensais)", "g/mês"),
                             ("entradas_5min_media", "Entradas na colmeia em 5 min", "abelhas")):
            s = comparar(pz, col, rot, un)
            if s:
                res_sec.append(s)
        graf_pesagens(d, saida / "grafico_pesagens.png")

    # --- 4. Indicadores térmicos e peso contínuo (colônias com kit)
    dia, term = termicos(kits, d)
    if not term.empty:
        dia.to_csv(saida / "kits_indicadores_diarios.csv", index=False, encoding="utf-8-sig")
        term.to_csv(saida / "kits_indicadores_por_colonia.csv", index=False, encoding="utf-8-sig")
        for col, rot, un in (("amortecimento", "Amortecimento térmico (amplitude ninho ÷ ar)", "razão"),
                             ("atraso_h", "Atraso térmico ar → ninho", "h"),
                             ("excesso_c", "Excesso térmico (ninho − ar)", "°C"),
                             ("gradiente_c", "Gradiente vertical (melgueira − ninho)", "°C"),
                             ("ganho_liquido_g_dia", "Ganho líquido de peso (balança do kit)", "g/dia")):
            s = comparar(term, col, rot, un)
            if s:
                res_sec.append(s)
        graf_ciclo_termico(kits, d, saida / "grafico_ciclo_termico.png")

    sec = pd.DataFrame(res_sec)
    if not sec.empty:
        sec["p_holm"] = holm(sec["p"].fillna(1).values)
        sec.to_csv(saida / "resultados_secundarios.csv", index=False, encoding="utf-8-sig")
        rel += ["2. RESULTADOS SECUNDÁRIOS (exploratórios; efeito = novas − antigas, dentro do meliponário)"]
        for _, r in sec.iterrows():
            if "efeito_pct" in r and pd.notna(r.get("efeito_pct")):
                txt = f"{r['efeito_pct']:+.1f} % (IC {_ic(r['ic95_inf_pct'], r['ic95_sup_pct'], ' %')})"
            else:
                txt = f"{r['efeito']:+.2f} {r['unidade']} (IC {_ic(r['ic95_inf'], r['ic95_sup'], '', 2)})"
            rel.append(f"   - {r['indicador']}: {txt}; p = {r['p']:.3f}; p ajustado (Holm) = {r['p_holm']:.3f}")
        rel.append("")

    # --- 5. Ações locais
    tp, rp = praticas(d)
    ta, ra = assistidos(d)
    rel.append("3. GANHO DAS AÇÕES LOCAIS (assistência técnica e capacitação)")
    if rp:
        tp.to_csv(saida / "indice_boas_praticas.csv", index=False, encoding="utf-8-sig")
        rel.append(f"   Índice de boas práticas (0 a 10), {rp['n']} meliponicultores: "
                   f"{rp['media_antes']:.1f} antes → {rp['media_depois']:.1f} depois (ganho médio {rp['ganho_medio']:+.1f})"
                   + (f"; p (Wilcoxon) = {rp['p_wilcoxon']:.3f}" if "p_wilcoxon" in rp else ""))
    if ra:
        ta.to_csv(saida / "producao_assistidos.csv", index=False, encoding="utf-8-sig")
        rel.append(f"   Produção dos meliponicultores assistidos, {ra['n']} meliponicultores: "
                   f"{ra['l_col_inicial']:.2f} L/colônia ({int(ra['ano_inicial'])}) → {ra['l_col_final']:.2f} L/colônia "
                   f"({int(ra['ano_final'])}); variação {ra['variacao_pct']:+.1f} %"
                   + (f"; p (Wilcoxon) = {ra['p_wilcoxon']:.3f}" if "p_wilcoxon" in ra else ""))
        rel.append("   Atenção: comparação antes × depois; inclui o efeito do ano (clima, florada).")
    if not rp and not ra:
        rel.append("   Sem dados de práticas ou de produção dos assistidos.")
    rel.append("")

    # --- 6. Ganhos econômicos
    rel.append("4. GANHOS ECONÔMICOS DA TECNOLOGIA NOVA (por colônia e por ano)")
    par = d["par"]
    if principal and not prod.empty and par.get("preco_l") not in (None, "") and pd.notna(par.get("preco_l")):
        base_l = prod.loc[prod["tratamento"] == "ANTIGA", "mel_ml_2027"].mean() / 1000
        dt = next((r["efeito"] for r in res_sec if r["indicador"].startswith("Tempo de manejo")), 0.0)
        tg, eq = ganhos(principal["efeito_pct"], (principal["ic95_inf_pct"], principal["ic95_sup_pct"]), base_l, dt, par)
        tg.to_csv(saida / "ganhos_economicos.csv", index=False, encoding="utf-8-sig")
        for _, r in tg.iterrows():
            rel.append(f"   {r['cenario']}: {r['ganho_l_colonia_ano']:+.2f} L → R$ {r['ganho_rs_colonia_ano']:,.2f}/ano; "
                       f"benefício líquido R$ {r['beneficio_liquido_rs']:,.2f}; B/C {r['relacao_beneficio_custo']:.2f}")
        rel.append(f"   Aumento de produção que paga a tecnologia (ponto de equilíbrio): {eq:.2f} L/colônia/ano")
    else:
        rel.append("   Preencha preço, custo e vida útil na aba F11_Ganhos para calcular.")
    rel += ["", "Notas: efeito estimado dentro de cada meliponário (o controle foi sorteado); valor-p exato pelo teste",
            "de aleatorização; IC 95 % por inversão do teste. Só a produção é resultado confirmatório; os demais são",
            "exploratórios. Com um meliponário por espécie e ambiente, diferenças entre espécies e ambientes são",
            "descritivas."]
    (saida / "relatorio_resultados.txt").write_text("\n".join(rel), encoding="utf-8")
    print("\n".join(rel))
    print(f"\nArquivos gravados em: {saida.resolve()}")


# =============================================================================
# Dados simulados (para testar a análise)
# =============================================================================
def simular(saida, semente=3, efeito_real=0.30, dias_kit=45):
    rng = np.random.default_rng(semente)
    saida = Path(saida)
    (saida / "kits").mkdir(parents=True, exist_ok=True)
    grupos = [("G01", "M. interrupta", "Rio/igapó", "Meliponicultor A"), ("G02", "M. interrupta", "Terra firme", "Meliponicultor B"),
              ("G03", "M. seminigra", "Rio/igapó", "Meliponicultor C"), ("G04", "M. seminigra", "Terra firme", "Meliponicultor D")]
    monitor = {"G01": "Monitor 1", "G04": "Monitor 1", "G02": "Monitor 2", "G03": "Monitor 2"}
    cad, base, extr, ocup, pes, chuva, manejo = [], [], [], [], [], [], []
    k = 0
    t0 = pd.Timestamp("2026-10-28")
    for g, esp, amb, mel in grupos:
        ctrl = rng.integers(4)
        mu = rng.normal(np.log(1500), 0.2)
        ano = rng.normal(0.05, 0.1)
        for i in range(4):
            col = f"{g}-C{i + 1}"
            trat = "ANTIGA" if i == ctrl else "NOVA"
            instr = trat == "ANTIGA" or i != (ctrl + 1) % 4  # 2 novas + 1 antiga com kit
            kit = None
            if instr:
                k += 1
                kit = f"K{k:02d}"
            cad.append(dict(colonia=col, grupo=g, especie=esp, ambiente=amb, meliponicultor=mel, monitor=monitor[g],
                            tratamento=trat, kit=kit))
            u = rng.normal(0, 0.35)
            p26 = math.exp(mu + u + rng.normal(0, 0.25))
            p27 = math.exp(mu + u + ano + (efeito_real if trat == "NOVA" else 0) + rng.normal(0, 0.25))
            base.append(dict(colonia=col, data=t0.date(), observador=monitor[g], discos_cria=int(rng.integers(4, 9)),
                             entradas_5min=int(rng.integers(15, 60)), peso_antes_extracao_kg=round(rng.normal(9, 1), 2),
                             tara_melgueira_kg=1.8 if trat == "NOVA" else None,
                             estado_melgueira="NOVA_VAZIA" if trat == "NOVA" else "POTES_MANTIDOS"))
            for safra, v in ((2026, p26), (2027, p27)):
                extr.append(dict(colonia=col, safra=safra, data=(t0 if safra == 2026 else pd.Timestamp("2027-10-05")).date(),
                                 mel_ml=round(v), mel_g=round(v * 1.35), umidade_pct=round(rng.normal(31 if trat == "NOVA" else 32, 2), 1),
                                 tempo_manejo_min=round(rng.normal(35 if trat == "NOVA" and safra == 2027 else 45, 6)),
                                 praticidade_1a5=int(rng.integers(3, 6)) if safra == 2027 else None, colonia_viva="S"))
            atraso = rng.normal(35 if trat == "NOVA" else 20, 10)
            for semana in range(0, 50, 2):
                dt = t0 + pd.Timedelta(days=14 * semana // 2 + 1)
                dias = (dt - t0).days
                nivel = int(np.clip(np.floor((dias - atraso) / 25) + 2, 0, 5)) if dias > atraso * 0.6 else 0
                ocup.append(dict(colonia=col, data=dt.date(), observador=monitor[g], nivel=nivel))
            for m in range(12):
                dt = t0 + pd.Timedelta(days=30 * m + 3)
                pes.append(dict(colonia=col, data=dt.date(), hora="07:00", observador=monitor[g],
                                peso_kg=round(7.5 + (0.25 if trat == "NOVA" else 0.18) * m + rng.normal(0, 0.15), 2),
                                entradas_5min=int(rng.integers(15, 70))))
            for _ in range(6):
                manejo.append(dict(colonia=col, data=(t0 + pd.Timedelta(days=int(rng.integers(1, dias_kit)))).date(),
                                   hora="09:00", tipo="ABERTURA", descricao="observação da melgueira", responsavel=monitor[g]))
            if kit:
                idx = pd.date_range(t0 + pd.Timedelta(days=1), periods=dias_kit * 144, freq="10min")
                h = idx.hour + idx.minute / 60
                ar = 27 + 4 * np.sin(2 * np.pi * (h - 9) / 24) + rng.normal(0, 0.3, len(idx))
                amort = (0.35 if trat == "NOVA" else 0.5) + rng.normal(0, 0.06)
                lag = int(round((12 if trat == "NOVA" else 8) + rng.normal(0, 2)))
                tc1 = rng.normal(29.5, 0.8) + amort * (np.roll(ar, lag) - 27) + rng.normal(0, 0.1, len(idx))
                tc3 = tc1 - rng.normal(2.5, 0.2) + rng.normal(0, 0.15, len(idx))
                dia_n = (idx - idx[0]).days
                peso = 8000 + ((30 if trat == "NOVA" else 18) + rng.normal(0, 6)) * dia_n - 60 * np.clip(np.sin(2 * np.pi * (h - 7) / 24), 0, None) + rng.normal(0, 8, len(idx))
                df = pd.DataFrame(dict(data_hora=idx.strftime("%Y-%m-%dT%H:%M:%S"), kit=kit, tc1_c=tc1.round(2),
                                       tc2_c=((tc1 + tc3) / 2).round(2), tc3_c=tc3.round(2), t_ar_c=ar.round(1),
                                       ur_ar_pct=np.clip(85 - 2 * (ar - 27), 40, 100).round(1),
                                       luz_lx=np.clip(30000 * np.sin(np.pi * (h - 6) / 12), 0, None).round(0),
                                       peso_g=peso.round(0), bateria_mv=3900))
                df.loc[rng.choice(len(df), 50, replace=False), "tc3_c"] = np.nan  # falhas
                df.to_csv(saida / "kits" / f"{kit}.csv", index=False)
    for g, *_ in grupos:
        for dd in range(300):
            chuva.append(dict(grupo=g, data=(t0 + pd.Timedelta(days=dd)).date(),
                              chuva_mm=float(np.round(rng.gamma(0.6, 12) if rng.random() < 0.55 else 0, 1)), leitor="meliponicultor"))
    prat, prodass = [], []
    for j in range(10):
        nome = f"Meliponicultor {j + 1:02d}"
        a = rng.integers(2, 6)
        for mom, val in (("ANTES", a), ("DEPOIS", min(10, a + rng.integers(0, 4)))):
            itens = np.zeros(10, int)
            itens[rng.choice(10, val, replace=False)] = 1
            prat.append(dict(meliponicultor=nome, momento=mom, data="2026-11-10" if mom == "ANTES" else "2027-10-20",
                             **{f"p{q + 1:02d}": int(itens[q]) for q in range(10)}))
        n = int(rng.integers(5, 25))
        l0 = rng.normal(1.4, 0.3)
        for safra, f in ((2026, 1.0), (2027, math.exp(rng.normal(0.15, 0.2)))):
            prodass.append(dict(meliponicultor=nome, safra=safra, colonias_produtivas=n, producao_total_l=round(n * l0 * f, 1)))
    arq = saida / "planilha_simulada.xlsx"
    with pd.ExcelWriter(arq) as w:
        pd.DataFrame(cad).to_excel(w, sheet_name=ABAS["cad"], index=False)
        pd.DataFrame(base).to_excel(w, sheet_name=ABAS["base"], index=False)
        pd.DataFrame(ocup).to_excel(w, sheet_name=ABAS["ocup"], index=False)
        pd.DataFrame(pes).to_excel(w, sheet_name=ABAS["pes"], index=False)
        pd.DataFrame(chuva).to_excel(w, sheet_name=ABAS["chuva"], index=False)
        pd.DataFrame(manejo).to_excel(w, sheet_name=ABAS["manejo"], index=False)
        pd.DataFrame(extr).to_excel(w, sheet_name=ABAS["extr"], index=False)
        pd.DataFrame(prat).to_excel(w, sheet_name=ABAS["prat"], index=False)
        pd.DataFrame(prodass).to_excel(w, sheet_name=ABAS["prodass"], index=False)
        pd.DataFrame([["Preço do mel (R$/L)", 120, None, "preco_l"],
                      ["Custo da caixa/melgueira nova (R$)", 150, None, "custo_tecnologia"],
                      ["Vida útil (anos)", 5, None, "vida_util_anos"],
                      ["Valor da hora de trabalho (R$/h)", 12, None, "valor_hora"],
                      ["Colônias na associação", 300, None, "colonias_associacao"]]).to_excel(w, sheet_name=ABAS["ganhos"], index=False, header=False)
    print(f"Dados FICTÍCIOS gravados em {saida.resolve()} (efeito real simulado: {(math.exp(efeito_real) - 1) * 100:+.0f} %).")
    print(f"Teste: python3 {Path(__file__).name} analisar --planilha {arq} --kits {saida / 'kits'} --saida {saida / 'resultados'}")


def main():
    ap = argparse.ArgumentParser(description="Análise do experimento de meliponicultura (FIS/IPÊ)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analisar")
    a.add_argument("--planilha", required=True, nargs="+",
                   help="planilha do Anexo 05a e/ou planilhas exportadas pelo app Coleta de Campo (uma por celular)")
    a.add_argument("--kits", default=None, help="pasta com os CSV dos kits (opcional)")
    a.add_argument("--saida", default="resultados")
    s = sub.add_parser("simular")
    s.add_argument("--saida", default="teste_simulado")
    s.add_argument("--efeito", type=float, default=30.0, help="efeito real simulado, em %%")
    p = sub.add_parser("poder")
    p.add_argument("--reps", type=int, default=2000)
    p.add_argument("--saida", default=None)
    arg = ap.parse_args()
    if arg.cmd == "analisar":
        import glob   # no Windows o PowerShell não expande "*.xlsx"
        planilhas = [x for p in arg.planilha for x in (sorted(glob.glob(p)) or [p])]
        analisar(planilhas, arg.kits, arg.saida)
    elif arg.cmd == "simular":
        simular(arg.saida, efeito_real=math.log(1 + arg.efeito / 100))
    else:
        tab = poder(arg.reps, saida=arg.saida)
        with pd.option_context("display.width", 160, "display.max_columns", 20):
            print(tab.to_string(index=False))


if __name__ == "__main__":
    main()
