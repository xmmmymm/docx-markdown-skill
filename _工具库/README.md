# _工具库 · 化学试题 docx→Markdown 提取 skill 流水线脚本

> **来源**：2026-09-19 全量移植自氮批次终态 `_工具库\`（钠→氯/硫→氮 四批工程收官沉淀，U1–U142 经验体系）。
> **基线**：`extract_content.py` = 氮批领先版（MD5 前 8 `BF0DFA64`，含 4 处 EQ 域超集分支）；其余 CORE 与四批共识终值一致。
> **本 skill 改动**（相对氮批母本，均已登记入 `_skill经验归档.md`）：
> ① 按件常量全部清空/参数化（make_md/make_skeleton/audit/copy_images/check_blank/zoom_img/render_ole_fig）；
> ② `DOCNAME`/成品 md 名改自动推导（= 输出目录名，与 `fix_fullwidth.py` 同口径）；
> ③ `_n_*` 脚本改名 `_sk_*`；`_templates\` 驱动模板改三要素（输入夹/输出根/当前件 stem）；
> ④ 合并 9 条历史待合并项（逐条见归档「建库轮」）。
> **用法**：每处理一个新 docx，先把本目录 `*.py` 拷进 `<输出目录>\work\`，再按「最小改动清单」改常量。
> **开工第 0 步（新）**：输入夹「提取信息表」——`<py> _sk_info.py check` 判「表有无／缺项／新增件」；
> 无表或缺必填 ⇒ **agent 停下询问用户**（输出根目录必填）→ `init` 生成骨架 → 填值 → `sync` 入库；
> 有表且齐全 ⇒ **直接按表复读开工（不再重填）**，`sync` 自动把新出现的 docx 入队并播报。
> **回写**：改进了**通用**逻辑须回写本目录 + 在 `..\_skill经验归档.md` 记「工具库改动」并过 U35 回归。

---

## 〇、执行模式（子代理自动处理）

S1–S8 由**团队模式子代理**执行；主代理只做判定/派发/S9 验收/S10 回写。

| 角色 | 谁 | 权限要点 |
|---|---|---|
| 协调者 | **主代理** | 唯一有权写 `_skill*.md` 与本目录；跑 S9–S10；播报后停下等确认 |
| 执行者 | **团队模式子代理**（每件一个） | `execute_command` + `write_to_file` 齐全；只写本件 `<输出目录>\` |

**派发写法（关键）**：

```
Task(
  subagent_name = "code-explorer",
  name          = "sk-doc<件号>-<件名简写>",   # 有 name 才进入团队模式（异步）
  team_name     = "sk-batch",
  mode          = "acceptEdits",              # 免逐次确认，才能无人值守跑脚本
  max_turns     = 300,
  prompt        = "<按《_skill规划.md》派发协议 6 要素自包含>"
)
```

**反面用法**：`Task(subagent_name="code-explorer")` 不带 `name` → 内置**只读**子代理（仅 5 个检索工具），**跑不了任何脚本**（U26）。

**派发前**：主代理跑 `_templates\_sk93_setup_s0.py`（一条命令完成：建输出目录 + 拷全套脚本进 `work\` + 解包 + S0 普查，见 `_templates\README.md`）。

---

## 一、脚本职责（27 CORE + skill 专属）

| 脚本 | 职责 | 是否需按文档改 |
|---|---|---|
| `s1_unpack.py` | **S1 解包**：docx → `work/unpacked/`，统计 media/embeddings/xml/rels，写 `s1_unpack_meta.json`。用法 `python s1_unpack.py <docx 绝对路径>` | 不用改 |
| `extract_content.py` | 解包内容 → `content_stream.txt` + `content_meta.json`。含：EQ 域状态机（跨 run、域栈、嵌套 `\o`、主槽箭头/线状槽分支）、跳过 `mc:Fallback`、下探 `w:txbxContent`、`w:cr` 段内换行、纯空白 script run 处置（U53）、`w:numPr`（`NUM_AUTO_NUMBER` 默认 False）、OMML 段落级内联（需同目录 `omml_render.py`）、`w:pict` 内嵌 `o:OLEObject`（U128，建库已并入） | 一般不用改 |
| `mtef_render.py` | MathType **MTEF5 二进制解析**，逐对象字节零剩余校验；输出 `mtef/formula_map.json` 等。UBAR/OBAR 条件等号；`PUA_MAP` 含 `0xEF01/0xEF04/0xEF05`（建库已并入③） | 一般不用改 |
| `omml_render.py` | **Word 原生公式（OMML）→ 线性化学文本**：条件等号 6 形态、`m:eqArr`/`m:limUpp` 双槽合并 `=(A、B)=`（建库已并入②）、`m:f`→`(a)/(b)`、`m:m` 矩阵、先下后上 | 一般不用改 |
| `prep_images.py` | 所有 media 铺白底 + 小图放大 3× → `work/imgview/` | 不用改 |
| `check_blank.py` | **像素级**空白图判定（暗像素计数）。**skill 版**：默认遍历 media 全部位图；或命令行传文件名（ASCII） | 不用改（可选传名） |
| `make_skeleton.py` | `⟨OLE:x⟩→公式文本`、`⟨IMG:x⟩→⟨FIG⟩/删除/文字`、`⟨S⟩/⟨P⟩→Unicode 上下标`；零残留校验 | 改 `IMG_DROP`/`IMG_TEXT`/`IMG_TEXT_SEQ`/`OLE_FIG`（skill 版已清空） |
| `normalize.py` | 排版修正共享模块（`STR_FIXES`+`RE_FIXES`，`make_md`/`audit` 共用）；题号规则次序已修（⑥）、系数空格口径已对称（⑨） | 按文档增删下标项（先长后短） |
| `make_md.py` | `skeleton.txt` → 成品 md：封面合并、`in_ans` 引用状态机、`ans_sec` 答案区状态机、选项引用块、管状表 | **skill 版 `DOCNAME` 自动推导**（仅特殊名才覆盖）+ 必要时 `COVER_*` |
| `copy_images.py` | 保留图 → `images/`（透明底合成白底；`DERIVED`；游离 media 校验自动推导） | 改 `KEEP`/`DERIVED`（已清空）；`MD` 已自动推导 |
| `audit.py` | 机审 **10 项**（占位符零残留/题号==答案/表格/图片三一致/内容保持/引用块/行尾离子/守恒/空格三态/符号旁单空格） | `ANS_DIFF`/`ANS_NOTE`（`DOCNAME` 已自动推导） |
| `fix_fullwidth.py` | 交付件全角清零复核（`＋ ／ ＝ ═ •`），幂等；收尾必跑 | 不用改 |
| `render_ole_fig.py` | 非 MathType OLE 高分辨率重渲染：**skill 版参数化**（argv[1]=WMF stem）→ `work/olefig/<stem>.png` | 不用改（传 stem） |
| `zoom_img.py` | 装置图局部放大（**skill 版**：按件填 `JOBS`） | 改 `JOBS`（已清空） |
| `zoom_profile.py` | 低分辨率图**像素剖面**（箭头指向客观判定）；**仅小图适用，≥1000px 禁用**（U43/U73） | 不用改 |
| `list_docx.py` | 逐字列目录内 docx 精确名 → `docx_list.json`（建队列用；界面显示分不清连续空格/U+3000，**建目录前必跑**） | 不用改 |
| `probe_*`（10 个） | 载体三连判（`probe_omml`/`probe_special`/`probe_ole`）、下标损坏筛查（`probe_fix2`）、自动编号（`probe_numpr`）、字符普查（`probe_chars`）、页眉页脚（`probe_hf`）、元素树（`probe_tree`）等 | 不用改 |
| `inspect_xml.py` / `dump_para.py` / `dump_wmf2.py` | XML 上下文 / 段落 token 序列 / 小 WMF 内容判定（**渲染全白的小 WMF 先跑它再判**，U15） | 不用改 |

### skill 专属脚本

| 脚本 | 职责 | 用法 |
|---|---|---|
| `_sk_info.py` | **输入夹「提取信息表」读写与同步**（开工第 0 步）：表＝`<输入夹>\_提取信息.md`（Markdown 表格，人可读可手改），固化 **skill 位置／输出根目录／批次名／特殊约定／逐件进度** ⇒ 该文件夹后续在新对话中**无需重填**（缺项才补问） | `<py> _sk_info.py check`（exit 0=可开工／3=无表须 init+询问／4=缺必填须补问／6=表解析异常已拒写）<br>`init`（生成骨架）／`sync`（新增件自动入队＋刷新 `_target.txt` 前两行＋写队列）／`status --index N --set done` |
| `scan_input.py` | **扫描输入夹第一层 .docx → 生成批次队列 json**（`queue/stem/src_abs/out_abs/size`，逐字照抄文件名；`.doc` 等报告跳过）；函数 `scan()` 供 `_sk_info.py` 复用（队列口径单一真源） | `<py> scan_input.py`（三要素读 `_target.txt`；详见 `_templates\README.md`） |
| `_sk_balance.py` | S9 独立守恒复算（U64/U91 三桶归因；变量水合物/方括号配位已并入⑧）；**须核退出码=0**（U119；2=路径不存在） | `<py> _sk_balance.py "<成品 md 路径>"` |
| `_sk_imgprep.py` | **反循环 1/3 · 判图卡片**：每图压成 2–3 KB 文本卡片（尺寸/暗像素/空白判定/84×30 ASCII 网格/16×16 签名 + 同图聚类）→ `work\_imgcards\`；含 U133 透明底先合成白底。**源目录无图 ⇒ exit 2**（防「S1 未跑」被当成「本文档无图」） | `<py> _sk_imgprep.py "<输出目录>" --grid 84x30` |
| `_sk_watchdog.py` | **反循环 3/3 · 看门狗**：磁盘增长轮询，零增长/污染源/单图自旋 ⇒ `STALLED`（退出码 3）；污染判据**前缀/后缀精确匹配** | `<py> _sk_watchdog.py "<输出目录>" --interval 120 --times 40 --stall 4` |
| `_sk0_baseline.py` | **基线漂移检测**：与 `..\_基线指纹.json` 比对全部 CORE 脚本 MD5（防手滑改坏；改 CORE 须登记指纹） | `<py> _sk0_baseline.py`（开工/收尾各一次） |

> 反循环三件套（U85–U87）：① 判图卡片（先机器后人工）② 进度契约（`figure_desc.md` 每判 1 张 append 1 行，写进派发指令）③ 看门狗（主代理按磁盘事实判停摆）。**`STALLED` 是"值得核查"信号而非换棒指令**（U95）。

## 二、标准调用顺序（S1–S8，子代理执行）

```powershell
$py = "<venv>\python.exe"
Set-Location "<输出目录>\work"
& $py s1_unpack.py "<源 docx 绝对路径>"      # S1
& $py extract_content.py                      # S2（判据: eqraw 为空）
& $py probe_fix2.py ; & $py probe_special.py ; & $py probe_ole.py
& $py mtef_render.py                          # S3（零 OLE 件空跑，不是"不适用" U75）
& $py prep_images.py ; & $py check_blank.py   # S4
& $py make_skeleton.py                        # S5（零残留）
& $py make_md.py                              # S6
& $py copy_images.py                          # S7
& $py audit.py                                # S8（FAILS 必须为「无」）
& $py fix_fullwidth.py                        # 收尾（幂等）
```

> stdout 只打 ASCII 摘要（GBK 终端会吞中文/抛 `UnicodeEncodeError`）；中文判定一律 Read 落盘文件。
> WMF→PNG/PDF：`"C:\Program Files\LibreOffice\program\soffice.exe" --headless --convert-to png --outdir <目录> *.wmf`（**outdir 须先存在**；`--convert-to txt` 本环境 exit=1 不可用，U141）。

## 三、移植到新文档的最小改动清单

0. 反循环三件套先就位：S4 前跑 `_sk_imgprep.py`；派发指令写入进度契约；主代理后台起看门狗；
1. `make_skeleton.py`：`IMG_DROP`/`IMG_TEXT`/`IMG_TEXT_SEQ`/`OLE_FIG`（按 `figure_desc.md` 判定填写）；
2. `copy_images.py`：`KEEP`/`DERIVED`（`orphans` 自动推导，勿手列）；
3. `normalize.py`：`STR_FIXES` 增该件下标损坏项（先长后短）；
4. `audit.py`：`ANS_DIFF`/`ANS_NOTE`（`DOCNAME` 已自动推导）；
5. `work/figure_desc.md`：保留图逐张描述 + 删除/转文字/游离清单。

## 四、几条易踩的通用坑（历轮实证，完整版见 `_skill经验归档.md` U 清单）

- **零残留判定禁用 `search_content`/`search_file`**（中文/双空格路径静默返回 0 假阴性，U27）→ Python 计数落盘或 Read；
- **命令行不直传中文路径**（GBK 转码损坏 argv，U93）→ 走 `_templates\` ASCII 驱动脚本 + `_target.txt`；
- **`〔图：…〕` 描述内不得出现机审残留词**（`oleObject`/`⟨`/`＋` 等，U25）；
- **载体五形态不可按同族外推**（U49）：每件必跑三连判 `probe_omml`+`probe_special`+`probe_ole`；
- **同图判定不可只靠 md5**（U68）；**低分辨率方向性结论须 `zoom_profile.py` 像素剖面**（U39）；
- **回改已交付件**：改源头脚本 → 重跑 S5–S8 → 复跑 `audit.py` 至 `FAILS: 无`（U28/U40）。

## 五、改库后的体检（一条命令）

```powershell
<py> ..\_chk_selftest.py        # exit 0 = 全绿；6 项：编译/基线/提示词一致/脱敏/守恒冒烟/信息表往返
<py> _sk0_baseline.py --write   # 改了 CORE 或新增脚本后重登记指纹（新增脚本也算漂移，U190）
```

> **进度回填已根治（U190）**：`_sk_info.py sync` 现在把 `status`/`done_date`/`counts`
> 三列**一律从信息表复读**写进 `queue.json`，并保留 `_target.txt` 第 3 行（当前件 stem）。
> 历史教训 U164/U168/U177 描述的"每次 sync 清空进度、须另跑按件回填脚本"**不再复现**。
> 另：写表前有**守恒守卫**（解析行数 ≠ 原文像数据行的行数 ⇒ 拒绝改写并 exit 6）
> 与 `.bak` 首次备份，防止备注里混入 `|` 等导致整表被残缺重写。
