# -*- coding: utf-8 -*-
"""mtef_render.py: MathType OLE (MTEF5) -> 线性文本
输入: work/unpacked/word/embeddings/oleObjectN.bin
输出: work/mtef/formula_map.json  {oleObjectN: text}
      work/mtef/parse_log.json    解析问题/未知字符/模板使用统计
零剩余校验: 每个对象解析后字节必须恰好耗尽, 否则记入 failures.
"""
import json, sys
from pathlib import Path
import olefile

BASE = Path(__file__).resolve().parent
EMB = BASE / "unpacked/word/embeddings"
OUT = BASE / "mtef"
OUT.mkdir(exist_ok=True)

# ---------- 字符映射 ----------
SUB_MAP = dict(zip("0123456789+-=()aeoxhklmnpstrijuv",
                   "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜᵣᵢⱼᵤᵥ"))
SUP_MAP = dict(zip("0123456789+-=()abcdefghijklmnoprstuvwxyz",
                   "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ"))
# 规范补充: —(em dash)/－(全角减)/−(减号)→⁻, ＋(全角加)→⁺
SUP_MAP.update({"\u2014": "⁻", "\uFF0D": "⁻", "\u2013": "⁻", "\u2212": "⁻", "\uFF0B": "⁺", "~": "˜",
                "\u2015": "⁻"})   # ―(U+2015 横杠) 作上标负号（钠批次 序3/序4 均见）
SUB_MAP.update({"\u2014": "₋", "\uFF0D": "₋", "\u2013": "₋", "\u2212": "₋", "\uFF0B": "₊",
                "\u2015": "₋"})
# 【氯批次 序3/序4 修订·通用，已同步钠批次】大写字母作下标（如 Vₐ、Nₐ 排版异常形态）；
#  序4 的 mtef_render 已实测该行，序3 归档登记过同一补丁 → 并入工具库。
SUB_MAP.update({"A": "ₐ"})
for _d in "₀₁₂₃₄₅₆₇₈₉":
    SUB_MAP[_d] = _d
for _d in "⁰¹²³⁴⁵⁶⁷⁸⁹":
    SUP_MAP[_d] = _d

# PUA / 私有区映射 (逐案积累)
PUA_MAP = {
    0xE98F: "·",
    0xEF05: " ",
    # 【U108/U111/U122·建库并入】氮批三件 600 dpi 目验实证：
    0xEF04: " ",     # 序6 双图证为半角空格（同 EF05）
    0xEF01: "",      # 序7/序10 双件证"无可见痕迹"（隐形间隔，删）
    0xF8FF: "",      # Apple logo 占位(不应出现)
    0xE962: "⇌",
}
# MTCode 特殊值修正
MTCODE_FIX = {
    0x00AD: "",      # soft hyphen
    0xFEFF: "",
    0x225C: "=(Δ)=",  # ≜ (delta-equals 复合字形)
}

LOG = {"unknown_pua": {}, "unconvertible_sub": {}, "unconvertible_sup": {},
       "templates": {}, "embell": {}, "piles": 0, "matrices": 0,
       "failures": {}, "arrow_debug": []}

def log_key(d, k):
    d[str(k)] = d.get(str(k), 0) + 1


def _cond_join(texts):
    """【U106/U109/U117·建库并入】条件等号/条件箭头的多条件连接：
    非空槽按出现序、「Δ/△」恒置末（化学惯例：加热符号最后，如 =(催化剂、Δ)= 、
    钠批先例 =(MnO₂、Δ)= ），顿号连接。替代旧 `"/".join`（`=(Δ/催化剂)=` 槽序颠倒形态
    与 `=(催化剂)=Δ` 兄弟 token 形态均读不通）。"""
    parts = [t for t in texts if t]
    tail = [t for t in parts if t in ("Δ", "△")]
    head = [t for t in parts if t not in ("Δ", "△")]
    return "、".join(head + tail)

