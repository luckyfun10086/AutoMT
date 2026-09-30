# -*- coding: utf-8 -*-
"""
Kirikiri (吉里吉里) 回写器 — 生成非破坏性 patch 封包
====================================================
不改动游戏原 .xp3：把改动的 .ks 打成新的 patch 档（Kirikiri 按文件名序
后挂载的封包覆盖先挂载的同名文件），卸载汉化只需删除该 patch 文件。

回写规则：
- 与提取完全相同的段切分，逐段替换（段即键，译文查 dict）
- 行内替换后重编码：UTF-16LE/UTF-8 原样；CP932 装不下时该文件升级为
  UTF-16LE+BOM（--keep-enc 可改为跳过该文件）

用法：
    python krkr_apply.py <游戏目录> <译文json> [--keep-enc]
"""
import json, sys, io, os, glob, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import krkr_xp3 as X
from krkr_extract import (decode_ks, encode_ks, kag_text_segments, translatable,
                          effective_files)


def patch_name(game):
    """生成排在所有现有 patch 之后的封包名"""
    names = [os.path.basename(p) for p in glob.glob(os.path.join(game, "*.xp3"))]
    return "patch_zz_automt.xp3" if names else "patch.xp3"


def apply_ks(text, tr):
    """段级替换。返回 (new_text, applied, missed)"""
    lines = text.split("\n")
    applied = missed = 0
    for li, line in enumerate(lines):
        st = line.strip()
        if not st or st[0] in ";*@":
            continue
        if not any(translatable(s) for _, _, s in kag_text_segments(line)):
            continue
        new_line, pos_shift = line, 0
        for start, end, seg in kag_text_segments(line):
            if not translatable(seg):
                continue
            zh = tr.get(seg, "")
            if isinstance(zh, str) and zh.strip():
                s0 = start + pos_shift
                s1 = end + pos_shift
                new_line = new_line[:s0] + zh + new_line[s1:]
                pos_shift += len(zh) - (end - start)
                applied += 1
            else:
                missed += 1
        lines[li] = new_line
    return "\n".join(lines), applied, missed


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    game = sys.argv[1]
    trfile = sys.argv[2]
    keep_enc = "--keep-enc" in sys.argv
    tr = json.load(open(trfile, encoding="utf-8"))
    files = effective_files(game)
    scripts = {n: v for n, v in files.items() if n.lower().endswith(".ks")}

    stats = {"applied": 0, "missed": 0, "enc_skip": 0, "enc_up": 0}
    changed = []
    for name, (arc, e) in sorted(scripts.items()):
        with open(arc, "rb") as f:
            data = X.read_entry_data(f, e)
        text, enc = decode_ks(data)
        new_text, ap, mi = apply_ks(text, tr)
        if ap == 0:
            continue
        out = encode_ks(new_text, enc)
        if out is None:
            if keep_enc:
                stats["enc_skip"] += 1
                continue
            out = encode_ks(new_text, "utf-16le")   # CP932 装不下 → 升级 UTF-16LE
            stats["enc_up"] += 1
        changed.append((name, out, e.mtime or int(time.time() * 1000)))
        stats["applied"] += ap
        stats["missed"] += mi

    if not changed:
        print("没有需要回写的改动（译文为空或全部未命中）")
        return
    dst = os.path.join(game, patch_name(game))
    with open(dst, "wb") as f:
        n = X.write_xp3(f, changed)
    msg = (f"回写完成：{stats['applied']} 段已翻译，{stats['missed']} 段无译文保持原文")
    if stats["enc_up"]:
        msg += f"，{stats['enc_up']} 个文件升级为 UTF-16LE"
    if stats["enc_skip"]:
        msg += f"，{stats['enc_skip']} 个文件编码不兼容已跳过"
    print(msg)
    print(f"已生成补丁封包: {dst}（{n} 个文件）")
    print("Kirikiri 会以后挂载的封包优先；若游戏未生效，请确认该文件名排在游戏现有 patch 之后")
    print("卸载汉化：删除该 patch 文件即可，原档案未被改动")


if __name__ == "__main__":
    main()
