# -*- coding: utf-8 -*-
"""
AutoMT 上位机（GUI）
====================
设置源语言/目标语言 → 拖拽 MTool 导出的 ManualTransFile.json 进窗口 → 自动
清洗-机翻-回填 → 实时显示进度 → 完成后展示译文文件位置。

拖拽支持需要 tkinterdnd2（可选）：pip install tkinterdnd2
未安装时可用「点击选择文件」按钮，功能完全一致。
"""
import json, re, sys, io, os, time, queue, random, hashlib, threading, traceback
import urllib.request, urllib.parse
from collections import Counter

import mt_config

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# ---------------- 翻译管线（与命令行版同源） ----------------
BS = chr(92)
MASK_PATTERNS = [
    re.compile(BS * 2 + r'js<[^>]*>'),
    re.compile(BS * 2 + r'js\[[^\]]*\]'),
    re.compile(BS * 2 + r'[cCvVnNiI]\[\d+\]'),
    re.compile(BS * 2 + r'[fgFf][bBiI]\[[^\]]*\]'),
    re.compile(BS * 2 + r'.'),
]
tokre = re.compile(r"〔T[0-9a-f]{8}〕")
loose = re.compile(r"[〔【\[\(（]\s*[TtＴ]\s*([0-9a-fA-F]{8})\s*[〕】\]\)）]")
FW = str.maketrans("０１２３４５６７８９ａｂｃｄｅｆＡＢＣＤＥＦ", "0123456789abcdefABCDEF")
VALID_NEXT = set('nNvVcCiIpPGFSfuwMLjsbot' + BS + '{}<>|.^^$[]()')
LANGS = [("英语 en", "en"), ("自动检测", "auto"), ("日语", "ja"), ("韩语", "ko"),
         ("俄语", "ru"), ("法语", "fr"), ("德语", "de"), ("西班牙语", "es"),
         ("葡萄牙语", "pt"), ("意大利语", "it"), ("泰语", "th"), ("越南语", "vi"),
         ("印尼语", "id"), ("中文(简)", "zh-CN"), ("中文(繁)", "zh-TW")]

def stable_tok(orig):
    return "〔T" + hashlib.md5(orig.encode("utf-8")).hexdigest()[:8] + "〕"

def canon(s):
    return loose.sub(lambda m: f"〔T{m.group(1).lower()}〕", s.translate(FW))

class Cancel(Exception):
    pass

