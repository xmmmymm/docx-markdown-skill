# -*- coding: utf-8 -*-
"""extract_content.py: 解包 docx -> content_stream.txt
输出: work/content_stream.txt, work/content_meta.json
段落一行一块; 表格 <TBL>...</TBL>, 单元格 ' ||| ' 分隔;
OLE 公式 ⟨OLE:oleObjectN⟩; 图片 ⟨IMG:imageN.ext⟩; 上下标 ⟨S⟩..⟨/S⟩ ⟨P⟩..⟨P⟩

本版要点(相对通用版新增):
1. EQ 域(instrText)跨多 run: 在段落级维护域状态机 begin/instrText/separate/end;
   域无结果文本时, 就地程序化还原指令:
     eq \\o(=====,\\s\\up7(△),\\s\\do5(　))  ->  =(Δ)=
     eq \\o\\al(2－,3)                       ->  ₃²⁻ (下标槽在前、上标槽在后)
2. mc:AlternateContent 只取 mc:Choice, 跳过 mc:Fallback(否则 WordArt 文本重复一次)。
3. 空白(全角空格/半角空格)的纯 script run 为游离残留, 丢弃。
4. Word 原生公式 OMML(m:oMath / m:oMathPara) 就地内联渲染(调 omml_render.render)。
   背景(钠批次 序3 实测): 该件零 MathType OLE、零 EQ 域、零 WMF, 157 个公式全为 OMML;
   旧版不认 m:oMath -> 公式被静默丢弃, 正文出现 "…生成使表面变暗…" 这类空洞(逻辑说不通)。
   注意: **同目录必须存在 omml_render.py**; 无 OMML 的文档本项零代价(只有 import)。
"""
import json, re, sys
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent
UNP = BASE / "unpacked"
sys.path.insert(0, str(BASE))

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}
for k, v in NS.items():
    ET.register_namespace(k, v)

from omml_render import render as omml_render  # noqa: E402

def qn(tag):
    p, t = tag.split(":")
    return "{%s}%s" % (NS[p], t)

MC_FALLBACK = qn("mc:Fallback")

# ---- rels ----
rels = {}
rt = ET.parse(UNP / "word/_rels/document.xml.rels").getroot()
for rel in rt:
    rels[rel.get("Id")] = (rel.get("Type", ""), rel.get("Target"))

def resolve(rid):
    return rels.get(rid, (None, None))[1]

# ================= EQ 域还原 =================
def _split_args(s):
    args, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1; cur.append(ch)
        elif ch == ")":
            depth -= 1; cur.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(cur)); cur = []
        else:
            cur.append(ch)
    args.append("".join(cur))
    return args

def _strip_s_cmd(s):
    # 【通用·本批序2 并入（源：氯批序5 / U52①）】源文 EQ 指令可写作 `\s\up 4(...)`
    #   （命令与数字之间有空格），旧正则 `\d*` 不容空格 → 去壳失败，吐出"逻辑说不通"的串。
    m = re.match(r"^\\s\\(up|do)\s*\d*(.*)$", s)
    if m:
        rest = m.group(2)
        if rest.startswith("(") and rest.endswith(")"):
            return rest[1:-1]
        return rest
    return s

COND_DROP = "\u3000 \t"

def _cond(t):
    t = t.replace("△", "Δ").replace("▲", "Δ")
    return "".join(c for c in t if c not in COND_DROP)

def _take_paren(s, i):
    """s[i]=='(' ; 返回 (inner, next_index)"""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    return s[i + 1:], len(s)

# ---- 线状槽判定（新增：嵌套 \o 的支持）----
# 背景（钠批次 序2「专题1 钠及钠的氧化物拓展」实测）：
#   源文条件等号域为 **嵌套** 形态：
#     eq \o(\o(\s\up6(_____),\s\up4(_____)),\s\up6(高温))
#   外层 \o(A,B) 把 B(高温) 叠在 A 之上；A 本身又是一个 \o，由两条"_____"线叠加
#   构成箭头底部（线状）。旧实现只认主槽字符集 "=＝—－-"，遇到 '_____' 便整串原样吐出，
#   产出 `\o(\s\up6(_____),\s\up4(_____))高温`（逻辑说不通）。
#   处理：主槽与条件槽都按"是否仅由线状字符组成"判定；线状槽不当作条件文字。
LINE_CHARS = set("=＝—－-_﹣−\u3000 \t~～")


