# -*- coding: utf-8 -*-
"""_题库_sync.py · 把「课后题」工作目录里的题库成品迁入本仓库 _题库\\，**重组分类 + 规范命名**。

**三条设计原则**
  ① **正文逐字节不动**：题库 md 是已过机审（`FAILS: 无`）的交付件，复制时不加头、不改一字；
     重命名只作用于**文件名**，原始名/路径写入 `题库清单.json` 供溯源。
  ② **命名规范化**：原文件名普遍含「学年/出版社/品牌角标/解析版」等噪声，跨批重复且不可排序。
     统一改为 `<类目码>-<两位序号>_<精简主题>.md`，如 `NA-01_钠及其化合物.md`。
  ③ **四层分类**：元素专题 / 题型专题 / 章节同步练 / 阶段检测卷，按 `CAT_TREE` + `TITLE_RULES` 判定。

用法（stdout 仅 ASCII，U2/U90；中文详情落盘 UTF-8）：
  <py> _题库_sync.py --src "<源根>" --dry-run   # 只探测+分类+规划命名，不落盘
  <py> _题库_sync.py --src "<源根>"             # 实际迁移
  <py> _题库_sync.py --src "<源根>" --verify    # 校验已迁移件的图片引用是否全部可达
  <py> _题库_sync.py --src "<源根>" --reset     # 清空 _题库\\ 后重迁（幂等重建）

排除项：work\\ 下全部文件、转换说明/_index/_prefacts/待裁决/_批次*/_skill* 等过程文件、
本工程自身目录（<源根>\\试题提取skill）。
"""
import argparse
import io
import json
import re
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "_题库"
REPORT = DEST / "_迁移报告.txt"
MANIFEST = DEST / "题库清单.json"

# ── 过程文件黑名单 ──────────────────────────────────────────────────
SKIP_EXACT = {"转换说明.md", "_index.md", "_prefacts.md", "待裁决.md", "README.md",
              "转换说明_草稿.md", "s3_cross_verify.md", "_启动提示词.md",
              "_skill规划.md", "_skill经验归档.md", "_提取信息.md"}
SKIP_PREFIX = ("_批次", "_skill", "转换说明", "_工作数据")
SKIP_DIRS = {"work", "images", "__pycache__", ".git", "unpacked", "figprev", "mtef",
             "preview", "_工作数据"}
SKIP_DIR_PREFIX = ("_备份",)   # 备份副本不入库；题型归类整理仍收录（见 CHILD_SUB）
# 顶层非题库文件（规范/说明性文档）
SKIP_ROOT_FILES = {"转换规范（优化版）.md", "提示词.txt", "提示词-优化版.txt"}

# 子目录级重定向：路径片段 → 强制子类与类目码
CHILD_SUB = [
    ("题型归类整理", "02_题型专题", "TYPED", "按题型归类"),
]

# ── 分类树：主类 → 子类 → 归属类目码 ────────────────────────────────
# 类目码决定文件名前缀；同一主类下子类按码归并
CAT_TREE = [
    ("01_元素专题", "NA", "钠及其化合物", r"钠|活泼的金属单质"),
    ("01_元素专题", "CL", "氯及其化合物", r"氯|卤素"),
    ("01_元素专题", "FE", "铁铝及金属材料", r"铁|铝|金属材料"),
    ("01_元素专题", "NI", "氮及其化合物", r"氮|氨|铵盐|硝酸"),
    ("01_元素专题", "S",  "硫及其化合物", r"硫|硫酸|二氧化硫"),
    ("02_题型专题", "FLOW", "工业流程题", r"工业流程|工艺流程|流程题"),
    ("02_题型专题", "EXP", "实验探究与计算", r"实验探究|重难点|计算|差量法|守恒"),
    ("02_题型专题", "MIX", "综合应用", r"跨章|备选题|易错易混|核心考点判断|综合应用"),
]
# 题型归类整理：文件名前缀 00_/01_…/14_ 即题型序号，直接归入「按题型归类」
RE_TYPED = re.compile(r"^(\d{2})_(?:题型|拓展|附录|总览)")
# 阶段检测与章节同步优先级低于元素/题型，须在元素/题型都落空后才启用
CAT_TREE_FALLBACK = [
    ("04_阶段检测卷", "TEST", r"月考|期中|期末|检测卷|检测练习|测试卷|周测|模拟|阶段检测|单元检测|质量提升|综合训练卷|综合练习"),
    ("03_章节同步练", "SYN", r"同步|课时|作业|分层|精练|培优|专项训练|巩固|随堂|练习"),
]

