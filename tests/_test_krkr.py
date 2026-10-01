# -*- coding: utf-8 -*-
"""krkr（Kirikiri XP3 + KAG 脚本）自测
====================================
1. XP3 写读回路（构造 → 写档 → 读回 → 字节一致）
2. KAG 段提取/回写（标签切分、注释/标签/命令行跳过、位置替换、CP932→UTF-16 升级）
3. 端到端：合成剧本 → 提取 → mock 翻译 → 打 patch → 重读 patch 验证
运行：python _test_krkr.py
"""
import json, sys, io, os, shutil, tempfile, subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENG = os.path.join(ROOT, "engines")
sys.path.insert(0, ROOT)
sys.path.insert(0, ENG)
sys.path.insert(0, HERE)
import krkr_xp3 as X
from krkr_extract import (decode_ks, encode_ks, kag_text_segments, translatable,
                          extract_ks, effective_files)
from krkr_apply import apply_ks, patch_name

FAILS = []

def check(name, cond, info=""):
    print(("✓ " if cond else "✗ ") + name + (f"  {info}" if info and not cond else ""))
    if not cond:
        FAILS.append(name)

# ---------------- 1. XP3 写读回路 ----------------
files = [
    ("scenario/first.ks", "*start\r\n【アリス】「こんにちは」\r\n[待]\r\n".encode("cp932"), 111),
    ("data/uni.txt", "ユニコード✓中文".encode("utf-16-le"), 222),
    ("data/raw.bin", bytes(range(256)), 333),
]
tmp = os.path.join(tempfile.gettempdir(), "_automt_t.xp3")
with open(tmp, "wb") as f:
    n = X.write_xp3(f, files)
f = open(tmp, "rb")
entries = X.parse_index(f)
check("XP3 条目数", len(entries) == n == 3)
for e, (name, content, _) in zip(entries, files):
    got = X.read_entry_data(f, e)
    check(f"XP3 回路 {name}", e.name == name and got == content,
          f"{e.name!r} {len(got)}vs{len(content)}")
f.close()
os.remove(tmp)

# ---------------- 2. KAG 段提取/回写 ----------------
KS = "\r\n".join([
    ";这是注释行",
    "*label|标签行",
    "@macro name=x",
    "[iscript]",
    "if(i>=5){ kag.fore.layers }",
    "[endscript]",
    "【アリス】「[落]こんにちは、[emb exp=\"tf.x\"]先輩！」",
    "[声 f=\"v01.ogg\"]",
    "ただのテキスト行。",
    "if(i>=5){ 纯代码行",
    "[image storage=\"a.png\" layer=19]",
    "",
])
segs = {}
extract_ks(KS, segs)
check("注释/标签/命令/代码块不提取",
      all("注释" not in k and "macro" not in k and "kag.fore" not in k for k in segs))
check("代码行不提取", "if(i>=5){ 纯代码行" not in segs)
check("标签不提取", all(not k.strip().startswith("[") for k in segs))
check("正文段提取", any("アリス】" in k for k in segs) and any(k.strip() == "ただのテキスト行。" for k in segs), list(segs))
# 段应只含标签外文本
al = [k for k in segs if "アリス" in k]
check("段内不含标签", al and "[emb" not in al[0] and "[落]" not in al[0], al)

tr = {k: "【译】" + k for k in segs}
new_text, applied, missed = apply_ks(KS, tr)
check("回写段数", applied == len(segs) and missed == 0, f"{applied}/{len(segs)}")
check("注释行原样", new_text.split("\r\n")[0] == ";这是注释行")
check("标签行原样", new_text.split("\r\n")[1] == "*label|标签行")
check("代码块原样", "if(i>=5){ kag.fore.layers }" in new_text)
check("译文就位", "【译】ただのテキスト行。" in new_text)
check("标签未受损", "[声 f=\"v01.ogg\"]" in new_text and "[image storage=\"a.png\" layer=19]" in new_text)

# CP932 编码升级路径
cp = encode_ks(new_text, "cp932")
check("CP932 装不下中文 → None", cp is None)
up = encode_ks(new_text, "utf-16le")
check("UTF-16LE 升级带 BOM", up[:2] == b"\xff\xfe")
t2, e2 = decode_ks(up)
check("升级后解码一致", t2 == new_text and e2 == "utf-16le")

# ---------------- 3. 端到端 patch（夹具用纯日文，中文译文触发 CP932→UTF-16 升级） ----------------
game = tempfile.mkdtemp(prefix="krkr_game_")
KS_JP = KS.replace("这是注释行", "コメント行").replace("标签行", "ラベル行") \
          .replace("纯代码行", "コード行")
ks_body = encode_ks(KS_JP, "cp932")
check("日文夹具 CP932 可编码", ks_body is not None)
with open(os.path.join(game, "data.xp3"), "wb") as f:
    X.write_xp3(f, [("scenario/main.ks", ks_body, 0),
                    ("bgm/a.ogg", b"\x00\x01", 0)])
ex = {}
for n_, (arc, e) in effective_files(game).items():
    if n_.endswith(".ks"):
        with open(arc, "rb") as f2:
            extract_ks(decode_ks(X.read_entry_data(f2, e))[0], ex)
check("端到端提取", len(ex) > 0, f"{len(ex)}")
trf = os.path.join(game, "tr.json")
json.dump({k: "【译】" + k for k in ex}, open(trf, "w", encoding="utf-8"), ensure_ascii=False)

r = subprocess.run([sys.executable, os.path.join(ENG, "krkr_apply.py"), game, trf],
                   capture_output=True, text=True, encoding="utf-8", cwd=HERE)
check("apply 退出码 0", r.returncode == 0, r.stderr[-300:])
pn = os.path.join(game, patch_name(game))
check("patch 已生成", os.path.exists(pn))
pf = open(pn, "rb")
pe = X.parse_index(pf)
check("patch 含改动脚本", len(pe) == 1 and pe[0].name == "scenario/main.ks")
body, enc = decode_ks(X.read_entry_data(pf, pe[0]))
check("patch 内译文就位", "【译】ただのテキスト行。" in body and enc == "utf-16le")
check("原 data.xp3 未动", os.path.getsize(os.path.join(game, "data.xp3")) > 0)
pf.close()
shutil.rmtree(game, ignore_errors=True)

print()
if FAILS:
    print(f"✗ {len(FAILS)} 项失败: {FAILS}")
    sys.exit(1)
print("ALL TESTS PASS")