def _is_line(t):
    return bool(t) and set(t) <= LINE_CHARS


def _is_arrow(t):
    """主槽是否为箭头本体（`――→`/`—→`/`→`）。
       【通用·本批序2 并入（源：氯批序5 / U52④；原 U84 待合并项，已做 U35 回归）】
       `―`(U+2015) 与 `→` 均不在 LINE_CHARS 内，旧实现把"条件箭头"域判成普通叠排，
       吐出 `――→O2`（箭头在前、条件掉到串尾，逻辑说不通）。"""
    return any(c in t for c in "→←↑↓")


def _slot(x):
    """把一个 \\o 槽位还原成文本：
       \\s\\upN(...) / \\s\\doN(...) 去壳取内容；嵌套 \\o(...) 递归还原。"""
    x = x.strip()
    if x.startswith("\\s\\up") or x.startswith("\\s\\do"):
        return _strip_s_cmd(x)
    if re.match(r"^\\o", x):
        return render_eq(x)
    return x

def render_eq(ins):
    out = []
    s = ins.strip()
    while s:
        if re.match(r"^eq\b", s, re.I):   # 【氯批次 序1 新增·通用】Word 域码大小写不敏感
            s = s[2:].lstrip()
        m = re.match(r"^\\o\\al\s*\(", s)
        if m:
            inner, nxt = _take_paren(s, m.end() - 1)
            s = s[nxt:]
            a = _split_args(inner)
            sup = a[0] if a else ""
            sub = a[1] if len(a) > 1 else ""
            out.append("⟨AL:%s|%s⟩" % (sub, sup))
            continue
        m = re.match(r"^\\o\s*\(", s)
        if m:
            inner, nxt = _take_paren(s, m.end() - 1)
            s = s[nxt:]
            a = _split_args(inner)
            main = _slot(a[0]) if a else ""
            over = under = ""
            for x in a[1:]:
                if x.startswith("\\s\\up"):
                    over = _slot(x)
                elif x.startswith("\\s\\do"):
                    under = _slot(x)
            over, under = _cond(over), _cond(under)
            if main and _is_arrow(main):
                # 【通用·本批序2 并入（源：氯批序5 / U52④）】主槽为箭头本体 + 上方条件
                #   `eq \o(――→,\s\up7(O2))` → `—O2→`（规范 §四.4 条件箭头口径 `—H₂O→`）
                # 【序3 修订·U101】`main` 本身可能已是**渲染好的条件箭头**（由嵌套域结果回填，
                #   如 `—空气→`），此时另一个槽里的条件是该箭头的**第二个条件**（如 `Δ`）
                #   → 合成 `—空气、Δ→`（多条件用 `、`，与钠批序0 `⇌(高温高压、催化剂)` 同口径）；
                #   旧实现只留 `—Δ→` ⇒ **丢掉"空气"**（逻辑说不通）。
                c = over or under
                if c and not _is_line(c) and not _is_arrow(c):
                    m2 = re.match(r"^[—―\-–\u2015]+\s*([^—―\-–\u2015].*?)\s*(→|←|↑|↓)$", main)
                    if m2:
                        out.append("—%s、%s%s" % (m2.group(1).strip(), c, m2.group(2)))
                    else:
                        out.append("—%s→" % c)
                else:
                    out.append(main)
            elif any(_is_arrow(x) for x in (main, over, under)):
                # 【序3 本件新增·待回写工具库】箭头**不在主槽**的形态（本件＝箭头写在 `\s\do`
                #   槽、条件文字写在 `\s\up` 槽）：`eq \o(\s\up 2(浓硝酸),\s\do 4(———→))`。
                #   此时 `_slot(a[0])` 取到的是"条件"（浓硝酸），箭头落在 `under`。旧实现回落
                #   到 `else` 做线性拼接 → `浓硝酸———→`（条件在前、箭头在后，非规范 `—条件→`）。
                #   此处按 §四.4 统一渲染为 `—条件→`。仅影响"箭头不在主槽"的域。
                _slots = [x for x in (main, over, under) if x]
                _arrow = next((x for x in _slots if _is_arrow(x)), "")
                _conds = [x for x in _slots if not _is_arrow(x) and not _is_line(x)]
                out.append(("—%s→" % _conds[0]) if _conds else _arrow)
            elif _is_line(main) or _is_line(over) or _is_line(under):
                # 线状槽 = 等号/箭头本体；条件取唯一的非线状槽。
                # ① 线状槽在**主槽**（U21，钠批序2）：
                #    `eq \o(\o(\s\up6(_____),\s\up4(_____)),\s\up6(高温))` → `=(高温)=`
                # ② 线状槽在 `\s\up`（【序4 本件新增】）：
                #    `eq \o(\s\up7(一定条件),\s\up 0(=======),\s\do 9())` → `=(一定条件)=`
                #    旧实现只判"主槽是否线状"，此形态下 `a[0]`＝条件(一定条件)、线状槽落在 `over`
                #    ⇒ 落入 else 线性拼接，吐出 `一定条件=======`（逻辑说不通，题13 解析）。
                #    现按规范 §四.4「条件等号」统一渲染为 `=(条件)=`。
                conds = [x for x in (main, over, under)
                         if x and not _is_line(x) and not _is_arrow(x)]
                c = conds[0] if conds else ""
                out.append("=(%s)=" % c if c else "=")
            else:
                out.append("".join(x for x in (main, over, under) if x))
            continue
        m = re.match(r"^\\(f|r|s|b|a|d|i|x|bc|jc)\s*\(", s)
        if m:
            inner, nxt = _take_paren(s, m.end() - 1)
            s = s[nxt:]
            cmd = m.group(1)
            a = _split_args(inner)
            if cmd == "f":
                out.append("(%s)/(%s)" % (a[0], a[1] if len(a) > 1 else ""))
            elif cmd == "r":
                out.append("√" + (a[1] if len(a) > 1 else a[0]))
            else:
                out.append(inner)
            continue
        out.append("⟪EQRAW:" + s + "⟫")
        break
    return "".join(out)

