# -*- coding: utf-8 -*-
"""
gerar_bastidores.py

Refaz bastidores.md e bastidores-2.md a partir do canone-limpo.md.

Como funciona, em uma frase: os dois modelos (modelo-bastidores.md e
modelo-bastidores-2.md) trazem marcadores no lugar dos números, e este script
descobre cada número olhando o canone-limpo.md (procurando a obra pelo título).

Uso (na pasta onde estão os arquivos):
    python gerar_bastidores.py            refaz os dois bastidores
    python gerar_bastidores.py --testar   só confere e mostra o relatório, sem gravar nada

Códigos de saída: 0 = tudo certo, 2 = gravou, mas com avisos para conferir,
1 = erro (nada foi gravado).
"""
import difflib
import os
import re
import sys
import unicodedata
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PASTA = Path(__file__).resolve().parent
LIMPO = PASTA / "canone-limpo.md"
PARES = [
    (PASTA / "modelo-bastidores.md", PASTA / "bastidores.md"),
    (PASTA / "modelo-bastidores-2.md", PASTA / "bastidores-2.md"),
]

# Total da junção original (antes de qualquer separação de obras).
TOTAL_BASE = 1224
FRASE_BASE = ("1039 originais — 327 itens da A + 735 entradas da B − 23 entradas da B "
              "que coincidem com itens da A — mais 185 entradas novas")
BLOCOS_PADRAO = 12

SEP = " — "
ITEM_RE = re.compile(r"^(\d+)\.\s+(\S.*)$")          # qualquer linha "N. alguma coisa" sem recuo
ETAPA_RE = re.compile(r"^#{1,6}\s*Etapa\s+(\d+)\b")  # cabeçalho "## Etapa 10: Nome"
BLOCO_RE = re.compile(r"\s\(Bloco\s+\d+\b")          # começo de "(Bloco 1 — ...)"
IDX_RE = re.compile(r"^[\-\*\s]*Etapa\s+(\d+):\s*(.+?):\s*(\d+)\s+itens\s*$")
TOTAL_RE = re.compile(r"Total:\s*(\d+)\s+itens(?:,\s*em\s+(\d+)\s+etapas\s+e\s+(\d+)\s+blocos)?")
MARCADOR_RE = re.compile(r"\{\{(.*?)\}\}")
ENTRADA_RE = re.compile(r"^- \{\{entrada\|(\d+)\|(\d+)\|(.+)\}\}\s*$")


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"')):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip().casefold()


def dividir(texto):
    if SEP in texto:
        a, t = texto.split(SEP, 1)
        return a.strip(), t.strip()
    return None, texto.strip()


# ------------------------------------------------------------------ leitura
def analisar_item(resto):
    """
    Entende os dois formatos de item do canone-limpo.md:
      Lista B:  **Autor — Título** (Bloco 1 — Antiguidade) · c. 1900
      Lista A:  *Título* (Autor), comentário sobre X (Bloco 1 — Antiguidade)
                "Título do artigo" (Autor), artigo sobre X (Bloco 1 — Antiguidade)
    Devolve (texto, autor, titulo).
    """
    mb = BLOCO_RE.search(resto)
    cabeca = (resto[:mb.start()] if mb else resto).strip()

    if cabeca.startswith("**") and "**" in cabeca[2:]:
        texto = cabeca[2:cabeca.index("**", 2)].strip()
        autor, titulo = dividir(texto)
        return texto, autor, titulo

    mi = re.match(r"^\*(?!\*)(.+?)\*(?!\*)(.*)$", cabeca)
    mq = re.match(r'^[“"](.+?)[”"](.*)$', cabeca)
    if mi:
        titulo, sobra = mi.group(1).strip(), mi.group(2)
    elif mq:
        titulo, sobra = mq.group(1).strip(), mq.group(2)
    else:
        titulo, sobra = cabeca, ""
    ma = re.match(r"^\s*\(([^)]*)\)", sobra)
    autor = ma.group(1).strip() if ma else None
    return titulo, autor, titulo


