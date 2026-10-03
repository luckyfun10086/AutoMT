# -*- coding: utf-8 -*-
"""
Wolf RPG Editor (ウディタ) 文本提取器
=====================================
桥接 Sinflower 的 MIT 工具链（首次运行自动下载到 bin/wolf/）：
  UberWolfCli.exe — 解包 .wolf 封包（全版本 + Pro 密钥自动检测）
  WolfTL.exe      — 从 Data/ 提取翻译文本为 JSON（create）/回写（patch）

流程：
  ① 游戏 .wolf 封包 → UberWolfCli 解包（原包改名 .wolf.automt.bak，
     引擎自动改读明文 Data/ 目录，无需重打包）
  ② WolfTL create → dump/{common,mps,db}/*.json
  ③ 收集：Message/Choices 的 stringArgs + 数据库行名/字段值（含日文者）

用法：
    python engines/wolf_extract.py <游戏目录>     # → <游戏名>_extracted.json
"""
import os, sys

_ENG = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_ENG))    # 项目根：mt_config 等
sys.path.insert(0, _ENG)                     # 引擎同目录
import json, io, re, glob, shutil, subprocess
import mt_config

TOOL_DIR = os.path.join(mt_config.base_dir(), "bin", "wolf")
TOOLS = {
    "UberWolfCli.exe": ("Sinflower/UberWolf", "v0.6.4"),
    "WolfTL.exe": ("Sinflower/WolfTL", "v0.6.2"),
}
# 只提取这些命令的 stringArgs（对话/选项）；Comment/Label/ByName 等为注释或逻辑引用
TEXT_CODES = {"Message", "Choices"}
JP = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def ensure_tools(log=print):
    """确保 bin/wolf 下的工具存在，缺失则从 GitHub Release 下载。"""
    import urllib.request
    os.makedirs(TOOL_DIR, exist_ok=True)
    for name, (repo, tag) in TOOLS.items():
        dst = os.path.join(TOOL_DIR, name)
        if os.path.exists(dst):
            continue
        url = f"https://github.com/{repo}/releases/download/{tag}/{name}"
        log(f"[wolf] 下载 {name} ({repo} {tag}, MIT)…")
        with urllib.request.urlopen(url, timeout=120) as r, open(dst, "wb") as f:
            shutil.copyfileobj(r, f)
        if os.path.getsize(dst) < 100_000:
            raise RuntimeError(f"{name} 下载异常")
        log(f"[wolf] {name} 下载完成")
    return TOOL_DIR


def run_tool(exe, *args, timeout=1800):
    r = subprocess.run([os.path.join(TOOL_DIR, exe)] + list(args),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{exe} 失败: {(r.stderr or r.stdout)[-300:]}")
    return r.stdout


def find_data_dir(game):
    """定位 Wolf 数据目录：明文 Data/ 优先；否则解包 .wolf（备份原包）。"""
    d = os.path.join(game, "Data")
    if os.path.isdir(d) and glob.glob(os.path.join(d, "BasicData", "*.dat")):
        return d
    wolves = sorted(glob.glob(os.path.join(game, "*.wolf")))
    if not wolves:
        raise SystemExit(f"未找到 Wolf 数据（Data/ 或 *.wolf）：{game}")
    ensure_tools()
    for w in wolves:
        bak = w + ".automt.bak"
        if not os.path.exists(bak):
            os.replace(w, bak)          # 先改名再解包（UberWolfCli 按名解包）
        else:
            os.remove(w)
    # UberWolfCli 接受 .wolf 文件列表；传 Game.exe 会处理全部封包——这里逐包解
    for bak in sorted(glob.glob(os.path.join(game, "*.wolf.automt.bak"))):
        # 工具按原名输出目录（Data/CG/...）：临时恢复原名→解包→再改回
        orig = bak[:-len(".automt.bak")]
        shutil.copy2(bak, orig)
        try:
            run_tool("UberWolfCli.exe", "-o", os.path.abspath(orig))
        finally:
            os.remove(orig)
    if not (os.path.isdir(d) and glob.glob(os.path.join(d, "BasicData", "*.dat"))):
        raise SystemExit("解包后仍未找到 Data/BasicData/*.dat")
    return d


def _collect_dump(dump, out):
    """遍历 WolfTL dump JSON 收集可翻文本。"""
    n = 0
    for sub in ("common", "mps"):
        for f in sorted(glob.glob(os.path.join(dump, sub, "*.json"))):
            try:
                d = json.load(open(f, encoding="utf-8-sig"))
            except Exception:
                continue
            n += _collect_events(d, out)

    def rec_db(x):
        nonlocal n
        if isinstance(x, dict):
            # 数据库行：{name: 行名, data: [{name, value}]} —— value 含日文即可翻
            if "data" in x and isinstance(x["data"], list):
                nm = x.get("name")
                if isinstance(nm, str) and JP.search(nm) and nm.strip():
                    out.setdefault(nm, "")
                    n += 1
                for c in x["data"]:
                    if isinstance(c, dict):
                        v = c.get("value")
                        if isinstance(v, str) and JP.search(v) and v.strip():
                            out.setdefault(v, "")
                            n += 1
            for v in x.values():
                rec_db(v)
        elif isinstance(x, list):
            for v in x:
                rec_db(v)

    for f in sorted(glob.glob(os.path.join(dump, "db", "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8-sig"))
        except Exception:
            continue
        rec_db(d)
    return n


def _collect_events(node, out):
    """事件树：codeStr ∈ {Message, Choices} 的 stringArgs 逐条收集。"""
    n = 0
    if isinstance(node, dict):
        if node.get("codeStr") in TEXT_CODES and isinstance(node.get("stringArgs"), list):
            for s in node["stringArgs"]:
                if isinstance(s, str) and s.strip() and JP.search(s):
                    out.setdefault(s, "")
                    n += 1
        for v in node.values():
            n += _collect_events(v, out)
    elif isinstance(node, list):
        for v in node:
            n += _collect_events(v, out)
    return n


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    game = sys.argv[1] if len(sys.argv) > 1 else "."
    game = os.path.abspath(game)
    ensure_tools()
    data_dir = find_data_dir(game)
    base = os.path.basename(game.rstrip("/\\"))
    work = os.path.join(mt_config.base_dir(), "wolf_work", base)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    print(run_tool("WolfTL.exe", os.path.abspath(data_dir), work, "create")[-200:])
    dump = os.path.join(work, "dump")
    out = {}
    n = _collect_dump(dump, out)
    dst = os.path.join(mt_config.base_dir(), f"{base}_extracted.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"work": work}, open(os.path.join(mt_config.base_dir(),
                                                 f"{base}_wolfwork.json"), "w",
                                    encoding="utf-8"))
    chars = sum(len(k) for k in out)
    print(f"Wolf 数据：{os.path.relpath(data_dir, game)}；工作目录 {work}")
    print(f"提取唯一文本 {n-n if False else len(out)} 条（{chars} 字符）")
    print(f"输出: {dst}")
    print(f"下一步: python mt_clean.py \"{os.path.basename(dst)}\" && python mt_translate.py && python mt_apply.py \"{os.path.basename(dst)}\"")
    print(f"最后:   python engines/wolf_apply.py <游戏目录> \"{os.path.basename(dst).replace('_extracted', '_extracted_translated')}\"")


if __name__ == "__main__":
    main()