AL_RE = re.compile(r"⟨AL:([^|⟩]*)\|([^⟩]*)⟩")

def _script_text(t, kind):
    from mtef_render import SUB_MAP, SUP_MAP, to_script
    return to_script(t, SUB_MAP if kind == "sub" else SUP_MAP, kind)

def al_sub_all(t):
    return AL_RE.sub(lambda m: _script_text(m.group(1), "sub") + _script_text(m.group(2), "sup"), t)

# ================= 文档流 =================
def self_blips(el, tag):
    """收集 el 子树的 tag 元素, 但不下探 w:txbxContent(避免与文本框内嵌套图形重复计数)"""
    res = []

    def rec(node):
        for ch in node:
            if ch.tag == qn("w:txbxContent"):
                continue
            if ch.tag == tag:
                res.append(ch)
            rec(ch)
    rec(el)
    return res


def _is_real_script_run(r):
    """该 run 是否为「带非空白文本的上下标 run」——用于判定其后的空白 script run 是否属排版空格。"""
    rpr = r.find(qn("w:rPr"))
    if rpr is None:
        return False
    va = rpr.find(qn("w:vertAlign"))
    if va is None or va.get(qn("w:val")) not in ("subscript", "superscript"):
        return False
    t = "".join(x.text or "" for x in r.iter(qn("w:t")))
    return t.strip("\u3000 \t\n") != ""


