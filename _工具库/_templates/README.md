# _templates · U93 ASCII 驱动脚本模板（skill 三要素版）

**为什么需要**：命令行（Git Bash / 从 bash 侧调 `powershell -Command`）直传中文路径 argv 会被 GBK 转码损坏 →
脚本收到乱码、`FileNotFoundError`、`exit=1`，极易误判为脚本缺陷（U93）。
中文路径**只能待在 UTF-8 源文件里**，由 Python 自己读取。

## 三要素 `_target.txt`（每件开工前更新）

```
# 注释行
<第 1 行> 输入文件夹绝对路径（docx 所在）
<第 2 行> 输出根目录绝对路径（成品落 <输出根>\<stem>\）
<第 3 行> 当前件 stem（docx 名去 .docx，逐字照抄队列 json 的 stem，勿手敲）
```

- 取值器：`_sk93_target.py`（`in_root()/out_root()/stem()/out()/work()/docx()/tool()/skillroot()`）；
  环境变量 `SKILL_TARGET`（三要素按 TAB 分隔）可整体覆盖。
- 更新 `_target.txt` 的正规方式：**主代理用 write_to_file 直接写**（或派发指令中给出 3 行内容让子代理写）；
  队列 json 里的 stem 是唯一真源。

## 模板一览（用法：在 `_templates` 目录内 `& $py <模板名>`，命令行全 ASCII）

| 模板 | 作用 | 对应阶段 |
|---|---|---|
| `_sk93_target.py` | 三要素共用取值器 | — |
| **`_sk93_setup_s0.py`** | **开工一步到位**：建 `<输出根>\<stem>\work` + 拷 `_工具库\*.py` 全套进 `work\`（已存在不覆盖）+ 放普查模板 + 解包 docx + 跑普查 | S1 + S0 |
| `_s0_census.py` | 通用 **S0 普查模板 v2**（自定位 `ROOT=work\`）：载体三连判、域数按 `fldChar begin`、`vertAlign`/Unicode 双判、空白码位、题号/答案区形态、media 尺寸档位、OLE ProgID | S0 |
| `_sk93_driver_s1unpack_census.py` | 解包 + 跑普查（被 setup_s0 复用） | S1 + S0 |
| `_sk93_imgprep.py` | 生成 `work\_imgcards\` 判图卡片（优先用件内 work 副本） | S4 前 |
| `_sk93_watchdog.py` | 后台看门狗，**默认 `--interval 120 --times 40 --stall 4`**（宽限须覆盖子代理只读启动阶段，U95①） | S4–S8 |
| `_sk93_s9check.py` | S9 零成本自检：污染扫描 / 图片三一致 / 引用行 / 题号—答案计数 / U94 两查 / audit 首行 / `_sk_balance.py` 复算（核退出码） | S9 |
| `_sk93_rerun_s5s8.py` | 改源头后重跑 `make_skeleton→make_md→copy_images→audit→fix_fullwidth` | S9-iter |
| `_sk12_pages.py` | docx→pdf→300dpi 整页派生（浮动对象定位，U129） | S9 |
| `_sk12_layout.py` | 整页 bbox + 邻近 words 定格（U129） | S9 |
| `_sk12_fdcheck.py` | `figure_desc.md` 与成品图述交叉核对 | S9 |
| `_sk12_p2p5.py` / `_sk12_p2raw.py` | 整页 PDF 文本层抽取（内容交叉核对，U141） | S9 |
| `_sk7_genprompt.py` | 从 `_skill规划.md` 提示词节自动抽取生成 `..\_启动提示词.md`（防两版漂移） | 收尾 |

**注意**：`subprocess.run([PY, script, 中文路径])` **列表参数不经 shell**，不受 U93 影响；
受影响的只有"在命令行里手打中文参数"。输出仍须纯 ASCII（U90）。
