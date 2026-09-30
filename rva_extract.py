# -*- coding: utf-8 -*-
"""
RPG Maker VX Ace / VX / XP 独立文本提取器（无需 MTool）
=======================================================
支持引擎：VX Ace（Data/*.rvdata2）、VX（*.rvdata）、XP（*.rxdata）——均为 Ruby Marshal 格式。

直接解析 Data/ 下的二进制数据文件（纯 Python Marshal 解析器 rvdata.py），
提取 对话(401,连续行合并)/滚动文本(405)/选项(102)/改名(320,324)/地图名/
物品·技能描述/技能使用消息/角色昵称，输出 OmniTrans 管线兼容的 {"原文": ""} 文件。

用法：
    python rva_extract.py <游戏目录>     # → <游戏名>_extracted.json
"""
import json, sys, io, os, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rvdata as R


def find_data_dir(game):
    for cand in ("Data", "data"):
        p = os.path.join(game, cand)
        if os.path.isdir(p) and any(f.lower().endswith((".rvdata2", ".rvdata", ".rxdata"))
                                    for f in os.listdir(p)):
            return p
    # 有些盗版移植把 Data 平铺在游戏根目录
    if any(f.lower().endswith((".rvdata2", ".rvdata", ".rxdata"))
           for f in os.listdir(game) if os.path.isfile(os.path.join(game, f))):
        return game
    raise SystemExit(f"未找到 Data 目录（.rvdata2/.rvdata/.rxdata）：{game}")


def cmd_code(cmd):
    c = cmd.ivar("@code")
    return c.v if isinstance(c, R.MInt) else None


def cmd_params(cmd):
    p = cmd.ivar("@parameters")
    return p.items if isinstance(p, R.MArray) else []


def s_text(node):
    """MStr → 文本；非字符串返回 None"""
    if isinstance(node, R.MStr):
        t = node.decode().strip("\r\n")
        return t if t.strip() else None
    return None


def collect_from_list(cmds, out):
    """事件指令列表（MArray of RPG::EventCommand）→ 抽取文本块。"""
    i = 0
    items = cmds.items if isinstance(cmds, R.MArray) else []
    while i < len(items):
        c = items[i]
        if not isinstance(c, R.MObj):
            i += 1
            continue
        code = cmd_code(c)
        p = cmd_params(c)
        if code == 401 or code == 405:
            lines = []
            while i < len(items) and isinstance(items[i], R.MObj) and cmd_code(items[i]) == code:
                t = s_text(cmd_params(items[i])[0]) if cmd_params(items[i]) else None
                lines.append(t if t is not None else "")
                i += 1
            block = "\n".join(lines)
            if block.strip():
                out[block] = ""
            continue
        elif code == 102 and p and isinstance(p[0], R.MArray):
            block = "\n".join(x for x in (s_text(t) for t in p[0].items) if x)
            if block.strip():
                out[block] = ""
        elif code in (320, 324) and len(p) > 1:
            t = s_text(p[1])
            if t:
                out[t] = ""
        i += 1


def walk_events(events, out):
    """RPG::Map@events（MHash int→RPG::Event）"""
    if not isinstance(events, R.MHash):
        return
    for _, ev in events.pairs:
        if not isinstance(ev, R.MObj):
            continue
        pages = ev.ivar("@pages")
        if isinstance(pages, R.MArray):
            for pg in pages.items:
                if isinstance(pg, R.MObj):
                    collect_from_list(pg.ivar("@list"), out)


def extract_file(path, fname, out):
    """单个 .rvdata2 → 文本。返回是否解析成功。"""
    try:
        root = R.loads(open(path, "rb").read())
    except Exception as e:
        print(f"  ⚠ 解析失败（跳过）: {fname}: {e}")
        return False
    fl = fname.lower()
    if fl.startswith("map") and not fl.startswith("mapinfos"):
        # RPG::Map：@display_name + @events
        if isinstance(root, R.MObj):
            dn = root.ivar("@display_name")
            t = s_text(dn) if dn is not None else None
            if t:
                out[t] = ""
            walk_events(root.ivar("@events"), out)
    elif fl == "mapinfos.rvdata2":
        # Hash int → RPG::MapInfo(@name)：存档/传送菜单里的地图名
        if isinstance(root, R.MHash):
            for _, mi in root.pairs:
                if isinstance(mi, R.MObj):
                    t = s_text(mi.ivar("@name"))
                    if t:
                        out[t] = ""
    elif fl == "commonevents.rvdata2":
        if isinstance(root, R.MArray):
            for ce in root.items:
                if isinstance(ce, R.MObj):
                    collect_from_list(ce.ivar("@list"), out)
    elif fl == "troops.rvdata2":
        if isinstance(root, R.MArray):
            for tr in root.items:
                if isinstance(tr, R.MObj):
                    pages = tr.ivar("@pages")
                    if isinstance(pages, R.MArray):
                        for pg in pages.items:
                            if isinstance(pg, R.MObj):
                                collect_from_list(pg.ivar("@list"), out)
    else:
        # Skills/Items/Weapons/Armors(@description) / Skills(@message1,2) / Actors(@nickname)
        if isinstance(root, R.MArray):
            for item in root.items:
                if not isinstance(item, R.MObj):
                    continue
                for key in ("@description", "@message1", "@message2", "@nickname"):
                    t = s_text(item.ivar(key))
                    if t:
                        out[t] = ""
    return True


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    game = sys.argv[1] if len(sys.argv) > 1 else "."
    data_dir = find_data_dir(game)
    files = sorted(glob.glob(os.path.join(data_dir, "*.rvdata2")))
    files += sorted(glob.glob(os.path.join(data_dir, "*.rvdata")))
    files += sorted(glob.glob(os.path.join(data_dir, "*.rxdata")))
    files = [f for f in files if not os.path.basename(f).lower().startswith(
        ("scripts.", "system.", "tilesets.", "animations.", "states.",
         "classes.", "enemies.", "areas.", "audiofiles.", "battlebacks1.",
         "battlebacks2.", "parallaxes.", "pictures.", "titles1.", "titles2.",
         "bcgs.", "battlebacks.", "elements.", "fonts.", "plugins."))]
    out = {}
    n_ok = 0
    for f in files:
        if extract_file(f, os.path.basename(f), out):
            n_ok += 1
    base = os.path.basename(os.path.abspath(game).rstrip("/\\"))
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{base}_extracted.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    chars = sum(len(k) for k in out)
    print(f"扫描 {n_ok}/{len(files)} 个数据文件，提取唯一文本 {len(out)} 条（{chars} 字符）")
    print(f"输出: {dst}")
    print("下一步: python mt_clean.py \"" + os.path.basename(dst) + "\" && python mt_translate.py && python mt_apply.py \"" + os.path.basename(dst) + "\"")
    print("最后:   python rva_apply.py <游戏目录> \"" + os.path.basename(dst).replace("_extracted", "_extracted_translated") + "\"")


if __name__ == "__main__":
    main()
