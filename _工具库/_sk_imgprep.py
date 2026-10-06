# -*- coding: utf-8 -*-
r"""【skill · 反循环机制 1/3】判图卡片预生成（把"读大图"换成"读 2~3 KB 文本"）。

背景（本机制要根治的病）：
  子代理在 S4 对**某一张图**反复裁剪放大 / 反复 Read 240 KB 原图 → 上下文被污染 →
  陷入"只对这一个内容重复思考、不干活"的循环（氯序7、硫序2/序4/序6 均因此换棒）。
  根因不是"提醒不够"，而是**流程让子代理必须靠读大图才能判图**。

做法：**先机器后人工** —— 在派发子代理之前，由主代理（或本脚本）把每张图压成一张
**纯文本卡片**（尺寸 + 暗像素 + 空白判定 + **暗像素占比网格 ASCII 像素图** + 16×16 灰度签名
+ 内容外接框），子代理判图时 **Read 卡片（约 2.5 KB）而非原图（可达数百 KB）**；
同图（16×16 签名 L1<64）自动聚类并给出"建议复用描述"。

用法：
    <py> _sk_imgprep.py "<输出目录>" [--grid 84x30] [--thresh 128] [--src imgview|media]
产物（全部落 <输出目录>\work\，stdout 仅 ASCII）：
    work\_imgcards\<name>.txt     每图一张卡片（Read 这个，不要 Read 原图）
    work\_imgcards\_index.md      汇总表（size / dark / 空白? / 同图组）
    work\_imgcards\_dup.json      同图聚类结果（供"复用描述"用）
    work\_imgcards\_wmf\          WMF/EMF 经 soffice 转 PNG 的缓存（仅转换用，非交付物）

修订记录（2026-09-18 · 氮批序0 首用发现，主代理修）：
  1) ASCII 网格原先直接对灰度图 BICUBIC 缩小 → 细线条被平均成近白，网格**几乎全空**
     （序0 `image11_view.png` 暗像素 11145/4.0% 却只渲染出 3 个点）。
     改为**先二值化、再用 BOX 缩小取每格暗像素占比**，按占比打 `# * + - .`（` `=全白）。
  2) 同图聚类原先 `L1/256 < 64`（相当于"逐像素平均差 <64"），阈值过大 → **13 张图被判成 1 组**。
     改为 `L1 求和 < 64`（U68 口径：同图 0–31、次近邻 4000+）。
  3) 新增 WMF/EMF 支持：PIL 打不开 → 用 `soffice --headless --convert-to png` 转一份再生成卡片
     （缓存 `work\_imgcards\_wmf\`；转换失败则该图卡片标注 `OPEN_FAIL`，由子代理按 U15 用 `dump_wmf2.py` 处置）。
  4) 新增内容外接框 `bbox`（`bw.getbbox()`），便于卡片不足时判断"是否为一条横线/角落小图"。
"""
import json
import os
import subprocess
import sys

try:
    from PIL import Image
except ImportError:
    print("NO_PIL")
    sys.exit(2)

try:
    BOX = Image.Resampling.BOX
    LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    BOX = Image.BOX
    LANCZOS = Image.LANCZOS

args = sys.argv[1:]
if not args:
    print("USAGE: _sk_imgprep.py <OUTDIR> [--grid WxH] [--thresh N] [--src imgview|media]")
    sys.exit(1)
OUT = args[0]
GRID = (84, 30)
THRESH = 128
SRC = "imgview"
i = 1
while i < len(args):
    if args[i] == "--grid" and i + 1 < len(args):
        w, h = args[i + 1].lower().split("x")
        GRID = (int(w), int(h))
        i += 2
    elif args[i] == "--thresh" and i + 1 < len(args):
        THRESH = int(args[i + 1])
        i += 2
    elif args[i] == "--src" and i + 1 < len(args):
        SRC = args[i + 1]
        i += 2
    else:
        i += 1

WORK = os.path.join(OUT, "work")
if SRC == "imgview":
    SRC_DIR = os.path.join(WORK, "imgview")
else:
    SRC_DIR = os.path.join(WORK, "unpacked", "word", "media")
CARD = os.path.join(WORK, "_imgcards")
os.makedirs(CARD, exist_ok=True)

exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".wmf", ".emf")
names = []
if os.path.isdir(SRC_DIR):
    for f in sorted(os.listdir(SRC_DIR)):
        if f.lower().endswith(exts):
            names.append(f)
if not names and os.path.isdir(os.path.join(WORK, "unpacked", "word", "media")):
    SRC_DIR = os.path.join(WORK, "unpacked", "word", "media")
    names = [f for f in sorted(os.listdir(SRC_DIR)) if f.lower().endswith(exts)]
# 源目录缺失或一张图都没有时必须报错退出：否则 CARDS=0 与"本文档确实无图"
# 无法区分，会把「S1 未跑 / OUT 指错」静默当成成功（下游 S4 判图范围因此为空）。
if not names:
    sys.stderr.write("BAD no images under %s (S1 not run, or wrong OUT?)\n"
                     % SRC_DIR.encode("unicode_escape").decode("ascii"))
    sys.exit(2)


