# -*- coding: utf-8 -*-
"""
OmniTrans 第一步：文本清洗（掩码）
================================
读取 MTool 导出的原文键值对 json（ManualTransFile.json，格式 {"原文": "译文"}，
未翻译的条目译文为空字符串），生成可供机翻的掩码工作文件。

核心经验（来自实弹项目）：
1. 机翻会吃掉/挪动控制码、换行、占位符 —— 必须先替换成 〔Txxxxxxxx〕 记号
2. 记号用内容哈希（md5 前8位）：同一原文永远同一记号，重跑/增量导出永不失效
3. 人名地名也掩码：否则 Alice 这类人名会被机翻成别的含义
4. 已翻译的条目（译文非空）自动跳过，天然支持断点增量

用法：
    python mt_clean.py [ManualTransFile.json 路径]   默认读当前目录 ManualTransFile.json
输出：
    mt_work/masked.json   待翻条目（记号形态，值为空）
    mt_work/tokens.json   记号->原文 对照表
人名表：
    同目录 names.txt，一行一个英文名，可选
"""
import json, re, sys, io, os, hashlib
import mt_config

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BS = chr(92)

# RPG Maker 控制码 + 任意反斜杠转义（覆盖 \c[n] \v[n] \js<> \. \{ \} \n字面量 等）
MASK_PATTERNS = [
    re.compile(BS * 2 + r'js<[^>]*>'),           # \js<...>
    re.compile(BS * 2 + r'js\[[^\]]*\]'),        # \js[...]
    re.compile(BS * 2 + r'[cCvVnNiI]\[\d+\]'),   # \c[27] \V[36] \N[4] \I[9]
    re.compile(BS * 2 + r'[fgFf][bBiI]\[[^\]]*\]'),  # \fb[...] \fi[...] 等
    re.compile(BS * 2 + r'.'),                   # 其余任意 \x（\.\{\}\| 等停顿/速度码）
]

def stable_tok(orig):
    """内容哈希记号：稳定、可重放、增量安全"""
    return "〔T" + hashlib.md5(orig.encode("utf-8")).hexdigest()[:8] + "〕"

def load_names():
    """每行一个词条，支持两种写法：
       Alice              —— 掩码后还原为原样（保持英文）
       Alice=爱丽丝        —— 掩码后还原为中文译名（推荐）"""
    names = []
    if os.path.exists("names.txt"):
        for line in open("names.txt", encoding="utf-8-sig"):
            n = line.strip()
            if n and not n.startswith("#"):
                names.append(n)
    return names

def mask(s, tokens, names, name_zh):
    parts = s.split("\n")
    out = []
    for pi, part in enumerate(parts):
        if pi:
            t = stable_tok("\n")
            tokens[t] = "\n"
            out.append(t)
        buf = part
        changed = True
        while changed:
            changed = False
            for pat in MASK_PATTERNS:
                m = pat.search(buf)
                if m:
                    t = stable_tok(m.group(0))
                    tokens[t] = m.group(0)
                    buf = buf[:m.start()] + t + buf[m.end():]
                    changed = True
                    break
        for entry in sorted(names, key=len, reverse=True):  # 长名优先，防子串误伤
            en_name, _, zh_name = entry.partition("=")
            if en_name and en_name in buf:
                t = stable_tok(en_name)
                tokens[t] = en_name          # 键还原用：永远是英文原词
                if zh_name:
                    name_zh[en_name] = zh_name  # 值还原用：替换成中文译名
                buf = buf.replace(en_name, t)
        out.append(buf)
    return "".join(out)

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "ManualTransFile.json"
    data = mt_config.load_loose_json(src)
    os.makedirs("mt_work", exist_ok=True)
    names = load_names()
    # 自动人名识别：用户词条优先，未覆盖的高频专名自动掩码（保持原文一致）
    todo = [k for k, v in data.items()
            if isinstance(k, str) and k.strip() and not (isinstance(v, str) and v.strip())]
    user_set = {n.partition("=")[0].strip().lower() for n in names}
    env = mt_config.load_env()
    lang = env.get("MT_SL", "en")
    if "--no-auto-names" in sys.argv or env.get("MT_AUTO_NAMES") == "0":
        auto = []
        print("自动人名识别已关闭（--no-auto-names / MT_AUTO_NAMES=0）：仅使用 names.txt 人工词条")
    else:
        auto = [(w, c) for w, c in mt_config.detect_names(todo, lang)
                if w.lower() not in user_set]
    for w, c in auto:
        names.append(w)
    if auto:
        print(f"自动识别专有名词 {len(auto)} 个（自动保持原文一致，如需译名可加进 names.txt）:")
        print("  " + ", ".join(f"{w}x{c}" for w, c in auto[:30]) + ("…" if len(auto) > 30 else ""))
    tokens = {}
    name_zh = {}
    masked = {}
    for k in todo:
        masked[mask(k, tokens, names, name_zh)] = ""
    # 增量：保留上次已翻的记号条目
    prev_path = "mt_work/masked.json"
    if os.path.exists(prev_path):
        prev = json.load(open(prev_path, encoding="utf-8"))
        kept = 0
        for k in prev:
            if k not in masked and isinstance(prev[k], str) and prev[k].strip():
                continue  # 原文中已消失的条目，不保留
        for k in masked:
            if k in prev and isinstance(prev[k], str) and prev[k].strip():
                masked[k] = prev[k]
                kept += 1
        if kept:
            print(f"保留上次译文: {kept} 条")
    # 合并旧 tokens（增量时旧记号仍被引用）
    if os.path.exists("mt_work/tokens.json"):
        old = json.load(open("mt_work/tokens.json", encoding="utf-8"))
        old.update(tokens)
        tokens = old
    json.dump(masked, open(prev_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(tokens, open("mt_work/tokens.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(name_zh, open("mt_work/names_map.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    chars = sum(len(k) for k in masked)
    print(f"待翻: {len(masked)} 条 / {chars} 字符；记号 {len(tokens)} 个；人名 {len(names)} 个")
    print(f"下一步: python mt_translate.py")

if __name__ == "__main__":
    main()
