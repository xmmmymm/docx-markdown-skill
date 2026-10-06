# -*- coding: utf-8 -*-
# S0 census (main agent, generic template v2 -- 序2 起用).
# Self-locating: ROOT = dirname(__file__) == <输出目录>\work ; reads ROOT\unpacked.
# stdout = ASCII summary only ; full detail -> s0_census.txt (UTF-8)
import re, json, io, os
import xml.etree.ElementTree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
V = 'urn:schemas-microsoft-com:vml'


def q(ns, t):
    return '{%s}%s' % (ns, t)


ROOT = os.path.dirname(os.path.abspath(__file__))
UNP = os.path.join(ROOT, 'unpacked')
DOC = os.path.join(UNP, 'word', 'document.xml')
raw = io.open(DOC, encoding='utf-8').read()

out = []


def w(s):
    out.append(s)


# ---------- 1. raw XML element counts (carrier triple test + structure) ----------
def c(tag, s=None):
    s = s if s is not None else raw
    return len(re.findall(tag, s))


cnt = {
    'w:p': c(r'<w:p[ >]'),
    'w:tbl': c(r'<w:tbl\b'),
    'w:tr': c(r'<w:tr[ >]'),
    'w:tab': c(r'<w:tab\b'),
    'w:br': c(r'<w:br\b'),
    'w:cr': c(r'<w:cr\b'),
    'w:t': c(r'<w:t[ >]'),
    'w:object': c(r'<w:object\b'),          # carrier 1 (MathType / other OLE)
    'w:instrText': c(r'<w:instrText\b'),    # carrier 3 (EQ field)
    'w:fldChar': c(r'<w:fldChar\b'),
    'fldSimple': c(r'<w:fldSimple\b'),
    'm:oMath': c(r'<m:oMath[ >]'),          # carrier 2 (native OMML)
    'm:oMathPara': c(r'<m:oMathPara\b'),
    'w:drawing': c(r'<w:drawing\b'),
    'v:imagedata': c(r'<v:imagedata\b'),
    'a:blip': c(r'<a:blip\b'),
    'vertAlign(sub)': c(r'w:val="subscript"'),
    'vertAlign(sup)': c(r'w:val="superscript"'),
    'w:numPr': c(r'<w:numPr\b'),
    'MC:Choice': c(r'<mc:Choice\b'),
    'MC:Fallback': c(r'<mc:Fallback\b'),
    'txbxContent': c(r'<w:txbxContent\b'),
    'w:sym': c(r'<w:sym\b'),
    'noBreakHyphen': c(r'<w:noBreakHyphen\b'),
    'softHyphen': c(r'<w:softHyphen\b'),
}
w('## 1. raw XML counts (carrier triple test first)')
for k, v in cnt.items():
    w('- %s = %d' % (k, v))
w('')

# ---------- 2. paragraphs ----------
tree = ET.parse(DOC)
root = tree.getroot()
paras = []
for p in root.iter(q(W, 'p')):
    txt = ''.join(t.text or '' for t in p.iter(q(W, 't')))
    paras.append(txt)
alltext = '\n'.join(paras)
w('## 2. paragraph count (incl. table paras) = %d ; chars = %d' % (len(paras), len(alltext)))
w('')

# ---------- 3. carrier 5 check: Unicode sub/superscript chars in text ----------
SUBS = '₀₁₂₃₄₅₆₇₈₉ₐₑₕₖₗₘₙₚₛₜ'
SUPS = '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿⁱ'
subc = sum(alltext.count(ch) for ch in SUBS)
supc = sum(alltext.count(ch) for ch in SUPS)
w('## 3. carrier-5 discriminators')
w('- Unicode subscript chars in text = %d' % subc)
w('- Unicode superscript chars in text = %d' % supc)
w('- vertAlign runs = %d/%d' % (cnt['vertAlign(sub)'], cnt['vertAlign(sup)']))
w('- pure-blank script runs = %d' % 0)
blankscript = 0
blankscript_prevtext = 0
for r_ in root.iter(q(W, 'r')):
    va = r_.find('%s/%s' % (q(W, 'rPr'), q(W, 'vertAlign')))
    if va is None:
        continue
    ts = [t.text or '' for t in r_.findall(q(W, 't'))]
    s = ''.join(ts)
    if s.strip() == '' and s != '':
        blankscript += 1
for p in root.iter(q(W, 'p')):
    rs = list(p.iter(q(W, 'r')))
    for i, r_ in enumerate(rs):
        va = r_.find('%s/%s' % (q(W, 'rPr'), q(W, 'vertAlign')))
        if va is None:
            continue
        s = ''.join(t.text or '' for t in r_.findall(q(W, 't')))
        if s != '' and s.strip() == '' and i > 0:
            prev = ''.join(t.text or '' for t in rs[i - 1].findall(q(W, 't')))
            if prev.strip():
                blankscript_prevtext += 1
w('- pure-blank script runs (total) = %d' % blankscript)
w('-   of which previous run has text (U53 layout space) = %d' % blankscript_prevtext)
w('')