def ler_limpo(caminho):
    txt = caminho.read_text(encoding="utf-8-sig")
    linhas = txt.splitlines()
    topo = {"total": None, "etapas": None, "blocos": None, "indice": {}}
    itens, erros = [], []
    tem_cabecalhos = any(ETAPA_RE.match(l) for l in linhas)
    etapa, prev, no_corpo = 0, 0, False

    for i, lin in enumerate(linhas, 1):
        mh = ETAPA_RE.match(lin)
        if mh:
            etapa, prev, no_corpo = int(mh.group(1)), 0, True
            continue
        m = ITEM_RE.match(lin)
        if m and (no_corpo or not tem_cabecalhos):
            num = int(m.group(1))
            if not tem_cabecalhos:
                no_corpo = True
                if num == 1:
                    etapa += 1
                    prev = 0
                if etapa == 0:
                    erros.append(f"linha {i}: o primeiro item não é o número 1")
                    etapa = 1
            if num != prev + 1:
                erros.append(f"linha {i} (etapa {etapa}): veio o número {num}, esperado {prev + 1}")
            prev = num
            texto, autor, titulo = analisar_item(m.group(2))
            itens.append({
                "e": etapa, "n": num, "texto": texto, "autor": autor, "titulo": titulo,
                "ntexto": norm(texto), "nt": norm(titulo), "na": norm(autor) if autor else None,
            })
        elif not no_corpo:
            mt = TOTAL_RE.search(lin)
            if mt and topo["total"] is None:
                topo["total"] = int(mt.group(1))
                if mt.group(2):
                    topo["etapas"], topo["blocos"] = int(mt.group(2)), int(mt.group(3))
            mi = IDX_RE.match(lin)
            if mi:
                topo["indice"][int(mi.group(1))] = (mi.group(2).strip(), int(mi.group(3)))

    if not itens:
        erros.append("não achei nenhum item (linhas que começam com  N. ) depois dos cabeçalhos de etapa")
        return itens, {}, topo, erros

    por_etapa = {}
    for it in itens:
        por_etapa.setdefault(it["e"], []).append(it)

    if topo["total"] is not None and topo["total"] != len(itens):
        erros.append(f"o topo diz {topo['total']} itens, mas contei {len(itens)}")
    for e, (_nome, n) in sorted(topo["indice"].items()):
        achei = len(por_etapa.get(e, []))
        if achei != n:
            erros.append(f"Etapa {e}: o índice do topo diz {n} itens, mas contei {achei}")
    for e in sorted(por_etapa):
        if topo["indice"] and e not in topo["indice"]:
            erros.append(f"Etapa {e}: existe no corpo, mas não está no índice do topo")
    return itens, por_etapa, topo, erros


# ----------------------------------------------------------- busca por título
class Relatorio:
    def __init__(self):
        self.avisos = []
        self.mudancas_antigas = []   # etapas 1-13: número mudou (inesperado)
        self.mudancas_novas = 0      # etapas 14-21: número mudou (esperado após separar)
        self.marcadores = 0


def achar_por_titulo(por_etapa, etapa, chave, fallback, rel):
    its = por_etapa.get(etapa, [])
    k = norm(chave)
    niveis = (
        lambda it: it["nt"] == k,
        lambda it: it["ntexto"] == k,
        lambda it: it["nt"].startswith(k) or it["ntexto"].startswith(k),
        lambda it: k in it["nt"] or k in it["ntexto"],
    )
    for f in niveis:
        c = [it["n"] for it in its if f(it)]
        if not c:
            continue
        if len(c) == 1:
            return c[0]
        if fallback in c:
            return fallback
        rel.avisos.append(f"Etapa {etapa}, «{chave}»: {len(c)} itens parecidos ({', '.join(map(str, c[:6]))}); "
                          f"mantive o número {fallback}. CONFIRA.")
        return fallback
    rel.avisos.append(f"Etapa {etapa}, «{chave}»: não achei esse título na lista; mantive o número {fallback}. CONFIRA.")
    return fallback


