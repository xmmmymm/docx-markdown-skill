# -*- coding: utf-8 -*-
"""make_skeleton.py: content_stream.txt + formula_map + 图片处置 -> skeleton.txt
置换: ⟨OLE:x⟩->公式文本; ⟨IMG:x⟩->⟨FIG:x⟩(保留)/删除(空白/装饰)/文字(符号图);
      ⟨S⟩..⟨/S⟩->Unicode下标; ⟨P⟩..⟨/P⟩->Unicode上标
零残留校验: 输出不得含 ⟨OLE ⟨IMG ⟨S ⟨P oleObject 等标记

【本件】示例为 序2「专题1  钠及钠的氧化物拓展」
- IMG_DROP     : 空白图/装饰图/推广广告（见 work/figure_desc.md 判据）
- IMG_TEXT     : 符号/公式图 → 文字（条件箭头等）
- IMG_TEXT_SEQ : **同一张图多处引用、每处文字不同**（精灵图 srcRect 裁出多条标题）
                 → 按出现顺序逐处取（钠批次 序3/序4：章节标题带 3 处）
- OLE_FIG      : 非 MathType 的 OLE（ACD/ChemSketch）→ 改判为保留插图
                 （序2 oleObject13/14 = 双线桥图 → 引用 images/image19.png）
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mtef_render import SUB_MAP, SUP_MAP, to_script

BASE = Path(__file__).resolve().parent
fmap = json.load(open(BASE / "mtef/formula_map.json", encoding="utf-8"))

# 【skill 版·按件常量全部清空，移植/复制到 work\ 后逐件填写】
# 空白图(像素级 dark=0)/纯装饰图/文末推广广告 → IMG_DROP（见 work/figure_desc.md 判据）
IMG_DROP = set()
# 符号/公式图 → 转文字（条件箭头 Δ 等）
IMG_TEXT = {}
# 同一图多处引用、每处文字不同（精灵图 srcRect 裁出多条标题）→ 按出现顺序取
# 用法示例：IMG_TEXT_SEQ = {"image4.png": ["能力进阶", "综合拔高", "真题挑战"]}
IMG_TEXT_SEQ = {}
# 非 MathType 的 OLE（ACD/ChemSketch）→ 改判为保留插图
# 用法示例：OLE_FIG = {"oleObject13": "image19.png"}
OLE_FIG = {}

stream = (BASE / "content_stream.txt").read_text(encoding="utf-8")
log = {"ole_missing": [], "ole_fig": [], "img_drop": [], "img_text": [],
       "sub_plain": [], "sup_plain": [], "ole_dup": []}

def ole_sub(m):
    name = m.group(1)
    if name in OLE_FIG:
        log["ole_fig"].append(name)
        return "⟨FIG:%s⟩" % OLE_FIG[name]
    if name in fmap and not fmap[name].startswith("⟨MISSING"):
        return fmap[name]
    log["ole_missing"].append(name)
    return "⟨MISSING:%s⟩" % name

SEQ_COUNTER = {}

def img_sub(m):
    name = m.group(1)
    if name in IMG_TEXT_SEQ:
        seq = IMG_TEXT_SEQ[name]
        k = SEQ_COUNTER.get(name, 0)
        SEQ_COUNTER[name] = k + 1
        log["img_text"].append(name)
        return seq[k] if k < len(seq) else seq[-1]
    if name in IMG_DROP:
        log["img_drop"].append(name)
        return ""
    if name in IMG_TEXT:
        log["img_text"].append(name)
        return IMG_TEXT[name]
    return "⟨FIG:%s⟩" % name

def s_sub(m):
    t = m.group(1)
    log["sub_plain"].append(t)
    return to_script(t, SUB_MAP, "sub")

def p_sub(m):
    t = m.group(1)
    log["sup_plain"].append(t)
    return to_script(t, SUP_MAP, "sup")

out = stream
# 【U134·建库并入·检测告警】MathType 对象可与"紧随其后的同义字面文本"重复
#   （形态：`…Cu的质量为(` + ⟨OLE:x⟩(值 m3−m1) + `m3-m1)g…` ⇒ 直落成品得读不通的
#   叠加串 `(m3−m1m3-m1)g`）。此处只**检测并落盘告警**（skeleton_log.ole_dup），
#   不自动改文本——是否去重/补下标须按"正确形态能否由同句唯一确定"人工裁决
#   （U104① 口径）；告警命中时 S9 必须逐条核验。
_DUP_TR = str.maketrans("₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹", "01234567890123456789")

def _norm_frag(s):
    s = s.translate(_DUP_TR)
    s = re.sub(r"[\s()（）]+", "", s)
    return s.replace("−", "-").replace("–", "-").replace("—", "-")

for _m in re.finditer(r"⟨OLE:(oleObject\d+)⟩([^\n⟨]{1,30})", stream):
    _name, _tail = _m.group(1), _m.group(2)
    if _name in OLE_FIG:
        continue
    _val = fmap.get(_name, "")
    if not _val or _val.startswith("⟨MISSING"):
        continue
    _a, _b = _norm_frag(_val), _norm_frag(_tail)
    if len(_a) >= 2 and len(_b) >= 2 and (_a in _b or _b in _a):
        log["ole_dup"].append([_name, _val, _tail.strip()])

out = re.sub(r"⟨OLE:(oleObject\d+)⟩", ole_sub, out)
out = re.sub(r"⟨IMG:([^:⟩]+)(?::A)?⟩", img_sub, out)
out = re.sub(r"⟨S⟩(.*?)⟨/S⟩", s_sub, out)
out = re.sub(r"⟨P⟩(.*?)⟨/P⟩", p_sub, out)

bad = []
for pat in [r"⟨OLE", r"⟨IMG", r"⟨S⟩", r"⟨P⟩", r"⟨/S⟩", r"⟨/P⟩", r"oleObject",
            r"⟨MISSING", r"⟨U\+", r"⟨AL"]:
    for m in re.finditer(pat, out):
        bad.append((pat, out[:m.start()].count("\n") + 1))
if bad:
    print("RESIDUAL:", bad[:20])
    sys.exit(1)

(BASE / "skeleton.txt").write_text(out, encoding="utf-8")
json.dump(log, open(BASE / "skeleton_log.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("skeleton ok, lines:", out.count("\n") + 1)
print("img_drop:", log["img_drop"])
print("img_text:", log["img_text"])
print("ole_fig:", log["ole_fig"])
print("ole_missing:", log["ole_missing"])
print("ole_dup:", json.dumps(log["ole_dup"], ensure_ascii=True))
print("fig residual:", out.count("⟨FIG"))
