# -*- coding: utf-8 -*-
"""
Ren'Py 回写器 — 生成官方 tl 翻译包（非破坏性）
===============================================
不改游戏任何文件：在 game/tl/<语言>/ 下生成 Ren'Py 官方格式翻译包。
游戏内 偏好设置→语言 切换后生效；卸载删除 tl/<语言> 即可。

生成两类块：
  translate <lang> <identifier>:     ← 对话（TranslateSay/Say，替换整句）
      # s "原文"
      s "译文"
  translate <lang> strings:          ← 菜单选项 + _("...") 界面字符串
      old "原文"
      new "译文"

用法：
    python renpy_apply.py <游戏目录> <译文json> [语言名=chinese]
"""
import json, sys, io, os, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renpy_rpyc as RC
from renpy_extract import find_game_dir, load_scripts


def rp_s(s):
    """Ren'Py 字符串字面量（双引号 + 三引号兜底）"""
    esc = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{esc}"'


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    root = sys.argv[1]
    trfile = sys.argv[2]
    lang = sys.argv[3] if len(sys.argv) > 3 else "chinese"
    tr = json.load(open(trfile, encoding="utf-8"))
    game_dir = find_game_dir(root)
    trees = load_scripts(game_dir)

    # 与提取一致地收集，带 identifier / who
    say_blocks = []          # (identifier, who, what, 译文)
    string_pairs = []        # (原文, 译文)
    seen_say = set()
    seen_str = set()
    for name, stmts in sorted(trees.items()):
        for item in RC.collect_dialogue(stmts):
            zh = tr.get(item["what"], "")
            ok = isinstance(zh, str) and zh.strip()
            if item["kind"] == "say" and item.get("identifier") and ok:
                key = ("say", item["identifier"])
                if key not in seen_say:
                    seen_say.add(key)
                    say_blocks.append((item["identifier"], item.get("who"),
                                       item["what"], zh))
            elif ok:
                if item["what"] not in seen_str:
                    seen_str.add(item["what"])
                    string_pairs.append((item["what"], zh))
        for s in RC.collect_py_strings(stmts):
            zh = tr.get(s, "")
            if isinstance(zh, str) and zh.strip() and s not in seen_str:
                seen_str.add(s)
                string_pairs.append((s, zh))

    if not say_blocks and not string_pairs:
        print("没有命中的译文（译文为空或原文已变化）")
        return

    tl_dir = os.path.join(game_dir, "tl", lang)
    os.makedirs(tl_dir, exist_ok=True)
    dst = os.path.join(tl_dir, "omnitrans_script.rpy")
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("# OmniTrans generated translation package\n")
        f.write(f"# language: {lang} | say: {len(say_blocks)} | strings: {len(string_pairs)}\n\n")
        for ident, who, what, zh in say_blocks:
            f.write(f"translate {lang} {ident}:\n")
            f.write(f"    # {rp_s(what)}\n")
            who_s = f"{who} " if who else ""
            f.write(f"    {who_s}{rp_s(zh)}\n\n")
        if string_pairs:
            f.write(f"translate {lang} strings:\n")
            for old, new in string_pairs:
                f.write(f"    old {rp_s(old)}\n")
                f.write(f"    new {rp_s(new)}\n\n")

    print(f"翻译包已生成: {dst}")
    print(f"对话 {len(say_blocks)} 句，字符串 {len(string_pairs)} 条")
    print(f"启动游戏 → 偏好设置(Preferences) → 语言(Language) 选择 {lang} 生效")
    print(f"卸载：删除 {tl_dir} 目录即可，游戏原文件未做任何改动")


if __name__ == "__main__":
    main()