def to_script(s, table, kind):
    # 【序2 修复·裁决2】槽内前导/尾随空白（转换器残留）先剥离——否则 `any(ch not in table...)`
    #   会把**可转换的槽**（如 OMML 上标 "- "）误判为"不可转换槽"→ 整槽原样返回，
    #   上标负号丢失（序2 实测 `2OH-` 应为 `2OH⁻`）。
    #   **最小侵入**：仅当"剥离后全部可转换"时才采用剥离结果，其余一律维持旧行为。
    _st = s.strip()
    if _st != s and _st and all(ch in table for ch in _st):
        s = _st
    # 纯字母槽且含不可转换字母 → 整槽保持原型(如 MCs、MPb、Kw)
    if s and any(ch not in table for ch in s):
        if not any(ch.isdigit() or ch in "₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹" for ch in s):
            for ch in s:
                if ch not in table:
                    log_key(LOG["unconvertible_" + kind], ch)
            return s
    out = []
    for ch in s:
        if ch in table:
            out.append(table[ch])
        else:
            log_key(LOG["unconvertible_" + kind], ch)
            out.append(ch)
    return "".join(out)

# ---------- 二进制读取 ----------
class RD:
    def __init__(self, data, name):
        self.d = data
        self.i = 0
        self.name = name
    def left(self):
        return len(self.d) - self.i
    def u8(self):
        v = self.d[self.i]; self.i += 1; return v
    def le16(self):
        v = self.d[self.i] | (self.d[self.i+1] << 8); self.i += 2; return v
    def uint(self):
        b = self.u8()
        if b == 255:
            return self.le16()
        return b
    def sint(self):
        b = self.u8()
        if b == 255:
            return self.le16() - 32768
        return b - 128
    def cstr(self):
        j = self.d.index(0, self.i)
        s = self.d[self.i:j].decode("gbk", errors="replace")
        self.i = j + 1
        return s
    def nudge(self):
        b0 = self.u8(); b1 = self.u8()
        if b0 == 128 and b1 == 128:
            dx = self.le16(); dy = self.le16()
            if dx >= 32768: dx -= 65536
            if dy >= 32768: dy -= 65536
            return dx, dy
        return b0 - 128, b1 - 128
    def dim_array(self):
        n = self.u8()
        pending = [None]
        def next_nib():
            if pending[0] is not None:
                v = pending[0]; pending[0] = None; return v
            byte = self.u8()
            pending[0] = byte & 15
            return byte >> 4
        vals = []
        for _ in range(n):
            cur = []
            while True:
                nib = next_nib()
                if nib == 0xF:
                    break
                cur.append(nib)
            vals.append(cur)
        # pending[0] 为奇数补齐的 0 nibble, 丢弃
        return vals

# ---------- MTEF 记录 ----------
END, LINE, CHAR, TMPL, PILE, MATRIX, EMBELL, RULER = 0, 1, 2, 3, 4, 5, 6, 7
FONT_STYLE_DEF, SIZE, FULL, SUB, SUB2, SYM, SUBSYM = 8, 9, 10, 11, 12, 13, 14
COLOR, COLOR_DEF, FONT_DEF, EQN_PREFS, ENCODING_DEF = 15, 16, 17, 18, 19

TMPL_NAMES = ["ANGLE","PAREN","BRACE","BRACK","BAR","DBAR","FLOOR","CEILING","OBRACK",
              "INTERVAL","ROOT","FRACT","UBAR","OBAR","ARROW","INTEG","SUM","PROD",
              "COPROD","UNION","INTER","INTOP","SUMOP","LIM","HBRACE","HBRACK","LDIV",
              "SUB","SUP","SUBSUP","DIRAC","VEC","TILDE","HAT","ARC","JSTATUS","STRIKE","BOX"]

EMBELL_CHARS = {2:"̇",3:"̈",4:"⃛",5:"′",6:"″",7:"‵",8:"~",9:"^",10:"̸",
                11:"→",12:"←",13:"↔",16:"−",17:"‾",18:"‴",24:"⃛⃛",
                25:"̣",29:"_",30:"~"}

