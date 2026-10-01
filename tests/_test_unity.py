# -*- coding: utf-8 -*-
"""Unity 适配器沙箱测试：level0 资产 + localization bundle 各打标记→保存→重载验证"""
import io, sys, os, re, shutil, importlib.util

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import UnityPy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "engines", f"{name}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

ua = load("unity_apply")
JP = re.compile(r'[\u3040-\u30ff]')

sb = os.path.join(os.path.dirname(__file__), "_unity_sandbox")
shutil.rmtree(sb, ignore_errors=True)
os.makedirs(sb)
G = r"E:\Ggame\隐身潜入改造\ステルス改変アプリ\StealthModificationApp_Data"

def find_jp_string(raw):
    i = 0
    while i + 4 <= len(raw):
        L = int.from_bytes(raw[i:i+4], "little")
        if 4 <= L <= 200 and i + 4 + L <= len(raw):
            try:
                s = raw[i+4:i+4+L].decode("utf-8")
                if JP.search(s) and 3 < len(s) < 50 and "\n" not in s:
                    return i, s
            except Exception:
                pass
        i += 4
    return None, None

def patch_file(path, tag, maxobjs=3):
    with open(path, "rb") as f:
        env = UnityPy.load(f.read())
    hits = 0
    for o in env.objects:
        if o.type.name == "MonoBehaviour":
            off, s = find_jp_string(o.get_raw_data())
            if off is not None:
                new, ok, skip = ua.rebuild_prefixed(o.get_raw_data(),
                                                    [{"off": off, "s": s}],
                                                    {s: tag + s}, None)
                assert ok == 1, (ok, s)
                o.set_raw_data(new)
                hits += 1
                if hits >= maxobjs:
                    break
    assert hits > 0, "未找到可标记对象"
    ua.save_env_to(env, path)
    return hits, s

def verify(path, tag):
    with open(path, "rb") as f:
        env = UnityPy.load(f.read())
    n = 0
    for o in env.objects:
        if o.type.name == "MonoBehaviour":
            if tag.encode("utf-8") in o.get_raw_data():
                n += 1
    return n

# 1) 普通资产文件
p1 = os.path.join(sb, "level0")
shutil.copy2(os.path.join(G, "level0"), p1)
hits, sample = patch_file(p1, "【测】")
n = verify(p1, "【测】")
print(f"资产文件: 标记 {hits} 个（样例 {sample!r}），重载后找到 {n} 个 ✓")

# 2) localization bundle
p2 = os.path.join(sb, "ja.bundle")
shutil.copy2(os.path.join(G, "StreamingAssets", "aa", "StandaloneWindows64",
                          "localization-string-tables-japanese(ja)_assets_all.bundle"), p2)
hits2, sample2 = patch_file(p2, "【束】")
n2 = verify(p2, "【束】")
print(f"Bundle: 标记 {hits2} 个（样例 {sample2!r}），重载后找到 {n2} 个 ✓")
print(f"Bundle 大小: 原 {os.path.getsize(os.path.join(G,'StreamingAssets','aa','StandaloneWindows64','localization-string-tables-japanese(ja)_assets_all.bundle'))} -> 新 {os.path.getsize(p2)}")

shutil.rmtree(sb)
print("ALL TESTS PASS")