# ---------- 4. blank codepoints (with positions) ----------
pos = {'NBSP_U00A0': [], 'U3000': [], 'U2000_200A': [], 'ZWSP_U200B': []}
afterdot = 0
for i, t in enumerate(paras):
    for j, ch in enumerate(t):
        o = ord(ch)
        if o == 0xA0:
            pos['NBSP_U00A0'].append(i)
            if j and t[j - 1] in '.．':
                afterdot += 1
        elif o == 0x3000:
            pos['U3000'].append(i)
        elif 0x2000 <= o <= 0x200A:
            pos['U2000_200A'].append((i, hex(o)))
        elif o == 0x200B:
            pos['ZWSP_U200B'].append(i)
w('## 4. blank codepoints')
for k, v in pos.items():
    w('- %s = %d  paras=%s' % (k, len(v), sorted(set(v))[:15] if k != 'U2000_200A' else v[:15]))
w('- NBSP immediately after a dot = %d' % afterdot)
w('')

# ---------- 5. fullwidth / special symbols ----------
fw = {}
for name, ch in [('PLUS_UFF0B', '\uff0b'), ('EQ_UFF1D', '\uff1d'), ('DBLEQ_U2550', '\u2550'),
                 ('BULLET_U2022', '\u2022'), ('GT_UFF1E', '\uff1e'), ('LT_UFF1C', '\uff1c'),
                 ('MINUS_UFF0D', '\uff0d'), ('TRIEQ_U225C', '\u225c'),
                 ('TRI_up_U25B3', '\u25b3'), ('DELTA_U0394', '\u0394'),
                 ('ARROW_R_U2192', '\u2192'), ('HARpoons_U21CC', '\u21cc'),
                 ('MIDDOT_U00B7', '\u00b7'), ('CDOT_U2219', '\u2219'), ('KDOT_U22C5', '\u22c5')]:
    fw[name] = alltext.count(ch)
w('## 5. fullwidth / special symbol counts')
for k, v in fw.items():
    w('- %s = %d' % (k, v))
w('- raw "===" in text = %d' % alltext.count('==='))
w('')

# ---------- 6. question-number morphology ----------
QT = re.compile(r'^(?:（多选）|（单选）)?\s*(\d+)\s*[．、]')
QTDOT = re.compile(r'^(?:（多选）|（单选）)?\s*(\d+)\.')
qt_hit, qt_dot, qt_loose = [], [], []
for i, t in enumerate(paras):
    s = t.strip()
    if not s:
        continue
    if QT.match(s):
        qt_hit.append((i, s[:38]))
    elif QTDOT.match(s):
        qt_dot.append((i, s[:38]))
    elif re.match(r'^.{0,8}?\d+\s*[．、]', s) and len(s) < 60:
        qt_loose.append((i, s[:38]))
w('## 6. question-number morphology')
w('- strict ^(（多选）)?\\d+[．、] = %d' % len(qt_hit))
for i, s in qt_hit[:45]:
    w('  p%d: %s' % (i, s))
w('- halfwidth dot form ^\\d+\\. = %d' % len(qt_dot))
for i, s in qt_dot[:20]:
    w('  p%d: %s' % (i, s))
w('- loose only = %d' % len(qt_loose))
for i, s in qt_loose[:15]:
    w('  p%d: %s' % (i, s))
w('')

# ---------- 7. answer-section morphology ----------
w('## 7. short lines containing ANS/JIEXI (len<30)')
for i, t in enumerate(paras):
    s = t.strip()
    if ('\u7b54\u6848' in s or '\u89e3\u6790' in s) and 0 < len(s) < 30:
        w('- p%d: %r' % (i, s))
w('')

# ---------- 8. labels ----------
lab = {}
for name in ['\u3010\u7b54\u6848\u3011', '\u3010\u53c2\u8003\u7b54\u6848\u3011', '\u3010\u8be6\u89e3\u3011',
             '\u3010\u89e3\u6790\u3011', '\u3010\u5206\u6790\u3011', '\u3010\u70b9\u775b\u3011',
             '\u7b54\u6848', '\u89e3\u6790']:
    lab[name] = alltext.count(name)
w('## 8. label counts')
for k, v in lab.items():
    w('- %s = %d' % (k, v))
w('')

# ---------- 9. lecture style + option lines ----------
w('## 9. lecture style')
for name in ['\u3010\u5178\u4f8b', '\u3010\u53d8\u5f0f', '\u3010\u8bfe\u65f6\u4f5c\u4e1a\u53c2\u8003\u7b54\u6848\u3011',
             '\u6807\u51c6\u7b54\u6848', '\u57fa\u7840', '\u63d0\u5347']:
    w('- %s = %d' % (name, alltext.count(name)))
opt = re.compile(r'^[A-E][\uff0e.\u3001]')
optn = [(i, t.strip()[:38]) for i, t in enumerate(paras) if opt.match(t.strip())]
w('- option-like lines ^[A-E][dot] = %d' % len(optn))
for i, s in optn[:15]:
    w('  p%d: %s' % (i, s))