# 命名噪声：品牌角标 / 学年 / 出版社 / 版本后缀
NOISE_PATTERNS = [
    r"（解析版）|\(解析版\)|【解析版】", r"（含解析）|\(含解析\)",
    r"（Word练习）|\(Word练习\)|（Word同步练习）|\(Word练习\)",
    r"-?\d{4}-\d{4}学年[^）\s]*", r"-?\d{4}-\d{4}[^）\s]*",
    r"人教版[^）\s]*必修[一二]?(?:第[一二]册)?|苏教版[^）\s]*必修[一二]?(?:第[一二]册)?",
    r"人教2019必修[一二]?(?:第[一二]册)?",
    r"【[^】]{2,14}】",                 # 【学霸笔记】【上好课】【学而思】【好题汇编】
    r"（新教材）|\(新教材\)|\[新教材\]", r"必修第[一二]册", r"必修[一二]册",
    r"高一化学(?:人教版)?(?:必修[一二]?册?)?|高二化学(?:人教版)?[^）\s]*",
    r"同步备课系列|备战[^）\s]*|核心考点判断题|易错易混辨析",
    r"\（含解析\）|\(含解析\)|\（解析版\）|\(解析版\)",
    r"-?—\s*高一化学.*$|-?\s*—.*答案$",   # 去掉「—高一化学…」「-备战…」尾巴
    r"\s+",
]
# 主题过长时的**补充线索**（同名兜底）：从这些前缀里取更具体的说法
# 例：「第五章第二节 氮及其化合物——氨气（第二课时）课时作业答案」
#   剥噪后只剩「第五章第二节氮及其化合物」⇒ 用 NH3/铵盐/硝酸 等线索补全
SUBTOPIC_HINTS = [
    (r"硝酸的制备", "硝酸的制备"), (r"氨气", "氨气"), (r"铵盐", "铵盐"),
    (r"氮气与氮的固定|氮气与固定", "氮气与固定"), (r"硝酸[（(]第", "硝酸的性质"),
    (r"硝酸", "硝酸"),
    (r"二氧化硫|\+4价硫|4价硫", "二氧化硫"), (r"\+6价硫|6价硫|硫酸", "硫酸"),
    (r"0价硫", "单质硫"), (r"2价硫", "硫化氢"), (r"不同价硫", "价态转化"),
    (r"钠的氧化物|钠及钠的氧化物|过氧化钠", "钠的氧化物"),
    (r"碳酸钠|碳酸氢钠|两种重要的钠盐", "钠盐"),
    (r"铁、铝|铁铝", "铁铝"), (r"氯离子", "氯离子"), (r"氯气", "氯气"),
]
RE_KP = re.compile(r"^\|\s*\*\*(?:考点|重难点)\s*\d*\s*([^*|]+?)\*\*", re.M)
RE_LEAD_NUM = re.compile(r"^\d+(?:\.\d+)*\s*")
# 多元素专题（如「钠、氯及其化合物」「铁、铝及其化合物」）专用子类
MULTI_SUB = [
    (r"钠.{0,3}氯|氯.{0,3}钠", "01_元素专题", "NACL", "钠氯综合"),
    (r"铁.{0,3}铝|铝.{0,3}铁", "01_元素专题", "FEAL", "铁铝综合"),
    (r"硫.{0,3}氮|氮.{0,3}硫", "01_元素专题", "SNI", "硫氮综合"),
]
# 命名禁用的文件系统字符（顺带规避 Windows 保留名）
BAD_CHARS = re.compile(r'[\\/:*?"<>|]')


