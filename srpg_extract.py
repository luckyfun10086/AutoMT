# -*- coding: utf-8 -*-
"""
SRPG Studio 独立提取器（桥接 Sinflower/SRPG-ToolBox）
=====================================================
支持引擎：SRPG Studio（data.dts / runtime.rts / environment.evs 特征）。
依赖 SRPG_Unpacker.exe（首次运行自动从 GitHub 下载到 bin/，MIT 开源）。

流程：data.dts 解包 → 生成翻译补丁 JSON（105+ 个结构化文件）→
收集全部日文文本 → 输出 OmniTrans 标准 {原文: ""} 文件。

消息整段合并翻译（多行 data 元素以 \\n 连接，掩码管线保证换行数不变），
回写由 srpg_apply.py 按原始边界切回。

用法：
    python srpg_extract.py <游戏目录>
输出：
    <游戏名>_extracted.json（OmniTrans 管线直接可用）
"""
import json, sys, io, os, re, subprocess, urllib.request, hashlib
import mt_config

TOOL_URL = ("https://github.com/Sinflower/SRPG-ToolBox/releases/download/"
            "v0.1.2/SRPG_Unpacker.exe")
JP = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')
SKIP_KEYS = {"type", "comment", "commandMsg", "customParameters", "command",
             "speaker", "id", "variable", "icon", "file", "path"}

def base():
    import mt_config
    return mt_config.base_dir()

def ensure_unpacker():
    exe = os.path.join(base(), "bin", "SRPG_Unpacker.exe")
    if not os.path.exists(exe):
        os.makedirs(os.path.dirname(exe), exist_ok=True)
        print("首次运行：下载 SRPG_Unpacker.exe (Sinflower/SRPG-ToolBox, MIT)...")
        urllib.request.urlretrieve(TOOL_URL, exe)
    return exe

def run(exe, args, cwd):
    r = subprocess.run([exe] + args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tail = (r.stdout or r.stderr).strip().splitlines()
    for line in tail[-3:]:
        print("  |", line)
    if r.returncode != 0:
        raise SystemExit(f"SRPG_Unpacker 失败: {args}")

def prepare(game):
    exe = ensure_unpacker()
    work = os.path.join(base(), "srpg_work", os.path.basename(game.rstrip("\\/")))
    os.makedirs(work, exist_ok=True)
    dts = os.path.join(game, "data.dts")
    if not os.path.exists(dts):
        raise SystemExit(f"未找到 data.dts（不是 SRPG Studio 游戏？）: {game}")
    out = os.path.join(work, "output")
    if not os.path.isdir(out):
        print("① 解包 data.dts（首次约 1-3 分钟）...")
        run(exe, [dts, "-o", "output"], work)
    if not os.path.isdir(os.path.join(work, "patch")):
        print("② 生成翻译补丁...")
        run(exe, [os.path.join("output", "project.dat"), "-c", "-o", "patch"], work)
    return work

def collect_msg(cmd):
    """message/choice 命令 → 合并整段文本（元素间 \\n 连接）"""
    data = cmd.get("data")
    if isinstance(data, list) and data and all(isinstance(x, str) for x in data) \
            and any(x.strip() for x in data):
        joined = "\n".join(data)
        if JP.search(joined):
            return joined
    return None

def collect_fields(node, out, key=None):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "data" and "type" in node:
                continue          # 消息 data 已按整段收集，避免逐元素重复
            collect_fields(v, out, k)
    elif isinstance(node, list):
        for v in node:
            collect_fields(v, out, key)
    elif isinstance(node, str) and key and key not in SKIP_KEYS:
        if node.strip() and JP.search(node) and len(node) < 2000:
            out[node] = ""

def walk_patch(patchdir):
    """返回 (消息集合, 字段集合, 文件数)"""
    msgs, fields, nfiles = {}, {}, 0
    for root, _, files in os.walk(patchdir):
        for fn in sorted(files):
            if not fn.endswith(".json"):
                continue
            nfiles += 1
            p = os.path.join(root, fn)
            d = json.load(open(p, encoding="utf-8"))
            def walk(n):
                if isinstance(n, dict):
                    if n.get("type") in ("message", "choice") and "data" in n:
                        m = collect_msg(n)
                        if m:
                            msgs[m] = ""
                    for v in n.values():
                        walk(v)
                elif isinstance(n, list):
                    for v in n:
                        walk(v)
            walk(d)
            collect_fields(d, fields)
    return msgs, fields, nfiles

def main():
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass
    game = sys.argv[1]
    work = prepare(game)
    print("③ 收集文本...")
    msgs, fields, nfiles = walk_patch(os.path.join(work, "patch"))
    allstr = dict(msgs)
    for k in fields:
        allstr.setdefault(k, "")
    name = os.path.basename(game.rstrip("\\/"))
    dst = os.path.join(base(), f"{name}_extracted.json")
    json.dump(allstr, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"扫描补丁文件 {nfiles} 个：消息 {len(msgs)} 条 + 界面/名称字段 {len(fields)} 条"
          f" = 共 {len(allstr)} 条唯一文本")
    print(f"输出: {dst}")
    print(f"下一步: python mt_clean.py \"{dst}\" && python mt_translate.py && "
          f"python mt_apply.py \"{dst}\"")
    print(f"最后:   python srpg_apply.py <游戏目录> \"{name}_extracted_translated.json\"")

if __name__ == "__main__":
    main()