w('')

# ---------- 10. EQ field instruction survey ----------
instr = []
for it in root.iter(q(W, 'instrText')):
    instr.append((it.text or '').strip())
pref = {}
for s in instr:
    m = re.match(r'\\([a-zA-Z]+)', s)
    key = '\\' + (m.group(1) if m else '?')
    pref[key] = pref.get(key, 0) + 1
w('## 10. EQ field instrText survey = %d' % len(instr))
for k, v in sorted(pref.items(), key=lambda x: -x[1]):
    w('- prefix %s = %d' % (k, v))
w('- nested \\o (\\o containing another \\o or \\s) = %d' % sum(1 for s in instr if s.count('\\o') > 1))
w('- sample instr (first 12, repr):')
for s in instr[:12]:
    w('  %r' % s[:90])
w('')

# ---------- 11. media inventory + rel mapping + orphans ----------
mdir = os.path.join(UNP, 'word', 'media')
w('## 11. media inventory')
files = sorted(os.listdir(mdir)) if os.path.isdir(mdir) else []
w('- count = %d' % len(files))
try:
    from PIL import Image
except Exception:
    Image = None
big = 0
for f in files:
    fp = os.path.join(mdir, f)
    sz = os.path.getsize(fp)
    dim = '?'
    if Image is not None:
        try:
            with Image.open(fp) as im:
                dim = '%dx%d' % im.size
                if max(im.size) >= 1000:
                    big += 1
        except Exception:
            dim = 'NOTIMG/ERR'
    w('- %s  %d B  %s' % (f, sz, dim))
w('- >=1000px count = %d' % big)

rels_p = os.path.join(UNP, 'word', '_rels', 'document.xml.rels')
relmap = {}
if os.path.isfile(rels_p):
    rr = io.open(rels_p, encoding='utf-8').read()
    for m_ in re.finditer(r'Id="([^"]+)"[^>]*Target="media/([^"]+)"', rr):
        relmap[m_.group(1)] = m_.group(2)
used_ids = set(re.findall(r'r:embed="([^"]+)"', raw)) | set(re.findall(r'r:id="([^"]+)"', raw))
used_names = sorted({relmap[i] for i in used_ids if i in relmap})
orphans = [f for f in files if f not in used_names]
w('- rel entries(media) = %d ; referenced in document.xml = %d ; orphan = %s' % (
    len(relmap), len(used_names), json.dumps(orphans)))
# header/footer media references
hf_used = []
for fn in sorted(os.listdir(os.path.join(UNP, 'word'))):
    if re.match(r'^(header|footer)\d*\.xml$', fn):
        s = io.open(os.path.join(UNP, 'word', fn), encoding='utf-8').read()
        ids = set(re.findall(r'r:(?:embed|id)="([^"]+)"', s))
        txt = ''.join(re.findall(r'<w:t[ >][^<]*</w:t>', s))
        txt = re.sub(r'<[^>]+>', '', ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', s)))
        hf_used.append((fn, sorted({relmap.get(i, '?') for i in ids}), len(txt)))
w('- header/footer files = %d' % len(hf_used))
for fn, mm, tl in hf_used:
    w('  %s media=%s textlen=%d' % (fn, mm, tl))
w('')

# ---------- 12. embeddings ----------
edir = os.path.join(UNP, 'word', 'embeddings')
w('## 12. embeddings (OLE)')
w('- exists = %s' % os.path.isdir(edir))
if os.path.isdir(edir):
    for f in sorted(os.listdir(edir)):
        fp = os.path.join(edir, f)
        b = open(fp, 'rb').read()
        prog = '?'
        i = b.find(b'CompObj')
        if i >= 0:
            seg = b[i:i + 200].replace(b'\x00', b' ')
            m2 = re.search(rb'[A-Za-z0-9/_ .]{3,40}', seg)
            prog = (m2.group(0).strip() if m2 else b'?')[:40].decode('latin1')
        streams = [s.decode('latin1') for s in re.findall(rb'\x01([A-Za-z0-9_]{3,20})', b)]
        w('- %s  %d B  compobj~%r  flows=%s' % (f, len(b), prog,
                                                sorted({s for s in streams if s in ('Ole10Native', 'Equation Native', 'PRINT', 'CompObj', 'ObjInfo')})))
w('- ole preview wmf in media = %d' % len([f for f in files if f.endswith('.wmf')]))
w('')

io.open(os.path.join(ROOT, 's0_census.txt'), 'w', encoding='utf-8').write('\n'.join(out))
print('OK paras=%d chars=%d qnum=%d qdot=%d media=%d orphan=%d big1000=%d obj=%d instr=%d omath=%d sub=%d sup=%d uni_sub=%d uni_sup=%d' % (
    len(paras), len(alltext), len(qt_hit), len(qt_dot), len(files), len(orphans), big,
    cnt['w:object'], cnt['w:instrText'], cnt['m:oMath'],
    cnt['vertAlign(sub)'], cnt['vertAlign(sup)'], subc, supc))
