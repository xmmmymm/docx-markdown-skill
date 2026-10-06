# -*- coding: utf-8 -*-
"""copy_images.py: 保留图 -> 目标 images/(透明底先合成白底), 并做引用/文件/描述三一致校验

【移植改动】KEEP / DERIVED（+ `MD` 文件名）
【本件】示例为 序2「专题1  钠及钠的氧化物拓展」：
- KEEP：正文引用且判定"保留"的 6 张（image3/9/10/11/13/15）
- image19.png：非 MathType 的 ACD/ChemSketch 对象(oleObject13/14)预览图的**高分辨率重渲染**
  （work/olefig/image19.png，由 render_ole_fig.py 生成）→ 直接复制
【不再需要按件改的部分（通用，2026-09-15 序3 起）】
- `orphans`（游离/删除 media 的"误复制"校验清单）改为**自动推导**，见下方注释。
  此前按件手列，序2 → 序3 连续两件因漏改造成 `!! 游离/删除 media 被误复制` 假告警。
"""
import json, os, re, shutil
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent
DST = BASE.parent
SRC = BASE / "unpacked/word/media"
OUT = DST / "images"
OUT.mkdir(exist_ok=True)

# 【skill 版·按件常量全部清空，移植/复制到 work\ 后逐件填写】
KEEP = []
# 派生的 OLE 插图（用法示例：[("olefig/image19.png", "image19.png")]）
DERIVED = []

# 【skill 版·自动推导】成品 md = 输出目录名 + ".md"（与 fix_fullwidth.py 同口径）
MD = DST / (DST.name + ".md")

log = []
for name in KEEP:
    src = SRC / name
    im = Image.open(src)
    mode0 = im.mode
    im = im.convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    out = bg.convert("RGB")
    dst = OUT / name
    # 【硫序3·通用】按扩展名选存储格式：.jpeg 源无透明底，若一律以 PNG 数据写入
    #   .jpeg 文件会产生"格式与扩展名不符"（全库既往 51 个 .jpeg 名实为 PNG 数据）。
    out.save(dst, "JPEG" if dst.suffix.lower() in (".jpg", ".jpeg") else "PNG")
    log.append("%s mode=%s -> RGB(白底) %dx%d %dB" % (name, mode0, out.size[0], out.size[1],
                                                     dst.stat().st_size))

for src_rel, name in DERIVED:
    src = BASE / src_rel
    shutil.copyfile(src, OUT / name)
    im = Image.open(src)
    log.append("%s <- work/%s  %dx%d %dB（派生：ChemSketch OLE 预览高分辨率重渲染）"
               % (name, src_rel, im.size[0], im.size[1], (OUT / name).stat().st_size))

# 游离/删除 media（应"未复制"者）**自动推导**，避免按件手列漏改造成 `!!` 假告警
# （钠批次 序2 → 序3 连续两件踩过）：
#   ① content_meta.orphan_media = 页眉页脚图 / OLE 预览 WMF 等未被正文引用的 media
#   ② skeleton_log.img_drop     = 空白·装饰·广告图（不复制）
#   ③ skeleton_log.img_text     = 符号/公式图（转文字，不复制）
_meta = json.loads((BASE / "content_meta.json").read_text(encoding="utf-8"))
_slog = json.loads((BASE / "skeleton_log.json").read_text(encoding="utf-8"))
orphans = sorted(set(_meta.get("orphan_media", []))
                 | set(_slog.get("img_drop", []))
                 | set(_slog.get("img_text", [])))
for o in orphans:
    if (OUT / o).exists():
        log.append("!! 游离/删除 media 被误复制: %s" % o)

md = MD.read_text(encoding="utf-8")
refs = re.findall(r"!\[\]\(images/([^)]+)\)", md)
descs = re.findall(r"!\[\]\(images/[^)]+\)〔图：([^〕]+)〕", md)
files = sorted(os.listdir(OUT))
log.append("引用处数=%d 唯一引用=%d 文件数=%d 带描述=%d" % (len(refs), len(set(refs)), len(files), len(descs)))
log.append("集合一致: %s" % (sorted(set(refs)) == files))
log.append("描述齐全: %s" % (len(descs) == len(refs) and all(d.strip() for d in descs)))
(BASE / "copy_report.txt").write_text("\n".join(log), encoding="utf-8")
print("copied", len(KEEP) + len(DERIVED))
print("refs=%d uniq=%d files=%d desc=%d" % (len(refs), len(set(refs)), len(files), len(descs)))
