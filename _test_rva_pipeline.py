# -*- coding: utf-8 -*-
"""rva_extract / rva_apply 全链路自测（合成 VX Ace 游戏样本）
============================================================
1. 用 rvdata.py 构造一个微型 VX Ace Data/ 目录（Map/CommonEvents/Items/Scripts）
2. rva_extract 提取 → 断言文本集合
3. 模拟翻译（加前缀）→ rva_apply 回写
4. 重新解析验证译文就位、控制码/参数原样、未修改文件字节不变
运行：python _test_rva_pipeline.py
"""
import json, sys, io, os, shutil, tempfile, subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rvdata as R

FAILS = []

def check(name, cond, info=""):
    print(("✓ " if cond else "✗ ") + name + (f"  {info}" if info and not cond else ""))
    if not cond:
        FAILS.append(name)

def evcmd(code, params, indent=0):
    return R.MObj(R.MSym("RPG::EventCommand"), [
        (R.MSym("@code"), R.MInt(code)),
        (R.MSym("@indent"), R.MInt(indent)),
        (R.MSym("@parameters"), R.MArray(params))])

def jstr(s):
    return R.MStr(s.encode("utf-8"), [(R.MSym("E"), R.TRUE)])

# ---------------- 构造合成游戏 ----------------
game = tempfile.mkdtemp(prefix="rva_game_")
data = os.path.join(game, "Data")
os.makedirs(data)

# Map1.rvdata2：两张对话（401×2 行合并 + 401×1）、选项 102、地图名
page_list = R.MArray([
    evcmd(0, []),
    evcmd(101, [jstr("Alice"), jstr("Face1"), R.MInt(0), R.MInt(2)]),
    evcmd(401, [jstr("Hello there!")]),
    evcmd(401, [jstr("How are you?")]),
    evcmd(0, []),
    evcmd(401, [jstr("Goodbye.")]),
    evcmd(102, [R.MArray([jstr("Yes"), jstr("No")]), R.MInt(0)]),
    evcmd(320, [R.MInt(1), jstr("Hero")]),
    evcmd(355, [R.MInt(1)]),   # 非文本指令（不含字符串）
])
page = R.MObj(R.MSym("RPG::Event::Page"), [(R.MSym("@list"), page_list)])
event = R.MObj(R.MSym("RPG::Event"), [
    (R.MSym("@name"), jstr("EV001")),
    (R.MSym("@pages"), R.MArray([page])),
])
map1 = R.MObj(R.MSym("RPG::Map"), [
    (R.MSym("@display_name"), jstr("Starting Forest")),
    (R.MSym("@autoplay_bgm"), R.TRUE),
    (R.MSym("@events"), R.MHash([(R.MInt(1), event)])),
    (R.MSym("@table"), R.MUserDef(R.MSym("Table"), bytes([0x01, 0x02, 0x03, 0x84, 0xA0]))),
])
open(os.path.join(data, "Map1.rvdata2"), "wb").write(R.dumps(map1))

# CommonEvents.rvdata2
ce = R.MArray([
    R.MObj(R.MSym("RPG::CommonEvent"), [
        (R.MSym("@name"), jstr("intro")),
        (R.MSym("@list"), R.MArray([
            evcmd(405, [jstr("Scrolling prologue line one")]),
            evcmd(405, [jstr("line two")]),
        ])),
    ]),
    R.NIL,
])
open(os.path.join(data, "CommonEvents.rvdata2"), "wb").write(R.dumps(ce))

# Items.rvdata2：@description
items = R.MArray([
    R.MObj(R.MSym("RPG::Item"), [
        (R.MSym("@id"), R.MInt(1)),
        (R.MSym("@description"), jstr("A red potion.")),
    ]),
])
open(os.path.join(data, "Items.rvdata2"), "wb").write(R.dumps(items))

# Scripts.rvdata2：必须被排除（不提取不回写）
scripts = R.MArray([R.MObj(R.MSym("RPG::Script"), [
    (R.MSym("@name"), jstr("Scene_Map")),
    (R.MSym("@code"), jstr("class Scene_Map; end")),
])])
open(os.path.join(data, "Scripts.rvdata2"), "wb").write(R.dumps(scripts))

orig_bytes = {f: open(os.path.join(data, f), "rb").read()
              for f in os.listdir(data)}

# ---------------- 提取 ----------------
r = subprocess.run([sys.executable, os.path.join(HERE, "rva_extract.py"), game],
                   capture_output=True, text=True, encoding="utf-8", cwd=HERE)