def find_soffice():
    for c in (r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if os.path.exists(c):
            return c
    return None


SOFFICE = find_soffice()


def convert_vector(path):
    """WMF/EMF -> PNG（缓存）；失败返回 None。"""
    if not SOFFICE:
        return None
    cache = os.path.join(CARD, "_wmf")
    os.makedirs(cache, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    out_png = os.path.join(cache, stem + ".png")
    if os.path.exists(out_png) and os.path.getsize(out_png) > 0:
        return out_png
    try:
        subprocess.run([SOFFICE, "--headless", "--convert-to", "png",
                        "--outdir", cache, path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=180)
    except Exception:
        return None
    return out_png if os.path.exists(out_png) and os.path.getsize(out_png) > 0 else None


def ratio_char(r):
    if r <= 0.0:
        return " "
    if r >= 0.50:
        return "#"
    if r >= 0.25:
        return "*"
    if r >= 0.10:
        return "+"
    if r >= 0.03:
        return "-"
    return "."


cards, sigs, rows = [], {}, []
for nm in names:
    p = os.path.join(SRC_DIR, nm)
    srcnote = ""
    try:
        im = Image.open(p)
        im.load()
    except Exception:
        conv = convert_vector(p) if nm.lower().endswith((".wmf", ".emf")) else None
        if not conv:
            rows.append((nm, "OPEN_FAIL", -1, "", ""))
            continue
        try:
            im = Image.open(conv)
            im.load()
            srcnote = "  src=soffice(%s)" % os.path.basename(conv)
        except Exception:
            rows.append((nm, "OPEN_FAIL", -1, "", ""))
            continue
    w, h = im.size
    # 【序13 修订·通用】透明底图必须先合成白底再统计：PIL 的 convert("L") **忽略 alpha**，
    #   全透明像素按其 RGB（常为黑）计入暗像素 ⇒ 卡片退化（序13 实测 image56 dark=99.838%、
    #   image70 94.077%，84×30 网格整幅为 "#"，判图信息量归零）。与交付侧 copy_images.py 的
    #   白底合成同口径；U127（小透明图卡片全黑/伪同图）的根因即在此。
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        im = Image.alpha_composite(base, rgba).convert("RGB")
        srcnote += "  white-composited"
    g = im.convert("L")
    total = w * h or 1

    # 二值化后才缩小：避免细线条被平均成近白（本次修订原因 1）
    bw = g.point(lambda v: 255 if v < THRESH else 0)
    hist = bw.histogram()
    dark = hist[255] if len(hist) > 255 else 0
    bbox = bw.getbbox()

    cell = bw.resize(GRID, BOX)
    cp = list(cell.tobytes())
    lines = []
    for r in range(GRID[1]):
        line = []
        for c in range(GRID[0]):
            line.append(ratio_char(cp[r * GRID[0] + c] / 255.0))
        lines.append("".join(line).rstrip())

    sigs[nm] = list(g.resize((16, 16), LANCZOS).tobytes())
    blank = "BLANK" if dark == 0 else ("NEAR_BLANK" if dark * 1.0 / total < 0.001 else "")
    card = []
    card.append("IMG %s" % nm)
    card.append("size=%dx%d  dark=%d (%.3f%%)  %s%s" % (
        w, h, dark, 100.0 * dark / total, blank, srcnote))
    card.append("bbox=%s  (content box in source pixels; None=all white)" % (bbox,))
    card.append("--- ascii %dx%d  legend: '#'>=50%% '*'>25%% '+'>10%% '-'>3%% '.'>0 ' '=0  (dark-pixel share per cell) ---" % (GRID[0], GRID[1]))
    card.extend(lines)
    card.append("--- end ---")
    stem = os.path.splitext(nm)[0]
    with open(os.path.join(CARD, stem + ".txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(card))
    rows.append((nm, "%dx%d" % (w, h), dark, blank, "card=%s.txt" % stem))

# 同图聚类（16×16 签名 L1 求和，U68 口径：同图 0–31、次近邻 4000+）
keys = [k for k in sigs]
groups = []
used = set()
for a in keys:
    if a in used:
        continue
    grp = [a]
    used.add(a)
    for b in keys:
        if b in used:
            continue
        d = sum(abs(x - y) for x, y in zip(sigs[a], sigs[b]))
        if d < 64:
            grp.append(b)
            used.add(b)
    groups.append(grp)
dup = [g for g in groups if len(g) > 1]

with open(os.path.join(CARD, "_dup.json"), "w", encoding="utf-8") as f:
    json.dump({"groups": groups, "dup_groups": dup}, f, ensure_ascii=False, indent=1)

idx = []
idx.append("# 判图卡片索引（由 `_sk_imgprep.py` 生成）")
idx.append("")
idx.append("- 源目录：`%s`" % SRC_DIR)
idx.append("- 判图时 **Read `work\\_imgcards\\<name>.txt`（约 2~3 KB）**，**不要 Read 原图**；仅在卡片不足以判定、且图 <1000 px 时才允许 Read 原图 1 次。")
idx.append("- 网格字符含义＝该格**暗像素占比**：`#`≥50% `*`>25% `+`>10% `-`>3% `.`>0 ` `=全白；`bbox` 为内容外接框（源图像素坐标）。")
idx.append("")
idx.append("| 图 | 尺寸 | 暗像素 | 空白判定 | 卡片 |")
idx.append("|---|---|---|---|---|")
for nm, sz, dark, blank, cf in rows:
    idx.append("| `%s` | %s | %s | %s | %s |" % (nm, sz, dark, blank or "-", cf))
idx.append("")
if dup:
    idx.append("## 同图组（16×16 签名 L1<64，可直接复用描述，U68）")
    idx.append("")
    for g in dup:
        idx.append("- " + " / ".join("`%s`" % x for x in g))
else:
    idx.append("## 同图组：无")
with open(os.path.join(CARD, "_index.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(idx))

print("CARDS=%d DUPGROUPS=%d BLANK=%d OPENFAIL=%d OUT=%s" % (
    len([r for r in rows if r[4]]), len(dup),
    len([r for r in rows if r[3] == "BLANK"]),
    len([r for r in rows if r[1] == "OPEN_FAIL"]), CARD))
