# -*- coding: utf-8 -*-
"""Wolf RPG 引擎自测（需外部样本，自动下载官方编辑器包 ~30MB，缓存复用）
=====================================================================
样本：Wolf RPG Editor 3.728 官方基本系统（明文 Data，Wolf 3.x 形态）
覆盖：注册表 → 提取 → mock 翻译 → 回写 → 复检 → 编码警告不误报
缓存不存在且无法下载时 SKIP（打印说明）。
运行：python tests/_test_wolf.py
"""
import os, sys, io, json, glob, shutil, zipfile, tempfile, subprocess, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENG = os.path.join(ROOT, "engines")
sys.path.insert(0, ROOT)
sys.path.insert(0, ENG)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

CACHE = os.path.join(tempfile.gettempdir(), "omnitrans_wolf_sample", "WOLF_RPG_Editor3", "Data")
URL = "https://www.silversecond.com/WolfRPGEditor/Data/WolfRPGEditor_3.728.zip"

def get_sample():
    if os.path.isdir(CACHE) and glob.glob(os.path.join(CACHE, "BasicData", "*.dat")):
        return CACHE
    z = os.path.join(tempfile.gettempdir(), "omnitrans_wolf_editor.zip")
    if not os.path.exists(z):
        try:
            print(f"[setup] 下载官方编辑器包（一次性，~30MB）…")
            with urllib.request.urlopen(URL, timeout=300) as r, open(z, "wb") as f:
                shutil.copyfileobj(r, f)
        except Exception as e:
            return None
    dest = os.path.dirname(CACHE)
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            if "/Data/BasicData/" in n or "/Data/MapData/" in n:
                zf.extract(n, dest)
    return CACHE if glob.glob(os.path.join(CACHE, "BasicData", "*.dat")) else None

sample = get_sample()
if not sample:
    print("SKIP：Wolf 样本不可用（下载失败/离线）。缓存路径：" + CACHE)
    sys.exit(0)

FAILS = []
def check(name, cond, info=""):
    print(("✓ " if cond else "✗ ") + name + (f"  {info}" if info and not cond else ""))
    if not cond:
        FAILS.append(name)

# 1) 引擎注册
import mt_config
e = mt_config.ENGINES.get("wolf")
check("注册表", e and e["supported"] and e["extractor"].endswith("wolf_extract.py"))

# 2) 干净游戏副本
game = tempfile.mkdtemp(prefix="wolf_t_")
shutil.copytree(sample, os.path.join(game, "Data"))

def run(*args):
    r = subprocess.run([sys.executable] + list(args), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    if r.returncode:
        print(r.stdout[-300:], r.stderr[-300:])
    return r

r = run(os.path.join(ENG, "wolf_extract.py"), game)
check("提取退出码 0", r.returncode == 0)
base = os.path.basename(game)
ext = os.path.join(ROOT, f"{base}_extracted.json")
check("输出存在", os.path.exists(ext))
d = json.load(open(ext, encoding="utf-8"))
check("提取条数 > 300", len(d) > 300, str(len(d)))

# 3) mock 翻译 → 回写 → 复检
tr = {}
for i, k in enumerate(d):
    if i >= 10:
        break
    tr[k] = "\n".join("【测】" + ln for ln in k.split("\n"))
trf = os.path.join(ROOT, "_wolf_t.json")
json.dump(tr, open(trf, "w", encoding="utf-8"), ensure_ascii=False)
r = run(os.path.join(ENG, "wolf_apply.py"), game, trf)
check("回写退出码 0", r.returncode == 0)
check("无编码误报（3.x 样本）", "编码警告" not in (r.stdout or ""))
check("备份存在", os.path.isdir(os.path.join(game, "Data.automt.bak")))

for f in glob.glob(os.path.join(ROOT, f"{base}_*")):
    os.remove(f)
shutil.rmtree(os.path.join(ROOT, "wolf_work"), ignore_errors=True)
run(os.path.join(ENG, "wolf_extract.py"), game)
d2 = json.load(open(ext, encoding="utf-8"))
hits = sum(1 for k in d2 if str(k).startswith("【测】"))
check("复检译文存活 ≥8/10", hits >= 8, str(hits))

for f in glob.glob(os.path.join(ROOT, f"{base}_*")) + [trf]:
    if os.path.exists(f):
        os.remove(f)
shutil.rmtree(os.path.join(ROOT, "wolf_work"), ignore_errors=True)
shutil.rmtree(game, ignore_errors=True)

print()
if FAILS:
    print(f"✗ {len(FAILS)} 项失败: {FAILS}")
    sys.exit(1)
print("ALL TESTS PASS")
