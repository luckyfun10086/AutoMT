# -*- coding: utf-8 -*-
"""
RPG Maker MV/MZ 独立回写器（无需 MTool）
=========================================
把译文 {"原文": "译文"} 直接写回游戏 data/*.json（自动备份原文件到 data_backup/）。
只替换完全匹配的文本块，找不到或行数不齐的一律跳过保持原文，绝不损坏游戏。

用法：
    python rpg_apply.py <游戏目录> <译文json>
"""
import os, sys
_ENG = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_ENG))    # 项目根：mt_config 等
sys.path.insert(0, _ENG)                     # 引擎同目录：krkr_xp3 等
import json, sys, io, os, glob, shutil

def find_data_dir(game):
    for cand in ("data", "www/data"):
        p = os.path.join(game, cand)
        if os.path.isdir(p):
            return p
    raise SystemExit(f"未找到 data 目录（试过 data 与 www/data）：{game}")

APPLIED = {"n": 0}
SKIPPED = {"n": 0}

def apply_to_list(cmds, tr):
    i = 0
    while i < len(cmds):
        c = cmds[i]
        code = c.get("code")
        p = c.get("parameters", [])
        if code == 401 or code == 405:
            start = i
            lines = []
            while i < len(cmds) and cmds[i].get("code") == code:
                lines.append(str(cmds[i]["parameters"][0]))
                i += 1
            block = "\n".join(lines)
            zh = tr.get(block, "")
            if isinstance(zh, str) and zh.strip():
                parts = zh.split("\n")
                if len(parts) == len(lines):
                    for j, ln in enumerate(parts):
                        cmds[start + j]["parameters"][0] = ln
                    APPLIED["n"] += 1
                else:
                    SKIPPED["n"] += 1
            continue
        elif code == 102 and isinstance(p[0], list):
            block = "\n".join(str(x) for x in p[0])
            zh = tr.get(block, "")
            if isinstance(zh, str) and zh.strip():
                parts = zh.split("\n")
                if len(parts) == len(p[0]):
                    c["parameters"][0] = parts
                    APPLIED["n"] += 1
                else:
                    SKIPPED["n"] += 1
        elif code in (320, 324) and len(p) > 1 and isinstance(p[1], str) and p[1].strip():
            zh = tr.get(p[1], "")
            if isinstance(zh, str) and zh.strip():
                c["parameters"][1] = zh
                APPLIED["n"] += 1
        i += 1

def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    game = sys.argv[1]
    trfile = sys.argv[2]
    tr = json.load(open(trfile, encoding="utf-8"))
    data_dir = find_data_dir(game)
    backup = os.path.join(os.path.dirname(data_dir), os.path.basename(data_dir) + "_backup")
    os.makedirs(backup, exist_ok=True)

    files = sorted(glob.glob(os.path.join(data_dir, "Map*.json")))
    files += [os.path.join(data_dir, n) for n in ("CommonEvents.json", "Troops.json")
              if os.path.exists(os.path.join(data_dir, n))]

    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        changed = False
        if os.path.basename(f).startswith("Map"):
            if not isinstance(d, dict):     # 个别汉化版会把 Map 文件改写为数组等
                continue
            dn = d.get("displayName")
            if isinstance(dn, str) and dn.strip() and tr.get(dn, "").strip():
                d["displayName"] = tr[dn]
                APPLIED["n"] += 1
                changed = True
            for ev in d.get("events", []):
                if not ev:
                    continue
                for pg in ev.get("pages", []):
                    before = APPLIED["n"] + SKIPPED["n"]
                    apply_to_list(pg.get("list", []), tr)
                    changed = changed or (APPLIED["n"] + SKIPPED["n"] > before)
        else:
            if not isinstance(d, list):    # 结构异常的 CommonEvents/Troops 跳过
                continue
            for item in d:
                if not item or not isinstance(item, dict):
                    continue
                if "list" in item:
                    apply_to_list(item["list"], tr)
                for pg in item.get("pages", []):
                    if isinstance(pg, dict):
                        apply_to_list(pg.get("list", []), tr)
            changed = True  # 简化：统一重写（内容校验由 json 往返保证）
        if changed:
            shutil.copy2(f, os.path.join(backup, os.path.basename(f)))
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"回写完成：{APPLIED['n']} 处已翻译，{SKIPPED['n']} 处行数不齐保持原文")
    print(f"原文件已备份到: {backup}")

if __name__ == "__main__":
    main()
