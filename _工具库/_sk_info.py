# -*- coding: utf-8 -*-
"""_sk_info.py · 【skill 专属】输入夹「提取信息表」读写与同步（免重复填参）。

信息表：`<输入夹>\\_提取信息.md`（与 docx 同级，**Markdown 表格**，人可读可手改）。
作用：把"输出根目录 / 批次名 / 特殊约定 / 逐件进度"固化在**输入夹自身**，使该文件夹
后续在新对话中的提取任务**无需重新填写**；本表是输入夹的权威源，`_target.txt` 与
`_队列\\queue.json` 均由本脚本按表同步。

子命令（stdout 仅 ASCII，U2/U90；中文详情一律落盘 UTF-8 报告）：
  <py> _sk_info.py check   # 报告：表是否存在 / 必填项缺失 / 新增·消失文件 / 队列状态
                           #   exit 0=可开工（可能需先 sync） 3=无表须 init+询问 4=缺必填须补问
  <py> _sk_info.py init    # 无表则生成骨架（含当前 docx 清单；输出根目录留「（待填）」）
  <py> _sk_info.py sync    # 同步：新增件追加（备注「新增」）/ 源文件缺失标注 / 刷新时间 /
                           #   写 _target.txt 前两行 + _队列\\queue.json（注入进度 status）
  <py> _sk_info.py status --stem "<stem>" --set done|run|todo|skip
                           # 单件状态回写（供 S10 收口；stem 走 argv 仅限 ASCII，
                           #   中文 stem 由 agent 直接编辑信息表或用 --index N）

输入夹 / 输出根取自 `_templates\\_target.txt` 前两行（或环境变量 SKILL_TARGET，TAB 分隔；
env 模式下**不写** `_target.txt`，供测试与并行场景）。第 2 行可为空/「（待填）」。
"""
import json
import os
import re
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
SKILL_ROOT = BASE.parent                      # 试题提取 skill 工程根
TPL = BASE / "_templates"
TARGET = TPL / "_target.txt"
QUEUE_DIR = SKILL_ROOT / "_队列"
REPORT = BASE / "_sk_info_check.txt"
TABLE_NAME = "_提取信息.md"
TABLE_VER = "1"

sys.path.insert(0, str(BASE))
import scan_input  # noqa: E402

KEYS = ["skill 位置", "输出根目录", "批次/项目名", "创建时间", "最近更新", "表版本", "输入夹"]
TODO, RUN, DONE, SKIP = "\u2b1c未开始", "\U0001f504进行中", "\u2705完成", "\u26a0需裁决"
STATUS_ALIAS = {"todo": TODO, "run": RUN, "done": DONE, "skip": SKIP,
                TODO: TODO, RUN: RUN, DONE: DONE, SKIP: SKIP}
PENDING = ("", "\uff08\u5f85\u586b\uff09", "(\u5f85\u586b)", "\u5f85\u586b", "-", "none")

RE_KV = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*$")
RE_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*"
                    r"\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*$")

SEC_BASIC = "## \u4e00\u3001\u57fa\u672c\u4fe1\u606f"
SEC_NOTES = "## \u4e8c\u3001\u7279\u6b8a\u7ea6\u5b9a"
SEC_ROWS = "## \u4e09\u3001\u6587\u4ef6\u6e05\u5355\u4e0e\u8fdb\u5ea6"


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def target_lines():
    """[in_root, out_root, stem]（缺项为 None）；env 模式优先且不写回。"""
    raw = os.environ.get("SKILL_TARGET", "")
    if raw:
        return [p.strip() or None for p in raw.split("\t")]
    if not TARGET.exists():
        return []
    out = []
    for ln in TARGET.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        out.append(ln.strip() or None)
    return out


def valid(v):
    return bool(v) and v.strip() not in PENDING


def table_path(in_root):
    return Path(in_root) / TABLE_NAME


