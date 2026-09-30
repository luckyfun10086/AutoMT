# AutoMT — MTool JSON 自动机翻工具

[English](README.md) | **简体中文**

把 MTool 导出的 `ManualTransFile.json`（`{"原文": "译文"}` 键值对，未翻条目译文为空）
全自动机翻成中文。默认走内置免费端点（公开、无需密钥）；也可在界面里填入**你自己的
翻译接口 URL 和 API Key**（保存在本机 `.env`，绝不入库）。不用 MTool？见下方
[独立 RPG Maker 提取](#独立-rpg-maker-提取无需-mtool)。

> [MTool](https://mtool.app/) —— 本项目为之打造的游戏翻译修改工具（非开源，官网 mtool.app）。

已在 7 万+条游戏文本上实弹验证。

## 下载

到 [**Releases**](https://github.com/luckyfun10086/AutoMT/releases) 页面下载 `AutoMT.exe`
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

## 上位机（推荐）

1. 顶部选择 **源语言 → 目标语言**（默认 英语 → 简体中文）
2. **把 MTool 导出的 json 拖进窗口**（或点击选文件）
3. 点「开始翻译」，实时看到：① 文本清洗 → ② 机翻翻译（进度条+速度+剩余时间）→ ③ 回填校验
4. 完成弹窗显示译文位置，**「打开输出文件夹」一键直达**；随时可取消，断点续翻

校验失败的条目自动进入分段扫尾重翻（记号绝不可能丢）。exe 版拖拽开箱即用；
源码运行需 `pip install tkinterdnd2`（未装时自动退化为点选文件）。

> 重新打包：`pip install pyinstaller && python -m PyInstaller --onefile --windowed --name AutoMT --collect-all tkinterdnd2 mt_gui.py`

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
| RPG Maker VX Ace / VX / XP | `.rvdata2` 二进制文件 | ❌ 不支持（二进制序列化格式） |
| Wolf RPG Editor | `.wolf` 封包 | ❌ 不支持 |

MV/MZ 的全部游戏文本都是明文 JSON（`Map*.json`、`CommonEvents.json`、
`Troops.json` 等），AutoMT 直接读写，全程无需第三方工具；VX Ace 及更早引擎请
改用 MTool。

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

- `mt_gui.py` — 上位机（兼 PyInstaller 打包入口）
- `mt_clean.py / mt_translate.py / mt_apply.py` — 命令行三步
- `mt_config.py` — 配置层（.env 读写/URL构建/响应解析/人名识别）
- `rpg_extract.py / rpg_apply.py` — RPG Maker MV/MZ 独立提取与回写
- `names.example.txt` — 人名表模板
- `_test_custom.py / _test_autonames.py / _test_rpg.py` — 自测（模拟API、四语言识别、提取回写全链路）

## 许可证

MIT
