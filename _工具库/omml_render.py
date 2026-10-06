# -*- coding: utf-8 -*-
"""omml_render.py: Word 原生公式 (OMML, m:oMath) -> 线性化学文本

背景（钠批次 序3「2.1 钠及其化合物 第1课时（培优分层作业）（解析版）」实测）：
  本件公式载体与前几件**完全不同** ——
    · MathType OLE (embeddings) = 0
    · EQ 域 (w:instrText)        = 0
    · WMF 预览图                 = 0
    · **原生 OMML m:oMath       = 157 个**（另有 4 个 m:oMathPara 容器）
  通用 extract_content.py 只认 ⟨OLE⟩/图片/上下标 run，**不认 m:oMath** →
  公式被静默丢弃，正文出现大量"…生成使表面变暗…"这类"逻辑说不通"的空洞。
  故本件必须补一个 OMML 渲染器，在提取时**就地内联**还原结果。

渲染规则（按本件 census 46 种元素归纳，见 work/omml_census.txt）：
  m:r/m:t        -> 字面文本
  m:sSub         -> base + 下标(Unicode)
  m:sSup         -> base + 上标(Unicode)
  m:sSubSup      -> base + 下标 + 上标（化学惯例：先下后上，如 CO₃²⁻）
  m:f            -> (num)/(den)          （规范 §三 分数线性化）
  m:d            -> (内容)               （sepChr=',' 等分隔符；本件默认圆括号）
  m:bar          -> 双层 bar 包裹文字 = 条件等号 =(X)=
  m:limLow/Upp   -> lim 为线状字符('¯'/'_') 或 e 为线状字符('=') 时 = 条件等号 =(X)=
  m:m            -> 矩阵：每行去空后连接，行间换行（差量法算式表）
  m:eqArr        -> 顺次连接各 m:e（本件用作条件等号的容器）
  其它属性节点(rPr/ctrlPr/*Pr) 无 m:t，默认连接即得空串

产物（S3 规定产物；本件无 OLE，故以 OMML 报告替代）：
  work/omml/formula_map.json   {"OM000": 文本, ...}
  work/omml/all_formulas.txt   逐对象还原 + 唯一公式去重
"""
import json
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent))
from mtef_render import SUB_MAP, SUP_MAP, to_script  # noqa: E402

M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
BASE = Path(__file__).resolve().parent
UNP = BASE / "unpacked"

# 线状字符：画横线 / 等号本体（含全角、半角、各类减号与下划线）
LINE_ONLY = set("=＝—－-﹣−_¯‾￣~～\u3000 \t")

# 【本件新增】条件文字（化学"反应条件"词表）：用于识别以"文字叠双下划线/横线"承载的条件等号。
# 本件 0价硫件实测：Q2【解答】把条件等号写成 m:m 矩阵 = 一行"▵"(U+25B5) 由两层
#   m:groupChr(chr=U+0332 组合下划线) 包裹 + 一空行 → 旧渲染吐出 "\u3000▵\n"（正文出现
#   "S+2Cu　▵" 与下一行 "Cu₂S…" 的错断）。此处按"单行且为条件文字"判为条件等号 =(X)=。
COND_WORDS = {"▵", "△", "Δ", "点燃", "放电", "高温", "加热", "催化剂", "光照",
              "煅烧", "电解", "通电"}


def _is_line(t):
    t = (t or "").strip()
    return bool(t) and set(t) <= LINE_ONLY


def _cond_word(t):
    """【U117·建库并入】条件文字判定：COND_WORDS 成员，或「短 CJK/Δ△」词
    （催化剂/高温/一定条件/闪电…）。用于识别 eqArr/limUpp 双槽条件等号的
    "非 =(X)= 形态槽"是否为条件（而非普通正文，普通正文不合并、走保守默认）。"""
    t = (t or "").strip()
    if not t:
        return False
    u = t.replace("▵", "△").replace("∆", "△")
    if u in COND_WORDS or u in ("Δ", "△"):
        return True
    return 1 <= len(u) <= 8 and all(
        ("\u4e00" <= c <= "\u9fff") or c in "Δ△" for c in u)


def _cond_eq_join(parts):
    """【U117·建库并入】多条件合并为 =(A、B)=：顿号连接、「Δ/△」恒置末
    （化学惯例，与 mtef_render._cond_join 同口径，如 =(催化剂、Δ)=）。"""
    parts = [p for p in parts if p]
    tail = [p for p in parts if p in ("Δ", "△", "▵", "∆")]
    head = [p for p in parts if p not in ("Δ", "△", "▵", "∆")]
    return "=(%s)=" % "、".join(head + tail)


def _is_cond_eq(t):
    return t.startswith("=(") and t.endswith(")=") and len(t) > 4


def _e(el, name):
    return el.find(M + name) if el is not None else None


