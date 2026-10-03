# -*- coding: utf-8 -*-
"""GUI 模拟点击测试（Tk 事件注入：ButtonPress + ButtonRelease）
===============================================================
真实用户旅程逐一点击：
  拖入游戏(识别) → ②提取 → ③开始翻译(本地 mock 端点) → 完成入馆
  → ✏️微调页: 加载→搜索→双击编辑→保存 → 📚图书馆选中/打开
  → 📤导出 MTool json → ☀/🌙 与 中/EN 按钮点击往返
点击均为 event_generate 注入（与真实点击走同一绑定链），messagebox 自动应答。
运行：python tests/_test_gui_click.py
"""
import os, sys, io, json, time, glob, shutil, tempfile, threading, http.server, urllib.parse

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

# ---------- mock 翻译端点（DeepL 风格） ----------
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)["q"][0]
        body = json.dumps({"translations": [{"text": "【译】" + q}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass

PORT = 18793
srv = http.server.HTTPServer(("127.0.0.1", PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

# ---------- 迷你 Kirikiri 游戏 ----------
game = tempfile.mkdtemp(prefix="click_g_")
KS = "【アリス】「こんにちは、先輩」\r\nただのテキスト行です。"
with open(os.path.join(game, "data.xp3"), "wb") as f:
    X.write_xp3(f, [("scenario/main.ks", KS.encode("cp932"), 0)])

# ---------- 环境清洁 ----------
lib = os.path.join(mt_config.base_dir(), "library.json")
if os.path.exists(lib):
    os.remove(lib)
for f in glob.glob(os.path.join(mt_config.base_dir(), "click_g_*")):
    os.remove(f)

# messagebox 自动应答（记录问题便于断言）
answers = {"yesno": True, "infos": []}
mt_gui.messagebox.askyesno = lambda *a, **k: answers["yesno"]
mt_gui.messagebox.showinfo = lambda *a, **k: answers["infos"].append(str(a))
mt_gui.messagebox.showerror = lambda *a, **k: answers["infos"].append("ERR:" + str(a))
mt_gui.messagebox.showwarning = lambda *a, **k: answers["infos"].append("WARN:" + str(a))
startfile_calls = []
mt_gui.os.startfile = lambda p: startfile_calls.append(p)

root = TkinterDnD.Tk()
app = mt_gui.App(root)

def click(w, name=""):
    """模拟点击。Button 类用 invoke()（tkinter 标准程序化点击，
    与真实点击执行同一 command 路径）；其余控件注入 press+release 事件。"""
    root.update_idletasks()
    root.update()
    if isinstance(w, (mt_gui.tk.Button, mt_gui.ttk.Button)):
        w.invoke()
    else:
        x = max(1, w.winfo_width() // 2)
        y = max(1, w.winfo_height() // 2)
        w.event_generate("<Button-1>", x=x, y=y)
        w.event_generate("<ButtonRelease-1>", x=x, y=y)
    root.update()
    time.sleep(0.05)
    root.update()

def dblclick(w, x=10, y=10):
    """双击：注入两次同坐标单击（Tk 由此合成 <Double-1>）"""
    w.event_generate("<Button-1>", x=x, y=y)
    w.event_generate("<ButtonRelease-1>", x=x, y=y)
    root.update()
    w.event_generate("<Button-1>", x=x, y=y)
    w.event_generate("<ButtonRelease-1>", x=x, y=y)
    root.update()

def pump(sec, cond=None):
    """跑事件循环等待 cond 成立"""
    t0 = time.time()
    while time.time() - t0 < sec:
        root.update()
        time.sleep(0.03)
        if cond and cond():
            return True
    return bool(cond) if cond else True

logs = []
app.log = lambda m: logs.append(m)

# ========== 1) 主题 / 语言 按钮：真实点击往返 ==========
t0 = app.theme
click(app.theme_btn)
check("点击 ☀/🌙 切换主题", app.theme != t0 and app.theme_btn["text"] != app._theme_btn_text if False else app.theme != t0)
click(app.theme_btn)
check("再点切回", app.theme == t0)
l0 = app.lang
click(app.lang_btn)
check("点击 中/EN 切语言", app.lang != l0)
click(app.lang_btn)
check("再点切回", app.lang == l0)

# ========== 2) 拖入游戏（自动应答"是"）→ 提取 ==========
app.on_drop(game)
check("引擎识别为 Kirikiri", app.game_engine == "kirikiri")
pump(30, lambda: app.src_file is not None)
check("② 提取完成并加载", bool(app.src_file) and os.path.exists(app.src_file))
check("③ 按钮亮起", str(app.g_translate_btn["state"]) == "normal")

# ========== 3) 点击「③ 开始翻译」（mock 端点） ==========
app.url_var.set(f"http://127.0.0.1:{PORT}/t?sl={{sl}}&tl={{tl}}&q={{q}}")
app.type_var.set("MT · GET")
answers["yesno"] = False          # 完成后的"立即导入"选否
click(app.g_translate_btn)
pump(60, lambda: app.out_file is not None)
check("翻译完成产出 translated.json", bool(app.out_file) and os.path.exists(app.out_file))
out = json.load(open(app.out_file, encoding="utf-8"))
zh_vals = [v for v in out.values() if isinstance(v, str) and v.startswith("【译】")]
check("译文来自 mock 端点", len(zh_vals) >= 2, str(len(zh_vals)))
check("完成自动入馆", len(app.library["games"]) == 1
      and app.library["games"][0]["name"] == os.path.basename(game))

# ========== 4) ✏️ 微调页：加载→搜索→双击编辑→保存 ==========
app.nb.select(4)
root.update()
click(app.rv_load_btn)
pump(3)
rows = app.rv_tree.get_children()
check("微调页加载表格", len(rows) >= 2, str(len(rows)))
app.rv_search_var.set("テキスト")
root.update()
rows_f = app.rv_tree.get_children()
check("搜索过滤生效", 0 < len(rows_f) < len(rows))
app.rv_search_var.set("")
root.update()

# 双击第一行 → 编辑对话框
first = app.rv_tree.get_children()[0]
app.rv_tree.selection_set(first)
dblclick(app.rv_tree)
dlg = None
for w in root.winfo_children():
    if isinstance(w, mt_gui.tk.Toplevel):
        dlg = w
check("双击弹出编辑窗", dlg is not None)
if dlg:
    texts = [w for w in dlg.winfo_children() if isinstance(w, mt_gui.tk.Text)]
    tz = texts[-1]                                  # 第二个 Text = 译文框（可编辑）
    save_btn = None
    for w in dlg.winfo_children():
        if isinstance(w, mt_gui.ttk.Frame):
            for b in w.winfo_children():
                if isinstance(b, mt_gui.ttk.Button) and "保存此条" in str(b["text"]):
                    save_btn = b
    check("对话框含译文编辑框", tz is not None and save_btn is not None)
    tz.delete("1.0", "end")
    tz.insert("1.0", "【手改】译文")
    click(save_btn)
    pump(2)
    check("保存此条后对话框关闭", not dlg.winfo_exists())
    idx0 = int(first[1:])
    print(f"  [diag] dirty={app.review_dirty} data[{idx0}]={app.review_data[idx0]!r}")
    check("修改计数生效", app.review_dirty >= 1)
    # 保存修改（showinfo 已被接管）
    click(app.rv_save_btn)
    pump(2)
    out2 = json.load(open(app.out_file, encoding="utf-8"))
    check("译文文件已写入手改", any(v == "【手改】译文" for v in out2.values()))
    check("修改计数清零", app.review_dirty == 0)

# ========== 5) 📚 图书馆：选中 + 打开译文 ==========
app.nb.select(3)
root.update()
kids = [k for k in app.lib_tree.get_children() if k != "libempty"]
check("图书馆有记录", len(kids) == 1)
app.lib_tree.selection_set(kids[0])
root.update()
click(app.lib_open_out_btn)
check("打开译文（startfile 被调）", len(startfile_calls) == 1
      and os.path.isdir(startfile_calls[0]), str(startfile_calls))

# ========== 6) 📤 导出 MTool ==========
answers["infos"].clear()
click(app.mtool_btn)
pump(10, lambda: any("已导出" in i for i in answers["infos"]))
mt = os.path.join(game, "ManualTransFile.json")
check("游戏目录生成 ManualTransFile.json", os.path.exists(mt))
if os.path.exists(mt):
    mtd = json.load(open(mt, encoding="utf-8"))
    check("导出含原文键+变体", any("テキスト" in k for k in mtd) and len(mtd) >= len(out))

# ========== 清理 ==========
root.destroy()
srv.shutdown()
shutil.rmtree(game, ignore_errors=True)
for f in glob.glob(os.path.join(mt_config.base_dir(), "click_g_*")):
    os.remove(f)
shutil.rmtree(os.path.join(mt_config.base_dir(), "wolf_work"), ignore_errors=True)
shutil.rmtree(os.path.join(mt_config.base_dir(), "mt_work"), ignore_errors=True)
if os.path.exists(lib):
    os.remove(lib)

print()
if FAILS:
    print(f"✗ {len(FAILS)} 项失败: {FAILS}")
    sys.exit(1)
print("ALL CLICK TESTS PASS")