def run_tokens(r, prev_script=False):
    """产出该 run 的 token: (kind, payload); kind ∈ t/i/f/o
    prev_script=True 表示**紧邻的前一个 run 是带文本的上下标 run**（见下方空白 script run 的处理）。"""
    vert = None
    rpr = r.find(qn("w:rPr"))
    if rpr is not None:
        va = rpr.find(qn("w:vertAlign"))
        if va is not None:
            vert = va.get(qn("w:val"))

    def walk(node):
        for ch in node:
            if ch.tag == MC_FALLBACK:
                continue
            if ch.tag == qn("w:t"):
                yield ("t", ch.text or "")
            elif ch.tag == qn("w:tab"):
                yield ("t", "\t")
            elif ch.tag == qn("w:br"):
                yield ("t", "\n")
            elif ch.tag == qn("w:cr"):
                # 【氯批次 序3 新增·通用】w:cr（carriage return）与 w:br 同为**段内换行**；
                #   旧版只处理 w:br → 源文用 w:cr 分行的选项（A/B 一行、C/D 一行）会**丢掉换行**，
                #   C 项被粘到 B 项尾部（氯批序3 实测 10 处：`…均属于电解质C．通常情况…`；
                #   并连带 1 处 `…8H₂OC. 2Fe²⁺…` 半角点号混排）。
                #   U35 回归（2026-09-16）：全库 20 个已解包 document.xml 中仅氯批序3 含 w:cr，
                #   其余 19 件为 0 → 对已交付件零影响。
                yield ("t", "\n")
            elif ch.tag == qn("w:noBreakHyphen"):
                yield ("t", "-")
            elif ch.tag == qn("w:instrText"):
                yield ("i", ch.text or "")
            elif ch.tag == qn("w:fldChar"):
                yield ("f", ch.get(qn("w:fldCharType")))
            elif ch.tag == qn("w:object"):
                ole = ch.find(".//" + qn("o:OLEObject"))
                if ole is not None:
                    tgt = resolve(ole.get(qn("r:id"))) or "?"
                    mm = re.search(r"(oleObject\d+)", tgt)
                    yield ("o", "\u27e8OLE:%s\u27e9" % (mm.group(1) if mm else tgt))
            elif ch.tag == qn("w:drawing"):
                for blip in self_blips(ch, qn("a:blip")):
                    tgt = resolve(blip.get(qn("r:embed")) or blip.get(qn("r:link"))) or "?"
                    mm = re.search(r"(image\d+\.\w+)", tgt)
                    anchor = ch.find(qn("wp:anchor")) is not None
                    yield ("o", "\u27e8IMG:%s%s\u27e9" % (mm.group(1) if mm else tgt, ":A" if anchor else ""))
                # 图形文本框(wps:txbx)内属于正文的文字需保留
                for txb in ch.findall(".//" + qn("w:txbxContent")):
                    yield from walk(txb)
            elif ch.tag == qn("w:pict"):
                if ch.find(".//" + qn("w:object")) is not None:
                    continue
                # 【U128·建库并入（源：氮批序12 件内超集）】MathType OLE 可直接挂在 <w:pict> 下
                #   （<o:OLEObject> 与 <v:shape> 并列、不经 <w:object> 包裹）⇒ 必须先认 OLE，
                #   否则会被当成 wmf 预览图静默丢弃（S2 三症状：ole refs=0 + emb>0 + missing_ole 非空）。
                ole = ch.find(".//" + qn("o:OLEObject"))
                if ole is not None:
                    tgt = resolve(ole.get(qn("r:id"))) or "?"
                    mm = re.search(r"(oleObject\d+)", tgt)
                    yield ("o", "\u27e8OLE:%s\u27e9" % (mm.group(1) if mm else tgt))
                    continue
                for im in self_blips(ch, qn("v:imagedata")):
                    tgt = resolve(im.get(qn("r:id"))) or "?"
                    mm = re.search(r"(image\d+\.\w+)", tgt)
                    yield ("o", "\u27e8IMG:%s\u27e9" % (mm.group(1) if mm else tgt))
                for txb in ch.findall(".//" + qn("w:txbxContent")):
                    yield from walk(txb)
            elif ch.tag in (qn("m:oMath"), qn("m:oMathPara")):
                yield ("t", omml_render(ch))
            else:
                yield from walk(ch)

    # 收集该 run 的文本/占位, 再整体套 vertAlign
    texts, others = [], []
    for kind, payload in walk(r):
        if kind == "t":
            texts.append(payload)
        else:
            others.append((kind, payload))
    txt = "".join(texts)
    if vert in ("subscript", "superscript") and txt.strip("\u3000 \t\n") == "" and not others:
        # 【氯批次 序5 修订·通用】纯空白 script run **不再一律丢弃**（旧规则见 U5）：
        #   源文常把"对齐用空格"也设成**下标格式**。氯序5 原始 XML 铁证：
        #     `C. 收集Cl` + 下标run `2` + 下标run(11 个空格) + `D. 尾气处理`
        #   → 旧规则丢弃该 run ⇒ `收集Cl₂D. 尾气处理`（4 处选项粘连 + 1 处 `Cl₂(4)` 粘连）。
        #   判据：若它**紧接在一个"带文本的上下标 run"之后** ⇒ 判为**排版空格**，压成单个半角空格；
        #   否则（前面不是上下标 run，如域残留的孤立下标空格）仍按 U5 丢弃。
        if prev_script:
            yield ("t", " ")
        return
    if vert in ("subscript", "superscript") and txt:
        mark = ("S", "/S") if vert == "subscript" else ("P", "/P")
        txt = "\u27e8%s\u27e9%s\u27e8%s\u27e9" % (mark[0], txt, mark[1])
    if txt:
        yield ("t", txt)
    for t in others:
        yield t

