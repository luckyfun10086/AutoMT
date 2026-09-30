# -*- coding: utf-8 -*-
"""
Ren'Py 文本提取器（无需 MTool / unrpyc）
=========================================
支持：.rpa 封包（RPA-2.0/3.0）与平铺 .rpyc（Ren'Py 6.99+/7/8 的 RPC2 格式）。

提取范围：
- 对话（TranslateSay/Say 的 what，含 who 角色标签）
- 菜单选项（Menu items）
- PyExpr 里的 _("...") 字符串（角色名/界面文本）

输出 {"原文": ""}；回写由 renpy_apply.py 生成官方 tl 翻译包（非破坏）。

用法：
    python renpy_extract.py <游戏目录>     # → <游戏名>_extracted.json
"""
import json, sys, io, os, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renpy_rpyc as RC


def find_game_dir(root):
    """定位 game/ 目录：直接是 game/、或子目录里有 renpy 核心"""
    if os.path.basename(os.path.abspath(root).rstrip("/\\")) == "game":
        return root
    for cand in (os.path.join(root, "game"), os.path.join(root, "renpy")):
        if os.path.isdir(cand) and os.path.basename(cand) == "game":
            return cand
    if os.path.isdir(os.path.join(root, "game")):
        return os.path.join(root, "game")
    # exe 旁边没有 game/ → 本身就是 game 内容（解包后）
    if glob.glob(os.path.join(root, "*.rpyc")) or glob.glob(os.path.join(root, "*.rpa")):
        return root
    raise SystemExit(f"未找到 game/ 目录或 .rpyc/.rpa：{root}")


def load_scripts(game_dir, log=print):
    """→ {源文件相对名: 语句树}。rpa 中的 .rpyc 一并解出。"""
    trees = {}
    # 平铺 .rpyc
    for p in sorted(glob.glob(os.path.join(game_dir, "*.rpyc"))):
        base = os.path.basename(p)
        try:
            _, stmts = RC.read_rpyc(p)
            trees[base] = stmts
        except ValueError as e:
            log(f"  ⚠ {base}: {e}")
    # .rpa 里的 .rpyc
    for p in sorted(glob.glob(os.path.join(game_dir, "*.rpa"))):
        try:
            files = RC.read_rpa(p)
        except ValueError as e:
            log(f"  ⚠ {os.path.basename(p)}: {e}")
            continue
        for name, data in files.items():
            if name.lower().endswith(".rpyc"):
                import tempfile
                tf = os.path.join(tempfile.gettempdir(), "automt_rpyc.tmp")
                open(tf, "wb").write(data)
                try:
                    _, stmts = RC.read_rpyc(tf)
                    trees[name] = stmts
                except ValueError as e:
                    log(f"  ⚠ {name} (in {os.path.basename(p)}): {e}")
    return trees


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    game_dir = find_game_dir(root)
    trees = load_scripts(game_dir)
    out = {}
    n_say = n_choice = n_str = 0
    for name, stmts in sorted(trees.items()):
        for item in RC.collect_dialogue(stmts):
            out.setdefault(item["what"], "")
            if item["kind"] == "say":
                n_say += 1
            else:
                n_choice += 1
        for s in RC.collect_py_strings(stmts):
            if s not in out:
                out[s] = ""
                n_str += 1
    base = os.path.basename(os.path.abspath(root).rstrip("/\\"))
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{base}_extracted.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    chars = sum(len(k) for k in out)
    print(f"脚本 {len(trees)} 个：对话 {n_say}，选项 {n_choice}，界面字符串 {n_str}")
    print(f"提取唯一文本 {len(out)} 条（{chars} 字符）")
    print(f"输出: {dst}")
    print("下一步: python mt_clean.py \"" + os.path.basename(dst) + "\" && python mt_translate.py && python mt_apply.py \"" + os.path.basename(dst) + "\"")


if __name__ == "__main__":
    main()
