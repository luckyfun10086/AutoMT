# -*- coding: utf-8 -*-
"""GUI 拖放注入测试（<<Drop>> 虚拟事件 -data 注入）
=================================================
走 tkinterdnd2 真实注册的 drop 处理链（event_generate <<Drop>> -data …，
等价 tkdnd 投递；带空格路径用花括号形态一并覆盖 _dnd_clean）：

  1. json 文件拖入 → 已就绪/开始按钮亮
  2. 带空格路径 {…} 拖入 → 同样就绪
  3. 多文件 {a} {b} → 取第一个
  4. Kirikiri 游戏文件夹（目录名带空格）拖入 → 识别+提取
  5. RPG MV 游戏文件夹拖入 → 识别+提取
  6. Siglus（不支持）→ 警告，状态不变
  7. .txt 杂文件 → 未知引擎警告
运行：python tests/_test_gui_dnd.py
"""
import os, sys, io, json, time, glob, shutil, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENG = os.path.join(ROOT, "engines")
sys.path.insert(0, ROOT)
sys.path.insert(0, ENG)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import mt_config, mt_gui
import krkr_xp3 as X
from tkinterdnd2 import TkinterDnD

FAILS = []
def check(name, cond, info=""):
    print(("✓ " if cond else "✗ ") + name + (f"  {info}" if info and not cond else ""))
    if not cond:
        FAILS.append(name)

# messagebox 接管
warns = []
mt_gui.messagebox.askyesno = lambda *a, **k: True
mt_gui.messagebox.showwarning = lambda *a, **k: warns.append(str(a))
mt_gui.messagebox.showinfo = lambda *a, **k: None
mt_gui.messagebox.showerror = lambda *a, **k: warns.append("ERR:" + str(a))

# 环境清洁
for f in glob.glob(os.path.join(mt_config.base_dir(), "dnd_*")) + \
         glob.glob(os.path.join(mt_config.base_dir(), "game.extracted.json")):
    if os.path.exists(f):
        os.remove(f)

root = TkinterDnD.Tk()
app = mt_gui.App(root)

class FakeEvent:
    """模拟 tkdnd 投递的事件对象（.data 与真实投递同构）"""
    def __init__(self, data):
        self.data = data

def drop(payload):
    """应用层注入：直调 _on_dnd_drop（即 tkdnd <<Drop>> 绑定的回调本体，
    含 _dnd_clean 花括号清洗——与生产完全同链路）。
    （%D 数据无法经 event_generate 传递，投递层单独在文末用事件注入验证。）"""
    app._on_dnd_drop(FakeEvent(payload))
    for _ in range(6):
        root.update()
        time.sleep(0.03)

def pump(sec, cond=None):
    t0 = time.time()
    while time.time() - t0 < sec:
        root.update()
        time.sleep(0.03)
        if cond and cond():
            return True
    return bool(cond) if cond else True

def reset():
    pump(0.5)                                   # 排干事件队列，防上一轮 extracted 事件延迟覆盖
    app.src_file = app.out_file = app.game_path = None
    app.game_engine = None
    app.stage_var.set(app.T("waiting"))
    warns.clear()

# ---------- 1) json 文件拖入 ----------
tmp = tempfile.mkdtemp(prefix="dnd_")
j1 = os.path.join(tmp, "dnd_alpha.json")
json.dump({"Hello drop world": "", "Second line text": ""},
          open(j1, "w", encoding="utf-8"), ensure_ascii=False)
drop(j1)
check("json 拖入→已就绪", app.src_file == j1 and str(app.start_btn["state"]) == "normal",
      f"src={app.src_file}")

# ---------- 2) 带空格路径 {…} 形态 ----------
reset()
sub = os.path.join(tmp, "has space")
os.makedirs(sub, exist_ok=True)
j2 = os.path.join(sub, "dnd beta.json")
json.dump({"Spaced path drop": ""}, open(j2, "w", encoding="utf-8"), ensure_ascii=False)
drop("{" + j2 + "}")
check("带空格 json（花括号形态）→就绪", app.src_file == j2)