def paras_tokens(p):
    """按文档顺序产出段落内 token(w:r / w:hyperlink / w:fldSimple / m:oMath)"""
    def from_container(node, state=None):
        # state[0] = 紧邻前一个 run 是否为「带文本的上下标 run」（跨 w:hyperlink 等容器保持状态）
        if state is None:
            state = [False]
        for child in node:
            if child.tag == MC_FALLBACK:
                continue
            if child.tag == qn("w:r"):
                yield from run_tokens(child, prev_script=state[0])
                state[0] = _is_real_script_run(child)
            elif child.tag in (qn("w:hyperlink"), qn("w:smartTag"), qn("w:ins"), qn("w:del")):
                yield from from_container(child, state)
            elif child.tag == qn("w:fldSimple"):
                ins = child.get(qn("w:instr")) or ""
                if re.match(r"^eq\b", ins.strip(), re.I):   # 【氯批次 序1 新增·通用】同上
                    yield ("t", al_sub_all(render_eq(ins)))
                else:
                    yield from from_container(child)
            elif child.tag in (qn("m:oMath"), qn("m:oMathPara")):
                yield ("t", omml_render(child))
    yield from from_container(p)

def para_text(p):
    """【序3 修订·域栈版（U101）】域状态改为**栈**，支持**嵌套域**。
    背景（本批序3「硝酸（第四课时）课时作业答案」实测）：源文的条件箭头常写成
      **两层嵌套域**——外层 `eq \\o(\\s\\up 4(<内层域>),\\s\\do 5(Δ))`，
      内层 `eq \\o(\\s\\up 2(空气),\\s\\do 4(―――→))`（"空气"在箭头上方、Δ 在下方）。
    旧实现（单层，`begin` 时 `instr = []` 重置）在内层 `begin` 处**丢掉外层的
    `eq \\o(\\s\\up 4(`**；内层 `end` 又把 `in_field` 置 False ⇒ 外层 `end` 不再渲染，
    其 `\\s\\do 5(Δ)` 条件**被静默丢弃** → 成品 `Cu―空气→CuO`（缺"加热"，逻辑说不通）。
    修法：① 每个域一层栈帧；② 内层域结束时把其**渲染结果/结果文本**回填进**父域**指令流
    （外层指令因而变成 `eq \\o(\\s\\up 4(―空气→),\\s\\do 5(Δ))`），再交由 `render_eq`
    的"箭头+额外条件"分支合成 `―空气、Δ→`。
    ⚠ 单层文档语义与旧实现**完全一致**（push/pop 等价于 reset/clear）。"""
    out = []
    stack = []          # 每层: {"instr": [...], "sep": bool, "res": [...], "dead": bool}
    for kind, payload in paras_tokens(p):
        if kind == "i":
            if stack and not stack[-1]["sep"]:
                stack[-1]["instr"].append(payload)
            continue
        if kind == "f":
            if payload == "begin":
                stack.append({"instr": [], "sep": False, "res": [], "dead": False})
            elif payload == "separate":
                if stack:
                    stack[-1]["sep"] = True
            elif payload == "end":
                if not stack:
                    continue
                f = stack.pop()
                # 与旧实现同口径：只有"无结果文本且指令非空"的域才由指令渲染
                txt = al_sub_all(render_eq("".join(f["instr"]))) \
                    if (not f["dead"] and not f["res"] and f["instr"]) else ""
                if stack:
                    if txt:
                        # 嵌套 EQ 域（子域无结果文本）：结果回填父域指令流，供父域整体渲染
                        stack[-1]["instr"].append(txt)
                    else:
                        # 兼容旧行为：子域未回填（有结果文本/空指令）⇒ 父域不再渲染
                        stack[-1]["dead"] = True
                elif txt:
                    out.append(txt)
            continue
        if kind == "t":
            if stack and stack[-1]["sep"]:
                stack[-1]["res"].append(payload)
            out.append(payload)
        else:
            out.append(payload)
    return "".join(out)

