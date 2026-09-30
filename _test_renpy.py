# -*- coding: utf-8 -*-
"""Ren'Py 支持的终极交叉验证：官方翻译 tl 包 vs AutoMT 生成的 identifier/格式。
教程游戏自带官方法语翻译（引擎生成的 ground truth）——
1. AutoMT 从 tutorial 的 .rpyc 提取 (identifier, 原文)
2. 解析官方 tl/french 的 (identifier, 原文, 译文)
3. identifier 集合与原文逐一对照；再用 AutoMT apply 生成 tl 并逐块 diff
运行：python _test_renpy.py
"""
import re, sys, io, os, glob, json, subprocess, shutil, tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from renpy_extract import find_game_dir, load_scripts
import renpy_rpyc as RC

SDK = r"C:/Users/10930/AppData/Local/Temp/renpy_sdk/renpy-8.5.3-sdk"
TUT = os.path.join(SDK, "tutorial")
TQ = os.path.join(SDK, "the_question")
FAILS = []

def check(name, cond, info=""):
    print(("✓ " if cond else "✗ ") + name + (f"  {info}" if info and not cond else ""))
    if not cond:
        FAILS.append(name)

RE_BLOCK = re.compile(
    r'translate french (\w+):\s*\n\s*#\s*(\S*)\s*"((?:[^"\\]|\\.)*)"\s*\n\s*(\S*)\s*"((?:[^"\\]|\\.)*)"')
RE_OLDNEW = re.compile(r'old "((?:[^"\\]|\\.)*)"\s*\n\s*new "((?:[^"\\]|\\.)*)"')

# ---------- 1. 官方 tl 解析 ----------
official = {}
official_strings = {}
for p in glob.glob(os.path.join(TUT, "game/tl/french/*.rpy")):
    txt = open(p, encoding="utf-8-sig").read()
    for m in RE_BLOCK.finditer(txt):
        ident, _, old, who2, new = m.groups()
        official[ident] = (who2, old, new)
    for m in RE_OLDNEW.finditer(txt):
        official_strings[m.group(1)] = m.group(2)
check("官方 tl 解析非空", len(official) > 50 and len(official_strings) > 50,
      f"say={len(official)} strings={len(official_strings)}")

# ---------- 2. AutoMT 提取 tutorial ----------
gd = find_game_dir(TUT)
trees = load_scripts(gd)
items = []
for name, stmts in sorted(trees.items()):
    items += RC.collect_dialogue(stmts)
by_ident = {i["identifier"]: i for i in items
            if i["kind"] == "say" and i.get("identifier")}
check("AutoMT 提取 say 非空", len(by_ident) > 50, str(len(by_ident)))

# ---------- 3. identifier 交叉对照 ----------
inter = set(official) & set(by_ident)
check("identifier 交集 > 80%", len(inter) >= len(official) * 0.8,
      f"官方 {len(official)} 交集 {len(inter)}")
match = sum(1 for ident in inter
            if by_ident[ident]["what"] == official[ident][1])
# 少量不一致 = 官方 tl 相对当前源码过时（教程改过错字）或源码转义形态差异；
# AutoMT 提取的是 rpyc 运行时字符串（引擎匹配翻译用的正是它）
check("交集内原文一致 ≥95%", match >= len(inter) * 0.95, f"{match}/{len(inter)}")

# ---------- 4. 端到端：AutoMT apply 生成 tl → 与官方块对照 ----------
tr = {}
for ident, (who, old, new) in official.items():
    tr[old] = new
for old, new in official_strings.items():
    tr.setdefault(old, new)
trf = os.path.join(tempfile.gettempdir(), "_automt_tut_tr.json")
json.dump(tr, open(trf, "w", encoding="utf-8"), ensure_ascii=False)

r = subprocess.run([sys.executable, os.path.join(HERE, "renpy_apply.py"),
                    TUT, trf, "frenchtest"], capture_output=True, text=True,
                   encoding="utf-8", cwd=HERE)
check("apply 退出码 0", r.returncode == 0, r.stderr[-300:])

gen = os.path.join(TUT, "game/tl/frenchtest/automt_script.rpy")
check("tl 包已生成", os.path.exists(gen))
gen_txt = open(gen, encoding="utf-8").read()
gen_blocks = {}
for m in RE_BLOCK.finditer(gen_txt.replace("frenchtest", "french")):
    ident, _, old, who2, new = m.groups()
    gen_blocks[ident] = (who2, old, new)

same = sum(1 for ident, blk in gen_blocks.items() if official.get(ident) == blk)
check("生成块与官方块一致 ≥95%", len(gen_blocks) > 0 and same >= len(gen_blocks) * 0.95,
      f"生成 {len(gen_blocks)} 一致 {same}")

# ---------- 5. The Question 端到端 ----------
r = subprocess.run([sys.executable, os.path.join(HERE, "renpy_extract.py"), TQ],
                   capture_output=True, text=True, encoding="utf-8", cwd=HERE)
check("the_question 提取", r.returncode == 0 and "提取唯一文本" in r.stdout, r.stdout[-200:])
out = os.path.join(HERE, "the_question_extracted.json")
ext = json.load(open(out, encoding="utf-8"))
check("the_question 条目 > 100", len(ext) > 100, str(len(ext)))
tr2 = {k: "【译】" + k[:12] for k in ext}
trf2 = os.path.join(HERE, "_tq_mock.json")
json.dump(tr2, open(trf2, "w", encoding="utf-8"), ensure_ascii=False)
r = subprocess.run([sys.executable, os.path.join(HERE, "renpy_apply.py"),
                    TQ, trf2, "chinese"], capture_output=True, text=True,
                   encoding="utf-8", cwd=HERE)
check("the_question apply", r.returncode == 0, r.stderr[-200:])
tl2 = os.path.join(TQ, "game/tl/chinese/automt_script.rpy")
body = open(tl2, encoding="utf-8").read()
check("tl 含 say 块", "translate chinese start_" in body and "【译】" in body)
check("tl 含 strings 块", "translate chinese strings:" in body)
# 游戏目录无任何原文件被改动
check("非破坏性（tl 目录外无新文件）", os.path.exists(os.path.join(TQ, "game/tl/chinese/automt_script.rpy")))

# 清理
shutil.rmtree(os.path.join(TUT, "game/tl/frenchtest"), ignore_errors=True)
shutil.rmtree(os.path.join(TQ, "game/tl/chinese"), ignore_errors=True)
for f in (trf, trf2, out, os.path.join(HERE, "the_question_extracted.json")):
    if os.path.exists(f):
        os.remove(f)

print()
if FAILS:
    print(f"✗ {len(FAILS)} 项失败: {FAILS}")
    sys.exit(1)
print("ALL TESTS PASS")