class Pipe:
    """三段式管线，供 GUI 线程调用；cb(stage, done, total, note)"""
    def __init__(self, src_json, workdir, sl, tl, cancel, cb, log,
                 endpoint=None, api_key=None, api_header=None, auto_names=True):
        self.src, self.work, self.sl, self.tl = src_json, workdir, sl, tl
        self.cancel, self.cb, self.log = cancel, cb, log
        self.endpoint = (endpoint or "").strip() or mt_config.DEFAULT_ENDPOINT
        self.headers = mt_config.build_headers(api_key, api_header)
        self.auto_names = auto_names

    def load_names(self):
        names = []
        base = os.path.dirname(os.path.abspath(__file__))
        for cand in (os.path.join(os.path.dirname(self.src), "names.txt"),
                     os.path.join(base, "names.txt")):
            if os.path.exists(cand):
                for line in open(cand, encoding="utf-8-sig"):
                    n = line.strip()
                    if n and not n.startswith("#"):
                        names.append(n)
                break
        return names

    def mask(self, s, tokens, names, name_zh):
        parts = s.split("\n")
        out = []
        for pi, part in enumerate(parts):
            if pi:
                t = stable_tok("\n")
                tokens[t] = "\n"
                out.append(t)
            buf = part
            changed = True
            while changed:
                changed = False
                for pat in MASK_PATTERNS:
                    m = pat.search(buf)
                    if m:
                        t = stable_tok(m.group(0))
                        tokens[t] = m.group(0)
                        buf = buf[:m.start()] + t + buf[m.end():]
                        changed = True
                        break
            for entry in sorted(names, key=len, reverse=True):
                en, _, zh = entry.partition("=")
                if en and en in buf:
                    t = stable_tok(en)
                    tokens[t] = en          # 键还原：永远英文原词
                    if zh:
                        name_zh[en] = zh     # 值还原：中文译名
                    buf = buf.replace(en, t)
            out.append(buf)
        return "".join(out)

    # ---------- 第一段：清洗 ----------
    def clean(self):
        os.makedirs(self.work, exist_ok=True)
        orig = json.load(open(self.src, encoding="utf-8"))
        names = self.load_names()
        # 自动人名识别：用户词条优先，未覆盖的高频专名自动掩码（保持原文一致）
        todo = [k for k, v in orig.items()
                if isinstance(k, str) and k.strip() and not (isinstance(v, str) and v.strip())]
        user_set = {n.partition("=")[0].strip().lower() for n in names}
        if self.auto_names:
            auto = [(w, c) for w, c in mt_config.detect_names(todo, self.sl)
                    if w.lower() not in user_set]
            if not auto and self.sl.split("-")[0].lower() in ("zh", "ko"):
                self.log("源语言为中文/韩文：无法自动识别人名，建议在 names.txt 中列出以保持一致")
            names.extend(w for w, _ in auto)
            if auto:
                self.log(f"自动识别专有名词 {len(auto)} 个（已自动保持原文一致）: "
                         + ", ".join(f"{w}×{c}" for w, c in auto[:30]))
        elif user_set:
            self.log("自动人名识别已关闭：仅使用 names.txt 中的人工词条")
        tokens, name_zh, masked = {}, {}, {}
        for i, k in enumerate(todo):
            if self.cancel.is_set():
                raise Cancel()
            masked[self.mask(k, tokens, names, name_zh)] = ""
            if i % 500 == 0:
                self.cb("clean", i, len(todo), "清洗掩码")
        mp, tp = os.path.join(self.work, "masked.json"), os.path.join(self.work, "tokens.json")
        if os.path.exists(mp):   # 断点：保留旧译文
            prev = json.load(open(mp, encoding="utf-8"))
            for k in masked:
                if k in prev and isinstance(prev[k], str) and prev[k].strip():
                    masked[k] = prev[k]
        if os.path.exists(tp):
            old = json.load(open(tp, encoding="utf-8"))
            old.update(tokens)
            tokens = old
        json.dump(masked, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(tokens, open(tp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        json.dump(name_zh, open(os.path.join(self.work, "names_map.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        self.log(f"清洗完成：待翻 {len(masked)} 条，人名表 {len(names)} 词")
        return masked, tokens

    # ---------- 端点 ----------
    def _open(self, url):
        req = urllib.request.Request(url, headers=self.headers)
        return urllib.request.urlopen(req, timeout=30)

    def mt_one(self, text, tries=5):
        for a in range(tries):
            if self.cancel.is_set():
                raise Cancel()
            try:
                with self._open(mt_config.build_url(self.endpoint, text, self.sl, self.tl)) as r:
                    return mt_config.parse_response(r.read().decode("utf-8", "replace"))
            except Cancel:
                raise
            except Exception:
                if a == tries - 1:
                    raise
                time.sleep(3 + 3 * a + random.random() * 2)

    def mt_batch(self, qs, tries=5):
        """多条合并请求——仅内置谷歌端点支持；自定义接口自动退化为逐条"""
        if self.endpoint != mt_config.DEFAULT_ENDPOINT:
            return [self.mt_one(q) for q in qs]
        u = (self.endpoint.replace("{sl}", self.sl).replace("{tl}", self.tl)
             .replace("&q={q}", "") + "".join("&q=" + urllib.parse.quote(q) for q in qs))
        for a in range(tries):
            if self.cancel.is_set():
                raise Cancel()
            try:
                with self._open(u) as r:
                    d = json.loads(r.read().decode("utf-8", "replace"))
                if isinstance(d, list) and len(d) == len(qs):
                    return [str(x) for x in d]
                raise ValueError("shape")
            except Cancel:
                raise
            except Exception:
                if a == tries - 1:
                    raise
                time.sleep(3 + 3 * a + random.random() * 2)

    # ---------- 第二段：批量机翻 ----------
    def translate(self, masked, seg=False):
        keys = [k for k, v in masked.items() if not (isinstance(v, str) and v.strip())]
        total, t0, done = len(keys), time.time(), 0
        self.log(f"机翻开始（{'分段' if seg else '批量'}模式）：{total} 条")
        if seg:
            segre = re.compile(r"(〔T[0-9a-f]{8}〕)")
            for k in keys:
                if self.cancel.is_set():
                    raise Cancel()
                parts = segre.split(k)
                out = []
                for p in parts:
                    if segre.fullmatch(p) or not p.strip():
                        out.append(p)
                    else:
                        out.append(self.mt_one(p))
                        time.sleep(0.15)
                masked[k] = "".join(out)
                done += 1
                if done % 10 == 0 or done >= total:
                    self._save(masked, "分段")
                    self.cb("trans", done, total, self._eta(t0, done, total))
        else:
            B = 8
            gi = 0
            while gi < len(keys):
                if self.cancel.is_set():
                    raise Cancel()
                group = keys[gi:gi + B]
                if len("".join(group)) > 6000:
                    group = group[:max(1, len(group) // 2)]
                try:
                    vals = self.mt_batch(group)
                except Exception:
                    vals = [self.mt_one(g) for g in group]
                for k, v in zip(group, vals):
                    masked[k] = v
                done += len(group)
                gi += len(group)
                if (gi // B) % 2 == 0 or done >= total:
                    self._save(masked, "批量")
                    self.cb("trans", done, total, self._eta(t0, done, total))
                time.sleep(0.45 + random.random() * 0.5)
        self._save(masked, "收尾")
        self.log(f"机翻完成：{done} 条，用时 {(time.time()-t0)/60:.1f} 分钟")
        return masked

    def _save(self, masked, tag):
        json.dump(masked, open(os.path.join(self.work, "masked.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    def _eta(self, t0, done, total):
        r = done / (time.time() - t0)
        return f"{r:.1f}条/秒 剩余{(total-done)/r/60:.0f}分" if r > 0 else "计算中"

    # ---------- 第三段：回填 ----------
    def apply(self, masked, tokens, auto_seg_sweep=True):
        try:
            name_zh = json.load(open(os.path.join(self.work, "names_map.json"), encoding="utf-8"))
        except FileNotFoundError:
            name_zh = {}

        def key_of(k):
            return tokre.sub(lambda m: tokens.get(m.group(0), m.group(0)), canon(k))

        def val_of(v):
            def r(m):
                o = tokens.get(m.group(0))
                return name_zh.get(o, o) if o is not None else m.group(0)
            return tokre.sub(r, canon(v))

        result = {}
        for round_ in range(2):
            ok = drop_tok = drop_nl = 0
            result = {}
            for k, v in list(masked.items()):
                if not (isinstance(v, str) and v.strip()):
                    continue
                ktoks = tokre.findall(k)
                if Counter(ktoks) != Counter(tokre.findall(canon(v))):
                    drop_tok += 1
                    masked[k] = ""
                    continue
                en, zh = key_of(k), val_of(v)
                zh = re.sub(r'(?<=[\u4e00-\u9fff〔])[ \t]+(?=[\u4e00-\u9fff〔〕])', '', zh)
                zh = re.sub(r'[ \t]*([。！？，、：；…～—])[ \t]*', r'\1', zh)
                zh = re.sub(r'\\(.)', lambda m: m.group(0) if m.group(1) in VALID_NEXT else m.group(1), zh)
                if en.count("\n") != zh.count("\n"):
                    drop_nl += 1
                    masked[k] = ""
                    continue
                result[k] = zh
                ok += 1
            self.cb("apply", ok, max(ok + drop_tok + drop_nl, 1), "回填校验")
            self.log(f"回填：成功 {ok}，记号丢失 {drop_tok}，换行异常 {drop_nl}")
            if not auto_seg_sweep or (drop_tok + drop_nl) == 0 or round_ == 1:
                break
            self.log("自动进入分段扫尾模式重翻失败条目…")
            masked = self.translate(masked, seg=True)
        # 写最终文件（键=英文原文精确匹配，值=中文）
        orig = json.load(open(self.src, encoding="utf-8"))
        out = dict(orig)
        for k, zh in result.items():
            out[key_of(k)] = zh
        dst = os.path.splitext(self.src)[0] + "_translated.json"
        json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        self._save(masked, "final")
        return dst, ok, drop_tok + drop_nl

    def run(self):
        masked, tokens = self.clean()
        if not masked:
            orig = json.load(open(self.src, encoding="utf-8"))
            dst = os.path.splitext(self.src)[0] + "_translated.json"
            json.dump(orig, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            self.log("没有需要翻译的条目（可能上次已全部翻完），已直接输出。")
            return dst, 0, 0
        masked = self.translate(masked)
        return self.apply(masked, tokens)

# ---------------- GUI ----------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("AutoMT 机翻上位机 — MTool JSON 自动翻译")
        root.geometry("680x520")
        self.q = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.src_file = None
        self.out_file = None
        self._build()
        self.root.after(100, self._poll)

    def _build(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="源语言:").pack(side="left")
        self.sl_var = tk.StringVar(value="英语 en")
        ttk.Combobox(top, textvariable=self.sl_var, values=[n for n, _ in LANGS],
                     width=10, state="readonly").pack(side="left", padx=4)
        ttk.Label(top, text="  →  目标语言:").pack(side="left")
        self.tl_var = tk.StringVar(value="中文(简)")
        ttk.Combobox(top, textvariable=self.tl_var, values=[n for n, _ in LANGS],
                     width=10, state="readonly").pack(side="left", padx=4)
        self.autonames_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="自动识别人名并保持一致", variable=self.autonames_var).pack(side="left", padx=6)
        ttk.Label(top, text="（人名表：输入 json 同目录或本工具目录 names.txt）").pack(side="left", padx=10)

        cfg = ttk.LabelFrame(self.root, text="翻译接口（个人配置，保存到本机 .env，不会进 git）", padding=6)
        cfg.pack(fill="x", padx=12, pady=(6, 0))
        ttk.Label(cfg, text="URL:").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar(value=mt_config.DEFAULT_ENDPOINT)
        ttk.Entry(cfg, textvariable=self.url_var).grid(row=0, column=1, columnspan=3, sticky="we", padx=4)
        ttk.Label(cfg, text="Key:").grid(row=1, column=0, sticky="w")
        self.key_var = tk.StringVar(value="")
        ttk.Entry(cfg, textvariable=self.key_var, show="*").grid(row=1, column=1, sticky="we", padx=4)
        ttk.Label(cfg, text="请求头:").grid(row=1, column=2, sticky="e")
        self.hdr_var = tk.StringVar(value="Authorization")
        ttk.Entry(cfg, textvariable=self.hdr_var, width=16).grid(row=1, column=3, sticky="w", padx=4)
        ttk.Button(cfg, text="保存到 .env", command=self.save_env).grid(row=0, column=4, rowspan=2, padx=6)
        ttk.Label(cfg, foreground="#777",
                  text="URL 用 {sl}/{tl}/{q} 占位符；留默认=免费谷歌端点（无需Key）。自定义接口将逐条请求。"
                  ).grid(row=2, column=0, columnspan=5, sticky="w")
        cfg.columnconfigure(1, weight=1)
        env = mt_config.load_env()
        if env.get("MT_ENDPOINT"):
            self.url_var.set(env["MT_ENDPOINT"])
        if env.get("MT_API_KEY"):
            self.key_var.set(env["MT_API_KEY"])
        if env.get("MT_API_HEADER"):
            self.hdr_var.set(env["MT_API_HEADER"])
        if env.get("MT_AUTO_NAMES"):
            self.autonames_var.set(env["MT_AUTO_NAMES"] == "1")

        self.drop = tk.Label(self.root, text="\n\n把 ManualTransFile.json 拖到这里\n（或点击选择文件）\n\n",
                             relief="ridge", bd=2, pady=18, font=("Microsoft YaHei", 12),
                             fg="#444", cursor="hand2")
        self.drop.pack(fill="x", padx=12, pady=6)
        self.drop.bind("<Button-1>", lambda e: self.pick())
        if HAS_DND:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", lambda e: self.on_drop(self._dnd_clean(e.data)))
        else:
            self.drop.config(text=self.drop.cget("text") + "\n（提示：pip install tkinterdnd2 可启用拖拽）")

        prog = ttk.Frame(self.root, padding=(12, 2))
        prog.pack(fill="x")
        self.stage_var = tk.StringVar(value="等待文件…")
        ttk.Label(prog, textvariable=self.stage_var).pack(anchor="w")
        self.bar = ttk.Progressbar(prog, maximum=100)
        self.bar.pack(fill="x", pady=4)
        self.detail_var = tk.StringVar(value="")
        ttk.Label(prog, textvariable=self.detail_var).pack(anchor="w")

        btns = ttk.Frame(self.root, padding=(12, 4))
        btns.pack(fill="x")
        self.start_btn = ttk.Button(btns, text="开始翻译", command=self.start, state="disabled")
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btns, text="取消", command=self.cancel_now, state="disabled")
        self.cancel_btn.pack(side="left", padx=6)
        self.open_btn = ttk.Button(btns, text="打开输出文件夹", command=self.open_out, state="disabled")
        self.open_btn.pack(side="left", padx=6)

        self.logbox = ScrolledText(self.root, height=10, font=("Consolas", 9), state="disabled")
        self.logbox.pack(fill="both", expand=True, padx=12, pady=(4, 10))

    @staticmethod
    def _dnd_clean(data):
        return data.strip("{}").split("} {")[0].strip()

    def log(self, msg):
        self.q.put(("log", msg))

    def on_drop(self, path):
        path = path.strip().strip('"')
        if not path.lower().endswith(".json"):
            messagebox.showerror("文件类型", "请拖入 .json 文件（MTool 导出的 ManualTransFile.json）")
            return
        self.set_file(path)

    def pick(self):
        p = filedialog.askopenfilename(title="选择 MTool 导出的 json",
                                       filetypes=[("JSON", "*.json"), ("所有文件", "*.*")])
        if p:
            self.set_file(p)

    def set_file(self, p):
        self.src_file = p
        self.out_file = None
        self.stage_var.set(f"已就绪：{os.path.basename(p)}")
        self.detail_var.set(f"路径：{p}")
        self.start_btn.config(state="normal")
        self.open_btn.config(state="disabled")
        self.log(f"已选择文件：{p}")

    def save_env(self):
        try:
            mt_config.save_env({
                "MT_ENDPOINT": self.url_var.get().strip(),
                "MT_API_KEY": self.key_var.get().strip(),
                "MT_API_HEADER": self.hdr_var.get().strip(),
                "MT_AUTO_NAMES": "1" if self.autonames_var.get() else "0",
            })
            self.log(f"配置已保存到 {mt_config.env_path()}（.env 已在 .gitignore 中，不会上传）")
            messagebox.showinfo("已保存", f"配置已写入：\n{mt_config.env_path()}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def start(self):
        if not self.src_file or (self.worker and self.worker.is_alive()):
            return
        sl = dict(LANGS)[self.sl_var.get()]
        tl = dict(LANGS)[self.tl_var.get()]
        try:
            mt_config.build_url(self.url_var.get().strip() or mt_config.DEFAULT_ENDPOINT,
                                "test", sl, tl)
        except ValueError as e:
            messagebox.showerror("接口 URL 有误", str(e))
            return
        h = hashlib.md5(self.src_file.encode()).hexdigest()[:8]
        work = os.path.join(mt_config.base_dir(), "mt_work", h)
        pipe = Pipe(self.src_file, work, sl, tl, self.cancel, self._cb, self.log,
                    endpoint=self.url_var.get().strip(),
                    api_key=self.key_var.get().strip(),
                    api_header=self.hdr_var.get().strip(),
                    auto_names=self.autonames_var.get())
        self.cancel.clear()
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.drop.config(fg="#888")
        self.log(f"开始：{self.sl_var.get()} → {self.tl_var.get()}")
        self.worker = threading.Thread(target=self._work, args=(pipe,), daemon=True)
        self.worker.start()

    def _work(self, pipe):
        try:
            dst, ok, drop = pipe.run()
            self.q.put(("done", (dst, ok, drop)))
        except Cancel:
            self.q.put(("cancelled", None))
        except Exception:
            self.q.put(("error", traceback.format_exc()))

    def _cb(self, stage, done, total, note):
        self.q.put(("prog", (stage, done, total, note)))

    def cancel_now(self):
        self.cancel.set()
        self.log("正在取消…（等待当前请求结束）")

    def open_out(self):
        if self.out_file and os.path.exists(self.out_file):
            os.startfile(os.path.dirname(self.out_file))

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.logbox.config(state="normal")
                    self.logbox.insert("end", f"[{time.strftime('%H:%M:%S')}] {payload}\n")
                    self.logbox.see("end")
                    self.logbox.config(state="disabled")
                elif kind == "prog":
                    stage, done, total, note = payload
                    name = {"clean": "① 文本清洗", "trans": "② 机翻翻译", "apply": "③ 回填校验"}[stage]
                    pct = done * 100 // max(total, 1)
                    self.stage_var.set(f"{name}  {done}/{total}  （{pct}%）")
                    self.bar["value"] = pct
                    self.detail_var.set(f"{note}    {pct}%")
                elif kind == "done":
                    dst, ok, drop = payload
                    self.out_file = dst
                    self.bar["value"] = 100
                    self.stage_var.set("③ 完成！")
                    self.detail_var.set(f"回填成功 {ok} 条，丢弃 {drop} 条（保持原文显示）")
                    self.log(f"输出文件：{dst}")
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.open_btn.config(state="normal")
                    self.drop.config(fg="#080")
                    messagebox.showinfo(
                        "翻译完成",
                        f"已翻译 {ok} 条（{drop} 条校验失败保持原文）。\n\n输出文件：\n{dst}")
                elif kind == "cancelled":
                    self.stage_var.set("已取消")
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.log("已取消。进度已保存，重新开始可断点续翻。")
                elif kind == "error":
                    self.stage_var.set("出错了")
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.log("错误：\n" + payload)
                    messagebox.showerror("出错了", payload[:1500])
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

def main():
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
