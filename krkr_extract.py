# -*- coding: utf-8 -*-
"""
Kirikiri (吉里吉里) 文本提取器 — XP3 封包 + KAG 脚本
====================================================
支持：.xp3 封包（zlib/raw 段，v1/v2 头，二级索引），.ks 剧本（CP932/UTF-16LE/UTF-8）。

提取规则（KAG）：
- 跳过 ';' 注释行、'*' 标签行、'@' 命令行
- 每行按 [标签] 切分，提取标签外含日文/字母的文本段
- '【名】「」' 说话人括号随段一起翻译（保持格式）

用法：
    python krkr_extract.py <游戏目录>     # → <游戏名>_extracted.json
"""
import json, sys, io, os, glob, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mt_config
import krkr_xp3 as X

# 含「可翻文字」判定：假名/汉字/谚文（纯 ASCII 段多为代码/标签残留，跳过）
HAS_LETTER = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
# 标签外文本段切分
TAG_SPLIT = re.compile(r"\[[^\[\]\r\n]*\]")
# 代码块/宏块标签（其内容是 TJS 代码，不是剧情文本）
CODE_BLOCK = re.compile(r"\[\s*(iscript|macro)\b|\[\s*eval\b")
CODE_BLOCK_END = re.compile(r"\[\s*(endscript|endmacro)\b")


def decode_ks(data):
    """检测 .ks 编码 → (text, encoding)"""
    if data[:2] == b"\xff\xfe":
        return data[2:].decode("utf-16-le", "replace"), "utf-16le"
    if data[:3] == b"\xef\xbb\xbf":
        return data[3:].decode("utf-8", "replace"), "utf-8"
    try:
        return data.decode("cp932"), "cp932"
    except UnicodeDecodeError:
        return data.decode("utf-8", "replace"), "utf-8"


def encode_ks(text, encoding):
    """按原编码写回；utf-16le 加 BOM。失败返回 None。"""
    if encoding == "utf-16le":
        return b"\xff\xfe" + text.encode("utf-16-le")
    if encoding == "utf-8":
        return b"\xef\xbb\xbf" + text.encode("utf-8")
    try:
        return text.encode("cp932")
    except UnicodeEncodeError:
        return None


def kag_text_segments(line):
    """一行 → [(start, end, text)] 标签外文本段（含位置便于回写）"""
    out = []
    pos = 0
    for m in TAG_SPLIT.finditer(line):
        seg = line[pos:m.start()]
        if seg:
            out.append((pos, m.start(), seg))
        pos = m.end()
    seg = line[pos:]
    if seg:
        out.append((pos, len(line), seg))
    return out


def translatable(seg):
    t = seg.strip()
    if not t or not HAS_LETTER.search(t):
        return False
    # 纯符号/括号组合（如 「」（）【】…― 等）不翻
    return bool(re.sub(r"[\s「」『』（）()【】《》…―ー、。．，．!！?？・]", "", t))


def extract_ks(text, out):
    """一个 .ks 文本 → 收集可翻段。返回段数。"""
    n = 0
    in_code = False
    for line in text.split("\n"):
        st = line.strip()
        if not st or st[0] in ";*@":
            continue
        if CODE_BLOCK.search(line):
            in_code = True
        if CODE_BLOCK_END.search(line):
            in_code = False
            continue
        if in_code:
            continue
        for _, _, seg in kag_text_segments(line):
            if seg.lstrip().startswith("["):
                continue          # 未闭合标签残留（标签内含 ] 的表达式）
            if translatable(seg):
                out[seg] = ""
                n += 1
    return n


def iter_game_archives(game):
    """游戏目录全部 .xp3，按文件名升序（后挂载覆盖先挂载——Kirikiri 约定）。
    排除本工具自己生成的 patch，防重复回写时把已译段当原文。"""
    arcs = [p for p in sorted(glob.glob(os.path.join(game, "*.xp3")))
            if os.path.basename(p) not in ("patch_zz_automt.xp3", "patch_zz_omnitrans.xp3")]
    return arcs


def effective_files(game, log=print):
    """枚举所有封包条目，后包覆盖前包 → 生效文件集 {name: (archive_path, entry)}"""
    files = {}
    for arc in iter_game_archives(game):
        try:
            with open(arc, "rb") as f:
                for e in X.parse_index(f):
                    files[e.name] = (arc, e)
        except ValueError as ex:
            log(f"  ⚠ 跳过 {os.path.basename(arc)}: {ex}")
    return files


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    game = sys.argv[1] if len(sys.argv) > 1 else "."
    files = effective_files(game)
    scripts = {n: v for n, v in files.items() if n.lower().endswith(".ks")}
    out = {}
    n_enc = n_read = 0
    for name, (arc, e) in sorted(scripts.items()):
        try:
            with open(arc, "rb") as f:
                data = X.read_entry_data(f, e)
        except Exception as ex:
            print(f"  ⚠ 读取失败 {name}: {ex}")
            continue
        text, _ = decode_ks(data)
        n_read += 1
        out_all = {}
        n = extract_ks(text, out_all)
        for k in out_all:
            out.setdefault(k, "")
    base = os.path.basename(os.path.abspath(game).rstrip("/\\"))
    dst = os.path.join(mt_config.base_dir(), f"{base}_extracted.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    chars = sum(len(k) for k in out)
    print(f"封包 {len(iter_game_archives(game))} 个，生效文件 {len(files)}，脚本 {n_read} 个")
    print(f"提取唯一文本段 {len(out)} 条（{chars} 字符）")
    print(f"输出: {dst}")
    print("下一步: python mt_clean.py \"" + os.path.basename(dst) + "\" && python mt_translate.py && python mt_apply.py \"" + os.path.basename(dst) + "\"")


if __name__ == "__main__":
    main()