def cell_text(tc):
    return " ".join(x for x in (para_text(p) for p in tc.findall(qn("w:p"))) if x).strip()

# ---- 自动编号（w:numPr）→ 字面题号（**默认关闭**，按件确认后启用，U48）----
# 背景：题干序号可能是 Word 自动编号（正文 <w:t> 内不含序号文本），旧提取器不认 w:numPr
#   → 题号丢失。⚠ 回归实测：解析正文/空段落/选项行都可能带 numId，**无条件启用会加伪序号**
#   （曾把 3 个解析段加成「1./2./3.」、把 1 个空段落加成孤立「1.」）。
#   故默认 `NUM_AUTO_NUMBER = False`（完全惰性、零影响）；仅当某件经
#   「numbering.xml + 答案区字面序号 + LibreOffice txt 导出」三方互证确认为
#   "自动编号承载题号/选项"时，再在**该件 work 副本**里置 True。
# 【U114·建库并入（源：氮批序8 件内超集）】para_number 按 numbering.xml 的
#   numFmt/lvlText 分流（upperLetter → A/B/C…，lowerLetter → a/b/c…，decimal → 1/2/3…；
#   lvlText 模板逐字还原，`%1` 换 token）。旧版一律产 decimal `%d.`，会把选项 `A.` 吐成 `1.`。
#   numId=0 是 Word 的"无编号"值 → 不加号。启用前的三方互证范式见氮批归档「归档 9」。
NUM_AUTO_NUMBER = False  # ← 默认关闭（U48）；按件确认后在 work 副本置 True
_num_counter = {}
_ABS_LVL = {}   # abstractNumId -> (numFmt, lvlText)
_NUM_ABS = {}   # numId -> abstractNumId


def _load_numbering():
    p = UNP / "word" / "numbering.xml"
    if not p.exists():
        return
    root = ET.parse(p).getroot()
    for an in root.findall(qn("w:abstractNum")):
        aid = an.get(qn("w:abstractNumId"))
        lv = an.find(qn("w:lvl"))
        fmt = lt = None
        if lv is not None:
            f = lv.find(qn("w:numFmt"))
            fmt = f.get(qn("w:val")) if f is not None else None
            t = lv.find(qn("w:lvlText"))
            lt = t.get(qn("w:val")) if t is not None else None
        _ABS_LVL[aid] = (fmt, lt)
    for nm in root.findall(qn("w:num")):
        a = nm.find(qn("w:abstractNumId"))
        if a is not None:
            _NUM_ABS[nm.get(qn("w:numId"))] = a.get(qn("w:val"))


_load_numbering()


def _fmt_token(fmt, n):
    if fmt == "upperLetter":
        return chr(ord("A") + n - 1)
    if fmt == "lowerLetter":
        return chr(ord("a") + n - 1)
    return str(n)


def para_number(p):
    if not NUM_AUTO_NUMBER:
        return ""
    ppr = p.find(qn("w:pPr"))
    if ppr is None:
        return ""
    npr = ppr.find(qn("w:numPr"))
    if npr is None:
        return ""
    nid = npr.find(qn("w:numId"))
    key = nid.get(qn("w:val")) if nid is not None else "?"
    if key in (None, "0"):
        return ""
    _num_counter[key] = _num_counter.get(key, 0) + 1
    n = _num_counter[key]
    fmt, lt = _ABS_LVL.get(_NUM_ABS.get(key), (None, None))
    tok = _fmt_token(fmt, n)
    return (lt or "%1.").replace("%1", tok)

