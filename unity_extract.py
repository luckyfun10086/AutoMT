# -*- coding: utf-8 -*-
"""
Unity 独立文本提取器
====================
支持：TextAsset（含 JSON 剧本）、MonoBehaviour 内嵌字符串（IL2CPP 无 typetree 也可，
按长度前缀扫描）、StreamingAssets 下的 .bundle（含 Addressables/Unity Localization 字符串表）。

不适用：编译进 DLL 代码里的字符串（需运行时方案）。

用法：
    python unity_extract.py <游戏目录>
输出：
    <游戏名>_extracted.json   {原文: ""}，接 AutoMT 三步管线
    unity_manifest.json        位置清单（回写用，勿删）
"""
import json, sys, io, os, re, glob
import UnityPy
import mt_config

JP = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')
PRINTABLE = re.compile(r'^[ -~\u3000-\u30ff\u4e00-\u9fff\uff00-\uffef'
                       r'，。！？…·—『』「」（）｛｝〈〉《》【】〜゛゜、。\n\r\t ←→↓↑★☆♥♡○●◎◇◆□■※☆♪]+$', re.S)

def find_data_dir(game):
    for cand in os.listdir(game):
        if cand.endswith("_Data") and os.path.isdir(os.path.join(game, cand)):
            return os.path.join(game, cand)
    raise SystemExit(f"未找到 *_Data 目录（不是 Unity 游戏？）: {game}")

def target_files(data_dir):
    out = []
    for f in sorted(os.listdir(data_dir)):
        p = os.path.join(data_dir, f)
        if os.path.isfile(p) and (f.endswith(".assets") or f.startswith("level")
                                  or f == "globalgamemanagers" or f == "resources.assets"):
            if not f.endswith(".resS"):
                out.append(p)
    out += sorted(glob.glob(os.path.join(data_dir, "StreamingAssets", "**", "*.bundle"),
                            recursive=True))
    return out

def scan_prefixed_strings(raw):
    """扫描 MonoBehaviour 原始字节中的 (int32长度 + UTF-8 + 4对齐) 字符串"""
    hits = []
    i = 0
    n = len(raw)
    while i + 4 <= n:
        L = int.from_bytes(raw[i:i+4], "little")
        if 2 <= L <= 4000 and i + 4 + L <= n:
            b = raw[i+4:i+4+L]
            try:
                s = b.decode("utf-8")
            except Exception:
                s = None
            if s and JP.search(s) and len(s) >= 2 and PRINTABLE.match(s):
                # 排除排版字符表（如 TMP LineBreaking：高字符多样性长串，翻了会破坏换行）
                if len(s) > 50 and len(set(s)) / len(s) > 0.6:
                    i += 4 + ((L + 3) // 4) * 4
                    continue
                hits.append((i, s))
                i += 4 + ((L + 3) // 4) * 4
                continue
        i += 4
    return hits

def json_string_values(node, out, key=None):
    if isinstance(node, dict):
        for k, v in node.items():
            json_string_values(v, out, k)
    elif isinstance(node, list):
        for v in node:
            json_string_values(v, out, key)
    elif isinstance(node, str):
        if JP.search(node) and len(node) < 3000:
            out.append(node)

def extract():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    game = sys.argv[1]
    data_dir = find_data_dir(game)
    files = target_files(data_dir)
    print(f"扫描 {len(files)} 个资产/Bundle 文件...")
    strings = {}          # 原文 -> ""（管线输入）
    manifest = []         # {"file","pid","kind", ...}
    for p in files:
        rel = os.path.relpath(p, data_dir)
        try:
            env = UnityPy.load(p)
        except Exception as e:
            print(f"  跳过 {rel}: {e}")
            continue
        dirty = False
        for obj in env.objects:
            t = obj.type.name
            try:
                if t == "MonoBehaviour":
                    raw = obj.get_raw_data()
                    hits = scan_prefixed_strings(raw)
                    if hits:
                        for off, s in hits:
                            strings[s] = ""
                        manifest.append({"file": rel, "pid": obj.path_id,
                                         "kind": "mono-raw",
                                         "items": [{"off": o, "s": s} for o, s in hits]})
                elif t == "TextAsset":
                    d = obj.read()
                    if re.match(r"(?i)^(linebreaking|leading characters|emoji)", d.m_Name or ""):
                        continue
                    script = d.m_Script
                    if isinstance(script, str):
                        txt = script
                    else:
                        txt = script.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
                    if not JP.search(txt):
                        continue
                    t2 = txt.lstrip()
                    if t2[:1] in "{[":
                        try:
                            j = json.loads(txt)
                        except Exception:
                            j = None
                        if j is not None:
                            vals = []
                            json_string_values(j, vals)
                            if vals:
                                for v in vals:
                                    strings[v] = ""
                                manifest.append({"file": rel, "pid": obj.path_id,
                                                 "kind": "textasset-json",
                                                 "name": d.m_Name})
                            continue
                    # 纯文本：按含日文的行收集
                    lines = [ln for ln in txt.split("\n") if JP.search(ln)]
                    if lines:
                        for ln in lines:
                            strings[ln] = ""
                        manifest.append({"file": rel, "pid": obj.path_id,
                                         "kind": "textasset-lines", "name": d.m_Name})
            except Exception:
                continue
    name = os.path.basename(game.rstrip("\\/"))
    dst = os.path.join(mt_config.base_dir(), f"{name}_extracted.json")
    mf = os.path.join(mt_config.base_dir(), "unity_manifest.json")
    json.dump(strings, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(manifest, open(mf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    nfiles = len({m["file"] for m in manifest})
    print(f"收集唯一文本 {len(strings)} 条（分布在 {nfiles} 个文件的 {len(manifest)} 个对象）")
    print(f"输出: {dst}")
    print(f"位置清单: {mf}")
    print(f"下一步: python mt_clean.py \"{dst}\" && python mt_translate.py && "
          f"python mt_apply.py \"{dst}\"")
    print(f"最后:   python unity_apply.py <游戏目录> \"{name}_extracted_translated.json\"")

if __name__ == "__main__":
    extract()
