# -*- coding: utf-8 -*-
r"""【skill · 反循环机制 3/3】看门狗：按**磁盘事实**判停摆，到点自动报警（主代理据此换棒）。

背景：子代理"陷入循环"时**不会报错、不会停下**，表现为"长时间零落盘"或"只对某一张图反复加工"。
经验的软约束（U43/U69/U74）挡不住 —— 因为执行者是子代理自己。
→ 改为：**主代理外部轮询磁盘**，用"产物是否增长"这一客观事实判定，不依赖任何口头回报。

判据（任一命中即 `STALLED`）：
  1. **零增长**：连续 `--stall` 次轮询，`ninja` 目标（默认 `work\` 全体 + `figure_desc.md` 行数）**无任何新增/变更**；
  2. **污染信号**：出现 `zoom_*` / `_tmp*` / `_app*` / `*_profile.txt` / `*_crop.png` 等污染源文件；
  3. **单图自旋**：`work\` 内某张图的派生文件（同 stem）数量 > `--spin`（默认 3）。

用法（阻塞式，适合短轮询）：
    <py> _sk_watchdog.py "<输出目录>" [--interval 60] [--times 10] [--stall 2]
用法（后台式，推荐：不占主代理命令行）：
    Start-Process -FilePath $py -ArgumentList '_sk_watchdog.py "<输出目录>" --interval 60 --times 20' -WindowStyle Hidden
    → 结果随时读 <输出目录>\work\_watchdog_out.txt
产物：`<输出目录>\work\_watchdog_out.txt`（UTF-8）；stdout 仅 ASCII。
退出码：0=正常（有增长） / 3=STALLED（建议换棒）
"""
import os
import sys
import time

# 污染源是"子代理产出的中间文件"，**不是工具脚本本身**
# （注意排除 .py：`zoom_profile.py`/`zoom_img.py` 是工具库自带脚本，不得误报）
# ⚠ 序2 实测修正：原用「子串包含」匹配 → 任何名字里带 `_tmp` 的取证临时件
#   （如 `_n2_tmp_probe.txt`）都会被判 `STALLED(pollution)` 并触发无谓换棒。
#   现改为**前缀/后缀精确匹配**：`zoom_`/`_tmp`/`_app` 须位于文件名开头，
#   `_profile.txt`/`_crop.png`/`_descr.txt` 须位于文件名结尾。
POLLUTION_PREFIX = ("zoom_", "_tmp", "_app")
POLLUTION_SUFFIX = ("_profile.txt", "_crop.png", "_descr.txt")
# ⚠ 序10 实测修正：后缀类污染源（zoom_profile 派生件）形如 `<图名>_profile.txt` / `<图名>_crop.png` /
#   `<图名>_descr.txt`，其**图名以 `image` 开头**。旧实现只判后缀 ⇒ 主代理自己的取证件
#   `_n10_descr.txt` 也被判污染，触发一次无谓 `STALLED(pollution)`（序10 误报，未换棒，U95）。
#   现要求后缀类**必须同时以 `image` 开头**。
POLLUTION_SUFFIX_STEM = "image"


def is_pollution(relpath):
    b = os.path.basename(relpath)
    if b.lower().endswith(".py"):
        return False
    if b.startswith(POLLUTION_PREFIX):
        return True
    return b.startswith(POLLUTION_SUFFIX_STEM) and b.endswith(POLLUTION_SUFFIX)


def snapshot(root):
    """返回 {relpath: (size, mtime)}"""
    snap = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            p = os.path.join(dp, f)
            try:
                st = os.stat(p)
                snap[os.path.relpath(p, root)] = (st.st_size, int(st.st_mtime))
            except OSError:
                # 遍历期间文件被删除/占用属正常竞态，跳过即可。
                # 收窄到 OSError（原为裸 Exception:pass，会连逻辑错误一并吞掉）
                pass
    return snap


def fd_lines(work):
    p = os.path.join(work, "figure_desc.md")
    if not os.path.isfile(p):
        return -1
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return len(f.read().splitlines())
    except Exception:
        return -1


def main():
    a = sys.argv[1:]
    if not a:
        print("USAGE: _sk_watchdog.py <OUTDIR> [--interval SEC] [--times N] [--stall N] [--spin N]")
        return 1
    out = a[0]
    interval, times, stall, spin = 60, 10, 2, 3
    i = 1
    while i < len(a):
        if a[i] == "--interval" and i + 1 < len(a):
            interval = int(a[i + 1]); i += 2
        elif a[i] == "--times" and i + 1 < len(a):
            times = int(a[i + 1]); i += 2
        elif a[i] == "--stall" and i + 1 < len(a):
            stall = int(a[i + 1]); i += 2
        elif a[i] == "--spin" and i + 1 < len(a):
            spin = int(a[i + 1]); i += 2
        else:
            i += 1

    work = os.path.join(out, "work")
    os.makedirs(work, exist_ok=True)
    log = []
    prev = snapshot(out)
    prev_lines = fd_lines(work)
    zero = 0
    verdict = "OK"
    for t in range(1, times + 1):
        time.sleep(interval)
        cur = snapshot(out)
        new = [k for k in cur if k not in prev or cur[k] != prev[k]]
        lines = fd_lines(work)
        grown = len(new) or (lines != prev_lines)
        poll = sorted({k for k in cur if is_pollution(k)})
        # 单图自旋：同 stem 派生文件数
        stems = {}
        for k in cur:
            b = os.path.basename(k)
            if "image" in b:
                s = b.split("_")[0]
                stems[s] = stems.get(s, 0) + 1
        spun = [s for s, c in stems.items() if c > spin]
        log.append("[%02d] t+%ds new_changed=%d fd_lines=%s poll=%d spun=%s"
                   % (t, t * interval, len(new), lines, len(poll), ",".join(spun) if spun else "-"))
        if new:
            log.append("      + " + "; ".join(new[:8]))
        if poll:
            log.append("      ! POLLUTION: " + "; ".join(os.path.basename(x) for x in poll[:8]))
        if grown:
            zero = 0
        else:
            zero += 1
        if poll:
            verdict = "STALLED(pollution)"
            break
        if spun:
            verdict = "STALLED(spin:%s)" % ",".join(spun)
            break
        if zero >= stall:
            verdict = "STALLED(no_progress x%d)" % zero
            break
        prev, prev_lines = cur, lines
    log.append("VERDICT=%s" % verdict)
    log.append("HINT=%s" % ("换棒：shutdown_request 停用该成员 → 删污染源 → 派干净上下文新成员，并在指令中给出「已判清单 + 剩余区间」"
                            if verdict.startswith("STALLED") else "正常，继续"))
    with open(os.path.join(work, "_watchdog_out.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log))
    print("VERDICT=%s (see work\\_watchdog_out.txt)" % verdict)
    return 3 if verdict.startswith("STALLED") else 0


if __name__ == "__main__":
    sys.exit(main())
