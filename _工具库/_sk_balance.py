# -*- coding: utf-8 -*-
r"""【skill · 通用】S9 独立守恒复算（U64 必备能力）。

来源：硫批次 `_工具库\_s9_balance9.py`（U64 范式第四实现，序6→序7→序8→序9 递进成熟版）；
本批仅做"参数化"改造（原本硬编码单件路径），逻辑逐字未改。

能力（U64）：系数 × 嵌套括号组（`2H₂SO₄`/`Ca(OH)₂`/(NH₄)₂SO₄）、只按顶层 `+` 切项、
先剥离「中文括注 `(浓)`」「条件等号 `=(X)=`」「`(4e⁻)` 标注」、括号倍数读在 `)` 之后；
另输出"伪方程式"清单（连接符为 `——`/`—`/`==`/`-` 而非 `=`，不入解析器 —— 见 U80）。

用法：
    <py> _sk_balance.py "<成品 md 绝对路径>"
    <py> _sk_balance.py                       # 缺省：取脚本所在目录的上级目录同名 md
输出：与 md 同目录 `work\_sk_balance_out.txt`（UTF-8）；stdout 仅 ASCII 摘要。
"""
import io
import re
import sys
from pathlib import Path

args = sys.argv[1:]
if args:
    MD = Path(args[0])
else:
    here = Path(__file__).resolve().parent          # <输出目录>\work
    outdir = here.parent
    MD = outdir / (outdir.name + ".md")
# 路径不存在时须给用法并以 2 退出（旧版直接 read_text ⇒ FileNotFoundError 裸栈）。
# 注意：stderr 亦须纯 ASCII（U2/U90，GBK 终端会吞中文）⇒ 用法行用英文。
if not MD.is_file():
    sys.stderr.write("BAD md not found: %s\n"
                     % MD.name.encode("unicode_escape").decode("ascii"))
    sys.stderr.write("usage: _sk_balance.py <path-to-final.md>\n"
                     "       (omit arg => <parent-of-work>\\<dirname>.md)\n")
    sys.exit(2)
stem = MD.stem

txt = MD.read_text(encoding="utf-8", errors="replace")
# 剔除 图描述 与 图片引用
txt = re.sub(r"〔图：[^〕]*〕", "", txt)
txt = re.sub(r"!\[\]\(images/[^)]*\)", "", txt)

WHITE = "\u00a0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u200b\u3000 "
# 【U136①·建库并入】`·`（结晶水/变量水合物 `SnO₂·xH₂O` / `CuSO₄·5H₂O`）计入公式
#   字符类 ⇒ 含水合物的段完整进入候选，解析时 ELEM 不认 `·` ⇒ 自然判"不可解析"
#   （unparsed 桶），**不再**因段被 `·` 切开而漏检/误判左右差 x 项的假阳性。
FC_RE = re.compile(r"[0-9A-Za-z₀-₉⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻()\[\]↑↓+·∙⋅]")
SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
# 注：SUP 曾在此定义但从未使用（上标由下面的"电荷剥离 + SUB"两步消化），已删。


def strip_noise(s):
    s = s.translate({ord(c): None for c in WHITE})
    # 2026-09-18 序0 修订：SUB/SUP 此前只定义未使用，Unicode 上下标式全部落进 unparsed。
    # 本脚本只做**原子守恒** ⇒ 电荷上标（²⁻/⁺/³⁺…）整体剥离，下标数字转 ASCII 后再解析。
    s = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]*[⁺⁻]", "", s)
    s = s.translate(SUB)
    s = re.sub(r"[↑↓]", "", s)
    s = re.sub(r"=\(([^)]{0,10})\)=", "=", s)                    # =(Δ)= 形态
    # 【U136②·建库并入】括注剥离只针对「中文/条件括注」(浓)、(点燃)——内层为纯拉丁/
    #   数字/加减/变量的括号组是化学式本体（(OH)、(NH4)、(x+1)），**不得剥离**
    #   （旧正则 `[(（][^)）]{0,14}[)）]` 会把 Ca(OH)₂ 剥成 Ca2、把 Na[Al(OH)₄]
    #   的 (OH) 剥掉 ⇒ 方括号配位单元误算，序13 实测右端 Al=8）。
    #   判据：内层**不含任何字母/数字**（纯中文/标点）才判括注剥离。
    s = re.sub(r"[（(]([^()（）\[\]]{0,14})[)）]",
               lambda m: "" if not re.search(r"[A-Za-z0-9]", m.group(1)) else m.group(0),
               s)
    s = re.sub(r"[(（]\d*e[⁻-][)）]", "", s)                       # (4e-)
    s = re.sub(r"[⇌=]{1,}", "=", s)
    s = re.sub(r"[→]{1,}", "=", s)
    return s


