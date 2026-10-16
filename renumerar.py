#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renumerar.py - renumera os itens de cada etapa do canone-limpo.md e corrige os numeros do topo
(total, itens por etapa, itens por bloco). Nao muda a ordem nem o texto dos itens.
Uso: python renumerar.py   (na pasta do canone-limpo.md)"""
import os, re, sys, shutil, time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ARQ = 'canone-limpo.md'
ITEM = re.compile(r'^(\d+)([.)])(\s+)(.*)$')
ETAPA = re.compile(r'^#+\s*Etapa\s+(\d+)\b')
BLOCO = re.compile(r'\(Bloco (\d+) \u2014')
TOP_ETAPA = re.compile(r'^(-\s*Etapa\s+(\d+):.*:\s*)(\d+)(\s+itens.*)$')
TOP_BLOCO = re.compile(r'^(-\s*\(Bloco (\d+) \u2014.*\):\s*)(\d+)(\s+itens.*)$')
TOP_TOTAL = re.compile(r'^(Total:\s*)(\d+)(\s+itens.*)$')


def main():
    if not os.path.exists(ARQ):
        print('PARADO: nao achei %s nesta pasta.' % ARQ)
        sys.exit(1)
    bruto = open(ARQ, 'rb').read()
    bom = bruto.startswith(b'\xef\xbb\xbf')
    texto = bruto.decode('utf-8-sig')
    crlf = '\r\n' in texto
    linhas = texto.replace('\r\n', '\n').split('\n')

    primeiro = None
    for i, l in enumerate(linhas):
        if ETAPA.match(l.strip()):
            primeiro = i
            break
    if primeiro is None:
        print('PARADO: nao achei nenhum cabecalho "## Etapa N". Nada foi gravado.')
        sys.exit(1)

    novas = list(linhas)
    etapa = None
    cont, mudou, ordem = {}, {}, []
    blocos, sem_bloco = {}, []
    for i in range(primeiro, len(linhas)):
        l = linhas[i]
        m = ETAPA.match(l.strip())
        if m:
            etapa = int(m.group(1))
            if etapa in cont:
                print('PARADO: a Etapa %d aparece duas vezes no guia. Nada foi gravado.' % etapa)
                sys.exit(1)
            cont[etapa] = 0
            mudou[etapa] = 0
            ordem.append(etapa)
            continue
        m = ITEM.match(l)
        if m and etapa is not None:
            cont[etapa] += 1
            n = cont[etapa]
            if int(m.group(1)) != n:
                mudou[etapa] += 1
                novas[i] = '%d%s%s%s' % (n, m.group(2), m.group(3), m.group(4))
            b = BLOCO.search(l)
            if b:
                k = int(b.group(1))
                blocos[k] = blocos.get(k, 0) + 1
            else:
                sem_bloco.append((etapa, n))

    for e in ordem:
        if cont[e] == 0:
            print('PARADO: a Etapa %d ficou com zero itens (formato nao reconhecido?). Nada foi gravado.' % e)
            sys.exit(1)

    total = sum(cont.values())
    mudancas = []
    topo_etapas = set()
    for i in range(primeiro):
        l = novas[i]
        m = TOP_ETAPA.match(l)
        if m and int(m.group(2)) in cont:
            e = int(m.group(2))
            topo_etapas.add(e)
            if int(m.group(3)) != cont[e]:
                novas[i] = m.group(1) + str(cont[e]) + m.group(4)
                mudancas.append('topo, Etapa %d: %s -> %d itens' % (e, m.group(3), cont[e]))
            continue
        m = TOP_BLOCO.match(l)
        if m:
            k = int(m.group(2))
            alvo = blocos.get(k, 0)
            if int(m.group(3)) != alvo:
                novas[i] = m.group(1) + str(alvo) + m.group(4)
                mudancas.append('topo, Bloco %d: %s -> %d itens' % (k, m.group(3), alvo))
            continue
        m = TOP_TOTAL.match(l)
        if m:
            if int(m.group(2)) != total:
                novas[i] = m.group(1) + str(total) + m.group(3)
                mudancas.append('topo, Total: %s -> %d itens' % (m.group(2), total))

    avisos = []
    for e in ordem:
        if e not in topo_etapas:
            avisos.append('A Etapa %d nao tem linha de contagem no topo (nada a ajustar la).' % e)
    if sem_bloco:
        avisos.append('%d itens sem "(Bloco K \u2014 ...)" (nao entram na contagem por bloco): %s' % (
            len(sem_bloco), ', '.join('Etapa %d item %d' % x for x in sem_bloco[:10])))
    ant = [e for e in ordem if e <= 13 and mudou[e]]
    if ant:
        avisos.append('Foram renumerados itens da Lista A (etapas %s). O bastidores acha pelo titulo, entao deve se ajustar; '
                      'se o atualizar.bat mostrar CONFIRA, ajuste a linha indicada no modelo-bastidores.md.'
                      % ', '.join(str(e) for e in ant))

    n_renum = sum(mudou.values())
    if n_renum == 0 and not mudancas:
        print('Nada a mudar: numeracao e topo ja estao certos (%d itens em %d etapas).' % (total, len(ordem)))
        for a in avisos:
            print('ATENCAO:', a)
        return

    pasta = os.path.join('copias', 'renumerar-' + time.strftime('%Y-%m-%d_%H-%M-%S'))
    os.makedirs(pasta, exist_ok=True)
    shutil.copy2(ARQ, os.path.join(pasta, ARQ))

    saida = '\n'.join(novas)
    if crlf:
        saida = saida.replace('\n', '\r\n')
    dados = saida.encode('utf-8')
    if bom:
        dados = b'\xef\xbb\xbf' + dados
    tmp = ARQ + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(dados)
    os.replace(tmp, ARQ)

    print('PRONTO. canone-limpo.md ajustado. Copia anterior em: %s' % pasta)
    print('Itens renumerados: %d' % n_renum)
    for e in ordem:
        if mudou[e]:
            print('   Etapa %d: %d numeros corrigidos (agora %d itens)' % (e, mudou[e], cont[e]))
    for c in mudancas:
        print('   ' + c)
    for a in avisos:
        print('ATENCAO:', a)


main()