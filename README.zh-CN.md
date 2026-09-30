# OmniTrans — 全引擎游戏自动机翻汉化

[English](README.md) | **简体中文**

一键游戏汉化：把游戏目录拖进来——RPG Maker MV/MZ、VX Ace/VX/XP、SRPG Studio、
Kirikiri、Ren'Py、TyranoScript、Unity——自动识别引擎，提取文本 → 机翻 → 回写，
全程自动备份（Kirikiri/Ren'Py 为非破坏覆盖补丁）。也支持直接翻译 MTool 导出的
`ManualTransFile.json`。默认走内置免费端点（公开、无需密钥、不审查内容），也可在
界面里填入**你自己的 DeepL/LLM 翻译接口**（保存在本机 `.env`，绝不入库）。

> [MTool](https://mtool.app/) —— 本项目最初为之打造的翻译工具（其 JSON 格式是
> 起点之一，非开源，官网 mtool.app）；后来的全引擎独立支持让工具长过了旧名字。

已在 7 万+条游戏文本上实弹验证。

## 下载

到 [**Releases**](https://github.com/luckyfun10086/OmniTrans/releases) 页面下载 `OmniTrans.exe`
——Windows 独立可执行文件，无需安装 Python。`.env`、`names.txt`、`mt_work/` 全部生成在
exe 同目录。

## 隐私与安全设计

- **代码零密钥**：仓库中不含任何 API Key、个人路径
- **个人配置隔离**：接口 URL / Key / 请求头保存在 `.env`（`.gitignore` 已排除）
- **本地数据隔离**：`mt_work/` 工作目录、`names.txt` 人名表、`ManualTransFile*.json`
  游戏文本全部被 `.gitignore` 排除——你的游戏内容和专有名词不会上传
- 上传仓库前建议检查：`git status` 不应看到 `.env` / `mt_work/` / 任何 json 文本

## 翻译接口（机翻 / AI 翻译两类）

在 GUI「翻译接口」栏选择 **Type（接口类型）**，填好信息后「保存到 .env」。

### 类型一：机翻（`MT · GET` 模板）

GET 模板端点，URL 用 `{sl}`（源语言）`{tl}`（目标语言）`{q}`（原文）占位符：

```
https://api.example.com/translate?source={sl}&target={tl}&text={q}
```

支持 / 实测过的接口：

| 服务 | 用法 |
|------|------|
| **内置免费端点**（谷歌） | 保持默认 URL 即可——无需 Key，批量 8 条/请求，基础质量 |
| **LibreTranslate**（自建/公共） | `https://libretranslate.com/translate?q={q}&source={sl}&target={tl}`，Key 填请求头 `X-api-key` |
| **MyMemory** | `https://api.mymemory.translated.net/get?q={q}&langpair={sl}|{tl}` |
| **DeepLX**（自建 DeepL 代理） | `http://localhost:1188/translate?text={q}&source_lang={sl}&target_lang={tl}` |
| 其它任意 GET 接口 | 按占位符拼 URL 即可；响应格式自动识别（谷歌列表 / `translations[]` / `translatedText` / 纯文本） |

### 类型二：AI 翻译（`AI · OpenAI` 兼容）

OpenAI 兼容的 **chat/completions** 端点（POST + JSON）。填完整 URL、API Key 和
模型名——质量远超机翻，按量计费：

| 服务 | URL | 模型示例 |
|------|-----|----------|
| **DeepSeek** | `https://api.deepseek.com/chat/completions` | `deepseek-chat` |
| **OpenAI** | `https://api.openai.com/v1/chat/completions` | `gpt-4o-mini` |
| **Kimi（月之暗面）** | `https://api.moonshot.cn/v1/chat/completions` | `moonshot-v1-8k` |
| **智谱 GLM** | `https://open.bigmodel.cn/api/paas/v4/chat/completions` | `glm-4-flash` |
| **OpenRouter**（Claude/Gemini/…） | `https://openrouter.ai/api/v1/chat/completions` | `anthropic/claude-3.5-haiku` |
| **Gemini**（OpenAI 兼容入口） | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` | `gemini-2.0-flash` |
| **Ollama**（本地部署，免 Key） | `http://localhost:11434/v1/chat/completions` | `qwen2.5:7b` |

**错误提示与敏感词兜底**：接口问题按三类给出清晰双语提示——**致命**（401 Key
无效 / 402 余额配额不足 / 404 模型名错误：立即弹窗终止，不再白白重试）；**跳过**
（内容被服务方安全策略拦截/敏感词）；**重试**（429 限流 / 网络抖动：自动退避）。
被拦截的条目会自动**改用内置免费机翻端点重译**（免费端点不审查内容）——质量不如
AI 但好过留英文，结束汇总里报告兜底条数。`.env` 里 `MT_FALLBACK=0` 可关闭。

等价的 `.env` 写法见 [`.env.example`](.env.example)。

> **质量与使用须知**：内置免费端点为基础机翻质量——看懂剧情足够，追求文采不行；
> 想要更好效果，请在下方接口栏配置 DeepL/LLM 端点。免费端点为非官方接口，随时
> 可能变更或限流；届时换任意自定义接口即可继续使用。请仅翻译你有权使用的内容。

## 上位机（推荐）—— 三大功能分区

界面按标签页分区：

1. **⚡ 快速翻译** —— 顶部选 **源语言 → 目标语言**，把 MTool 导出的 json（或任意
   `*_extracted.json`）拖进窗口，点「开始」：① 清洗掩码 → ② 机翻（进度条+速度+剩余时间）→
   ③ 回填校验
2. **🎮 游戏汉化** —— 把 **游戏目录 / EXE** 拖到窗口任意位置：自动识别引擎（显示引擎徽章），
   引导式流程 ② 提取文本 → ③ 开始翻译 → ④ 导入游戏；底部表格实时列出全部引擎支持状态
3. **⚙ 设置** —— 翻译接口配置（保存在本机 `.env`）

翻译完成后自动询问是否导入游戏并跳回游戏页。随时可取消，断点续翻。

校验失败的条目自动进入分段扫尾重翻（记号绝不可能丢）。exe 版拖拽开箱即用；
源码运行需 `pip install tkinterdnd2`（未装时自动退化为点选文件）。

> 重新打包：`pip install pyinstaller && python -m PyInstaller --onefile --windowed --name OmniTrans --collect-all tkinterdnd2 --collect-all sv_ttk mt_gui.py`

输出：输入文件同目录 `xxx_translated.json`（键=英文原文精确匹配，MTool 可直接用）。

## 人名保护

### names.txt（可选，永远优先）

一行一个词条，两种写法：

```
Alice=爱丽丝       掩码后还原成中文译名（推荐）
Wonderland=仙境
Bob               不写 = 号则保持英文原样
```

掩码词不经过机翻——**绝不会被乱译**，`=译名` 形式保证全篇统一。

### 自动人名识别（零配置，按语言分治，可关闭）

不写 names.txt 也行，工具按源语言自动识别专有名词并保持全文一致：

| 源语言 | 识别方法 | 说明 |
|--------|----------|------|
| 英语等拉丁文字 | 大小写形态统计 + 内置高频词库 | 人名几乎总是首字母大写、从不小写；普通词混现自动排除，thanks/doctor 等习惯大写词由词库滤掉 |
| **日语** | 片假名串重复检测 | 日式游戏人名几乎全是片假名（アリス、リチャード），这是硬特征；附带游戏术语停用表（ダメージ/スキル 等不误判） |
| 俄语等变格语言 | 大写前缀聚类 | 同一人名的各变格（Алиса/Алису/Алисе）聚为一簇，取最常见词形 |
| 中文/韩文 | 不自动识别 | 无大小写/假名特征，日志会提示改用 names.txt |

运行日志会列出识别到的词及出现次数，全程透明可复核。
**不想要这个行为？** GUI 顶部取消勾选「自动识别人名并保持一致」（随「保存到 .env」
持久化）；命令行用 `--no-auto-names` 或 `.env` 里 `MT_AUTO_NAMES=0`。关闭后人名按
普通文本交由机翻（更自然的译名，但一致性不保证），names.txt 人工词条在任何模式下都生效。

## 独立 RPG Maker 提取（无需 MTool）

**支持的引擎：**

| 引擎 | 数据位置 | 支持状态 |
|------|----------|----------|
| RPG Maker **MZ** | `data/` | ✅ 完整支持 |
| RPG Maker **MV** | `www/data/`（部分发行版在 `data/`） | ✅ 完整支持 |
| **RPG Maker VX Ace / VX / XP** | `Data/*.rvdata2`（VX `.rvdata` / XP `.rxdata`） | ✅ 完整支持——纯 Python Ruby Marshal 4.8 编解码器，字节级还原 |
| **SRPG Studio** | `data.dts`（配 `runtime.rts`/`environment.evs`） | ✅ 完整支持（桥接 [SRPG-ToolBox](https://github.com/Sinflower/SRPG-ToolBox)，首次运行自动下载其命令行工具，MIT 开源） |
| **Kirikiri / KAG**（.xp3） | `data.xp3` + `patch*.xp3` | ✅ 完整支持——按挂载顺序解析全部封包；回写为**非破坏覆盖补丁** |
| **Ren'Py**（6.99+/7/8） | `game/*.rpa`、`game/*.rpyc` | ✅ 完整支持——生成官方 `game/tl/<语言>/` 翻译包（非破坏） |
| **TyranoScript** | `data/scenario/*.ks` | ✅ 完整支持 |
| **Unity**（TextAsset 剧本 / MonoBehaviour 内嵌文本 / Addressables・Localization 字符串表 Bundle） | `*_Data` + `StreamingAssets/**/*.bundle` | ✅ 支持（依赖 UnityPy，`pip install UnityPy`；不支持编译进 DLL 的字符串） |

可识别但暂不支持：SiglusEngine（Key 社）、AliceSoft（.ain）、ExHIBIT、
Wolf RPG、NScripter——拖入即提示引擎名称与替代方案。

MV/MZ 的全部游戏文本都是明文 JSON（`Map*.json`、`CommonEvents.json`、
`Troops.json` 等），OmniTrans 直接读写，全程无需第三方工具。

```
python rpg_extract.py <游戏目录>      # → game.extracted.json
python mt_clean.py game.extracted.json  # ① 掩码
python mt_translate.py                  # ② 机翻（断点可续）
python mt_apply.py game.extracted.json  # ③ 还原 → game.extracted_translated.json
python rpg_apply.py <游戏目录> game.extracted_translated.json   # 回写游戏
```

提取范围：对话（401，连续行自动合并成整段，翻译质量更好）、滚动文本（405）、
选项（102）、角色改名（320/324）、地图显示名 —— 覆盖 `Map*.json`、
`CommonEvents.json`、`Troops.json`。

安全机制：回写前自动备份原文件到 `data_backup/`；只替换完全匹配的文本块；
译文行数与原文不齐的一律跳过保持原文——**坏翻译绝不会损坏游戏**。

### RPG Maker VX Ace / VX / XP 游戏

`.rvdata2` 是 Ruby Marshal 4.8 二进制序列化。OmniTrans 自带纯 Python 零依赖的
Marshal 编解码器（`rvdata.py`），读写**字节级还原**——经手工构造的规范字节串、
300 轮随机树模糊测试、与 `rubymarshal` 库的双向交叉验证。

```
python rva_extract.py <游戏目录>     # 对话/选项/改名/地图名/技能·物品文本
python mt_clean.py <游戏名>_extracted.json && python mt_translate.py && python mt_apply.py <游戏名>_extracted.json
python rva_apply.py <游戏目录> <游戏名>_extracted_translated.json
```

安全机制：只替换完全匹配的文本块（行数不齐保持原文）；`Scripts`/`System` 永不触碰；
改动文件备份到 `Data_backup/`；写回前重新解析校验 + 临时文件原子替换；译文就地修改
字符串节点——Marshal 链接表/符号表永不失效。

### Kirikiri（吉里吉里）游戏 —— ADV 视觉小说

全部 `*.xp3` 按挂载顺序解析（后挂载覆盖先挂载——`data.xp3` → `patch001.xp3` → …），
支持 v1/v2 头、二级索引、zlib 与 raw 索引，以及三种不同打包器布局（真实游戏实测）。
KAG `.ks` 剧本（CP932 / UTF-16LE / UTF-8）逐行提取：`[标签]` 外文本，跳过注释、
标签行、`@` 命令与内嵌 TJS（`iscript`/`macro`）块。

```
python krkr_extract.py <游戏目录>    # → <游戏名>_extracted.json（真实游戏 44,296 段实测）
python mt_clean.py <游戏名>_extracted.json && python mt_translate.py && python mt_apply.py <游戏名>_extracted.json
python krkr_apply.py <游戏目录> <游戏名>_extracted_translated.json
```

回写**非破坏**：只有改动的 `.ks` 打成 `patch_zz_omnitrans.xp3`（最后挂载、覆盖原文件），
删除该文件即卸载汉化。CP932 脚本装不下中文时自动升级为 UTF-16LE+BOM
（`--keep-enc` 改为跳过该文件）。

### Ren'Py 游戏

读取 `.rpa` 封包（RPA-2.0/3.0）与 `.rpyc` 字节码（Ren'Py 6.99+/7/8 的 RPC2 格式），
受限 Unpickler 绝不执行任意代码。对话取自 `TranslateSay`/`Say` 节点（**引擎自带的
翻译标识符**），菜单选项与 `_()` 界面字符串一并收集。

```
python renpy_extract.py <游戏目录>   # → <游戏名>_extracted.json
python mt_clean.py <游戏名>_extracted.json && python mt_translate.py && python mt_apply.py <游戏名>_extracted.json
python renpy_apply.py <游戏目录> <游戏名>_extracted_translated.json [语言名]
```

`renpy_apply.py` 生成**官方格式翻译包** `game/tl/<语言>/omnitrans_script.rpy`（默认语言
`chinese`）——对话用 `translate <语言> <标识符>:` 块 + 选项/界面用
`translate <语言> strings:` 块。游戏内 偏好设置→语言 切换生效；删除目录即卸载。
游戏文件零改动。

已用 SDK 自带的教程官方法语翻译做交叉验证：788 个语句标识符全部匹配，
重新生成的翻译块与官方一致。

### TyranoScript 游戏

```
python tyrano_extract.py <游戏目录>  # data/scenario/*.ks + 系统 json 角色名
python mt_clean.py <游戏名>_extracted.json && python mt_translate.py && python mt_apply.py <游戏名>_extracted.json
python tyrano_apply.py <游戏目录> <游戏名>_extracted_translated.json
```

提取 `[标签]` 外文本段（跳过注释/标签行/说话人行/macro·eval 块，`[link]` 选项文本
包含），回写按段精确替换；原文件逐个备份为 `*.automt.bak`。

### SRPG Studio 游戏专用流程

```
python srpg_extract.py <游戏目录>      # 自动：下载工具→解包→生成补丁→收集文本
python mt_clean.py <游戏名>_extracted.json
python mt_translate.py                # 机翻或 AI（.env 配 MT_API_TYPE=openai+模型）
python mt_apply.py <游戏名>_extracted.json
python srpg_apply.py <游戏目录> <游戏名>_extracted_translated.json
```

安全机制：原 `data.dts` 自动备份为 `.automt.bak`；消息按原始行边界切回，行数不齐
一律跳过保原文；检测到 `localization.dat`（官方本地化）自动停用，否则会覆盖自定义
翻译。已实弹验证（943MB 游戏：6985 条文本提取→26 条标记翻译→回包→再解析确认）。

### Unity 游戏

```
pip install UnityPy
python unity_extract.py <游戏目录>      # 扫描 assets/level/bundle → 收集文本+位置清单
python mt_clean.py <游戏名>_extracted.json && python mt_translate.py && python mt_apply.py <游戏名>_extracted.json
python unity_apply.py <游戏目录> <游戏名>_extracted_translated.json
```

提取范围：TextAsset（自动识别 JSON 剧本按值提取）、MonoBehaviour 内嵌字符串
（IL2CPP 无 typetree 也可，按长度前缀扫描）、StreamingAssets 下的 .bundle
（含 Addressables / Unity Localization 字符串表）。自动排除 TMP 排版字符表
（LineBreaking 等）防破坏换行。

安全机制：写回采用**临时文件+原子替换**（绝不在产出完成前截断原文件）；每个改动
文件自动备份 `.automt.bak`；字符串按字节前缀原位重建，校验不符自动跳过。
已实弹验证（IL2CPP+Addressables 游戏：283 条提取→68 处回写→重提取标记全数找回）。

> 提示：自带部分翻译的游戏（如已装汉化补丁），提取结果会同时含有已翻与未翻条目；
> 只想补漏的话，可在 `<游戏名>_extracted.json` 里删掉已翻条目再走管线。Unity
> Localization 游戏的译文写在原语言表内（游戏选该语言显示译文）。

## 命令行三步流程（与 GUI 等价）

```
python mt_clean.py [文件]   ① 文本清洗：控制码/换行/人名 → 〔T哈希〕记号
python mt_translate.py      ② 机翻执行器（断点可续；--seg 为分段扫尾模式）
python mt_apply.py [文件]   ③ 还原回填：校验+清理 → 输出 translated.json
```

默认读当前目录 `ManualTransFile.json`。

## 关键机制（实战踩坑沉淀）

| 机制 | 原因 |
|------|------|
| 记号=内容哈希 | 重跑、增量导出永不失效 |
| 已翻条目自动跳过 | 三步全部支持断点续跑 |
| 批量 8 条/请求 + 节流抖动 + 指数退避 | 4.7 万条跑 2.5 小时无封禁 |
| `--seg` 分段模式 | 机翻偶发丢记号；按记号切开只翻文字段后绝无可能丢 |
| 还原时计数校验 | 同一记号多次出现也能对账 |
| 括号变形容错 | 机翻会把〔〕改成【】（）、加空格、全角化——全部归一处理 |
| 清理只用 `[ \t]` | `\s` 会把真实换行吃掉（实弹项目 1258 条冤案） |
| 非法转义消毒 | 机翻注入 `\空格` `\~` 等，按引擎合法集去掉反斜杠 |
| 校验失败留空 | MTool 对空译文回退原文显示，绝不崩游戏 |

## 典型工作流

```
1. MTool 打开游戏 → 导出 ManualTransFile.json → 拷到本目录
2. （可选）把该游戏的人名地名写进 names.txt
3. python mt_clean.py
4. python mt_translate.py          # 中断没关系，重跑即续
5. python mt_apply.py
6. 若有"记号丢失"报告：
   python mt_translate.py --seg    # 只翻剩下的顽固条目
   python mt_apply.py
7. ManualTransFile_translated.json 导回 MTool / 放回游戏目录
```

## 文件说明

- `mt_gui.py` — 上位机（三大功能分区标签页，兼 PyInstaller 打包入口）
- `mt_clean.py / mt_translate.py / mt_apply.py` — 命令行三步
- `mt_config.py` — 配置层（.env 读写/URL构建/响应解析/人名识别/引擎注册表）
- `rpg_extract.py / rpg_apply.py` — RPG Maker MV/MZ 独立提取与回写
- `rvdata.py` + `rva_extract.py / rva_apply.py` — Ruby Marshal 编解码器 + VX Ace/VX/XP 管线
- `krkr_xp3.py` + `krkr_extract.py / krkr_apply.py` — XP3 封包编解码 + Kirikiri 管线
- `renpy_rpyc.py` + `renpy_extract.py / renpy_apply.py` — rpyc/rpa 读取器 + Ren'Py tl 翻译包
- `tyrano_extract.py / tyrano_apply.py` — TyranoScript 管线
- `names.example.txt` — 人名表模板
- `_test_custom.py / _test_autonames.py / _test_rpg.py / _test_rva.py /
  _test_rva_pipeline.py / _test_krkr.py / _test_renpy.py / _test_tyrano.py` —
  自测（模拟API、四语言识别、各引擎提取回写全链路）

## 许可证

MIT