def segs(line):
    """取"公式字符连续段"（含 =）"""
    out = []
    cur = ""
    for ch in line:  # noqa: F401 (kept for readability)
        if FC_RE.match(ch) or ch == "=":
            cur += ch
        else:
            if "=" in cur:
                out.append(cur)
            cur = ""
    if "=" in cur:
        out.append(cur)
    return out


ELEM = re.compile(r"([A-Z][a-z]?)(\d*)")


def parse_side(side):
    """返回 {elem: count}；失败返回 None"""
    # 【序9 新增·通用】strip_noise 后仍残留的 Unicode 上标数字（如 `1.38×10⁶g` 的 `⁶`）
    #   会被 Python `str.isdigit()` 判真、并被 ELEM 的 `\d*` 吞入 → `int('10⁶')` 抛 ValueError，
    #   使整个脚本中断、无任何输出（序9 实测 exit 1、stdout 空）。非化学方程式片段
    #   （量级式/计算式）至此直接判"不可解析"。
    if re.search(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]", side):
        return None
    d = {}
    i = 0
    n = len(side)
    while i < n:
        before = i          # 防死循环：每轮必须使 i 前进（2026-09-18 序0 实测：顶层 ")" 导致 i 不前进 → 挂死）
        c = side[i]
        if c.isdigit():
            j = i
            while j < n and side[j].isdigit():
                j += 1
            coef = int(side[i:j])
            i = j
            if i >= n:
                return None
            grp, i = read_group(side, i)
            if grp is None:
                return None
            for k, v in grp.items():
                d[k] = d.get(k, 0) + coef * v
        elif c == "+":
            i += 1
        else:
            grp, i2 = read_group(side, i)
            if grp is None:
                return None
            i = i2
            for k, v in grp.items():
                d[k] = d.get(k, 0) + v
        if i == before:      # 未前进 ⇒ 不可解析，放弃（防死循环）
            return None
    return d


def _match_paren(s, i):
    """【U136②·建库并入】s[i] 为 ( 或 [ ：返回**计数匹配**的闭括号索引（无则 -1）。
    旧 `s.find(close, i)` 只找第一个闭括号，嵌套组 ((NH₄)₂…) 会错切。"""
    depth = 0
    close = ")" if s[i] == "(" else "]"
    for k in range(i, len(s)):
        if s[k] in "([":
            depth += 1
        elif s[k] in ")]":
            depth -= 1
            if depth == 0 and s[k] == close:
                return k
    return -1


def read_group(s, i):
    """读一个化学式（含嵌套括号/方括号配位），返回 ({elem:count}, 新 i)"""
    d = {}
    n = len(s)
    while i < n:
        before = i           # 防死循环：每轮必须前进
        c = s[i]
        if c in "([":
            j = _match_paren(s, i)
            if j < 0:
                return None, i
            inner = s[i + 1:j]
            if inner == "":
                i = j + 1
                continue
            # 【U136②·建库并入】内层递归解析（旧版只支持"元素+数字"序列，
            # Na[Al(OH)₄] 的内层 Al(OH)₄ 含括号 ⇒ 直接判不可解析；递归后
            # 方括号配位单元可正确计数）。倍数仍读在闭括号之后。
            sub, _k = read_group(inner, 0)
            if sub is None:
                return None, i
            mult = ""
            j2 = j + 1
            while j2 < n and s[j2].isdigit():
                mult += s[j2]
                j2 += 1
            m = int(mult) if mult else 1
            for kk, vv in sub.items():
                d[kk] = d.get(kk, 0) + vv * m
            i = j2
            continue
        if c in ")]":
            return d, i
        if c == "+":                      # 顶层项分隔：交回 parse_side 处理
            return d, i
        mm = ELEM.match(s, i)
        if not mm:
            return None, i
        cnt = int(mm.group(2)) if mm.group(2) else 1
        d[mm.group(1)] = d.get(mm.group(1), 0) + cnt
        i = mm.end()
        if i == before:      # ELEM 匹配空串 ⇒ 未前进，退出防死循环
            return None, i
    return d, i