def strip_noise(title: str) -> str:
    t = title
    # ① 先剥「品牌/学年/出版社/版本」等噪声
    for p in NOISE_PATTERNS:
        t = re.sub(p, "", t)
    # ② 再剥「含解析/解析版/新教材」等**括号包裹**的后缀（整段删，不留残渣）
    for _ in range(3):
        t2 = re.sub(r"\(?[（(【\[]?\s*(含解析|解析版|新教材|Word练习|Word同步练习)\s*[）)】\]]?", "", t)
        if t2 == t:
            break
        t = t2
    t = t.strip(" ·-—－_|、，,。.")
    # ③ 清理空括号与孤立括号
    for _ in range(4):
        t2 = re.sub(r"[（(]\s*[-—－·,，]*\s*[）)]", "", t)
        if t2 == t:
            break
        t = t2
    t = re.sub(r"\s+", " ", t)
    return t.strip(" ·-—－_|、，,。.")


def is_question_bank(p: Path, src: Path):
    if p.suffix.lower() != ".md":
        return False, "not-md"
    rel = p.relative_to(src)
    if any(part in SKIP_DIRS or part.startswith(SKIP_DIR_PREFIX) for part in rel.parts):
        return False, "in-skip-dir"
    if len(rel.parts) == 1 and p.name in SKIP_ROOT_FILES:
        return False, "root-spec-doc"
    n = p.name
    if n in SKIP_EXACT or n.startswith(SKIP_PREFIX):
        return False, "process-file"
    try:
        txt = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False, "unreadable"
    if len(txt) < 1500:
        return False, "too-small(%d)" % len(txt)
    score = 0
    if "【答案】" in txt:
        score += 2
    if "【解析】" in txt or "【详解】" in txt:
        score += 2
    if RE_KP.search(txt):
        score += 1
    if re.search(r"^\s*\d+[．.]", txt, re.M):
        score += 1
    if "高考真题" in txt:
        score += 1
    # 「按题型归类」系列以「收录 N 道原题」标记，无【答案】但结构完整
    if re.search(r"收录\s*\d+\s*道原题", txt):
        score += 3
    return (score >= 3), "score=%d" % score


def title_of(txt: str, fallback: str) -> str:
    """取文件自身的标题行（跳过表格行/空行/注释行）。"""
    for ln in txt.splitlines()[:8]:
        s = ln.strip().lstrip("#").strip()
        if s and not s.startswith("|") and not s.startswith(">"):
            return s
    return fallback