class P:
    def __init__(self, rd):
        self.rd = rd
        self.depth = 0

    def parse_records(self, stop_at_end=True):
        """解析对象列表, 返回 token 列表; 遇 END 结束"""
        tokens = []
        while self.rd.left() > 0:
            tag = self.rd.u8()
            if tag == END:
                return tokens
            elif tag == LINE:
                tokens.append(self.r_line())
            elif tag == CHAR:
                tokens.append(self.r_char())
            elif tag == TMPL:
                tokens.append(self.r_tmpl(tokens))
            elif tag == PILE:
                tokens.append(self.r_pile())
            elif tag == MATRIX:
                tokens.append(self.r_matrix())
            elif tag == EMBELL:
                emb = self.r_embell()
                if tokens:
                    tokens[-1] = tokens[-1] + emb
                else:
                    tokens.append(emb)
            elif tag == RULER:
                self.r_ruler()
            elif tag in (FULL, SUB, SUB2, SYM, SUBSYM):
                pass  # typesize 记录无选项字节
            elif tag == SIZE:
                self.r_size()
            elif tag == FONT_STYLE_DEF:
                self.rd.uint(); self.rd.u8()
            elif tag == COLOR:
                self.rd.uint()
            elif tag == COLOR_DEF:
                self.r_color_def()
            elif tag == FONT_DEF:
                self.rd.uint(); self.rd.cstr()
            elif tag == EQN_PREFS:
                self.r_eqn_prefs()
            elif tag == ENCODING_DEF:
                self.rd.cstr()
            elif tag >= 100:
                n = self.rd.uint()
                self.rd.i += n
            else:
                raise ValueError("unknown tag %d at %d" % (tag, self.rd.i - 1))
        return tokens

    def opts_nudge(self):
        opts = self.rd.u8()
        if opts & 0x08:
            self.rd.nudge()
        return opts

    def r_line(self):
        opts = self.opts_nudge()
        if opts & 0x04:
            self.rd.le16()  # line spacing
        if opts & 0x02:
            self.r_ruler()
        if opts & 0x01:  # NULL line: 无对象列表
            return ""
        toks = self.parse_records()
        return self.join_tokens(toks)

    def r_char(self):
        opts = self.opts_nudge()
        tface = self.rd.sint()
        mtcode = None
        ch8 = ch16 = None
        if not (opts & 0x20):
            mtcode = self.rd.le16()
        if opts & 0x04:
            ch8 = self.rd.u8()
        if opts & 0x10:
            ch16 = self.rd.le16()
        ch = self.map_char(mtcode, ch16 if ch16 is not None else ch8, tface)
        if opts & 0x01:  # embellishments
            embs = self.parse_records()
            # embell 已在 parse_records 中作为 EMBELL 处理, 这里拼上
            ch = ch + "".join(t for t in embs)
        return ch

    def map_char(self, mtcode, fontpos, tface):
        cp = mtcode
        if cp is None:
            cp = fontpos
        if cp is None:
            return ""
        if cp in MTCODE_FIX:
            return MTCODE_FIX[cp]
        if 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp:
            if cp in PUA_MAP:
                return PUA_MAP[cp]
            log_key(LOG["unknown_pua"], hex(cp))
            return "⟨U+%04X⟩" % cp
        try:
            return chr(cp)
        except ValueError:
            log_key(LOG["unknown_pua"], hex(cp))
            return "⟨U+%04X⟩" % cp

    def r_tmpl(self, tokens):
        opts = self.opts_nudge()
        sel = self.rd.u8()
        b1 = self.rd.u8()
        if b1 & 0x80:
            var = (b1 & 0x7F) | (self.rd.u8() << 8)
        else:
            var = b1
        # MathType 6.9 对所有模板都写 template-specific options 字节
        self.rd.u8()
        name = TMPL_NAMES[sel] if sel < len(TMPL_NAMES) else "T%d" % sel
        log_key(LOG["templates"], name)
        subs = self.parse_records()
        subs = [s for s in subs]
        return self.render_tmpl(name, sel, var, subs, tokens)

    def render_tmpl(self, name, sel, var, subs, tokens):
        nz = [s for s in subs if s != ""]
        if name in ("ANGLE","PAREN","BRACE","BRACK","BAR","DBAR","FLOOR","CEILING","OBRACK"):
            pairs = {"ANGLE":("⟨","⟩"),"PAREN":("(",")"),"BRACE":("{","}"),
                     "BRACK":("[","]"),"BAR":("|","|"),"DBAR":("‖","‖"),
                     "FLOOR":("⌊","⌋"),"CEILING":("⌈","⌉"),"OBRACK":("⟦","⟧")}
            l, r = pairs[name]
            body = nz[0] if nz else ""
            left = l if var & 1 else ""
            right = r if var & 2 else ""
            return left + body + right
        if name == "INTERVAL":
            lmap = {0:"(",1:")",2:"[",3:"]"}
            l = lmap.get(var & 3, "("); r = lmap.get((var >> 4) & 3, ")")
            return l + (nz[0] if nz else "") + r
        if name == "ROOT":
            # 槽位可能全空（nz==[]）：旧写法 len(nz)==1 兜不住空表，会 nz[0] IndexError
            # （被 main 的 except 吞掉 ⇒ 该对象降级为 ⟨MISSING⟩、公式丢失）
            if var == 0 or len(nz) < 2:
                return "√" + (nz[-1] if nz else "")
            idx = to_script(nz[0], SUP_MAP, "sup")
            return idx + "√" + nz[1]
        if name == "FRACT":
            if len(nz) >= 2:
                return "(%s)/(%s)" % (nz[0], nz[1])
            return (nz[0] if nz else "")
        if name in ("UBAR","OBAR"):
            # 双线 under/overbar 包裹文本 = 化学条件等号写法 =(X)=
            # 【氯批次 序6 修订·通用，已同步钠批次】源文「加热条件等号」可见两种画法：
            #   ① 复合字形 ≜（0x225C → "=(Δ)="）；② 由 Δ 字符带**下划线 embell
            #   （EMBELL 29 → '_'）** + UBAR 自身横线拼成双横线（视觉同为 Δ 置于双横线上）。
            #   画法② 的 TMPL 常带 var = 0，旧口径仅 `var & 1` 才判条件等号 → 漏判、输出 "Δ_"。
            #   故：槽文本以 `_`（embell 下划线）收尾时同样判为条件等号，并剥离该 `_`。
            #   U35 回归：全库普查 UBAR/OBAR/DBAR/BAR 仅序6 的 oleObject59 命中（n=1）；
            #   未命中时本分支与旧版逐字节同结果（纯超集）→ 对已交付件零影响。
            # 【U106·建库并入】多槽条件（600 dpi 目验"上槽催化剂 / 下槽Δ"）：旧版只取 nz[0]，
            #   其余非空槽被静默丢弃或甩到等号后 ⇒ 全部并入条件（_cond_join：顿号、Δ 置末）。
            body = nz[0] if nz else ""
            has_bar = bool(var & 1) or body.endswith("_")
            if has_bar:
                core = body[:-1] if body.endswith("_") else body
                extra = [s for s in nz[1:] if s and s != "_"]
                if extra:
                    core = _cond_join([core] + extra)
                return "=(%s)=" % core
            return body
        if name == "ARROW":
            return self.render_arrow(var, subs)
        if name in ("SUM","PROD","COPROD","UNION","INTER","INTOP","SUMOP","INTEG"):
            sym = {"SUM":"∑","PROD":"∏","COPROD":"∐","UNION":"∪","INTER":"∩",
                   "INTOP":"∫","SUMOP":"∑","INTEG":"∫"}[name]
            body = nz[0] if nz else ""
            extra = "".join(nz[1:])
            return sym + extra + body
        if name == "LIM":
            main = nz[0] if nz else ""
            rest = nz[1:]
            if main in ("=","＝","→","⇌","-"):
                if rest:
                    # 【U109·建库并入】旧 "/".join 会产出 `=(Δ/催化剂)=`（槽序颠倒、读不通）
                    return "=(%s)=" % _cond_join(rest)
                return "=" if main in ("＝",) else main
            return "lim" + to_script("".join(rest), SUB_MAP, "sub") + main
        if name in ("HBRACE","HBRACK"):
            return nz[0] if nz else ""
        if name == "LDIV":
            return "".join(nz)
        if name in ("SUB","SUP","SUBSUP"):
            # MathType 6.9 恒写两个槽: [下标槽, 上标槽], 空槽为 NULL LINE('')
            subraw = subs[0] if len(subs) > 0 else ""
            supraw = subs[1] if len(subs) > 1 else ""
            if name == "SUB":
                subraw = next((s for s in subs if s), "")
                supraw = ""
            elif name == "SUP":
                supraw = next((s for s in reversed(subs) if s), "")
                subraw = ""
            sub = to_script(subraw, SUB_MAP, "sub")
            sup = to_script(supraw, SUP_MAP, "sup")
            precedes = var & 1
            if tokens and not precedes:
                base = tokens.pop()
                return base + sub + sup
            # 前置上下标或无 base: 附加到下一个 token 由 join 处理
            return "⟨PRE:%s%s⟩" % (sub, sup)
        if name == "DIRAC":
            return "|" + "".join(nz) + "⟩"
        if name == "VEC":
            return (nz[0] if nz else "") + "⃗"
        if name == "TILDE":
            return (nz[0] if nz else "") + "~"
        if name == "HAT":
            return (nz[0] if nz else "") + "^"
        if name == "ARC":
            return nz[0] if nz else ""
        if name in ("JSTATUS",):
            return "".join(nz)
        if name == "STRIKE":
            return nz[0] if nz else ""
        if name == "BOX":
            return nz[0] if nz else ""
        return "".join(nz)

    def render_arrow(self, var, subs):
        # ArroBoxClass 子对象: [上槽?][下槽?] + 箭头字符(可能为 CHAR 文本)
        texts = []
        arrowch = None
        for s in subs:
            if s in ("=", "＝"):
                arrowch = "="
            elif s in ("→","←","↔","⇌","⇋","⇒","⇐","⇔","↔"):
                arrowch = s
            elif s != "":
                texts.append(s)
        single = not (var & 1)
        harpoon = bool(var & 2)
        if arrowch is None:
            if single:
                if var & 0x10:
                    arrowch = "←"
                elif var & 0x20:
                    arrowch = "→"
                else:
                    arrowch = "→"
            elif harpoon:
                arrowch = "⇋" if (var & 0x20) else "⇌"
            else:
                arrowch = "⇒"
        LOG["arrow_debug"].append({"var": var, "texts": texts, "ch": arrowch})
        # 【U112·建库并入】可逆号有时被写成两个半箭头字符（⇀ 与 ↽/⇽）混在 texts 里
        #   （氮批序13 oleObject88/116 实测 `=(催化剂/加热/⇀/⇽)=` 实为 ⇌(催化剂、加热)）：
        #   成对出现 ⇒ 剥离半箭头、箭头本体判 ⇌。
        if "⇀" in texts and ("↽" in texts or "⇽" in texts):
            texts = [t for t in texts if t not in ("⇀", "↽", "⇽")]
            arrowch = "⇌"
        if not texts:
            return arrowch
        cond = _cond_join(texts)   # 【U109·建库并入】"/"join → 顿号 + Δ 置末
        if arrowch == "=":
            return "=(%s)=" % cond
        if arrowch == "→":
            return "=(%s)=" % cond  # 化学条件箭头统一等号风格? 先记录
        if arrowch == "⇌":
            return "⇌(%s)" % cond
        return arrowch + "(" + cond + ")"

    def r_pile(self):
        opts = self.opts_nudge()
        self.rd.u8(); self.rd.u8()  # halign, valign
        if opts & 0x02:
            self.r_ruler()
        LOG["piles"] += 1
        toks = self.parse_records()
        return " ".join(t for t in toks if t)

    def r_matrix(self):
        opts = self.opts_nudge()
        self.rd.u8()  # valign
        self.rd.u8()  # halign
        rows = self.rd.u8(); cols = self.rd.u8()
        self.rd.i += (rows + 1) + (cols + 1)  # partition lines
        LOG["matrices"] += 1
        toks = self.parse_records()
        cells = [t for t in toks]
        out = []
        for r in range(rows):
            row = cells[r*cols:(r+1)*cols]
            out.append(" ".join(c for c in row if c))
        return " ; ".join(o for o in out if o)

    def r_embell(self):
        opts = self.opts_nudge()
        e = self.rd.u8()
        log_key(LOG["embell"], e)
        return EMBELL_CHARS.get(e, "")

    def r_ruler(self):
        n = self.rd.u8()
        for _ in range(n):
            self.rd.u8()       # stop type
            self.rd.le16()     # 16-bit offset

    def r_size(self):
        b = self.rd.u8()
        if b == 101:        # 显式点尺寸
            self.rd.le16()
        elif b == 100:      # 大 delta
            self.rd.u8(); self.rd.le16()
        else:               # lsize, dsize+128
            self.rd.u8()

    def r_color_def(self):
        opts = self.rd.u8()
        # color values: cmyk(4) or rgb(3) 16-bit each? 按 4 个 16 位读取(保守)
        nvals = 4 if (opts & 1) else 3
        for _ in range(nvals):
            self.rd.le16()
        if opts & 0x04:
            self.rd.cstr()

    def r_eqn_prefs(self):
        self.rd.u8()  # options
        self.rd.dim_array()  # sizes
        self.rd.dim_array()  # spaces
        n = self.rd.u8()   # styles count
        for _ in range(n):
            idx = self.rd.uint()
            if idx:
                self.rd.u8()

    def join_tokens(self, toks):
        out = []
        for t in toks:
            if t.startswith("⟨PRE:"):
                out.append(t)
                continue
            if out and out[-1].startswith("⟨PRE:"):
                pre = out.pop()
                m = pre[5:-1]
                out.append(m + t)
            else:
                out.append(t)
        res = "".join(out)
        # 残留前置标记(下文无 base, base 在公式外): 去壳保留内容
        import re as _re
        res = _re.sub(r"⟨PRE:([^⟩]*)⟩", r"\1", res)
        # 【U106·建库并入】条件等号"下槽条件被甩到等号之后"的**兄弟 token 形态**：
        #   源文把 Δ 作为独立 CHAR 紧跟条件等号模板 ⇒ 旧输出 `=(催化剂)=Δ`（逻辑说不通，
        #   氮批序5/6/10/11/13 五件曾用件内 STR_FIXES 修）。此处统一归并（顿号、Δ 恒置末）。
        res = _re.sub(r"=\(([^()=]+)\)=([Δ△])", r"=(\1、\2)=", res)
        return res