lines = txt.split("\n")
cands = []
for i, l in enumerate(lines, 1):
    for sg in segs(l):
        cands.append((i, sg))

eq, frag, unparsed, bad = [], [], [], []
for ln, sg in cands:
    s = strip_noise(sg)
    if "=" not in s or s.count("=") != 1:
        frag.append((ln, sg))
        continue
    L, R = s.split("=")
    if not L or not R:
        frag.append((ln, sg))
        continue
    dl = parse_side(L)
    dr = parse_side(R)
    if dl is None or dr is None or not dl or not dr:
        unparsed.append((ln, sg, dl, dr))
        continue
    eq.append((ln, sg, dl, dr))
    if dl != dr:
        bad.append((ln, sg, dl, dr))

out = io.StringIO()


def p(x=""):
    out.write(str(x) + "\n")


p("== S9 独立守恒复算（%s）==" % stem)
p("cands=%d  eq=%d  balanced=%d  unbalanced=%d  frag=%d  unparsed=%d" %
  (len(cands), len(eq), len(eq) - len(bad), len(bad), len(frag), len(unparsed)))
p("")
p("-- 可解析整式 --")
for ln, sg, dl, dr in eq:
    p("  L%-4d %-46s %s  %s" % (ln, sg, dl, "OK" if dl == dr else "!! DIFF right=%s" % dr))
p("")
p("-- 不守恒 --")
for ln, sg, dl, dr in bad:
    p("  L%-4d %s  left=%s right=%s" % (ln, sg, dl, dr))
p("")
p("-- 碎片（含 = 但非单等号 / 缺边）--")
for ln, sg in frag[:20]:
    p("  L%-4d %s" % (ln, sg[:80]))
p("")
p("-- 无法解析 --")
for ln, sg, dl, dr in unparsed[:20]:
    p("  L%-4d %-40s dl=%s dr=%s" % (ln, sg[:60], dl, dr))
p("")
p("-- 伪方程式（连接符 —— / == / —，非 = ；信息性，U80）--")
for i, l in enumerate(lines, 1):
    if re.search(r"[\u2014]{1,}|\S=\S|===", l) and re.search(r"[A-Z][a-z]?\d*[\u2014=]", l):
        if "\u2014" in l or "==" in l:
            p("  L%-4d %s" % (i, l[:120]))
p("")
# 【U136③·建库并入】数值残缺检查：序13 的本件唯一计量真错误（`0. mol×1+0.3mol×3=1mol`，
#   小数点后无数字）藏在 unparsed/碎片里、机审第 8 项与 unbalanced 均未报出 ⇒
#   对**全文行**扫"数字+小数点+空白/行尾+非数字"形态（正常小数 0.3mol 不匹配），
#   命中即列"数值残缺疑似"清单，须按 U104①（能否由同句唯一确定）人工裁决。
p("-- 数值残缺疑似（数字后空小数点，U136③）--")
NUMBROKE_RE = re.compile(r"\d\.(?:[ \u00a0\u3000]+(?=[^\d\s])|(?=$))")
nb = [(i, l.strip()[:110]) for i, l in enumerate(lines, 1) if NUMBROKE_RE.search(l)]
for i, l in nb:
    p("  L%-4d %s" % (i, l))
if not nb:
    p("  (none)")

dst = Path(args[1]) if len(args) > 1 else (MD.parent / "work" / "_sk_balance_out.txt")
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(out.getvalue(), encoding="utf-8")
# stdout 一律 ASCII（U2）：中文路径会触发 GBK UnicodeEncodeError，故只打计数摘要
print("WROTE balance_out ; eq=%d bad=%d frag=%d unparsed=%d numbroken=%d" % (
    len(eq), len(bad), len(frag), len(unparsed), len(nb)))