def classify(stem: str, txt: str, rel: Path):
    """→ (主类, 子类, 类目码, 精简主题, 考点列表, 章节号或None)。"""
    kps = [k.strip() for k in RE_KP.findall(txt)[:12]]
    head = title_of(txt, stem)
    probe = " ".join([stem, head] + kps)

    # 章节同步练：形如「2.1 xxx」「5.2 氮及其化合物」
    m = RE_LEAD_NUM.match(stem) or RE_LEAD_NUM.match(head)
    chap = None
    if m:
        raw = m.group(0).strip()
        top = raw.split(".")[0]
        if top.isdigit() and int(top) <= 20:
            chap = raw

    topic = sanitize_topic(strip_noise(stem))
    if len(topic) < 2:
        topic = sanitize_topic(strip_noise(head))

    # 0) 「题型归类整理」目录：文件名前缀即题型序号，强制归入按题型归类
    if any(part == "题型归类整理" for part in rel.parts):
        if stem.startswith("00_"):
            return "02_题型专题", "按题型归类", "TYPED", "总览与组卷建议", kps, chap
        if RE_TYPED.match(stem):
            return "02_题型专题", "按题型归类", "TYPED", topic, kps, chap

    # 1) 多元素综合专题（须先于单元素判定，否则「钠、氯」会被 NA 抢走）
    #    仅当**两个元素都出现**且不是单元素主导（标题以某元素起头）时才判综合
    lead = strip_noise(stem)[:1] or strip_noise(head)[:1]
    for pat, main, code, sub in MULTI_SUB:
        if not re.search(pat, probe):
            continue
        # 单元素主导：标题首字即该类目元素 ⇒ 归单元素而非综合
        m2 = re.search(r"^(钠|氯|铁|铝|硫|氮)", lead)
        if m2 and re.match(r"^(钠|氯|铁|铝|硫|氮)[^、,，/]{0,6}(实验探究|计算|氧化还原|综合题)", probe):
            pass      # 明确是跨元素题型题，仍按综合处理
        elif m2:
            continue   # 纯单元素，归单元素分支
        return main, sub, code, topic, kps, chap

    # 2) 元素 / 题型专题
    for main, code, sub, pat in CAT_TREE:
        if re.search(pat, probe):
            return main, sub, code, topic, kps, chap

    # 3) 阶段检测 / 章节同步
    for main, code, pat in CAT_TREE_FALLBACK:
        if re.search(pat, probe):
            sub = ("第%s章" % chap.split(".")[0]) if (chap and code == "SYN") else sub_default(code)
            return main, sub, code, topic, kps, chap
    return "03_章节同步练", "未归类", "SYN", topic, kps, chap


def sanitize_topic(t: str, limit: int = 34) -> str:
    """去文件系统非法字符 + 清理空/孤立括号 + 截断时保证括号配平。"""
    t = BAD_CHARS.sub("", t)
    t = re.sub(r"\s+", " ", t)
    # 反复清理空括号（噪声剥离后可能残留「（）」「（）-」等）
    for _ in range(4):
        t2 = re.sub(r"[（(]\s*[-—－·,，]*\s*[）)]", "", t)
        if t2 == t:
            break
        t = t2
    # **先配平再截断**：噪声剥离常只删掉左括号留下右括号（如「……（第一章 …））」
    t = rebalance(t.strip(" ·-—－_|、，,。."))
    if len(t) > limit:
        cut = max(t.rfind(c, 0, limit + 1) for c in " ·-—－_|、，")
        t = (t[:cut] if cut >= limit // 2 else t[:limit]).strip(" ·-—－_|、，,。.")
        t = rebalance(t)
    return t.strip(" ·-—－_|、，,。.") or "未命名"


def rebalance(t: str) -> str:
    """括号配平：丢弃无左括号配对的右括号；末尾若缺右括号则补齐。"""
    out, depth = [], 0
    for ch in t:
        if ch in "（(":
            depth += 1
            out.append("（")
        elif ch in "）)":
            if depth == 0:
                continue          # 孤立右括号，丢弃
            depth -= 1
            out.append("）")
        else:
            out.append(ch)
    t = "".join(out)
    return t + "）" * depth      # 末尾补齐


def sub_default(code: str) -> str:
    return {"TEST": "各类检测卷", "SYN": "章节同步练"}.get(code, "未归类")


def collect(src: Path, skill_dir):
    qb, skipped = [], []
    for p in sorted(src.rglob("*.md")):
        try:
            rel = p.relative_to(src)
        except ValueError:
            continue
        if skill_dir is not None and (p == skill_dir or skill_dir in p.parents):
            skipped.append((rel, "this-skill"))
            continue
        ok, why = is_question_bank(p, src)
        (qb if ok else skipped).append((rel, why))
    return qb, skipped


def plan(qb):
    """规划目标路径；同类目码内按主题排序后编号，保证跨机稳定。"""
    buckets = {}
    for rel, _ in qb:
        txt = (SRC_ROOT / rel).read_text(encoding="utf-8")
        main, sub, code, topic, kps, chap = classify(rel.stem, txt, rel)
        buckets.setdefault((main, sub, code), []).append((rel, topic, kps, chap))
    out = []
    for (main, sub, code), items in sorted(buckets.items()):
        # ① 同一桶内若出现重名，用「原始名中的具体线索」消歧
        seen = Counter(t for _, t, _, _ in items)
        resolved = []
        for rel, topic, kps, chap in items:
            if seen[topic] > 1:
                hint = hint_topic(rel.stem)
                if hint and hint != topic:
                    topic = "%s·%s" % (topic, hint)
            resolved.append((rel, topic, kps, chap))
        items = resolved
        # ② 排序键：章节号在前（若有），否则按源路径保证稳定
        items.sort(key=lambda x: (x[3] is None, x[3] or "", x[0].as_posix()))
        for i, (rel, topic, kps, chap) in enumerate(items, 1):
            fname = "%s-%02d_%s.md" % (code, i, topic)
            out.append({"rel": rel, "dir": "%s/%s" % (main, sub),
                        "code": code, "seq": i, "topic": topic,
                        "fname": fname, "kps": kps, "chap": chap,
                        "orig": rel.stem})
    return out


def hint_topic(stem: str) -> str:
    """从原始名里找比通用主题更具体的线索（用于同桶重名消歧）。"""
    for pat, name in SUBTOPIC_HINTS:
        if re.search(pat, stem):
            return name
    return ""


def do_copy(plan_list):
    ncopy = nimg = 0
    for it in plan_list:
        src_md = SRC_ROOT / it["rel"]
        ddir = DEST / it["dir"] / it["fname"][:-3]
        ddir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_md, ddir / it["fname"])
        ncopy += 1
        refs = sorted(set(re.findall(r"!\[[^\]]*\]\(images/([^)]+)\)", src_md.read_text(encoding="utf-8"))))
        it["refs"] = refs
        src_img = src_md.parent / "images"
        if refs and src_img.is_dir():
            (ddir / "images").mkdir(exist_ok=True)
            for r in refs:
                s = src_img / r
                if s.is_file():
                    shutil.copy2(s, ddir / "images" / r)
                    nimg += 1
                else:
                    BROKEN.append("%s/%s :: images/%s (源缺失)" % (it["dir"], it["fname"], r))
    return ncopy, nimg


