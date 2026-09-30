# AutoMT — MTool 导出文件自动机翻工具（开源版）

把 MTool 导出的 `ManualTransFile.json`（`{"原文": "译文"}` 键值对，未翻条目译文为空）
全自动机翻成中文。默认走内置免费端点（公开、无需密钥）；也可在界面里填入**你自己的
翻译接口 URL 和 API Key**（保存在本机 `.env`，绝不入库）。

## 隐私与安全设计

- **代码零密钥**：仓库中不含任何 API Key、个人路径；`python -m py_compile` 可自查
- **个人配置隔离**：接口 URL / Key / 请求头保存在 `.env`（`.gitignore` 已排除）
- **本地数据隔离**：`mt_work/` 工作目录、`names.txt` 人名表、`ManualTransFile*.json`
  游戏文本全部被 `.gitignore` 排除——你的游戏内容和专有名词不会上传
- 上传仓库前建议检查：`git status` 不应看到 `.env` / `mt_work/` / 任何 json 文本

## 自定义翻译接口

GUI 中部「翻译接口」栏：

- **URL**：用 `{sl}`（源语言）`{tl}`（目标语言）`{q}`（URL编码后的原文）三个占位符，
  例如 `https://api.example.com/translate?source={sl}&target={tl}&text={q}`
- **Key / 请求头**：默认以 `Authorization: Bearer <Key>` 发送；自定义头（如 `X-Api-Key`）
  则以原值发送
- 「保存到 .env」持久化；留默认则用内置免费端点（无需 Key，批量 8 条/请求）
- 响应格式自动识别：谷歌 `/t` 列表、DeepL 风格 `{"translations":[{"text":..}]}`
  （DeepL）、`{"translatedText":..}`（MyMemory）、纯文本

等价的 `.env` 写法见 [`.env.example`](.env.example)。

## 上位机（推荐）

```
python mt_gui.py
```
- 顶部选择 源语言 → 目标语言（默认 英语 → 简体中文）
- **把 json 文件直接拖进窗口**（或点击选文件）→ 点「开始翻译」
- 实时进度条：① 文本清洗 → ② 机翻翻译（速度/剩余时间）→ ③ 回填校验
- 完成弹窗展示译文位置，一键「打开输出文件夹」
- 校验失败的条目自动进入分段扫尾重翻；随时可取消，断点续翻
- 输出：输入文件同目录 `xxx_translated.json`（键=英文原文精确匹配，MTool 可直接用）

> 拖拽需要 `pip install tkinterdnd2`（未装时仍可用「点击选择文件」）

## 命令行三步流程（等价）

```
python mt_clean.py        ① 文本清洗：控制码/换行/人名 → 〔T哈希〕记号
python mt_translate.py    ② 提交翻译：批量请求谷歌端点（断点可续）
python mt_apply.py        ③ 替换原文：还原记号 → 校验 → 清理 → 回填输出
```

默认读取当前目录的 `ManualTransFile.json`（可用参数指定路径）。
最终输出 `ManualTransFile_translated.json`，放回游戏目录或用 MTool 导入即可。

## 人名保护（可选但强烈建议）

同目录建 `names.txt`，一行一个词条，两种写法：

```
Aura=奥菈          掩码后还原成中文译名（推荐）
Roya=罗雅
Corruption=堕落
Mammon             不写 = 号则保持英文原样
```

这些词会被掩码成记号送翻（**机翻绝不会把 Aura 翻成「光环」**）、回填时按等号
还原成统一译名。项目经验：约 90 个人名地名即可覆盖一款 RPG。

> 注意：改了 names.txt 后，如需让已翻条目也用新译名，删除 `mt_work/` 重跑全流程，
> 或只重跑 mt_apply.py（记号表会以最新 names.txt 为准重新生成于下次 clean）。

## 关键机制（实战踩坑沉淀）

| 机制 | 原因 |
|------|------|
| 记号=内容哈希 | 重跑、增量导出永不失效；同码同记号天然去重 |
| 已翻条目自动跳过 | 三步全部支持断点续跑 |
| 批量 8 条/请求 + 节流抖动 + 指数退避 | 4.7 万条跑 2.5 小时无封禁 |
| `--seg` 分段模式 | 机翻偶发丢记号时，按记号切开只翻文字段，记号 100% 保留 |
| 还原时计数校验 | 同一记号多次出现也能对账，丢一不可 |
| 括号变形容错 | 机翻会把〔〕改成【】（）、加空格、全角化——全部归一处理 |
| 清理只用 `[ \t]` | `\s` 会把真实换行吃掉（实弹项目中 1258 条冤案） |
| 非法转义消毒 | 机翻注入 `\空格` `\~` 等，按 RPG 合法集去掉反斜杠 |
| 校验失败留空 | MTool 对空译文回退原文显示，绝不崩游戏 |

## 典型工作流

```
1. MTool 打开游戏 → 导出 ManualTransFile.json → 拷到本目录
2. 编辑 names.txt 放入该游戏的人名地名
3. python mt_clean.py
4. python mt_translate.py          # 中断没关系，重跑即续
5. python mt_apply.py
6. 若有"记号丢失"报告：
   python mt_translate.py --seg    # 只会翻剩下的顽固条目
   python mt_apply.py
7. ManualTransFile_translated.json 导回 MTool / 放回游戏目录
```

## 文件说明

- `mt_clean.py`   清洗掩码（第一步）
- `mt_translate.py` 机翻执行器（第二步，`--seg` 为分段扫尾模式）
- `mt_apply.py`   还原回填（第三步）
- `names.txt`     人名表（自建，可选）
- `mt_work/`      工作目录（掩码文件+记号表，勿删——增量续跑靠它）