print(r.stdout.strip())
check("提取退出码 0", r.returncode == 0, r.stderr[-300:])
dst = next(l for l in r.stdout.splitlines() if l.startswith("输出:")).split(":", 1)[1].strip()
check("输出文件存在", os.path.exists(dst))
ext = json.load(open(dst, encoding="utf-8"))
expect = {
    "Hello there!\nHow are you?",   # 401×2 合并
    "Goodbye.",                      # 401×1
    "Yes\nNo",                       # 102 选项合并
    "Hero",                          # 320 改名
    "Starting Forest",               # 地图名
    "Scrolling prologue line one\nline two",  # 405×2
    "A red potion.",                 # 物品描述
}
check("提取集合精确匹配", set(ext.keys()) == expect,
      f"got={sorted(ext.keys())}")
check("Scripts/控制码/人名未被提取", all("Scene_Map" not in k and "Alice" not in k for k in ext))

# ---------------- 模拟翻译（逐行加前缀，模拟真实译文的行结构） ----------------
tr = {k: "\n".join("【译】" + ln for ln in k.split("\n")) for k in ext}
trf = dst.replace("_extracted.json", "_translated.json")
json.dump(tr, open(trf, "w", encoding="utf-8"), ensure_ascii=False)

# ---------------- 回写 ----------------
r = subprocess.run([sys.executable, os.path.join(HERE, "rva_apply.py"), game, trf],
                   capture_output=True, text=True, encoding="utf-8", cwd=HERE)
print(r.stdout.strip())
check("回写退出码 0", r.returncode == 0, r.stderr[-300:])

# ---------------- 复检 ----------------
m1 = R.loads(open(os.path.join(data, "Map1.rvdata2"), "rb").read())
ev = m1.ivar("@events").pairs[0][1]
lst = ev.ivar("@pages").items[0].ivar("@list").items
blocks401 = []
texts = {}
for c in lst:
    if isinstance(c, R.MObj):
        code = c.ivar("@code").v
        pr = c.ivar("@parameters")
        if code in (401, 405):
            blocks401.append(pr.items[0].decode())
        if code == 102:
            texts[102] = [x.decode() for x in pr.items[0].items]
        if code == 320:
            texts[320] = pr.items[1].decode()
        if code == 101:
            texts[101] = pr.items[0].decode()   # 角色名：未在提取范围，应保持原文
        if code == 355:
            texts[355] = pr.items[0].v
check("401 合并块回写", blocks401[0] == "【译】Hello there!" and blocks401[1] == "【译】How are you?", blocks401)
check("401 单行回写", blocks401[2] == "【译】Goodbye.", blocks401)
cev = R.loads(open(os.path.join(data, "CommonEvents.rvdata2"), "rb").read())
t405a = cev.items[0].ivar("@list").items[0].ivar("@parameters").items[0].decode()
t405b = cev.items[0].ivar("@list").items[1].ivar("@parameters").items[0].decode()
check("405 滚动文本回写", t405a == "【译】Scrolling prologue line one" and t405b == "【译】line two",
      (t405a, t405b))
check("102 选项回写", texts.get(102) == ["【译】Yes", "【译】No"], texts.get(102))
check("320 改名回写", texts.get(320) == "【译】Hero", texts.get(320))
check("101 人名保持原样", texts.get(101) == "Alice", texts.get(101))
check("355 参数原样", texts.get(355) == 1)
check("地图名回写", m1.ivar("@display_name").decode() == "【译】Starting Forest")
tbl = m1.ivar("@table")
check("Table 二进制原样透传", isinstance(tbl, R.MUserDef) and tbl.data == bytes([0x01, 0x02, 0x03, 0x84, 0xA0]))

it = R.loads(open(os.path.join(data, "Items.rvdata2"), "rb").read())
check("物品描述回写", it.items[0].ivar("@description").decode() == "【译】A red potion.")

check("Scripts.rvdata2 字节不变",
      open(os.path.join(data, "Scripts.rvdata2"), "rb").read() == orig_bytes["Scripts.rvdata2"])
check("备份目录存在", os.path.isdir(os.path.join(game, "Data_backup")))
check("备份内容=原文件",
      open(os.path.join(game, "Data_backup", "Map1.rvdata2"), "rb").read() == orig_bytes["Map1.rvdata2"])

# 清理
shutil.rmtree(game, ignore_errors=True)
for f in (dst, trf):
    if f and os.path.exists(f):
        os.remove(f)
mtw = os.path.join(HERE, "mt_work")
if os.path.isdir(mtw):
    shutil.rmtree(mtw, ignore_errors=True)

print()
if FAILS:
    print(f"✗ {len(FAILS)} 项失败: {FAILS}")
    sys.exit(1)
print("ALL TESTS PASS")