def parse_ole(path):
    ole = olefile.OleFileIO(str(path))
    data = ole.openstream("Equation Native").read()
    ole.close()
    mtef = data[28:]
    rd = RD(mtef, path.name)
    ver = rd.u8()
    if ver != 5:
        raise ValueError("MTEF version %d" % ver)
    rd.u8(); rd.u8(); rd.u8(); rd.u8()  # platform/product/ver/subver
    rd.cstr()      # app key, e.g. DSMT6
    rd.u8()        # equation options
    p = P(rd)
    toks = p.parse_records()
    text = p.join_tokens(toks)
    rest = rd.left()
    # 允许结尾若干 0x00
    d = rd.d
    while rd.left() > 0 and rd.d[rd.i] == 0:
        rd.i += 1
    leftover = rd.left()
    return text, leftover, len(mtef) - leftover

def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    fmap = {}
    files = sorted(EMB.glob("oleObject*.bin"), key=lambda p: int(p.stem[9:]))
    if only:
        files = [EMB / (only + ".bin")]
    ok = 0
    for f in files:
        name = f.stem
        try:
            text, leftover, used = parse_ole(f)
            if leftover != 0:
                LOG["failures"][name] = "leftover %d bytes" % leftover
            else:
                ok += 1
            fmap[name] = text
        except Exception as e:
            LOG["failures"][name] = "%s: %s" % (type(e).__name__, e)
            fmap[name] = "⟨MISSING:%s⟩" % name
    (OUT / "formula_map.json").write_text(json.dumps(fmap, ensure_ascii=False, indent=0), encoding="utf-8")
    (OUT / "parse_log.json").write_text(json.dumps(LOG, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- S3 规定产物 all_formulas.txt：逐对象还原结果 + 零剩余校验 + 唯一公式去重 ----
    L = ["# MathType OLE (MTEF5) 程序化还原结果 —— S3 产物",
         "对象数: %d   成功(字节零剩余): %d   失败: %d" % (len(files), ok, len(LOG["failures"])),
         "模板使用: %s" % LOG["templates"],
         "未知 PUA: %s" % LOG["unknown_pua"],
         "不可转换下标: %s   不可转换上标: %s" % (LOG["unconvertible_sub"], LOG["unconvertible_sup"]),
         "",
         "## 逐对象（工作簿 embeddings/oleObjectN.bin → 线性文本）"]
    for f in files:
        n = f.stem
        L.append("[%s] 还原: %s" % (n, fmap.get(n, "")))
        L.append("        %s" % ("!! " + LOG["failures"][n] if n in LOG["failures"]
                                 else "字节零剩余: OK"))
    uniq = sorted(set(fmap.values()))
    L += ["", "## 唯一公式去重（%d 个）" % len(uniq)]
    for u in uniq:
        L.append("  %s   ← %d 个对象" % (u, sum(1 for v in fmap.values() if v == u)))
    (OUT / "all_formulas.txt").write_text("\n".join(L) + "\n", encoding="utf-8")

    print("total:", len(files), "ok:", ok, "failed:", len(LOG["failures"]))
    print("all_formulas.txt written")
    print("templates:", LOG["templates"])
    print("unknown_pua:", LOG["unknown_pua"])
    print("unconv sub:", ascii(LOG["unconvertible_sub"]))
    print("unconv sup:", ascii(LOG["unconvertible_sup"]))
    for k, v in list(LOG["failures"].items())[:10]:
        print("FAIL", k, v)

if __name__ == "__main__":
    main()