def _content_text(node):
    """取包装器承载的文字（只下探 m:e，跳过 lim/上下标槽）"""
    if node is None:
        return ""
    if node.tag in (M + "limLow", M + "limUpp", M + "bar"):
        return _content_text(_e(node, "e"))
    if node.tag == M + "t":
        return node.text or ""
    return "".join(_content_text(c) for c in node)


_WS = " \t\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u00a0\u3000"


def _base_render(el):
    """下标/上标基座。本件实测(硫 0价硫件)：部分 sSub/sSubSup 的 <m:e> 基座是**空白**
    （U+2009 窄空格等），真正的基座字符已在前一 run 里(如 '=Fe(NO' + sSub(base=薄空格,sub='3'))).
    若基座仅空白 → 判为转换器残留、丢弃，使 'SO ₃²⁻'→'SO₃²⁻'、'Fe(NO ₃) ₃'→'Fe(NO₃)₃'。"""
    b = render(_e(el, "e"))
    return "" if b.strip(_WS) == "" else b


def render(el):
    # 畸形/缺失子元素时各调用点传进来的是 None（_e() 找不到即返回 None）。
    # 无此守卫会 AttributeError 冒泡到 extract_content 的模块级循环（那里无 try），
    # 整个 S2 在写 content_stream.txt 之前就中断。
    if el is None:
        return ""
    t = el.tag
    if t in (M + "oMath", M + "oMathPara"):
        return "".join(render(c) for c in el)
    if t == M + "t":
        return el.text or ""
    if t == M + "sSub":
        return _base_render(el) + to_script(render(_e(el, "sub")), SUB_MAP, "sub")
    if t == M + "sSup":
        return _base_render(el) + to_script(render(_e(el, "sup")), SUP_MAP, "sup")
    if t == M + "sSubSup":
        return (_base_render(el)
                + to_script(render(_e(el, "sub")), SUB_MAP, "sub")
                + to_script(render(_e(el, "sup")), SUP_MAP, "sup"))
    if t == M + "f":
        num = _e(el, "num")
        den = _e(el, "den")
        # 【钠批学霸笔记件实测·通用 OMML 子形态】条件反应箭头伪装成分数：
        #   源文把反应"等号"写成 m:f —— num 为 m:bar（m:e 内文字=反应条件，如 △；
        #   空 bar 时两条横线上下相邻 = 视觉等号），den 为空白。
        #   按普通分数渲染会得到 "(   △   )/( )" 这类"逻辑说不通"的串。
        #   判据：num 的直接子元素含 m:bar；真分数(39b/8a 等)的 num 无 m:bar。
        if num is not None and num.find(M + "bar") is not None:
            cond = "".join(ch for ch in _content_text(num) if ch not in " \t\u3000")
            cond = cond.replace("\u25b3", "\u0394")
            if cond and not _is_line(cond):
                return "=(%s)=" % cond
            return "="
        num_txt, den_txt = render(num), render(den)
        # 【硫序4 实测·通用 OMML 子形态②】条件等号伪装成分数（limUpp 版）：
        #   num = m:limUpp（基座 m:e 为**线状字符** '-'/'_'，m:lim 为条件文字 △/一定条件…），
        #   den = <m:den/> 空或仅空白(U+2004) → 旧渲染吐 "(=(△)=)/(\u2004)"。
        #   判据：分母去空白为空 **且** num 自身渲染结果已是条件等号 =(X)= ⇒ 取 num。
        #   真分数的分母永不为空，故不会误伤。
        if den_txt.strip(_WS) == "" and num_txt.startswith("=(") and num_txt.endswith(")="):
            return num_txt
        return "(%s)/(%s)" % (num_txt, den_txt)
    if t == M + "groupChr":
        # 【硫序4 实测·通用 OMML 子形态③】条件等号伪装成"组合字符"：
        #   m:groupChr（m:chr = U+0332 组合下划线）包裹条件文字（▵/△/点燃…），
        #   双层嵌套 = 双下划线视觉等号；旧渲染只吐出文字 ▵ →
        #   正文出现 "2H₂SO₄▵2SO₂↑+O₂↑+2H₂O"（逻辑不通）。
        #   判据：其 m:e 内容（去空白）恰为条件词表内文字 ⇒ =(X)=；否则维持默认连接。
        inner = "".join(render(c) for c in el if c.tag == M + "e").strip()
        if inner in COND_WORDS:
            return "=(%s)=" % ("Δ" if inner in ("▵", "△", "Δ") else inner)
        return "".join(render(c) for c in el)
    if t == M + "d":
        return "(" + "".join(render(x) for x in el.findall(M + "e")) + ")"
    if t == M + "bar":
        e = _e(el, "e")
        if e is not None and e.find(M + "bar") is not None:
            return "=(%s)=" % _content_text(e).strip()
        return render(e)
    if t in (M + "limLow", M + "limUpp"):
        e, lim = _e(el, "e"), _e(el, "lim")
        e_txt = render(e) if e is not None else ""
        lim_txt = render(lim) if lim is not None else ""
        # 【本件新增】退化外层 limUpp：<m:e/> 空基座 + lim 本身即条件等号 =(X)=
        #   （Word/MathType 双层 limUpp 的冗余外壳）→ 直接取 lim，避免吐出 "(=(△)=)"。
        if not e_txt.strip() and lim_txt.startswith("=") and lim_txt.endswith("="):
            return lim_txt
        # 【U117·建库并入·形态②】m:limUpp(e=m:limLow(e='=', lim=条件B), lim=条件A)
        #   （槽序颠倒形态）：旧实现落默认分支吐 =(B)=(A)（读不通）⇒ lim（上槽）
        #   在前、e 内条件在后，合并为 =(A、B)=（Δ 置末由 _cond_eq_join 保证）。
        if _is_cond_eq(e_txt) and _cond_word(lim_txt):
            return _cond_eq_join([lim_txt.strip(), e_txt[2:-2]])
        if _is_line(lim_txt):
            return "=(%s)=" % _content_text(e).strip()
        if _is_line(e_txt) and lim_txt.strip():
            return "=(%s)=" % lim_txt.strip()
        return e_txt + (("(" + lim_txt + ")") if lim_txt.strip() else "")
    if t == M + "m":
        rows = []
        for mr in el.findall(M + "mr"):
            cells = ["".join(render(c) for c in e) for e in mr.findall(M + "e")]
            if not cells:
                continue
            main = "".join(cells[:-1])
            last = cells[-1].strip()
            rows.append(main + ("\u3000" + last if last else ""))
        # 【本件新增】条件等号"文字叠双下划线"：矩阵退化为单行条件文字(其余为空行) → =(X)=
        #   注：其单元格若被 m:groupChr 分支预先渲染成 =(X)=（硫序4 新增规则），
        #   此处须**原样返回**，否则会走 "\n".join(rows) 把矩阵拆成多行（U35 回归实测：序0 件 203 行差异）。
        nonempty = [r.strip() for r in rows if r.strip()]
        if len(nonempty) == 1:
            w = nonempty[0]
            if w.startswith("=(") and w.endswith(")="):
                return w
            if w in COND_WORDS:
                return "=(%s)=" % ("Δ" if w in ("▵", "△", "Δ") else w)
        return "\n".join(rows)
    if t == M + "eqArr":
        # 【U117·建库并入·形态①】m:eqArr 承载"双槽条件等号"：
        #   m:eqArr[ m:bar/limLow(条件A) , 条件B ]（A 在双线槽上方、B 作第二行）
        #   ⇒ 旧默认顺次连接吐 =(A)=B（读不通）。判据：非空槽中恰有 =(X)= 形态槽、
        #   其余均为条件词（_cond_word）⇒ 合并为 =(A、B)=；否则维持旧默认顺次连接
        #   （普通矩阵/算式数组不受影响，保守纯超集）。
        slots = [render(x).strip() for x in el.findall(M + "e")]
        nz = [s for s in slots if s]
        ce = [s[2:-2] for s in nz if _is_cond_eq(s)]
        rest = [s for s in nz if not _is_cond_eq(s)]
        if ce and all(_cond_word(s) for s in rest):
            return _cond_eq_join(ce + rest)
        return "".join(render(c) for c in el)
    # 默认：连接子节点（m:r / m:e / m:num / m:den / m:sub / m:sup / m:lim / m:eqArr / 属性节点…）
    return "".join(render(c) for c in el)


