# -*- coding: utf-8 -*-
"""GUI 按钮反馈测试：成功/失败/取消后的按钮状态与颜色反馈
=====================================================
直接向事件队列注入 done/error/cancelled/applied 事件（即 worker 真实投递的
消息），断言 _poll 状态机对按钮可用性与 stage 标签颜色的处理：
  - 失败：所有工作流按钮恢复可用（不卡死），stage 红色 ❌
  - 取消：③ 翻译按钮恢复，stage 中性色
  - 提取成功：②③ 可用，stage 绿色
  - 导入成功：④/📤 恢复，stage 绿色
运行：python tests/_test_gui_feedback.py
"""
import os, sys, io, time, json, glob, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import mt_config, mt_gui
from tkinterdnd2 import TkinterDnD

FAILS = []
def check(name, cond, info=""):
    print(("✓ " if cond else "✗ ") + name + (f"  {info}" if info and not cond else ""))
    if not cond:
        FAILS.append(name)

lib = os.path.join(mt_config.base_dir(), "library.json")
if os.path.exists(lib):
    os.remove(lib)
mt_gui.messagebox.showinfo = lambda *a, **k: None
mt_gui.messagebox.showerror = lambda *a, **k: None
mt_gui.messagebox.askyesno = lambda *a, **k: False

root = TkinterDnD.Tk()
app = mt_gui.App(root)
root.update()

def states():
    return tuple(str(b["state"]) for b in (app.start_btn, app.g_extract_btn,
                                           app.g_translate_btn, app.apply_btn,
                                           app.mtool_btn))

def fg():
    return str(app.lbl_stage.cget("foreground"))

def fire(kind, payload=None):
    app.q.put((kind, payload))
    for _ in range(20):
        root.update()
        time.sleep(0.03)

# ---- 场景 1：提取失败（模拟 worker 投递 error）----
app.game_path = r"E:\fake\game"
app.apply_script = "engines/krkr_apply.py"
app.g_extract_btn.config(state="disabled")   # game_extract() 点击后即禁用
app.g_translate_btn.config(state="disabled")
app.apply_btn.config(state="disabled")
app.mtool_btn.config(state="disabled")
app.start_btn.config(state="disabled")
fire("error", "Simulated extraction failure")
s = states()
check("失败后 ②③④📤 全部恢复可用", s == ("normal",) * 5, str(s))
check("失败 stage 红色", fg() == app.pal["err"], fg())
check("失败 stage 文案带 ❌", app.stage_var.get().startswith("❌"))

# ---- 场景 2：翻译取消 ----
for b in (app.start_btn, app.g_translate_btn):
    b.config(state="disabled")
app.cancel_btn.config(state="normal")
fire("cancelled")
s = states()
check("取消后 开始/③ 恢复", str(app.start_btn["state"]) == "normal"
      and str(app.g_translate_btn["state"]) == "normal")
check("取消 stage 中性色", fg() == app.pal["hint"], fg())

# ---- 场景 3：提取成功 ----
tmp_json = os.path.join(mt_config.base_dir(), "fb_test_extracted.json")
json.dump({"hello": ""}, open(tmp_json, "w", encoding="utf-8"))
app.g_extract_btn.config(state="disabled")
fire("extracted", tmp_json)
check("提取成功 ②③ 恢复", str(app.g_extract_btn["state"]) == "normal"
      and str(app.g_translate_btn["state"]) == "normal")
check("提取成功 stage 绿色", fg() == app.pal["ok"], fg())

# ---- 场景 4：翻译完成（无游戏上下文 → 不询问导入）----
app.game_path = None
app.apply_script = None
fire("done", (tmp_json.replace("_extracted", "_extracted_translated"), 1, 0))
check("完成后 开始/③ 恢复", str(app.start_btn["state"]) == "normal"
      and str(app.g_translate_btn["state"]) == "normal")

# ---- 场景 5：导入成功 ----
app.game_path = r"E:\fake\game"
app.apply_script = "engines/krkr_apply.py"
for b in (app.apply_btn, app.mtool_btn, app.g_extract_btn):
    b.config(state="disabled")
app.library = {"games": [{"name": "fb", "applied": False}]}
app.game_engine = "kirikiri"
app._game_title_of = lambda a, b: "fb"
fire("applied", r"E:\fake\game")
check("导入成功 ④/📤/② 恢复", str(app.apply_btn["state"]) == "normal"
      and str(app.mtool_btn["state"]) == "normal"
      and str(app.g_extract_btn["state"]) == "normal")
check("导入成功 stage 绿色", fg() == app.pal["ok"], fg())

root.destroy()
os.remove(tmp_json)
if os.path.exists(lib):
    os.remove(lib)

print()
if FAILS:
    print(f"✗ {len(FAILS)} 项失败: {FAILS}")
    sys.exit(1)
print("ALL FEEDBACK TESTS PASS")
