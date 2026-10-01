# -*- coding: utf-8 -*-
"""
Unity 独立回写器
================
按 unity_manifest.json 的位置把译文写回资产（MonoBehaviour 长前缀串原位重建 /
TextAsset JSON 值替换 / 纯文本行替换），UnityPy 重打包，原文件备份 .automt.bak。

用法：
    python unity_apply.py <游戏目录> <译文json>
"""
import os, sys
_ENG = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_ENG))    # 项目根：mt_config 等
sys.path.insert(0, _ENG)                     # 引擎同目录：krkr_xp3 等

import json, sys, io, os, re, shutil
import UnityPy
import mt_config
from unity_extract import (find_data_dir, json_string_values, JP)

def rebuild_prefixed(raw, items, tr, stat):
    """按偏移降序替换长度前缀串；返回(新bytes, 命中数, 跳过数)"""
    out = raw
    ok = skip = 0
    for it in sorted(items, key=lambda x: -x["off"]):
        off, s = it["off"], it["s"]
        zh = tr.get(s, "")
        if not (isinstance(zh, str) and zh.strip()):
            continue
        L = int.from_bytes(out[off:off+4], "little")
        old_pad = (L + 3) // 4 * 4
        if out[off+4:off+4+L].decode("utf-8", "replace") != s:
            skip += 1
            continue
        nb = zh.encode("utf-8")
        new_pad = (len(nb) + 3) // 4 * 4
        pad = b"\x00" * (new_pad - len(nb))
        out = out[:off] + len(nb).to_bytes(4, "little") + nb + pad + out[off+4+old_pad:]
        ok += 1
    return out, ok, skip

def apply_textasset_json(txt, tr):
    j = json.loads(txt)
    cnt = [0]
    def rep(n):
        if isinstance(n, dict):
            for k in list(n):
                v = n[k]
                if isinstance(v, str) and JP.search(v):
                    zh = tr.get(v, "")
                    if isinstance(zh, str) and zh.strip():
                        n[k] = zh
                        cnt[0] += 1
                else:
                    rep(v)
        elif isinstance(n, list):
            for i, v in enumerate(n):
                if isinstance(v, str) and JP.search(v):
                    zh = tr.get(v, "")
                    if isinstance(zh, str) and zh.strip():
                        n[i] = zh
                        cnt[0] += 1
                else:
                    rep(v)
    rep(j)
    return json.dumps(j, ensure_ascii=False, indent=2), cnt[0]

def save_env_to(env, p):
    """安全保存：先完整产出临时文件，再原子替换目标（绝不在产出前截断原文件）"""
    import tempfile
    if type(env.file).__name__ == "BundleFile":
        data = env.file.save()
        tmp = p + ".automt.tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, p)
    else:
        with tempfile.TemporaryDirectory() as td:
            env.save(out_path=td)
            produced = os.listdir(td)
            fn = os.path.basename(p)
            if fn in produced:
                src = os.path.join(td, fn)
            elif len(produced) == 1:
                src = os.path.join(td, produced[0])   # 内存加载时文件名为内部哈希
            else:
                raise RuntimeError(f"env.save 产出异常 {produced}（期望 {fn}）")
            tmp = p + ".automt.tmp"
            shutil.copy2(src, tmp)
            os.replace(tmp, p)

def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    game = sys.argv[1]
    trfile = sys.argv[2]
    tr = mt_config.load_loose_json(trfile)
    data_dir = find_data_dir(game)
    mf_path = os.path.join(mt_config.base_dir(), "unity_manifest.json")
    manifest = json.load(open(mf_path, encoding="utf-8"))

    by_file = {}
    for m in manifest:
        by_file.setdefault(m["file"], []).append(m)

    stat = {"mono": 0, "skip": 0, "json": 0, "lines": 0, "files": 0}
    for rel, entries in sorted(by_file.items()):
        p = os.path.join(data_dir, rel)
        if not os.path.exists(p):
            print(f"  缺失 {rel}，跳过")
            continue
        with open(p, "rb") as f:
            env = UnityPy.load(f.read())   # 从内存加载，避免文件锁
        changed = False
        for m in entries:
            obj = next((o for o in env.objects if o.path_id == m["pid"]), None)
            if obj is None:
                continue
            if m["kind"] == "mono-raw":
                raw = obj.get_raw_data()
                new, ok, skip = rebuild_prefixed(raw, m["items"], tr, stat)
                if ok:
                    obj.set_raw_data(new)
                    stat["mono"] += ok
                    stat["skip"] += skip
                    changed = True
            elif m["kind"] == "textasset-json":
                d = obj.read()
                txt = d.m_Script if isinstance(d.m_Script, str) else \
                    d.m_Script.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
                new_txt, n = apply_textasset_json(txt, tr)
                if n:
                    stat["json"] += n
                    if isinstance(d.m_Script, str):
                        d.m_Script = new_txt
                    else:
                        d.m_Script = new_txt.encode("utf-8", "surrogateescape").decode("utf-16", "surrogatepass")
                    obj.save_typetree(d.__dict__) if False else obj.save()
                    changed = True
            elif m["kind"] == "textasset-lines":
                d = obj.read()
                txt = d.m_Script if isinstance(d.m_Script, str) else \
                    d.m_Script.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
                lines = txt.split("\n")
                n = 0
                for i, ln in enumerate(lines):
                    if JP.search(ln):
                        zh = tr.get(ln, "")
                        if isinstance(zh, str) and zh.strip():
                            lines[i] = zh.split("\n")[0]
                            n += 1
                if n:
                    stat["lines"] += n
                    new_txt = "\n".join(lines)
                    if isinstance(d.m_Script, str):
                        d.m_Script = new_txt
                    obj.save()
                    changed = True
        if changed:
            bak = p + ".automt.bak"
            if not os.path.exists(bak):
                shutil.copy2(p, bak)
            save_env_to(env, p)
            stat["files"] += 1
            print(f"  已写回 {rel}（备份 .automt.bak）")
    print(f"完成：MonoBehaviour串 {stat['mono']}（跳过 {stat['skip']}），"
          f"JSON值 {stat['json']}，文本行 {stat['lines']}，共改 {stat['files']} 个文件")
    print("进游戏验证；异常时把对应文件的 .automt.bak 改回原名即可还原。")

if __name__ == "__main__":
    main()