def achar_entrada(por_etapa, etapa, fallback, texto, rel):
    """Devolve a lista de números de item que correspondem a uma 'entrada acrescentada'."""
    its = por_etapa.get(etapa, [])
    nt = norm(texto)
    exato = [it["n"] for it in its if it["ntexto"] == nt]
    if exato:
        return exato[:1]

    autor, titulo = dividir(texto)
    partes = [p.strip() for p in titulo.split(";") if p.strip()]
    na = norm(autor) if autor else None
    achados, faltaram = set(), []
    for p in partes:
        np_ = norm(p)
        cand = []
        for it in its:
            if na is not None and it["na"] != na:
                continue
            t = it["nt"] if na is not None else it["ntexto"]
            if t == np_ or np_ in t or (len(t) >= 6 and t in np_):
                cand.append(it["n"])
        if not cand:
            melhor, razao = None, 0.0
            for it in its:
                if na is not None and it["na"] != na:
                    continue
                t = it["nt"] if na is not None else it["ntexto"]
                r = difflib.SequenceMatcher(None, np_, t).ratio()
                if r > razao:
                    melhor, razao = it["n"], r
            if melhor is not None and razao >= 0.8:
                cand = [melhor]
        if cand:
            achados.update(cand)
        else:
            faltaram.append(p)

    if not achados:
        rel.avisos.append(f"Etapa {etapa}, entrada «{texto[:70]}»: não achei na lista; mantive o número {fallback}. CONFIRA.")
        return [fallback]
    if faltaram:
        rel.avisos.append(f"Etapa {etapa}, entrada «{texto[:70]}»: não achei a(s) obra(s) {faltaram}; "
                          f"mostrei só os itens que achei. CONFIRA.")
    return sorted(achados)


def lista_pt(nums):
    s = [str(n) for n in nums]
    if len(s) == 1:
        return s[0]
    return ", ".join(s[:-1]) + " e " + s[-1]


# ------------------------------------------------------------------ marcadores
def frase_total(total):
    if total == TOTAL_BASE:
        return f"Total: {total} linhas ({FRASE_BASE})"
    d = total - TOTAL_BASE
    if d > 0:
        extra = (f"; depois disso, a separação de itens que juntavam várias obras "
                 f"(um item por obra) acrescentou {d}")
    else:
        extra = f"; depois disso, ficaram {abs(d)} a menos"
    return f"Total: {total} linhas ({FRASE_BASE}, que somavam {TOTAL_BASE}{extra})"


class Contexto:
    def __init__(self, itens, por_etapa, topo, rel):
        self.itens, self.por_etapa, self.topo, self.rel = itens, por_etapa, topo, rel
        self.contagem_avisada = set()

    def marcador(self, inner):
        self.rel.marcadores += 1
        p = inner.split("|")
        tipo = p[0]
        if tipo == "n":
            e, chave, fb = int(p[1]), p[2], int(p[3])
            n = achar_por_titulo(self.por_etapa, e, chave, fb, self.rel)
            if n != fb:
                if e <= 13:
                    self.rel.mudancas_antigas.append(f"Etapa {e}, «{chave}»: {fb} → {n}")
                else:
                    self.rel.mudancas_novas += 1
            return str(n)
        if tipo == "count":
            e = int(p[1])
            n = len(self.por_etapa.get(e, []))
            if len(p) > 2 and int(p[2]) != n and e not in self.contagem_avisada:
                self.contagem_avisada.add(e)
                self.rel.avisos.append(
                    f"Etapa {e}: tinha {p[2]} itens e agora tem {n}. A contagem foi atualizada, mas as linhas de "
                    f"origem (só A / só B / A+B) dessa etapa, na seção 2 do bastidores, não podem ser recalculadas "
                    f"(a etapa devia ficar fixa).")
            return str(n)
        if tipo == "total_frase":
            return frase_total(len(self.itens))
        if tipo == "n_etapas":
            return str(self.topo["etapas"] or len(self.por_etapa))
        if tipo == "n_blocos":
            return str(self.topo["blocos"] or BLOCOS_PADRAO)
        raise ValueError(f"marcador desconhecido: {{{{{inner}}}}}")

    def entrada(self, e, fb, texto):
        self.rel.marcadores += 1
        nums = achar_entrada(self.por_etapa, e, fb, texto, self.rel)
        if nums != [fb]:
            if e >= 14:
                self.rel.mudancas_novas += 1
            else:
                self.rel.mudancas_antigas.append(f"Etapa {e}, entrada «{texto[:50]}»: {fb} → {lista_pt(nums)}")
        rotulo = "item" if len(nums) == 1 else "itens"
        return (e, nums[0], f"- Etapa {e}, {rotulo} {lista_pt(nums)}: {texto}")


