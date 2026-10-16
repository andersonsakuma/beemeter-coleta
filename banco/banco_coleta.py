#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Banco de dados da Coleta de Campo — experimento de meliponicultura, Cametá do Ramos (FIS/IPÊ)

Junta num único arquivo SQLite tudo o que é levantado em campo: as planilhas enviadas pelos
celulares (app Coleta de Campo), as cópias de segurança .json, a planilha do Anexo 05a, os CSV
descarregados dos kits e os .zip de fotos. Reimportar o mesmo arquivo não duplica nada.

Uso (Windows: troque "python3" por "python"):
    python3 banco_coleta.py criar   --banco coleta.sqlite        (opcional: importar já cria)
    python3 banco_coleta.py importar --banco coleta.sqlite coleta-monitor1-*.xlsx coleta-monitor2-*.xlsx
    python3 banco_coleta.py importar --banco coleta.sqlite kits/*.csv fotos-*.zip copia-*.json Anexo_05a.xlsx
    python3 banco_coleta.py resumo   --banco coleta.sqlite
    python3 banco_coleta.py exportar --banco coleta.sqlite --planilha consolidado.xlsx --kits pasta_kits
    python3 banco_coleta.py consulta --banco coleta.sqlite "SELECT * FROM v_producao"

A planilha consolidada sai no formato do Anexo 05a e vai direto para o programa de análise (Anexo 05b):
    python3 analise_meliponicultura.py analisar --planilha consolidado.xlsx --kits pasta_kits

Dependências: pandas e openpyxl (as mesmas do Anexo 05b). O SQLite já vem com o Python.
O arquivo .sqlite abre no DB Browser for SQLite (sqlitebrowser.org) para consulta e conferência.
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import math
import sqlite3
import sys
import zipfile
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
ESQUEMA = AQUI / "esquema.sql"

ABA_TABELA = {
    "F01_Cadastro": "colonias", "F02_LinhaBase": "linha_base", "F03_InstalacaoKit": "instalacao_kit",
    "F04_VerificacaoKit": "verificacao_kit", "F05_Ocupacao": "ocupacao", "F06_PesagemAtividade": "pesagem_atividade",
    "F07_Chuva": "chuva", "F08_Manejo": "manejo", "F09_Extracao": "extracao", "F10_Assistencia": "assistencia",
    "F10_Praticas": "praticas", "F10_ProducaoAssistidos": "producao_assistidos", "Sorteios": "sorteios",
}
COLECAO_TABELA = {"F01": "colonias", "F02": "linha_base", "F03": "instalacao_kit", "F04": "verificacao_kit",
                  "F05": "ocupacao", "F06": "pesagem_atividade", "F07": "chuva", "F08": "manejo", "F09": "extracao",
                  "F10A": "assistencia", "F10P": "praticas", "F10R": "producao_assistidos", "SORTEIO": "sorteios"}
META = ("id", "registrado_em", "editado_em", "dispositivo", "excluido", "origem")
FAIXAS = {("ocupacao", "nivel"): (0, 5), ("extracao", "umidade_pct"): (10, 60), ("pesagem_atividade", "peso_kg"): (0, 50),
          ("chuva", "chuva_mm"): (0, 300), ("extracao", "praticidade_1a5"): (1, 5), ("verificacao_kit", "bateria_v"): (2.5, 4.5)}


# ----------------------------------------------------------------------------- utilidades
def conectar(banco, criar=False):
    p = Path(banco)
    if not p.exists() and not criar:
        sys.exit(f"Banco {p} não existe. Crie com: banco_coleta.py criar --banco {p}")
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA.read_text(encoding="utf-8"))   # idempotente: cria o que faltar e refaz as visões
    return con


def colunas(con, tabela):
    return [(r["name"], r["type"].upper()) for r in con.execute(f"PRAGMA table_info({tabela})")]


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def vazio(v):
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(v, str) and v.strip() == ""


def normalizar(v, tipo, nome):
    """Converte o valor lido da planilha/JSON para o tipo da coluna do banco."""
    if vazio(v):
        return None
    if nome in ("data", "assistido_desde"):
        if isinstance(v, (pd.Timestamp, dt.datetime, dt.date)):
            return pd.Timestamp(v).strftime("%Y-%m-%d")
        s = str(v).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return dt.datetime.strptime(s[:19] if "T" in s or " " in s else s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return s
    if nome == "hora":
        if isinstance(v, (dt.time, dt.datetime, pd.Timestamp)):
            return v.strftime("%H:%M")
        return str(v).strip()[:5]
    if "INT" in tipo:
        try:
            f = float(str(v).replace(",", "."))
            return int(round(f))
        except ValueError:
            return None
    if "REAL" in tipo:
        try:
            return float(str(v).replace(",", "."))
        except ValueError:
            return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, (pd.Timestamp, dt.datetime)):
        return v.isoformat()
    return str(v).strip()


def tempo(reg):
    return max(str(reg.get("editado_em") or ""), str(reg.get("registrado_em") or ""))


# ----------------------------------------------------------------------------- gravação
def gravar(con, tabela, regs, origem, cont):
    cols = colunas(con, tabela)
    nomes = [c for c, _ in cols]
    tipos = dict(cols)
    for bruto in regs:
        r = {c: normalizar(bruto.get(c), tipos[c], c) for c in nomes if c not in ("excluido", "origem")}
        r["excluido"] = 1 if bruto.get("_excluido") else 0
        r["origem"] = origem
        if tabela == "colonias":
            gravar_colonia(con, r, cont)
            continue
        if not r.get("id"):   # planilha digitada à mão: identificador estável a partir do conteúdo
            base = json.dumps({k: r[k] for k in nomes if k not in META}, sort_keys=True, default=str)
            r["id"] = "p05a-" + hashlib.sha1((tabela + base).encode()).hexdigest()[:16]
        ex = con.execute(f"SELECT registrado_em, editado_em FROM {tabela} WHERE id = ?", (r["id"],)).fetchone()
        if ex is None:
            con.execute(f"INSERT INTO {tabela} ({','.join(r)}) VALUES ({','.join('?' * len(r))})", list(r.values()))
            cont["novos"] += 1
        elif tempo(r) > tempo(dict(ex)):
            sets = ",".join(f"{k}=?" for k in r if k != "id")
            con.execute(f"UPDATE {tabela} SET {sets} WHERE id = ?", [v for k, v in r.items() if k != "id"] + [r["id"]])
            cont["atualizados"] += 1
        else:
            cont["ignorados"] += 1


def gravar_colonia(con, r, cont):
    """Cadastro: uma linha por colônia, juntada campo a campo (vale o valor preenchido mais recente)."""
    if not r.get("colonia") or r.get("excluido"):
        cont["ignorados"] += 1
        return
    ex = con.execute("SELECT * FROM colonias WHERE colonia = ?", (r["colonia"],)).fetchone()
    if ex is None:
        con.execute(f"INSERT INTO colonias ({','.join(r)}) VALUES ({','.join('?' * len(r))})", list(r.values()))
        cont["novos"] += 1
        return
    ex = dict(ex)
    mais_novo = tempo(r) >= tempo(ex)
    muda = {}
    for k, v in r.items():
        if k in ("colonia", "id", "registrado_em", "dispositivo", "excluido", "origem") or v is None:
            continue
        if ex.get(k) is None or (mais_novo and ex.get(k) != v):
            muda[k] = v
    if mais_novo and r.get("editado_em"):
        muda["editado_em"] = r["editado_em"]
    if muda:
        muda["origem"] = r["origem"]
        con.execute(f"UPDATE colonias SET {','.join(k + '=?' for k in muda)} WHERE colonia = ?", list(muda.values()) + [r["colonia"]])
        cont["atualizados"] += 1
    else:
        cont["ignorados"] += 1


# ----------------------------------------------------------------------------- importação
def ler_aba(caminho, aba):
    try:
        df = pd.read_excel(caminho, sheet_name=aba)
    except ValueError:
        return []
    df = df.dropna(how="all")
    if df.empty:
        return []
    chave = df.iloc[:, 0]
    df = df[chave.notna() & (chave.astype(str).str.strip() != "")]
    for col in ("colonia", "meliponicultor", "kit", "grupo"):
        if col in df.columns:
            v = df[col].astype(str).str.strip().str.upper()
            df = df[~(v.str.startswith("EX-") | (v == "EXEMPLO"))]   # linhas de exemplo do Anexo 05a
    return df.to_dict("records")


def importar_planilha(con, caminho, cont):
    xl = pd.ExcelFile(caminho)
    tipo = "planilha_app" if "Origem" in xl.sheet_names else "planilha_05a"
    for aba, tabela in ABA_TABELA.items():
        if aba in xl.sheet_names:
            regs = ler_aba(caminho, aba)
            if tabela == "colonias":
                regs.sort(key=tempo)
            gravar(con, tabela, regs, Path(caminho).name, cont)
    if "F11_Ganhos" in xl.sheet_names:
        g = pd.read_excel(caminho, sheet_name="F11_Ganhos", header=None)
        for _, r in g.iterrows():
            if len(r) > 3 and isinstance(r.iloc[3], str) and r.iloc[3].strip() and not vazio(r.iloc[1]):
                try:
                    valor = float(r.iloc[1])
                except (TypeError, ValueError):
                    continue
                con.execute("INSERT INTO parametros (chave, valor, descricao, origem) VALUES (?,?,?,?) "
                            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor, descricao=excluded.descricao, origem=excluded.origem",
                            (r.iloc[3].strip(), valor, str(r.iloc[0]), Path(caminho).name))
    return tipo


def importar_json(con, caminho, cont):
    d = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if d.get("formato") != "coleta-campo":
        raise ValueError("não é uma cópia do aplicativo Coleta de Campo")
    for col, regs in d.get("colecoes", {}).items():
        tabela = COLECAO_TABELA.get(col)
        if tabela:
            regs = [r for r in regs if isinstance(r, dict)]
            if tabela == "colonias":
                regs.sort(key=tempo)
            gravar(con, tabela, regs, Path(caminho).name, cont)
    return "copia_json"


def importar_csv_kit(con, caminho, cont):
    df = pd.read_csv(caminho)
    falta = {"data_hora", "kit"} - set(df.columns)
    if falta:
        raise ValueError(f"CSV sem as colunas {falta}")
    cols = ["kit", "data_hora", "tc1_c", "tc2_c", "tc3_c", "t_ar_c", "ur_ar_pct", "luz_lx", "peso_g", "bateria_mv"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    antes = con.total_changes
    linhas = [[None if vazio(v) else (str(v) if c in ("kit", "data_hora") else float(v)) for c, v in zip(cols, r)] + [Path(caminho).name]
              for r in df[cols].itertuples(index=False)]
    con.executemany(f"INSERT OR IGNORE INTO leituras_kit ({','.join(cols)}, origem) VALUES ({','.join('?' * (len(cols) + 1))})", linhas)
    novos = con.total_changes - antes
    cont["novos"] += novos
    cont["ignorados"] += len(linhas) - novos
    return "kits_csv"


def importar_fotos(con, caminho, cont, banco):
    pasta = Path(banco).resolve().parent / "fotos"
    pasta.mkdir(exist_ok=True)
    with zipfile.ZipFile(caminho) as z:
        for nome in z.namelist():
            base = Path(nome).name
            if not base.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            if con.execute("SELECT 1 FROM fotos WHERE nome = ?", (base,)).fetchone():
                cont["ignorados"] += 1
                continue
            dados = z.read(nome)
            (pasta / base).write_bytes(dados)
            con.execute("INSERT INTO fotos (nome, arquivo, bytes, sha256, origem) VALUES (?,?,?,?,?)",
                        (base, f"fotos/{base}", len(dados), hashlib.sha256(dados).hexdigest(), Path(caminho).name))
            cont["novos"] += 1
    return "fotos_zip"


def importar(banco, arquivos, forcar=False):
    con = conectar(banco, criar=True)   # cria o banco na primeira importação
    lista = [x for p in arquivos for x in (sorted(glob.glob(p)) or [p])]   # o PowerShell não expande "*"
    if not lista:
        sys.exit("Nenhum arquivo para importar.")
    for arq in lista:
        p = Path(arq)
        if not p.exists():
            print(f"  ✗ {arq}: não encontrado")
            continue
        h = sha256(p)
        if not forcar and con.execute("SELECT 1 FROM importacoes WHERE sha256 = ?", (h,)).fetchone():
            print(f"  · {p.name}: já importado antes (use --forcar para repetir)")
            continue
        cont = {"novos": 0, "atualizados": 0, "ignorados": 0}
        try:
            ext = p.suffix.lower()
            if ext in (".xlsx", ".xlsm"):
                tipo = importar_planilha(con, p, cont)
            elif ext == ".json":
                tipo = importar_json(con, p, cont)
            elif ext == ".csv":
                tipo = importar_csv_kit(con, p, cont)
            elif ext == ".zip":
                tipo = importar_fotos(con, p, cont, banco)
            else:
                print(f"  ✗ {p.name}: tipo de arquivo não reconhecido")
                continue
        except Exception as e:   # um arquivo ruim não derruba a importação dos outros
            con.rollback()
            print(f"  ✗ {p.name}: {e}")
            continue
        con.execute("INSERT INTO importacoes (arquivo, sha256, tipo, importado_em, novos, atualizados, ignorados) VALUES (?,?,?,?,?,?,?)",
                    (p.name, h, tipo, dt.datetime.now().isoformat(timespec="seconds"), cont["novos"], cont["atualizados"], cont["ignorados"]))
        con.commit()
        print(f"  ✓ {p.name} ({tipo}): {cont['novos']} novo(s), {cont['atualizados']} atualizado(s), {cont['ignorados']} já existente(s)")
    con.close()


# ----------------------------------------------------------------------------- saída
def exportar(banco, planilha=None, pasta_kits=None):
    con = conectar(banco)
    if planilha:
        with pd.ExcelWriter(planilha) as w:
            for aba, tabela in ABA_TABELA.items():
                cols = [c for c, _ in colunas(con, tabela) if c not in ("excluido", "origem")]
                df = pd.read_sql(f"SELECT {','.join(cols)} FROM {tabela} WHERE excluido = 0", con)
                for c in ("data", "assistido_desde"):
                    if c in df.columns:
                        df[c] = pd.to_datetime(df[c], errors="coerce")
                df.to_excel(w, sheet_name=aba, index=False)
            par = pd.read_sql("SELECT descricao, valor, NULL AS x, chave FROM parametros", con)
            par.to_excel(w, sheet_name="F11_Ganhos", index=False, header=False)
        print(f"Planilha consolidada (formato do Anexo 05a): {Path(planilha).resolve()}")
    if pasta_kits:
        pk = Path(pasta_kits)
        pk.mkdir(parents=True, exist_ok=True)
        kits = [r[0] for r in con.execute("SELECT DISTINCT kit FROM leituras_kit ORDER BY kit")]
        for k in kits:
            df = pd.read_sql("SELECT kit, data_hora, tc1_c, tc2_c, tc3_c, t_ar_c, ur_ar_pct, luz_lx, peso_g, bateria_mv "
                             "FROM leituras_kit WHERE kit = ? ORDER BY data_hora", con, params=(k,))
            df.to_csv(pk / f"{k}.csv", index=False)
        print(f"{len(kits)} arquivo(s) de kit em {pk.resolve()}")
    con.close()


def resumo(banco):
    con = conectar(banco)
    print(f"BANCO {Path(banco).resolve()}\n")
    print("Registros por tabela (sem os excluídos):")
    for aba, tabela in ABA_TABELA.items():
        n = con.execute(f"SELECT COUNT(*), MIN(data), MAX(data) FROM {tabela} WHERE excluido = 0").fetchone() \
            if "data" in dict(colunas(con, tabela)) else con.execute(f"SELECT COUNT(*), NULL, NULL FROM {tabela} WHERE excluido = 0").fetchone()
        print(f"  {aba:<24} {n[0]:>6}" + (f"   {n[1]} a {n[2]}" if n[1] else ""))
    k = con.execute("SELECT COUNT(*), COUNT(DISTINCT kit), MIN(data_hora), MAX(data_hora) FROM leituras_kit").fetchone()
    print(f"  {'Leituras dos kits':<24} {k[0]:>6}   {k[1]} kit(s)" + (f", {k[2][:10]} a {k[3][:10]}" if k[2] else ""))
    print(f"  {'Fotos':<24} {con.execute('SELECT COUNT(*) FROM fotos').fetchone()[0]:>6}")
    print(f"  {'Arquivos importados':<24} {con.execute('SELECT COUNT(*) FROM importacoes').fetchone()[0]:>6}")

    alertas = []
    for g, n_ant, n_sem in con.execute("SELECT grupo, SUM(tratamento='ANTIGA'), SUM(tratamento IS NULL) FROM colonias "
                                       "WHERE excluido = 0 GROUP BY grupo ORDER BY grupo"):
        if n_ant != 1:
            alertas.append(f"{g}: {n_ant or 0} colônia(s) ANTIGA (esperado 1 por grupo — sorteio feito?)")
        if n_sem:
            alertas.append(f"{g}: {n_sem} colônia(s) sem tratamento")
    for (tab, col), (lo, hi) in FAIXAS.items():
        for r in con.execute(f"SELECT * FROM {tab} WHERE excluido = 0 AND {col} IS NOT NULL AND ({col} < ? OR {col} > ?)", (lo, hi)):
            r = dict(r)
            alertas.append(f"{tab}.{col} = {r[col]} fora de {lo}–{hi} ({r.get('colonia') or r.get('grupo') or r.get('kit')}, {r.get('data')})")
    for g, d, n in con.execute("SELECT grupo, data, COUNT(*) FROM chuva WHERE excluido = 0 GROUP BY grupo, data HAVING COUNT(*) > 1"):
        alertas.append(f"chuva {g} {d}: {n} leituras no mesmo dia")
    for g, n in con.execute("SELECT grupo, COUNT(DISTINCT controle) FROM sorteios WHERE excluido = 0 GROUP BY grupo HAVING COUNT(*) > 1"):
        alertas.append(f"{g}: sorteio registrado mais de uma vez ({n} resultado(s) diferente(s)) — confira qual vale")
    for c, s, d, n in con.execute("SELECT colonia, safra, data, COUNT(*) FROM extracao WHERE excluido = 0 "
                                  "GROUP BY colonia, safra, data HAVING COUNT(*) > 1"):
        alertas.append(f"extração {c} safra {s} em {d}: {n} registros no mesmo dia (duplicidade?)")
    for c, s26, s27 in con.execute("SELECT colonia, mel_ml_2026, mel_ml_2027 FROM v_producao WHERE tratamento IS NOT NULL"):
        if s26 is None:
            alertas.append(f"{c}: sem extração de 2026 (linha de base de produção)")
    for kit, ult in con.execute("SELECT c.kit, MAX(v.data) FROM colonias c LEFT JOIN verificacao_kit v ON v.kit = c.kit AND v.excluido = 0 "
                                "WHERE c.kit IS NOT NULL AND c.excluido = 0 GROUP BY c.kit"):
        if ult is None:
            alertas.append(f"kit {kit}: nenhuma verificação registrada")
        elif (dt.date.today() - dt.date.fromisoformat(ult)).days > 14:
            alertas.append(f"kit {kit}: última verificação em {ult}")
    print("\nConferências:" if alertas else "\nConferências: nada a apontar.")
    for a in alertas[:80]:
        print("  ! " + a)
    if len(alertas) > 80:
        print(f"  … e mais {len(alertas) - 80}")
    con.close()


def consulta(banco, sql):
    con = conectar(banco)
    df = pd.read_sql(sql, con)
    with pd.option_context("display.width", 200, "display.max_columns", 40, "display.max_rows", 200):
        print(df.to_string(index=False))
    con.close()


def main():
    ap = argparse.ArgumentParser(description="Banco de dados da Coleta de Campo (FIS/IPÊ)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nome in ("criar", "importar", "resumo", "exportar", "consulta"):
        s = sub.add_parser(nome)
        s.add_argument("--banco", default="coleta.sqlite", help="arquivo do banco (padrão: coleta.sqlite)")
        if nome == "importar":
            s.add_argument("arquivos", nargs="+", help=".xlsx do app ou do Anexo 05a, .json, .csv dos kits, .zip de fotos")
            s.add_argument("--forcar", action="store_true", help="reimporta arquivos já importados")
        if nome == "exportar":
            s.add_argument("--planilha", help="planilha consolidada no formato do Anexo 05a")
            s.add_argument("--kits", help="pasta para os CSV dos kits")
        if nome == "consulta":
            s.add_argument("sql")
    a = ap.parse_args()
    if a.cmd == "criar":
        conectar(a.banco, criar=True).close()
        print(f"Banco pronto: {Path(a.banco).resolve()}")
    elif a.cmd == "importar":
        importar(a.banco, a.arquivos, a.forcar)
    elif a.cmd == "resumo":
        resumo(a.banco)
    elif a.cmd == "exportar":
        if not a.planilha and not a.kits:
            sys.exit("Informe --planilha e/ou --kits.")
        exportar(a.banco, a.planilha, a.kits)
    else:
        consulta(a.banco, a.sql)


if __name__ == "__main__":
    main()