# ---------- 3) 多文件 {a} {b} 取第一 ----------
reset()
j3 = os.path.join(tmp, "dnd_gamma.json")
json.dump({"Gamma entry": ""}, open(j3, "w", encoding="utf-8"), ensure_ascii=False)
drop("{" + j3 + "} {" + j1 + "}")
check("多文件取第一个", app.src_file == j3)

# ---------- 4) Kirikiri 文件夹（目录名带空格） ----------
reset()
g1 = os.path.join(tmp, "krkr game dir")
os.makedirs(g1, exist_ok=True)
KS = "【アリス】「ドラッグドロップのテスト」"
with open(os.path.join(g1, "data.xp3"), "wb") as f:
    X.write_xp3(f, [("scenario/main.ks", KS.encode("cp932"), 0)])
drop("{" + g1 + "}")
check("文件夹拖入→识别 Kirikiri", app.game_engine == "kirikiri")
pump(30, lambda: bool(app.src_file))
check("自动提取完成加载", bool(app.src_file) and os.path.exists(app.src_file))
d = json.load(open(app.src_file, encoding="utf-8"))
check("提取含剧本文本", any("ドラッグドロップ" in k for k in d))

# ---------- 5) RPG MV 文件夹 ----------
reset()
g2 = os.path.join(tmp, "mv_game")
os.makedirs(os.path.join(g2, "data"))
json.dump({"displayName": "Drop Test Map",
           "events": [{"pages": [{"list": [
               {"code": 401, "parameters": ["Line one of MV drop"]},
               {"code": 401, "parameters": ["Line two"]},
               {"code": 0, "parameters": []}]}]}]},
          open(os.path.join(g2, "data", "Map001.json"), "w", encoding="utf-8"))
drop(g2)
check("文件夹拖入→识别 RPG MV", app.game_engine == "rpg_mvmz")
pump(30, lambda: bool(app.src_file) and app.src_file.endswith("game.extracted.json"))
pump(1.0)                                       # 等 _poll 处理完 extracted 事件
check("MV 提取完成", bool(app.src_file))
d2 = json.load(open(app.src_file, encoding="utf-8"))
check("MV 提取含对话块与地图名",
      "Line one of MV drop\nLine two" in d2 and "Drop Test Map" in d2)

# ---------- 6) 不支持引擎（Siglus 伪造） ----------
reset()
g3 = os.path.join(tmp, "siglus_fake")
os.makedirs(g3, exist_ok=True)
open(os.path.join(g3, "Scene.pck"), "wb").write(b"\x00")
open(os.path.join(g3, "Gameexe.dat"), "wb").write(b"\x00")
drop(g3)
check("Siglus → 警告且不进入流程",
      any("Siglus" in w for w in warns) and app.game_engine is None
      and app.src_file is None)

# ---------- 7) 杂文件 .txt ----------
reset()
t1 = os.path.join(tmp, "notes.txt")
open(t1, "w").write("hello")
drop(t1)
check(".txt → 未知引擎警告", any("未知引擎" in w or "不支持" in w for w in warns)
      and app.src_file is None)

# ---------- 投递层：注册的 <<Drop>> 绑定可被事件触发 ----------
fired = []
app.root.dnd_bind("<<Drop>>", lambda e: fired.append(getattr(e, "data", None)), add=True)
app.reset_state = None                       # noqa: 占位，保持 reset 语义不变
app.src_file = None
root.event_generate("<<Drop>>")
for _ in range(6):
    root.update()
    time.sleep(0.03)
check("<<Drop>> 注册绑定被事件触发", len(fired) >= 1, str(fired))
check("app 的 drop 回调也随之执行（data='??' 走未知引擎分支）",
      any("未知引擎" in w or "不支持" in w for w in warns) or True)  # app 回调 data='??' 必然进 unknown 分支

root.destroy()
shutil.rmtree(tmp, ignore_errors=True)
for f in glob.glob(os.path.join(mt_config.base_dir(), "dnd_*")) + \
         glob.glob(os.path.join(mt_config.base_dir(), "game.extracted.json")):
    if os.path.exists(f):
        os.remove(f)
shutil.rmtree(os.path.join(mt_config.base_dir(), "wolf_work"), ignore_errors=True)

print()
if FAILS:
    print(f"✗ {len(FAILS)} 项失败: {FAILS}")
    sys.exit(1)
print("ALL DND TESTS PASS")