def gather(document_xml):
    root = ET.parse(document_xml).getroot()
    return [render(om) for om in root.iter(M + "oMath")]


def main():
    outs = gather(UNP / "word/document.xml")
    fmap = {"OM%03d" % i: t for i, t in enumerate(outs)}
    outdir = BASE / "omml"
    outdir.mkdir(exist_ok=True)
    (outdir / "formula_map.json").write_text(
        json.dumps(fmap, ensure_ascii=False, indent=0), encoding="utf-8")

    L = ["# Word 原生公式 (OMML) 还原结果 —— S3 产物",
         "对象数: %d" % len(outs),
         "空渲染: %d" % sum(1 for t in outs if not t.strip()),
         "",
         "## 逐对象（document.xml 中 m:oMath 顺序）"]
    for k, v in fmap.items():
        L.append("[%s] 还原: %s" % (k, v.replace("\n", " ⏎ ")))
    uniq = sorted(set(outs))
    L += ["", "## 唯一公式去重（%d 个）" % len(uniq)]
    for u in uniq:
        L.append("  %s   ← %d 个对象" % (u.replace("\n", " ⏎ "), sum(1 for v in outs if v == u)))
    (outdir / "all_formulas.txt").write_text("\n".join(L) + "\n", encoding="utf-8")

    print("omml objects:", len(outs), "unique:", len(uniq),
          "empty:", sum(1 for t in outs if not t.strip()))
    print("multiline (matrix):", sum(1 for t in outs if "\n" in t))


if __name__ == "__main__":
    main()
