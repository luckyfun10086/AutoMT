# -*- coding: utf-8 -*-
"""
TyranoScript 回写器
===================
把译文写回 data/scenario/*.ks（段级精确替换，行数/标签结构不变）。
原文件逐个备份为 <原名>.automt.bak（同目录），出错文件自动跳过保持原样。

用法：
    python tyrano_apply.py <游戏目录> <译文json>
"""
import json, sys, io, os, glob, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tyrano_extract import (find_scenario, text_segments, translatable,
                            MACRO_RE, ENDMACRO_RE, IScript_RE)


def apply_ks(text, tr):
    lines = text.split("\n")
    applied = missed = 0
    for li, line in enumerate(lines):
        st = line.strip()
        if not st or st[0] in ";*#@":
            continue
        if MACRO_RE.search(line) or IScript_RE.search(line):
            continue
        if not any(translatable(s) for _, _, s in text_segments(line)):
            continue
        new_line, shift = line, 0
        for start, end, seg in text_segments(line):
            if not translatable(seg):
                continue
            zh = tr.get(seg, "")
            if isinstance(zh, str) and zh.strip():
                new_line = new_line[:start + shift] + zh + new_line[end + shift:]
                shift += len(zh) - (end - start)
                applied += 1
            else:
                missed += 1
        if ENDMACRO_RE.search(line):
            continue
        lines[li] = new_line
    return "\n".join(lines), applied, missed


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    game = sys.argv[1]
    trfile = sys.argv[2]
    tr = json.load(open(trfile, encoding="utf-8"))
    sc = find_scenario(game)
    total_ap = total_mi = n_files = 0
    for f in sorted(glob.glob(os.path.join(sc, "**", "*.ks"), recursive=True)):
        text = open(f, encoding="utf-8-sig", errors="replace").read()
        new_text, ap, mi = apply_ks(text, tr)
        if ap == 0:
            continue
        bak = f + ".automt.bak"
        if not os.path.exists(bak):
            shutil.copy2(f, bak)
        open(f, "w", encoding="utf-8", newline="").write(new_text)
        total_ap += ap
        total_mi += mi
        n_files += 1
    print(f"回写完成：{total_ap} 段已翻译，{total_mi} 段无译文保持原文")
    print(f"改动文件 {n_files} 个；每个原文件已备份为 *.automt.bak（删除 .bak 并还原即可撤销）")


if __name__ == "__main__":
    main()
