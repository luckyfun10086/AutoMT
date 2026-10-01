# -*- coding: utf-8 -*-
"""mtool_export 合成回环测试
============================
1. 变体生成：行拆分 / 行首码剥离 / 全码剥离，原键不被覆盖
2. 模拟 MTool 查键：对假设 MTool 持有的各种形态键，查表命中率 100%
运行：python _test_mtoolexport.py
"""
import os, sys, io, json, subprocess, tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENG = os.path.join(ROOT, "engines")
sys.path.insert(0, ROOT)
sys.path.insert(0, ENG)
sys.path.insert(0, HERE)
from mtool_export import build

FAILS = []

def check(name, cond, info=""):
    print(("✓ " if cond else "✗ ") + name + (f"  {info}" if info and not cond else ""))
    if not cond:
        FAILS.append(name)

# ---------------- 合成译文 ----------------
tr = {
    "Hello there!\nHow are you?": "【译】你好呀！\n【译】你好吗？",          # 多行对话
    "Yes.\nNo.\nMaybe": "【译】是。\n【译】否。\n【译】也许",                 # 选项块
    "\\C[2]About Demo:\\c[0] Please note.": "【译】关于演示：请注意。",      # 行首控制码
    "So\\..\\.. this is Roya.": "【译】所以……这是罗亚。",                    # 行中停顿码
    "plain single line": "【译】单行文本",
    "行数不齐\n的块": "【译】整块译文放首行",                               # 行数不齐
}
out = build(tr)

check("原键全部保留", all(out.get(k) == v for k, v in tr.items()))
check("行拆分-对话", out.get("Hello there!") == "【译】你好呀！"
      and out.get("How are you?") == "【译】你好吗？")
check("行拆分-选项", out.get("Yes.") == "【译】是。" and out.get("Maybe") == "【译】也许")
check("行首码剥离", out.get("About Demo: Please note.") == "【译】关于演示：请注意。")
check("全码剥离", out.get("So.. this is Roya.") == "【译】所以……这是罗亚。")
check("行数不齐-首行整译", out.get("行数不齐") == "【译】整块译文放首行")
check("单行原文无变体噪音", "plain single line" in out)
print(f"  键数: 原 {len(tr)} → 导出 {len(out)}")

# ---------------- 模拟 MTool 运行时查键 ----------------
# 假设 MTool 以各种形态拦截文本，逐一查表
mtool_forms = [
    "Hello there!\nHow are you?",          # 完整块
    "Hello there!",                        # 逐行
    "How are you?",
    "Yes.", "No.", "Maybe",                # 逐项选项
    "\\C[2]About Demo:\\c[0] Please note.",# 原码形态
    "About Demo: Please note.",            # 行首码已剥
    "So\\..\\.. this is Roya.",            # 停顿码原样
    "So.. this is Roya.",                    # 停顿码已剥（字面点保留）
    "plain single line",
    "行数不齐",
]
missed = [k for k in mtool_forms if k not in out]
check("模拟 MTool 查键 100% 命中", not missed, missed)

# ---------------- CLI 回路 ----------------
tmp = tempfile.mkdtemp()
src = os.path.join(tmp, "game_extracted_translated.json")
json.dump(tr, open(src, "w", encoding="utf-8"), ensure_ascii=False)
gdir = os.path.join(tmp, "game")
os.makedirs(gdir)
r = subprocess.run([sys.executable, os.path.join(ENG, "mtool_export.py"), src,
                    "--dir", gdir], capture_output=True, text=True,
                   encoding="utf-8", cwd=HERE)
check("CLI 退出码 0", r.returncode == 0, r.stderr[-200:])
dst = os.path.join(gdir, "ManualTransFile.json")
check("输出到游戏目录", os.path.exists(dst))
loaded = json.load(open(dst, encoding="utf-8"))
check("CLI 输出与 build 一致", loaded == out)

# 空/非法值不导出
tr2 = {"good": "ok", "empty": "", "num": 5}
out2 = build(tr2)
check("空译文与非字符串跳过", "good" in out2 and "empty" not in out2 and "num" not in out2)

import shutil
shutil.rmtree(tmp, ignore_errors=True)

print()
if FAILS:
    print(f"✗ {len(FAILS)} 项失败: {FAILS}")
    sys.exit(1)
print("ALL TESTS PASS")