def do_verify(plan_list):
    broken = 0
    for it in plan_list:
        base = DEST / it["dir"] / it["fname"][:-3]
        md = base / it["fname"]
        if not md.is_file():
            print("MISSING_MD %s" % (it["dir"] + "/" + it["fname"]))
            broken += 1
            continue
        for r in sorted(set(re.findall(r"!\[[^\]]*\]\(images/([^)]+)\)",
                                       md.read_text(encoding="utf-8")))):
            if not (base / "images" / r).is_file():
                print("BROKEN %s :: images/%s" % (it["dir"], r))
                broken += 1
    return broken


def write_index(plan_list, stats):
    DEST.mkdir(parents=True, exist_ok=True)
    man = []
    for it in plan_list:
        base = DEST / it["dir"] / it["fname"][:-3]
        md = base / it["fname"]
        man.append({
            "类目码": it["code"], "分类": it["dir"], "题名": it["fname"][:-3],
            "精简主题": it["topic"], "章节号": it["chap"] or "",
            "考点": it["kps"][:6], "图片数": len(it.get("refs", [])),
            "大小KB": round(md.stat().st_size / 1024, 1) if md.is_file() else 0,
            "原始文件名": it["orig"], "源相对路径": it["rel"].as_posix(),
        })
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1),
                        encoding="utf-8", newline="\n")

    tree = {}
    for m in man:
        tree.setdefault(m["分类"], {}).setdefault(m["类目码"], []).append(m)
    L = ["# 题库索引", "",
         "> 由 `_题库_sync.py` 自动生成，**勿手改**。命名规则：`<类目码>-<两位序号>_<精简主题>.md`；",
         "> 正文逐字节取自原始交付件（已过机审 `FAILS: 无`），原始文件名见 `题库清单.json`。", "",
         "共 **%d** 份题库 / **%d** 张配图，按四层归类。" % (len(man), stats["img"]), ""]
    L += ["## 类目码对照", "",
          "| 码 | 主类 › 子类 | 份数 |", "|---|---|---|"]
    seen = {}
    for m in man:
        k = (m["类目码"], m["分类"])
        seen[k] = seen.get(k, 0) + 1
    for (code, cat), n in sorted(seen.items()):
        L.append("| `%s` | %s | %d |" % (code, cat.replace("/", " › "), n))
    tot_img = sum(m["图片数"] for m in man)
    L.append("")
    L.append("合计 **%d** 份 / **%d** 处图片引用。" % (len(man), tot_img))
    L.append("")
    for cat in sorted(tree):
        L += ["## %s（%d）" % (cat.replace("/", " › "), sum(len(v) for v in tree[cat].values())), ""]
        for code in sorted(tree[cat]):
            L += ["### `%s`（%d）" % (code, len(tree[cat][code])), "",
                  "| 文件 | 规模 | 考点 |", "|---|---|---|"]
            for m in sorted(tree[cat][code], key=lambda x: x["题名"]):
                kp = "、".join(m["考点"][:4]) if m["考点"] else "—"
                L.append("| [%s](%s/%s/%s.md) | %.1f KB ｜ %d 图 | %s |"
                         % (m["题名"], cat, m["题名"], m["题名"], m["大小KB"], m["图片数"], kp))
            L.append("")
    (DEST / "README.md").write_text("\n".join(L), encoding="utf-8", newline="\n")


