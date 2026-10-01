# -*- coding: utf-8 -*-
"""独立提取/回写器测试：构造合成 RPG MV data 目录，走 提取→假翻译→回写 全链路"""
import io, sys, json, os, tempfile, shutil, importlib.util
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "engines", f"{name}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

rx = load("rpg_extract")
ra = load("rpg_apply")

tmp = tempfile.mkdtemp()
game = os.path.join(tmp, "MyGame")
data = os.path.join(game, "data")
os.makedirs(data)

# 合成 Map001.json：两段对话（多行合并）、一个选项、一个改名
map1 = {
    "displayName": "Starting Village",
    "events": [None, {"pages": [{"list": [
        {"code": 101, "parameters": ["Actor1", 0, 0, 2]},
        {"code": 401, "parameters": ["Hello, hero!"]},
        {"code": 401, "parameters": ["Welcome to the village."]},
        {"code": 0, "parameters": []},
        {"code": 102, "parameters": [["Yes.", "No."], 1, 0]},
        {"code": 320, "parameters": [1, "Hero"]},
    ]}]}, {"pages": [{"list": [
        {"code": 405, "parameters": ["The world is at stake."]},
    ]}]}],
}
json.dump(map1, open(os.path.join(data, "Map001.json"), "w", encoding="utf-8"))
json.dump([{"name": "CE1", "list": [
    {"code": 401, "parameters": ["Common event line."]},
]}], open(os.path.join(data, "CommonEvents.json"), "w", encoding="utf-8"))

# 1) 提取
out, stats = rx.extract(data)
expect = {
    "Hello, hero!\nWelcome to the village.",
    "Yes.\nNo.",
    "Hero",
    "Starting Village",
    "The world is at stake.",
    "Common event line.",
}
assert set(out.keys()) == expect, (set(out.keys()), expect)
print("提取 ✓  唯一文本", len(out), "条；401 两行已合并:", "Hello, hero!\nWelcome to the village." in out)

# 2) 假翻译（前缀"译"，多行块行数保持一致）
tr = {}
for k in out:
    tr[k] = "\n".join("译<" + ln + ">" for ln in k.split("\n"))
tr["坏行数"] = "x"   # 不应被使用

# 3) 回写（模拟 main 的核心流程：载入→应用→落盘）
ra.APPLIED["n"] = 0
ra.SKIPPED["n"] = 0
for f in [os.path.join(data, "Map001.json"), os.path.join(data, "CommonEvents.json")]:
    d = json.load(open(f, encoding="utf-8"))
    if "Map" in os.path.basename(f):
        dn = d.get("displayName")
        if dn and tr.get(dn, "").strip():
            d["displayName"] = tr[dn]
        for ev in d.get("events", []):
            if ev:
                for pg in ev.get("pages", []):
                    ra.apply_to_list(pg.get("list", []), tr)
    else:
        for item in d:
            ra.apply_to_list(item["list"], tr)
    json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False)

d1 = json.load(open(os.path.join(data, "Map001.json"), encoding="utf-8"))
pg = d1["events"][1]["pages"][0]["list"]
assert pg[1]["parameters"][0] == "译<Hello, hero!>", pg[1]
assert pg[2]["parameters"][0] == "译<Welcome to the village.>", pg[2]
assert pg[4]["parameters"][0] == ["译<Yes.>", "译<No.>"], pg[4]
assert pg[5]["parameters"][1] == "译<Hero>", pg[5]
assert d1["displayName"] == "译<Starting Village>"
d2 = json.load(open(os.path.join(data, "CommonEvents.json"), encoding="utf-8"))
assert d2[0]["list"][0]["parameters"][0] == "译<Common event line.>"
print("回写 ✓  对话/选项/改名/地图名/公共事件全部正确；APPLIED =", ra.APPLIED["n"])

# 4) 行数不齐跳过保护
cmds = [{"code": 401, "parameters": ["a"]}, {"code": 401, "parameters": ["b"]}]
ra.APPLIED["n"] = ra.SKIPPED["n"] = 0
ra.apply_to_list(cmds, {"a\nb": "只有一行"})
assert cmds[0]["parameters"][0] == "a" and ra.SKIPPED["n"] == 1
print("行数保护 ✓")

shutil.rmtree(tmp)
print("ALL TESTS PASS")
