# -*- coding: utf-8 -*-
r"""zoom_profile.py —— 图片「像素剖面 + 局部放大」核验工具

用途：S4/S9 阶段核对**低分辨率图**的细节，客观判定不能靠目视的要素：
- 单线桥/双线桥的**箭头起止与指向**（箭头端 = 逐行暗像素宽度递增的实心三角）；
- 装置图**导管长短与进出方向**、液面高度、加热位置；
- 流程图的**箭头方向**与节点连接；
- 坐标轴的刻度线位置与量程。

原理：对每一行统计暗像素的 x 区间与数量，并给出「逐行最宽连续暗段」；
实心箭头会表现为若干行内「最宽暗段」单调递增后又骤减（如 14→11→7→5），
而普通直线/竖笔则保持等宽（如恒为 2）。据此可区分「箭头端」与「尾端」。

用法：
    python zoom_profile.py <图片路径> [--zoom 8] [--crop x0,y0,x1,y1]
                           [--thresh 128] [--no-rows]

输出（与图片同目录）：
    <图片名>_profile.txt : 逐行剖面（UTF-8；stdout 只打 ASCII 摘要）
    <图片名>_zoom.png    : 整图 --zoom 倍放大（透明底先合成白底）
    <图片名>_crop.png    : --crop 区域的 --zoom 倍放大（给出 --crop 时）

说明：本工具为**只读**分析，不修改任何交付物；中文一律写文件，避免 GBK 终端乱码。
"""
import argparse
import sys
from pathlib import Path

from PIL import Image


def load_rgb(path):
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    return bg.convert("RGB")


def parse_crop(s):
    parts = [int(float(x)) for x in s.replace(" ", "").split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--crop 需 4 个值：x0,y0,x1,y1")
    return tuple(parts)


def profile(g, thresh):
    w, h = g.size
    px = g.load()
    rows = []
    for y in range(h):
        xs = [x for x in range(w) if px[x, y] < thresh]
        runs, cur = [], 0
        for x in range(w):
            if px[x, y] < thresh:
                cur += 1
            else:
                if cur:
                    runs.append(cur)
                cur = 0
        if cur:
            runs.append(cur)
        rows.append((y, xs, runs))
    return rows


def main():
    ap = argparse.ArgumentParser(description="图片像素剖面 + 局部放大（只读）")
    ap.add_argument("image", help="图片绝对/相对路径")
    ap.add_argument("--zoom", type=int, default=8, help="放大倍数（默认 8）")
    ap.add_argument("--crop", type=parse_crop, default=None, help="区域放大 x0,y0,x1,y1（原图像素坐标）")
    ap.add_argument("--thresh", type=int, default=128, help="暗像素阈值（默认 128）")
    ap.add_argument("--no-rows", action="store_true", help="不输出逐行剖面（只出放大图）")
    args = ap.parse_args()

    src = Path(args.image)
    if not src.exists():
        print("ERR: image not found:", src.name)
        return 2
    rgb = load_rgb(src)
    w, h = rgb.size
    g = rgb.convert("L")

    L = ["# zoom_profile · %s" % src.name,
         "size: %dx%d  thresh: %d  zoom: %d" % (w, h, args.thresh, args.zoom), ""]

    if not args.no_rows:
        rows = profile(g, args.thresh)
        L.append("== 逐行暗像素 (y: x范围 计数) ==")
        for y, xs, runs in rows:
            if xs:
                L.append("y=%4d x=[%4d..%4d] n=%4d" % (y, xs[0], xs[-1], len(xs)))
        L.append("")
        L.append("== 逐行最宽连续暗段（>=2；箭头端表现为单调递增后骤减）==")
        for y, xs, runs in rows:
            if runs and max(runs) >= 2:
                L.append("y=%4d maxrun=%3d runs=%s" % (y, max(runs), runs))
        L.append("")
        L.append("== 提示 ==")
        L.append("- 等宽(如恒为 2~3)的竖笔 = 引线/尾端；宽度单调递增(如 14→11→7→5) = 实心箭头端。")
        L.append("- 横线所在 y 即桥/引线高度；横线 x 区间即该桥覆盖的横向范围。")

    whole = src.with_name(src.stem + "_zoom.png")
    rgb.resize((w * args.zoom, h * args.zoom), Image.LANCZOS).save(whole)
    L.append("zoom image -> %s" % whole.name)
    if args.crop:
        c = rgb.crop(args.crop)
        cp = src.with_name(src.stem + "_crop.png")
        c.resize((c.width * args.zoom, c.height * args.zoom), Image.LANCZOS).save(cp)
        L.append("crop image (%s) -> %s" % (args.crop, cp.name))

    dst = src.with_name(src.stem + "_profile.txt")
    dst.write_text("\n".join(L), encoding="utf-8")
    print("OK: %s -> %s (size %dx%d)" % (src.name, dst.name, w, h))
    return 0


if __name__ == "__main__":
    sys.exit(main())
