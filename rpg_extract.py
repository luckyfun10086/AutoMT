# -*- coding: utf-8 -*-
"""
RPG Maker MV/MZ 独立文本提取器（无需 MTool）
=============================================
支持引擎：RPG Maker MZ (data/) 与 RPG Maker MV (www/data/，部分发行版在 data/)。
不支持：VX Ace 及更早（.rvdata2 二进制）、Wolf RPG（.wolf 封包）——请改用 MTool。

直接读取游戏目录下 data/*.json，
提取 对话(401)/滚动文本(405)/选项(102)/改名(320,324)/地图名，
输出 OmniTrans 管线兼容的 {"原文": ""} 文件。

连续 401 行自动合并为整段（保留 \\n），翻译质量更好；回写由 rpg_apply.py 负责。

用法：
    python rpg_extract.py <游戏目录>        # 输出 game.extracted.json
"""
import json, sys, io, os, glob
import mt_config

def find_data_dir(game):
    for cand in ("data", "www/data"):
        p = os.path.join(game, cand)
        if os.path.isdir(p):
            return p
    raise SystemExit(f"未找到 data 目录（试过 data 与 www/data）：{game}")

def collect_from_list(cmds, out):
    """一个事件指令列表 → 抽取文本块。返回 (blocks, hits) 供回写器复用同结构。"""
    i = 0
    while i < len(cmds):
        c = cmds[i]
        code = c.get("code")
        p = c.get("parameters", [])
        if code == 401 or code == 405:
            lines = []
            while i < len(cmds) and cmds[i].get("code") == code:
                lines.append(str(cmds[i]["parameters"][0]))
                i += 1
            block = "\n".join(lines)
            if block.strip():
                out[block] = ""
            continue
        elif code == 102 and isinstance(p[0], list):
            block = "\n".join(str(x) for x in p[0])
            if block.strip():
                out[block] = ""
        elif code in (320, 324) and len(p) > 1 and isinstance(p[1], str) and p[1].strip():
            out[p[1]] = ""
        i += 1

def extract(data_dir):
    out = {}
    stats = {}
    def walk_events(events):
        for ev in events:
            if not ev:
                continue
            for pg in ev.get("pages", []) or [ev]:  # Map 有 pages；CommonEvents 无
                if "list" in pg:
                    collect_from_list(pg["list"], out)
    for f in sorted(glob.glob(os.path.join(data_dir, "Map*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        if not isinstance(d, dict):
            continue
        if isinstance(d.get("displayName"), str) and d["displayName"].strip():
            out[d["displayName"]] = ""
        walk_events(d.get("events", []))
        stats[os.path.basename(f)] = 1
    for name in ("CommonEvents.json", "Troops.json"):
        p = os.path.join(data_dir, name)
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            for item in d:
                if not item:
                    continue
                if "list" in item:
                    collect_from_list(item["list"], out)
                for pg in item.get("pages", []):
                    collect_from_list(pg.get("list", []), out)
            stats[name] = 1
    return out, stats

def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    game = sys.argv[1] if len(sys.argv) > 1 else "."
    data_dir = find_data_dir(game)
    out, stats = extract(data_dir)
    dst = os.path.join(mt_config.base_dir(), "game.extracted.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    chars = sum(len(k) for k in out)
    print(f"扫描 {len(stats)} 个数据文件，提取唯一文本 {len(out)} 条（{chars} 字符）")
    print(f"输出: {dst}")
    print("下一步: python mt_clean.py game.extracted.json && python mt_translate.py && python mt_apply.py game.extracted.json")
    print("最后:   python rpg_apply.py <游戏目录> game.extracted_translated.json")

if __name__ == "__main__":
    main()
