#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerar_indice.py - gera o indice compacto (indice-compacto.txt) a partir do canone-limpo.md.

Uso, na pasta onde esta o canone-limpo.md:
    python gerar_indice.py

Sempre que mudar o limpo, rode de novo: ele substitui o indice-compacto.txt.
Nao altera o canone-limpo.md.

Conferencia automatica (voce nao precisa atualizar nada a mao):
Compara o que achou com os numeros do topo do limpo ("Etapa 5: Platao: 71 itens").
  igual ........................ ok
  achou MAIS que o topo ........ aviso: item novo, o texto do topo ficou desatualizado
  achou so um pouco MENOS ...... aviso (ate 10% a menos)
  achou bem MENOS, ou zero ..... PROBLEMA: formato de linha nao reconhecido
Se houver PROBLEMA, grava indice-compacto-PROBLEMA.txt e NAO mexe no indice-compacto.txt.
"""
import os, re, sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

arq = sys.argv[1] if len(sys.argv) > 1 else 'canone-limpo.md'
if not os.path.exists(arq):
    print('Nao achei', arq, '- rode o script na pasta onde ele esta.')
    sys.exit(1)

BLOCO = re.compile(r'\s*\(Bloco \d+ — [^()]*(\([^()]*\))?[^()]*\)')
TAGS = re.compile(r'\s*·\s*\[(só A|só B|A\+B)\]')

esperado = {}   # numero da etapa -> itens declarados no topo do limpo
etapas = []
atual = None

with open(arq, encoding='utf-8') as f:
    for linha in f:
        l = linha.rstrip('\n')
        s = l.strip()

        m = re.match(r'^-\s*Etapa\s+(\d+):.*:\s*(\d+)\s+itens', s)
        if m and atual is None:
            esperado[int(m.group(1))] = int(m.group(2))
            continue

        m = re.match(r'^#+\s*Etapa\s+(\d+)\b\s*:?\s*(.*)', s)
        if m:
            atual = {'num': int(m.group(1)),
                     'titulo': 'Etapa %s: %s' % (m.group(1), m.group(2).strip()),
                     'itens': [], 'amostra': []}
            etapas.append(atual)
            continue

        if atual is None:
            continue
        if s.startswith('#'):
            atual = None
            continue

        if s and len(atual['amostra']) < 3:
            atual['amostra'].append(s[:150])

        m = re.match(r'^(\d+)[.)]\s+(.*)', l)
        if m:
            t = m.group(2).replace('*', '')
            t = BLOCO.sub('', t)
            t = TAGS.sub('', t)
            atual['itens'].append('%s. %s' % (m.group(1), t.strip()))

texto = '\n'.join(['\n'.join(['## ' + e['titulo']] + e['itens']) for e in etapas]) + '\n'

print('CONFERENCIA (achados x numero escrito no topo do limpo)')
problemas, avisos = [], []
total = 0
for e in etapas:
    achou = len(e['itens'])
    total += achou
    decl = esperado.get(e['num'])
    if decl is None:
        status = 'sem numero no topo'
    elif achou == decl:
        status = 'ok'
    elif achou > decl:
        status = 'aviso: %d a mais que o topo' % (achou - decl)
        avisos.append((e, decl, achou))
    elif achou >= 0.9 * decl:
        status = 'aviso: %d a menos que o topo' % (decl - achou)
        avisos.append((e, decl, achou))
    else:
        status = 'PROBLEMA'
        problemas.append(e)
    print('  Etapa %2d: achei %3d | topo diz %s | %s' % (
        e['num'], achou, '-' if decl is None else decl, status))

print('\nTOTAL achado: %d | soma do topo: %d' % (total, sum(esperado.values())))

destino = 'indice-compacto-PROBLEMA.txt' if problemas else 'indice-compacto.txt'
with open(destino, 'w', encoding='utf-8') as f:
    f.write(texto)
print('Gravei %s (%.0f KB)' % (destino, os.path.getsize(destino) / 1024))

print()
if problemas:
    print('RESULTADO: PROBLEMA. Estas etapas parecem incompletas. 3 primeiras linhas de cada:')
    for e in problemas:
        print('\n--', e['titulo'])
        for a in e['amostra']:
            print('   ', a)
    print('\nO indice-compacto.txt anterior NAO foi alterado.')
elif avisos:
    print('RESULTADO: OK. O indice esta certo e foi atualizado.')
    print('Nota: o numero escrito no topo do limpo esta desatualizado nas etapas marcadas')
    print('"aviso". Isso nao afeta o indice; so o texto do topo do limpo.')
else:
    print('RESULTADO: OK. O indice esta certo e foi atualizado.')