SRC_ROOT = None
BROKEN = []


def main():
    global SRC_ROOT, BROKEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    src = Path(a.src)
    if not src.is_dir():
        sys.stderr.write("BAD --src: not a directory\n")
        return 2
    SRC_ROOT = src
    skill_dir = next((d for d in src.iterdir() if d.is_dir() and d.name == "试题提取skill"), None)

    qb, skipped = collect(src, skill_dir)
    plan_list = plan(qb)

    if a.reset and DEST.exists() and not a.verify:
        shutil.rmtree(DEST)

    lines = ["== _题库_sync ==", "src: %s" % src, "time: %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
             "question_bank=%d skipped=%d" % (len(qb), len(skipped)),
             "plan: " + ("dry-run" if a.dry_run else ("verify" if a.verify else "copy")), ""]
    for it in plan_list:
        lines.append("%-52s -> %-28s %s" % (it["rel"].as_posix()[:52], it["dir"], it["fname"]))

    ncopy = nimg = 0
    if a.verify:
        broken = do_verify(plan_list)
        lines += ["", "verify_broken=%d" % broken]
    elif a.dry_run:
        for it in plan_list:
            it["refs"] = sorted(set(re.findall(r"!\[[^\]]*\]\(images/([^)]+)\)",
                                            (src / it["rel"]).read_text(encoding="utf-8"))))
            nimg += len(it["refs"])
    else:
        ncopy, nimg = do_copy(plan_list)
        write_index(plan_list, {"img": nimg})
        lines += ["", "copied_md=%d copied_img=%d broken=%d" % (ncopy, nimg, len(BROKEN))]

    lines.append("")
    if not a.verify:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("\n".join(lines), encoding="utf-8", newline="\n")

    print("SRC=%s" % src)
    print("QB=%d SKIPPED=%d PLAN=%d COPIED_MD=%d COPIED_IMG=%d BROKEN=%d"
          % (len(qb), len(skipped), len(plan_list), ncopy, nimg,
             len(BROKEN) if not a.verify else broken))
    print("DETAIL=_题库/_迁移报告.txt")
    return 1 if (BROKEN or (a.verify and broken)) else 0


if __name__ == "__main__":
    sys.exit(main())