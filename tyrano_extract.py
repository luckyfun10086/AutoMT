# -*- coding: utf-8 -*-
"""
TyranoScript 文本提取器
=======================
TyranoScript（HTML5 视觉小说引擎）的游戏文本在 data/scenario/*.ks：
- [标签] 外的文本为对话；`;` 注释、`*` 标签行、`#说话人` 行跳过
- [macro]...[endmacro] 内是脚本不翻
- 编码 UTF-8；Character 显示名在 data/system/*.json（一并提取）

用法：
    python tyrano_extract.py <游戏目录>     # → <游戏名>_extracted.json
"""
import json, sys, io, os, glob, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mt_config

TAG_SPLIT = re.compile(r"\[[^\[\]\r\n]*\]")
HAS_LETTER = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7afA-Za-z]")
MACRO_RE = re.compile(r"\[\s*macro\b")
ENDMACRO_RE = re.compile(r"\[\s*endmacro\b")
IScript_RE = re.compile(r"\[\s*(iscript|eval|if|elsif|else|endif|call|jump)\b")

SCENARIO_DIRS = ("data/scenario", "scenario")


def find_scenario(game):
    for d in SCENARIO_DIRS:
        p = os.path.join(game, d)
        if os.path.isdir(p) and glob.glob(os.path.join(p, "**", "*.ks"), recursive=True):
            return p
    raise SystemExit(f"未找到 data/scenario/*.ks：{game}")


def text_segments(line):
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
    return bool(re.sub(r"[\s「」『』（）()【】《》…―ー、。．，．!！?？・]", "", t))


def extract_ks(text, out):
    n = 0
    in_macro = False
    for line in text.split("\n"):
        st = line.strip()
        if not st or st[0] in ";*#@":
            continue
        if MACRO_RE.search(line):
            in_macro = True
        if ENDMACRO_RE.search(line):
            in_macro = False
            continue
        if in_macro or IScript_RE.search(line):
            continue
        for _, _, seg in text_segments(line):
            if translatable(seg):
                out[seg] = ""
                n += 1
    return n


def extract_system_json(game, out):
    """data/system 与 data 下的 json：角色名等 UI 字段"""
    n = 0
    fields = ("name", "jname", "nickname")
    for p in (glob.glob(os.path.join(game, "data", "system", "*.json"))
              + glob.glob(os.path.join(game, "data", "*.json"))):
        try:
            d = json.load(open(p, encoding="utf-8-sig"))
        except Exception:
            continue

        def rec(x):
            nonlocal n
            if isinstance(x, dict):
                for k, v in x.items():
                    if k in fields and isinstance(v, str) and v.strip() \
                            and re.search(r"[\u3040-\u30ff\u3400-\u9fff]", v):
                        out.setdefault(v, "")
                        n += 1
                    else:
                        rec(v)
            elif isinstance(x, list):
                for i in x:
                    rec(i)
        rec(d)
    return n


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    game = sys.argv[1] if len(sys.argv) > 1 else "."
    sc = find_scenario(game)
    out = {}
    n_files = 0
    for f in sorted(glob.glob(os.path.join(sc, "**", "*.ks"), recursive=True)):
        text = open(f, encoding="utf-8-sig", errors="replace").read()
        extract_ks(text, out)
        n_files += 1
    n_sys = extract_system_json(game, out)
    base = os.path.basename(os.path.abspath(game).rstrip("/\\"))
    dst = os.path.join(mt_config.base_dir(), f"{base}_extracted.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    chars = sum(len(k) for k in out)
    print(f"剧本 {n_files} 个 + 系统 json；提取唯一文本 {len(out)} 条（{chars} 字符）")
    print(f"输出: {dst}")
    print("下一步: python mt_clean.py \"" + os.path.basename(dst) + "\" && python mt_translate.py && python mt_apply.py \"" + os.path.basename(dst) + "\"")


if __name__ == "__main__":
    main()