def parse(text):
    """→ {"fields":{k:v}, "notes":[..], "rows":[{...}], "created":..,"updated":..}"""
    fields, notes, rows = {}, [], []
    sec = 0
    for ln in text.split("\n"):
        s = ln.strip()
        if s.startswith("## "):
            sec = 1 if s.startswith(SEC_BASIC) else 2 if s.startswith(SEC_NOTES) \
                else 3 if s.startswith(SEC_ROWS) else 0
            continue
        if sec == 1:
            m = RE_KV.match(s)
            if m and m.group(1) in KEYS:
                fields[m.group(1)] = m.group(2)
        elif sec == 2:
            if s.startswith("- "):
                notes.append(s[2:])
        elif sec == 3:
            m = RE_ROW.match(s)
            if m:
                rows.append({"stem": m.group(2), "size": m.group(3), "status": m.group(4),
                             "date": m.group(5), "note": m.group(6)})
    return {"fields": fields, "notes": notes, "rows": rows,
            "created": fields.get("创建时间") or now(),
            "updated": fields.get("最近更新") or now()}


def render(in_root, d):
    L = ["# 提取信息表 · " + Path(in_root).name, "",
         "> 本表由「试题提取 skill」维护（**skill 位置**见下表；新对话把**本文件夹**路径交给 agent 即可按表继续，无需重填）。",
         "> 人可手改，改后下次开工以本表为准（缺项才补问）；结构固定（字段名勿改），`输出根目录` 为唯一必填项。", "",
         SEC_BASIC, "", "| 项 | 值 |", "|---|---|",
         "| skill 位置 | %s |" % d["fields"].get("skill 位置", str(SKILL_ROOT)),
         "| 输出根目录 | %s |" % d["fields"].get("输出根目录", "（待填）"),
         "| 批次/项目名 | %s |" % d["fields"].get("批次/项目名", "（待填，可空）"),
         "| 创建时间 | %s |" % d["created"],
         "| 最近更新 | %s |" % d["updated"],
         "| 表版本 | %s |" % TABLE_VER,
         "| 输入夹 | %s |" % in_root, "",
         SEC_NOTES, "",
         "> 该输入夹的额外要求（命名/版式/图片处理/跳过某件…）；无则留空，逐条 `- ` 起首。", ""]
    L += ["- " + n for n in d["notes"]]
    if not d["notes"]:
        L.append("- （无）")
    L += ["", SEC_ROWS, "",
          "| # | 文件（stem） | 大小(MB) | 状态 | 完成日期 | 备注 |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(d["rows"]):
        L.append("| %d | %s | %s | %s | %s | %s |" % (
            i, r["stem"], r.get("size", ""), r.get("status", TODO),
            r.get("date", ""), r.get("note", "")))
    return "\n".join(L) + "\n"


def disk_stems(in_root):
    out = {}
    for p in sorted(Path(in_root).iterdir()):
        if p.is_dir() or p.name.startswith("~$"):
            continue
        if p.name.lower().endswith(".docx"):
            out[p.name[:-5]] = p.stat().st_size
    return out


def write_target(in_root, out_root, keep_stem=None):
    """更新 _target.txt 前两行（保留注释头与第 3 行）。env 模式不写。"""
    if os.environ.get("SKILL_TARGET"):
        return False
    head = ["# _sk93_target · 三要素目标文件（每件开工前更新；# 开头为注释行）",
            "# 第 1 行：输入文件夹绝对路径（docx 所在，只扫第一层 .docx）",
            "# 第 2 行：输出根目录绝对路径（成品将落 <输出根>\\<stem>\\）",
            "# 第 3 行：当前件 stem（docx 文件名去 .docx，逐字照抄队列 json 的 stem，勿手敲）",
            "# 注：前两行由 _sk_info.py sync 按「提取信息表」自动写入，勿手改。"]
    L = [in_root or "", out_root or "", keep_stem or ""]
    TARGET.write_text("\n".join(head + L) + "\n", encoding="utf-8", newline="\n")
    return True


def do_init(in_root, out_root):
    tp = table_path(in_root)
    if tp.exists():
        print("INIT_SKIP table_exists=1")
        return 0
    rows = [{"stem": s, "size": "%.2f" % (sz / 1048576.0), "status": TODO,
             "date": "", "note": ""} for s, sz in disk_stems(in_root).items()]
    d = {"fields": {"skill 位置": str(SKILL_ROOT),
                    "输出根目录": out_root if valid(out_root) else "（待填）",
                    "批次/项目名": "（待填，可空）"},
         "notes": [], "rows": rows, "created": now(), "updated": now()}
    tp.write_text(render(in_root, d), encoding="utf-8", newline="\n")
    print("INIT_OK rows=%d" % len(rows))
    return 0


def do_sync(in_root, out_root):
    tp = table_path(in_root)
    if not tp.exists():
        do_init(in_root, out_root)
    d = parse(tp.read_text(encoding="utf-8"))
    d["fields"]["skill 位置"] = str(SKILL_ROOT)     # 自动刷新（skill 被移动时失而复得）
    disks = disk_stems(in_root)
    have = {r["stem"]: r for r in d["rows"]}
    added = removed = 0
    stamp = time.strftime("%Y-%m-%d")
    for s, sz in disks.items():
        if s in have:
            have[s]["size"] = "%.2f" % (sz / 1048576.0)
            have[s]["note"] = have[s]["note"].replace("新增 %s" % stamp, "").strip()
        else:
            d["rows"].append({"stem": s, "size": "%.2f" % (sz / 1048576.0),
                              "status": TODO, "date": "", "note": "新增 %s" % stamp})
            added += 1
    for r in d["rows"]:
        if r["stem"] not in disks:
            tag = "⚠ 源文件缺失 %s" % stamp
            if tag not in r["note"]:
                r["note"] = (r["note"] + " " + tag).strip()
            removed += 1
    d["updated"] = now()
    tp.write_text(render(in_root, d), encoding="utf-8", newline="\n")
    wrote_target = write_target(str(in_root), out_root if valid(out_root) else None)

    queued = "need_out_root"
    if valid(out_root):
        payload = scan_input.scan(in_root, out_root)
        st = {r["stem"]: r.get("status", TODO) for r in d["rows"]}
        for it in payload["queue"]:
            it["status"] = st.get(it["stem"], TODO)
        scan_input.write_queue(payload)
        queued = "ok:%d" % len(payload["queue"])
    print("SYNCED added=%d missing=%d rows=%d target=%s queue=%s"
          % (added, removed, len(d["rows"]), "written" if wrote_target else "env-skip", queued))
    return 0


def do_check(in_root, out_root):
    tp = table_path(in_root)
    lines = ["== _sk_info check ==", "输入夹: %s" % in_root,
             "输出根目录(_target.txt): %s" % (out_root or "(空)")]
    if not tp.exists():
        lines += ["表: 不存在（需 init + 询问用户）", "",
                  "NEED_ASK: 输出根目录（必填）、批次/项目名（可空）、特殊约定（可空）"]
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("TABLE=none MISSING=1 NEW=0 REMOVED=0 QUEUE=none detail=_sk_info_check.txt")
        return 3
    d = parse(tp.read_text(encoding="utf-8"))
    missing = [k for k in ("输出根目录",) if not valid(d["fields"].get(k))]
    sk = d["fields"].get("skill 位置", "")
    sk_ok = bool(sk) and (Path(sk) / "_skill规划.md").exists() and (Path(sk) / "_工具库").is_dir()
    sk_cur = (sk == str(SKILL_ROOT))
    disks = set(disk_stems(in_root))
    table_stems = {r["stem"] for r in d["rows"]}
    new = sorted(disks - table_stems)
    gone = sorted(table_stems - disks)
    lines += ["表: 存在",
              "skill 位置: %s  [%s]" % (sk or "(空)",
                                       "有效" if sk_ok else "无效（跑 sync 可自动刷新）"),
              "（本脚本所在 skill: %s）" % SKILL_ROOT,
              "输出根目录(表): %s" % d["fields"].get("输出根目录", ""),
              "批次/项目名: %s" % d["fields"].get("批次/项目名", ""),
              "创建时间: %s   最近更新: %s" % (d["created"], d["updated"]),
              "--- 特殊约定 ---"] + (["  " + n for n in d["notes"]] or ["  （无）"]) + [
              "--- 进度（%d 件）---" % len(d["rows"])]
    for r in d["rows"]:
        lines.append("  [%s] %s  %s  %s" % (r.get("status", ""), r["stem"],
                                            r.get("date", ""), r.get("note", "")))
    lines += ["--- 磁盘 vs 表 ---",
              "新增(未登记) %d: %s" % (len(new), new or "无"),
              "消失(源文件缺) %d: %s" % (len(gone), gone or "无")]
    qp = QUEUE_DIR / "queue.json"
    qinfo = "none"
    if qp.exists():
        try:
            pq = json.loads(qp.read_text(encoding="utf-8"))
            qinfo = "ok:%d" % len(pq.get("queue", []))
        except Exception:
            qinfo = "broken"
    lines += ["--- 队列 ---", "queue.json: %s" % qinfo, "",
              "结论: " + ("需补问缺失项 -> %s" % missing if missing
                        else ("需 sync 自动入队 %d 件" % len(new) if new else "可直接开工（按表复读，无需再问）"))
              + ("；skill 位置需 sync 刷新" if not sk_cur else "；skill 位置已就位")]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("TABLE=ok MISSING=%d NEW=%d REMOVED=%d QUEUE=%s SKILL_OK=%d SKILL_CUR=%d detail=_sk_info_check.txt"
          % (len(missing), len(new), len(gone), qinfo, 1 if sk_ok else 0, 1 if sk_cur else 0))
    return 4 if missing else 0


def do_status(in_root, out_root, args):
    tp = table_path(in_root)
    if not tp.exists():
        print("STATUS_FAIL no_table")
        return 5
    d = parse(tp.read_text(encoding="utf-8"))
    stem = args.get("stem")
    idx = args.get("index")
    newst = STATUS_ALIAS.get((args.get("set") or "").strip())
    if not newst:
        print("STATUS_FAIL bad_set")
        return 5
    hit = None
    for i, r in enumerate(d["rows"]):
        if (idx is not None and str(i) == str(idx)) or (stem and r["stem"] == stem):
            hit = r
            break
    if hit is None:
        print("STATUS_FAIL not_found")
        return 5
    hit["status"] = newst
    hit["date"] = time.strftime("%Y-%m-%d") if newst == DONE else hit.get("date", "")
    d["updated"] = now()
    tp.write_text(render(in_root, d), encoding="utf-8", newline="\n")
    print("STATUS_OK set=%s" % (args.get("set") or "").strip())
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    L = target_lines()
    in_root = L[0] if len(L) > 0 else None
    out_root = L[1] if len(L) > 1 else None
    if not in_root or not Path(in_root).is_dir():
        sys.stderr.write("BAD in_root: set line 1 of _target.txt "
                         "(or SKILL_TARGET env) to the input folder\n")
        return 2
    if cmd == "init":
        return do_init(in_root, out_root)
    if cmd == "sync":
        return do_sync(in_root, out_root)
    if cmd == "status":
        args = {}
        for i, a in enumerate(sys.argv[2:]):
            if a.startswith("--"):
                args[a[2:]] = sys.argv[2 + i + 1] if len(sys.argv) > 2 + i + 1 else ""
        return do_status(in_root, out_root, args)
    return do_check(in_root, out_root)


if __name__ == "__main__":
    sys.exit(main())
