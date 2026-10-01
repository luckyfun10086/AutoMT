# -*- coding: utf-8 -*-
"""TyranoScript 提取/回写自测（合成游戏样本）
运行：python _test_tyrano.py
"""
import json, sys, io, os, shutil, tempfile, subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENG = os.path.join(ROOT, "engines")
sys.path.insert(0, ROOT)
sys.path.insert(0, ENG)

FAILS = []

def check(name, cond, info=""):
    print(("✓ " if cond else "✗ ") + name + (f"  {info}" if info and not cond else ""))
    if not cond:
        FAILS.append(name)

# ---------------- 合成 Tyrano 游戏 ----------------
game = tempfile.mkdtemp(prefix="tyrano_game_")
sc = os.path.join(game, "data", "scenario")
os.makedirs(sc)
KS = "\n".join([
    ";comment line",
    "*start",
    "#akari",
    "今日はいい天気ですね。[p]",
    "[bg storage=room.jpg time=800]",
    "[chara_show name=akari]",
    "はい、そうです。[l][r]",
    "選択して下さい：",
    "[link target=a]はい[endlink][r]",
    "[macro name=test]",
    "マクロ内テキスト",
    "[endmacro]",
    "タグと[emb exp=\"x\"]テキストの混在行",
    "[eval exp=\"f.x = 1\"]",
])
open(os.path.join(sc, "first.ks"), "w", encoding="utf-8").write(KS)
os.makedirs(os.path.join(game, "data", "system"), exist_ok=True)
json.dump({"charas": [{"name": "akari", "jname": "あかり"}]},
          open(os.path.join(game, "data", "system", "chara.json"), "w", encoding="utf-8"))

r = subprocess.run([sys.executable, os.path.join(ENG, "tyrano_extract.py"), game],
                   capture_output=True, text=True, encoding="utf-8", cwd=HERE)
print(r.stdout.strip())
check("提取退出码 0", r.returncode == 0, r.stderr[-300:])
import glob
dst = glob.glob(os.path.join(ROOT, "tyrano_game_*_extracted.json"))[0]
ext = json.load(open(dst, encoding="utf-8"))
expect = {"今日はいい天気ですね。", "はい、そうです。", "選択して下さい：",
          "はい", "タグと", "テキストの混在行", "あかり"}
check("提取集合", set(ext.keys()) == expect, sorted(ext.keys()))

# ---------------- mock 翻译 + 回写 ----------------
tr = {k: "【译】" + k for k in ext}
trf = os.path.join(HERE, "tyrano_mock.json")
json.dump(tr, open(trf, "w", encoding="utf-8"), ensure_ascii=False)
r = subprocess.run([sys.executable, os.path.join(ENG, "tyrano_apply.py"), game, trf],
                   capture_output=True, text=True, encoding="utf-8", cwd=HERE)
print(r.stdout.strip())
check("回写退出码 0", r.returncode == 0, r.stderr[-300:])

after = open(os.path.join(sc, "first.ks"), encoding="utf-8").read()
check("译文就位", "【译】今日はいい天気ですね。[p]" in after)
check("标签保持", "[bg storage=room.jpg time=800]" in after)
check("混在行两段都翻", "【译】タグと[emb exp=\"x\"]【译】テキストの混在行" in after)
check("宏内未翻", "マクロ内テキスト" in after)
check("备份存在", os.path.exists(os.path.join(sc, "first.ks.automt.bak")))
check("备份=原文", json.dumps("今日はいい天気ですね。" in open(
    os.path.join(sc, "first.ks.automt.bak"), encoding="utf-8").read()))

shutil.rmtree(game, ignore_errors=True)
for f in (dst, trf):
    if os.path.exists(f):
        os.remove(f)

print()
if FAILS:
    print(f"✗ {len(FAILS)} 项失败: {FAILS}")
    sys.exit(1)
print("ALL TESTS PASS")
