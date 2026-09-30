# -*- coding: utf-8 -*-
"""
SRPG Studio 独立回写器（桥接 Sinflower/SRPG-ToolBox）
=====================================================
把译文 {"原文": "译文"} 写回补丁 JSON → 重新打包 data.dts → 备份并替换游戏文件。
消息按原始元素边界切回（掩码管线已保证换行总数一致）；行数不齐的条目跳过保原文。

自动处理：
- 游戏目录 data.dts → 备份为 data.dts.automt.bak（仅首次）
- localization.dat 存在时改名为 localization.dat.automt.bak
  （SRPG 官方本地化会覆盖自定义翻译，必须移除才生效）

用法：
    python srpg_apply.py <游戏目录> <译文json>
"""
import json, sys, io, os, re, subprocess, shutil
import mt_config
from srpg_extract import ensure_unpacker, run, JP, SKIP_KEYS

def chunk_back(data, zh):
    """整段译文按原始元素边界切回；失败返回 None"""
    counts = [el.count("\n") for el in data]
    parts = zh.split("\n")
    if len(parts) != sum(counts) + len(counts):
        return None
    out, i = [], 0
    for c in counts:
        out.append("\n".join(parts[i:i + c + 1]))
        i += c + 1
    return out

def apply_file(d, tr, stat):
    def rep(n):
        if isinstance(n, dict):
            if n.get("type") in ("message", "choice") and isinstance(n.get("data"), list):
                data = n["data"]
                if data and all(isinstance(x, str) for x in data) \
                        and any(x.strip() for x in data):
                    joined = "\n".join(data)
                    zh = tr.get(joined, "")
                    if isinstance(zh, str) and zh.strip():
                        chunks = chunk_back(data, zh)
                        if chunks is not None:
                            n["data"] = chunks
                            stat["msg"] += 1
                        else:
                            stat["skip"] += 1
            for k in list(n):
                v = n[k]
                if isinstance(v, str):
                    if k not in SKIP_KEYS and v.strip() and JP.search(v):
                        zh = tr.get(v, "")
                        if isinstance(zh, str) and zh.strip():
                            n[k] = zh
                            stat["fld"] += 1
                elif k != "type" or True:
                    rep(v)
        elif isinstance(n, list):
            for i, v in enumerate(n):
                if isinstance(v, str):
                    if v.strip() and JP.search(v):
                        zh = tr.get(v, "")
                        if isinstance(zh, str) and zh.strip():
                            n[i] = zh
                            stat["fld"] += 1
                else:
                    rep(v)
    rep(d)

def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    game = sys.argv[1]
    trfile = sys.argv[2]
    tr = mt_config.load_loose_json(trfile)
    work = os.path.join(os.path.dirname(os.path.abspath(__file__)), "srpg_work",
                        os.path.basename(game.rstrip("\\/")))
    patchdir = os.path.join(work, "patch")
    if not os.path.isdir(patchdir):
        raise SystemExit("未找到补丁目录，请先运行 srpg_extract.py")

    stat = {"msg": 0, "skip": 0, "fld": 0}
    for root, _, files in os.walk(patchdir):
        for fn in sorted(files):
            if not fn.endswith(".json"):
                continue
            p = os.path.join(root, fn)
            d = json.load(open(p, encoding="utf-8"))
            apply_file(d, tr, stat)
            json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"回写：消息 {stat['msg']} 条，行数不齐跳过 {stat['skip']} 条，"
          f"名称/界面字段 {stat['fld']} 处")

    exe = ensure_unpacker()
    print("① 应用补丁到工程（就地写入 output/project.dat）...")
    run(exe, [os.path.join("output", "project.dat"), "-a", "-o", "patch"], work)
    print("② 重新打包 data.dts（约 1-2 分钟）...")
    run(exe, ["output", "-o", "patched_data.dts"], work)
    patched = os.path.join(work, "patched_data.dts")

    dts = os.path.join(game, "data.dts")
    bak = dts + ".automt.bak"
    if not os.path.exists(bak):
        shutil.copy2(dts, bak)
        print(f"原 data.dts 已备份: {bak}")
    shutil.copy2(patched, dts)
    print("已替换游戏 data.dts ✓")

    loc = os.path.join(game, "localization.dat")
    if os.path.exists(loc):
        os.rename(loc, loc + ".automt.bak")
        print("检测到 localization.dat（官方本地化会覆盖自定义翻译）→ 已停用改名"
              f"为 {os.path.basename(loc)}.automt.bak")
    print("完成！进游戏验证；异常时把 data.dts.automt.bak 改回 data.dts 即可还原。")

if __name__ == "__main__":
    main()