def renderizar(modelo, ctx):
    saida, grupo = [], []

    def fecha():
        for _e, _n, lin in sorted(grupo, key=lambda x: (x[0], x[1])):
            saida.append(lin)
        grupo.clear()

    for lin in modelo.split("\n"):
        m = ENTRADA_RE.match(lin)
        if m:
            grupo.append(ctx.entrada(int(m.group(1)), int(m.group(2)), m.group(3)))
            continue
        fecha()
        saida.append(MARCADOR_RE.sub(lambda mm: ctx.marcador(mm.group(1)), lin))
    fecha()
    return "\n".join(saida)


# ------------------------------------------------------------------------ main
def main():
    testar = "--testar" in sys.argv[1:]

    if not LIMPO.exists():
        print(f"ERRO: não achei {LIMPO.name} nesta pasta ({PASTA}).")
        return 1
    for modelo, _ in PARES:
        if not modelo.exists():
            print(f"ERRO: não achei {modelo.name} nesta pasta. Ele precisa ficar junto do script.")
            return 1

    itens, por_etapa, topo, erros = ler_limpo(LIMPO)
    if erros:
        print(f"ERRO: o {LIMPO.name} não passou na conferência. Nada foi gravado:")
        for e in erros[:30]:
            print("  -", e)
        if len(erros) > 30:
            print(f"  ... e mais {len(erros) - 30} problemas.")
        return 1
    print(f"Lista limpa: {len(itens)} itens em {len(por_etapa)} etapas (conferido com o topo do arquivo).")

    rel = Relatorio()
    ctx = Contexto(itens, por_etapa, topo, rel)
    resultados = []
    for modelo, destino in PARES:
        texto = renderizar(modelo.read_text(encoding="utf-8-sig"), ctx)
        sobra = MARCADOR_RE.findall(texto)
        if sobra or "{{" in texto or "}}" in texto:
            print(f"ERRO: sobrou marcador sem preencher em {modelo.name}: {sobra[:3]}. Nada foi gravado.")
            return 1
        resultados.append((destino, texto))

    for destino, texto in resultados:
        antigo = destino.read_text(encoding="utf-8-sig") if destino.exists() else None
        situacao = "sem mudanças" if antigo == texto else ("seria atualizado" if testar else "atualizado")
        if not testar and antigo != texto:
            tmp = destino.with_suffix(destino.suffix + ".tmp")
            tmp.write_text(texto, encoding="utf-8", newline="\n")
            os.replace(tmp, destino)
        print(f"{destino.name}: {situacao}")

    rel.avisos = list(dict.fromkeys(rel.avisos))
    rel.mudancas_antigas = list(dict.fromkeys(rel.mudancas_antigas))
    if rel.mudancas_novas:
        print(f"{rel.mudancas_novas} números mudaram nas etapas 14 a 21 (esperado quando itens são separados).")
    if rel.mudancas_antigas:
        print("Números que mudaram nas etapas 1 a 13 (essas etapas deviam estar fixas, confira):")
        for x in rel.mudancas_antigas[:30]:
            print("  -", x)
    if rel.avisos:
        print(f"ATENÇÃO: {len(rel.avisos)} ponto(s) para conferir:")
        for x in rel.avisos[:40]:
            print("  -", x)
        if len(rel.avisos) > 40:
            print(f"  ... e mais {len(rel.avisos) - 40}.")
    if testar:
        print("(modo --testar: nada foi gravado)")
    return 2 if rel.avisos else 0


if __name__ == "__main__":
    sys.exit(main())