out_lines = []
meta = {"tables": 0, "images": [], "oles": [], "paragraphs": 0}
body = ET.parse(UNP / "word/document.xml").getroot().find(qn("w:body"))

for child in body:
    if child.tag == qn("w:p"):
        meta["paragraphs"] += 1
        out_lines.append(para_number(child) + para_text(child))
    elif child.tag == qn("w:tbl"):
        meta["tables"] += 1
        out_lines.append("<TBL>")
        for tr in child.findall(qn("w:tr")):
            cells = []
            for tc in tr.findall(qn("w:tc")):
                tcpr = tc.find(qn("w:tcPr"))
                span, vmerge = 1, None
                if tcpr is not None:
                    gs = tcpr.find(qn("w:gridSpan"))
                    if gs is not None:
                        span = int(gs.get(qn("w:val")))
                    vm = tcpr.find(qn("w:vMerge"))
                    if vm is not None:
                        vmerge = vm.get(qn("w:val")) or "continue"
                txt = cell_text(tc)
                if vmerge == "continue":
                    txt = ""
                cells.append(txt)
                for _ in range(span - 1):
                    cells.append("<MERGE>")
            out_lines.append(" ||| ".join(cells))
        out_lines.append("</TBL>")
    elif child.tag == qn("w:sectPr"):
        pass

stream = "\n".join(out_lines)
(BASE / "content_stream.txt").write_text(stream, encoding="utf-8")

img_refs = re.findall(r"\u27e8IMG:([^\u27e9:]+)(:A)?\u27e9", stream)
ole_refs = re.findall(r"\u27e8OLE:(oleObject\d+)\u27e9", stream)
meta["images"] = sorted(set(n for n, a in img_refs), key=lambda s: (len(s), s))
meta["image_ref_count"] = len(img_refs)
meta["oles"] = sorted(set(ole_refs), key=lambda s: int(s[9:]))
meta["ole_ref_count"] = len(ole_refs)
# media/embeddings 目录可能不存在（零 OLE 的文档根本没有 word/embeddings），必须容错
media_dir = UNP / "word/media"
media_all = sorted(p.name for p in media_dir.iterdir()) if media_dir.exists() else []
# word/embeddings 里除 oleObjectN.bin 外还可能出现嵌入式工作簿（如
# Microsoft_Excel_Worksheet1.xlsx）或子目录 ⇒ 先按名前缀过滤再取序号，
# 否则 int(s[9:]) 会 ValueError 裸栈（S2 在写 content_stream 之前就挂）。
emb_dir = UNP / "word/embeddings"
emb_all = sorted((p.name[:-4] for p in emb_dir.iterdir()
                  if p.is_file() and p.name.startswith("oleObject") and p.name.endswith(".bin")),
                 key=lambda s: int(s[9:])) if emb_dir.exists() else []
meta["media_all"] = media_all
meta["emb_all_count"] = len(emb_all)
meta["ole_all"] = emb_all
meta["orphan_media"] = [m for m in media_all if m not in meta["images"]]
meta["missing_ole"] = [o for o in emb_all if o not in meta["oles"]]
meta["eqraw"] = re.findall(r"⟪EQRAW:([^⟫]*)⟫", stream)
meta["omml_total"] = sum(1 for _ in ET.parse(UNP / "word/document.xml").getroot().iter(qn("m:oMath")))
(BASE / "content_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
print("paragraphs:", meta["paragraphs"], "tables:", meta["tables"])
print("image refs:", meta["image_ref_count"], "unique:", len(meta["images"]))
print("ole refs:", meta["ole_ref_count"], "unique:", len(meta["oles"]), "emb files:", len(emb_all))
print("orphan media:", meta["orphan_media"])
print("missing ole:", meta["missing_ole"][:10])
print("eqraw:", ascii(meta["eqraw"]))
print("omml_total:", meta["omml_total"])
print("AL residual:", stream.count("\u27e8AL"))
