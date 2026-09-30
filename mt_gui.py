# -*- coding: utf-8 -*-
"""
AutoMT 上位机（GUI，中英双语）
===============================
- 顶部 中/EN 切换按钮，所有界面文字即时切换，选择持久化到 .env (MT_LANG)
- 设置源/目标语言 → 拖拽 MTool 导出的 json → 自动 清洗-机翻-回填 → 实时进度
- 拖拽支持需要 tkinterdnd2：pip install tkinterdnd2（未装时用「选择文件」按钮）
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

# ---------------- 界面文案（中/英） ----------------
S = {
    "zh": {
        "title": "AutoMT — MTool JSON 自动机翻",
        "lang_btn": "EN", "lang_of": "中文",
        "src": "源语言:", "tgt": "→ 目标语言:",
        "names_hint": "（人名表：json 同目录或本工具目录 names.txt）",
        "autonames": "自动识别人名并保持一致",
        "api_frame": "翻译接口（个人配置，保存到本机 .env，不会上传）",
        "url": "URL:", "key": "Key:", "header": "请求头:",
        "save_env": "保存到 .env",
        "api_hint": "MT·GET：URL 用 {sl}/{tl}/{q} 占位符，留默认=免费端点 | AI·OpenAI：URL 填 chat/completions 地址+模型名，支持 DeepSeek/Kimi/GLM/OpenRouter/Ollama 等",
        "drop": "拖入 ManualTransFile.json 或游戏目录\n（或点击选择文件）",
        "drop_nodnd": "\n（提示：pip install tkinterdnd2 可启用拖拽）",
        "start": "开始翻译", "cancel": "取消", "open_out": "打开输出文件夹",
        "waiting": "等待文件…", "ready": "已就绪：{}", "done_stage": "③ 完成！",
        "stage_clean": "① 文本清洗", "stage_trans": "② 机翻翻译", "stage_apply": "③ 回填校验",
        "cancelled": "已取消", "error": "出错了",
        "msg_done_t": "翻译完成", "msg_done_b": "已翻译 {} 条（{} 条校验失败保持原文）。\n\n输出文件：\n{}",
        "msg_badurl": "接口 URL 有误", "msg_saved": "已保存",
        "msg_saved_b": "配置已写入：\n{}", "msg_savefail": "保存失败",
        "msg_type": "文件类型", "msg_type_b": "请拖入 .json 文件（MTool 导出的 ManualTransFile.json）",
        "sel_file": "选择 MTool 导出的 json",
        "no_trans": "没有需要翻译的条目（可能上次已全部翻完），已直接输出。",
        # 管线日志
        "log_auton": "自动识别专有名词 {} 个（已自动保持原文一致）: {}",
        "log_auton_off": "自动人名识别已关闭：仅使用 names.txt 中的人工词条",
        "log_zhko": "源语言为中文/韩文：无法自动识别人名，建议在 names.txt 中列出以保持一致",
        "log_clean": "清洗完成：待翻 {} 条，人名表 {} 词",
        "log_trans_b": "机翻开始（批量模式）：{} 条",
        "log_trans_s": "机翻开始（分段模式）：{} 条",
        "log_trans_ok": "机翻完成：{} 条，用时 {:.1f} 分钟",
        "log_apply": "回填：成功 {}，记号丢失 {}，换行异常 {}",
        "log_seg": "自动进入分段扫尾模式重翻失败条目…",
        "log_speed": "{:.1f}条/秒 剩余{:.0f}分", "log_calc": "计算中",
        "log_cancel": "正在取消…（等待当前请求结束）",
        "log_cancelled": "已取消。进度已保存，重新开始可断点续翻。",
        "log_cfg": "配置已保存到 {}（.env 已被 .gitignore 排除，不会上传）",
        "log_start": "开始：{} → {}",
    },
    "en": {
        "title": "AutoMT — MTool JSON Auto-Translator",
        "lang_btn": "中文", "lang_of": "EN",
        "src": "Source:", "tgt": "→ Target:",
        "names_hint": "(names list: names.txt next to the json or next to this tool)",
        "autonames": "Auto-detect names & keep consistent",
        "api_frame": "Translation API (personal config, saved to local .env, never uploaded)",
        "url": "URL:", "key": "Key:", "header": "Header:",
        "save_env": "Save to .env",
        "api_hint": "MT·GET: URL with {sl}/{tl}/{q} placeholders, default = free endpoint | AI·OpenAI: full chat/completions URL + model (DeepSeek/Kimi/GLM/OpenRouter/Ollama…)",
        "drop": "Drop ManualTransFile.json or a game folder here\n(or click to browse)",
        "drop_nodnd": "\n(tip: pip install tkinterdnd2 enables drag & drop)",
        "start": "Start", "cancel": "Cancel", "open_out": "Open output folder",
        "waiting": "Waiting for a file…", "ready": "Ready: {}", "done_stage": "③ Done!",
        "stage_clean": "① Clean & mask", "stage_trans": "② Translate", "stage_apply": "③ Validate & apply",
        "cancelled": "Cancelled", "error": "Error",
        "msg_done_t": "Translation complete",
        "msg_done_b": "Translated {} strings ({} failed validation, kept original).\n\nOutput file:\n{}",
        "msg_badurl": "Invalid API URL", "msg_saved": "Saved",
        "msg_saved_b": "Configuration written to:\n{}", "msg_savefail": "Save failed",
        "msg_type": "File type", "msg_type_b": "Please drop a .json file (MTool-exported ManualTransFile.json)",
        "sel_file": "Select MTool-exported json",
        "no_trans": "Nothing to translate (possibly all done in a previous run); output written directly.",
        "log_auton": "Auto-detected {} proper nouns (kept consistent): {}",
        "log_auton_off": "Auto name detection off: using only manual names.txt entries",
        "log_zhko": "Source is Chinese/Korean: no auto name detection, list names in names.txt for consistency",
        "log_clean": "Clean done: {} strings to translate, names list {} entries",
        "log_trans_b": "Translating (batch mode): {} strings",
        "log_trans_s": "Translating (segment mode): {} strings",
        "log_trans_ok": "Translation done: {} strings in {:.1f} min",
        "log_apply": "Apply: ok {}, token-lost {}, newline-mismatch {}",
        "log_seg": "Falling back to segment-wise mode for failed strings…",
        "log_speed": "{:.1f}/s, ~{:.0f} min left", "log_calc": "calculating",
        "log_cancel": "Cancelling… (waiting for current request)",
        "log_cancelled": "Cancelled. Progress saved; restart to resume.",
        "log_cfg": "Config saved to {} (.env is gitignored, never uploaded)",
        "log_start": "Start: {} → {}",
    },
}

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
LANGS = [("English", "en"), ("Auto · 自动", "auto"), ("日本語", "ja"), ("한국어", "ko"),
         ("Русский", "ru"), ("Français", "fr"), ("Deutsch", "de"), ("Español", "es"),
         ("Português", "pt"), ("Italiano", "it"), ("ไทย", "th"), ("Tiếng Việt", "vi"),
         ("Bahasa", "id"), ("中文(简)", "zh-CN"), ("中文(繁)", "zh-TW")]

def stable_tok(orig):
    return "〔T" + hashlib.md5(orig.encode("utf-8")).hexdigest()[:8] + "〕"

def canon(s):
    return loose.sub(lambda m: f"〔T{m.group(1).lower()}〕", s.translate(FW))

class Cancel(Exception):
    pass

class Pipe:
    """三段式管线；cb(stage, done, total, note)；log(msg)"""
    def __init__(self, src_json, workdir, sl, tl, cancel, cb, log,
                 endpoint=None, api_key=None, api_header=None, auto_names=True, lang="zh",
                 api_type="get", model=None, fallback=True, fallback_endpoint=None):
        self.src, self.work, self.sl, self.tl = src_json, workdir, sl, tl
        self.cancel, self.cb, self.log = cancel, cb, log
        self.api_type = api_type
        self.model = model
        self.api_key = api_key
        self.api_header = api_header
        self.endpoint = (endpoint or "").strip() or mt_config.DEFAULT_ENDPOINT
        self.headers = mt_config.build_headers(api_key, api_header)
        self.auto_names = auto_names
        self.fallback = fallback
        self.fallback_endpoint = (fallback_endpoint or "").strip() or mt_config.DEFAULT_ENDPOINT
        self.policy_skips = 0
        self.fallback_saved = 0
        self.L = S[lang if lang in S else "zh"]

    def load_names(self):
        names = []
        base = mt_config.base_dir()
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
        orig = mt_config.load_loose_json(self.src)
        names = self.load_names()
        todo = [k for k, v in orig.items()
                if isinstance(k, str) and k.strip() and not (isinstance(v, str) and v.strip())]
        user_set = {n.partition("=")[0].strip().lower() for n in names}
        if self.auto_names:
            auto = [(w, c) for w, c in mt_config.detect_names(todo, self.sl)
                    if w.lower() not in user_set]
            if not auto and self.sl.split("-")[0].lower() in ("zh", "ko"):
                self.log(self.L["log_zhko"])
            names.extend(w for w, _ in auto)
            if auto:
                self.log(self.L["log_auton"].format(
                    len(auto), ", ".join(f"{w}×{c}" for w, c in auto[:30])))
        elif user_set:
            self.log(self.L["log_auton_off"])
        tokens, name_zh, masked = {}, {}, {}
        for i, k in enumerate(todo):
            if self.cancel.is_set():
                raise Cancel()
            masked[self.mask(k, tokens, names, name_zh)] = ""
            if i % 500 == 0:
                self.cb("clean", i, len(todo), "")
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
        self.log(self.L["log_clean"].format(len(masked), len(names)))
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
                r = mt_config.translate_once(
                    text, self.sl, self.tl, endpoint=self.endpoint,
                    api_key=self.api_key, api_header=self.api_header,
                    api_type=self.api_type, model=self.model)
                return r
            except Cancel:
                raise
            except mt_config.ApiError as e:
                if e.kind == "fatal":
                    raise                      # 401/402/404：立即终止，不浪费重试
                if e.kind == "skip":
                    # 敏感词被服务方拦截 → 机翻免费端点兜底（不审查内容）
                    self.policy_skips += 1
                    if self.policy_skips == 1:
                        self.log(e.args[0] + "（后续同类拦截不再逐条提示，结束时汇总）")
                    r = self._fallback_translate(text)
                    if r is not None:
                        return r
                    return ""                  # 兜底也失败：留空保原文
                if a == tries - 1:             # retry：退避重试
                    raise
                time.sleep(3 + 3 * a + random.random() * 2)
            except Exception:
                if a == tries - 1:
                    raise
                time.sleep(3 + 3 * a + random.random() * 2)
        return ""

    def _fallback_translate(self, text):
        """主接口内容拦截后，用内置免费机翻端点兜底；成功返回译文，失败返回 None。"""
        if not self.fallback:
            return None
        if self.api_type == "get" and self.endpoint == self.fallback_endpoint:
            return None                        # 主接口已是免费端点，无路可退
        try:
            r = mt_config.translate_once(text, self.sl, self.tl,
                                         endpoint=self.fallback_endpoint,
                                         api_type="get")
            if isinstance(r, str) and r.strip():
                self.fallback_saved += 1
                if self.fallback_saved == 1:
                    self.log("[fallback] 内容拦截 → 已自动改用免费机翻兜底 "
                             "(quality=MT) / blocked string retranslated via free MT")
                return r
        except Exception:
            pass
        return None

    def mt_batch(self, qs, tries=5):
        """多条合并请求——仅内置谷歌端点支持；自定义/AI 接口自动退化为逐条"""
        if self.api_type != "get" or self.endpoint != mt_config.DEFAULT_ENDPOINT:
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

    # ---------- 第二段：机翻 ----------
    def translate(self, masked, seg=False):
        keys = [k for k, v in masked.items() if not (isinstance(v, str) and v.strip())]
        total, t0, done = len(keys), time.time(), 0
        self.log(self.L["log_trans_s" if seg else "log_trans_b"].format(total))
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
                    self._save(masked)
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
                    self._save(masked)
                    self.cb("trans", done, total, self._eta(t0, done, total))
                time.sleep(0.45 + random.random() * 0.5)
        self._save(masked)
        self.log(self.L["log_trans_ok"].format(done, (time.time() - t0) / 60))
        return masked

    def _save(self, masked):
        json.dump(masked, open(os.path.join(self.work, "masked.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    def _eta(self, t0, done, total):
        r = done / (time.time() - t0)
        return self.L["log_speed"].format(r, (total - done) / r / 60) if r > 0 else self.L["log_calc"]

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
            self.cb("apply", ok, max(ok + drop_tok + drop_nl, 1), "")
            self.log(self.L["log_apply"].format(ok, drop_tok, drop_nl))
            if not auto_seg_sweep or (drop_tok + drop_nl) == 0 or round_ == 1:
                break
            self.log(self.L["log_seg"])
            masked = self.translate(masked, seg=True)
        orig = mt_config.load_loose_json(self.src)
        out = dict(orig)
        for k, zh in result.items():
            out[key_of(k)] = zh
        dst = os.path.splitext(self.src)[0] + "_translated.json"
        json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        self._save(masked)
        return dst, ok, drop_tok + drop_nl

    def run(self):
        masked, tokens = self.clean()
        if not masked:
            orig = json.load(open(self.src, encoding="utf-8"))
            dst = os.path.splitext(self.src)[0] + "_translated.json"
            json.dump(orig, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            self.log(self.L["no_trans"])
            return dst, 0, 0
        masked = self.translate(masked)
        if self.policy_skips:
            msg = (f"[safety-policy] {self.policy_skips} blocked by content policy"
                   f" / {self.policy_skips} 条被内容策略拦截")
            if self.fallback_saved:
                msg += (f"；其中 {self.fallback_saved} 条已由免费机翻兜底重译"
                        f" / {self.fallback_saved} salvaged via free MT")
            else:
                msg += "，保持原文 / kept as original"
            self.log(msg)
        return self.apply(masked, tokens)

# ---------------- GUI ----------------
ACCENT = "#2563eb"      # 主色
ACCENT_HOVER = "#1d4ed8"
BG = "#f5f6f8"
DROP_BG = "#eef2ff"
DROP_BORDER = "#c7d2fe"

# 接口类型（语言中立标签）
API_TYPES = [("MT · GET", "get"), ("AI · OpenAI", "openai")]

class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.src_file = None
        self.out_file = None
        env = mt_config.load_env()
        self.lang = env.get("MT_LANG", "zh")
        if self.lang not in S:
            self.lang = "zh"
        self._style()
        self._build()
        self.root.after(100, self._poll)

    def T(self, key):
        return S[self.lang][key]

    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        base_font = ("Microsoft YaHei UI", 10) if self.lang == "zh" else ("Segoe UI", 10)
        self.root.option_add("*Font", base_font)
        st.configure("TFrame", background=BG)
        st.configure("TLabelframe", background=BG, borderwidth=1, relief="solid")
        st.configure("TLabelframe.Label", background=BG, foreground="#374151",
                     font=(base_font[0], 10, "bold"))
        st.configure("TLabel", background=BG, foreground="#1f2937")
        st.configure("Hint.TLabel", foreground="#8a93a3", font=(base_font[0], 8))
        st.configure("TButton", padding=(10, 5))
        st.configure("Accent.TButton", foreground="#ffffff", background=ACCENT,
                     padding=(16, 6), font=(base_font[0], 10, "bold"))
        st.map("Accent.TButton",
               background=[("active", ACCENT_HOVER), ("disabled", "#9db4f5")])
        st.configure("TProgressbar", thickness=14, background=ACCENT,
                     troughcolor="#e5e7eb")
        st.configure("TCombobox", padding=(4, 3))

    def _build(self):
        self.root.title(self.T("title"))
        self.root.geometry("720x600")
        self.root.minsize(640, 540)
        self.root.configure(bg=BG)

        # ---- 顶栏：标题 + 语言切换 ----
        head = ttk.Frame(self.root, padding=(14, 10, 14, 0))
        head.pack(fill="x")
        ttk.Label(head, text=self.T("title"),
                  font=("Microsoft YaHei UI", 13, "bold"),
                  foreground="#111827").pack(side="left")
        self.lang_btn = tk.Button(head, text=self.T("lang_btn"), command=self.toggle_lang,
                                  relief="flat", bg="#e5e7eb", fg="#374151",
                                  activebackground="#d1d5db", padx=12, pady=2,
                                  cursor="hand2", font=("Segoe UI", 9, "bold"))
        self.lang_btn.pack(side="right")

        # ---- 语言与选项行 ----
        row1 = ttk.Frame(self.root, padding=(14, 8))
        row1.pack(fill="x")
        self.lbl_src = ttk.Label(row1, text=self.T("src"))
        self.lbl_src.pack(side="left")
        self.sl_var = tk.StringVar(value="English")
        names_list = [n for n, _ in LANGS]
        ttk.Combobox(row1, textvariable=self.sl_var, values=names_list,
                     width=11, state="readonly").pack(side="left", padx=(4, 10))
        self.lbl_tgt = ttk.Label(row1, text=self.T("tgt"))
        self.lbl_tgt.pack(side="left")
        self.tl_var = tk.StringVar(value="中文(简)" if self.lang == "zh" else "中文(简)")
        ttk.Combobox(row1, textvariable=self.tl_var, values=names_list,
                     width=11, state="readonly").pack(side="left", padx=4)
        self.autonames_var = tk.BooleanVar(value=True)
        self.ck_autonames = ttk.Checkbutton(row1, text=self.T("autonames"),
                                            variable=self.autonames_var)
        self.ck_autonames.pack(side="left", padx=14)
        self.lbl_names_hint = ttk.Label(row1, text=self.T("names_hint"), style="Hint.TLabel")
        self.lbl_names_hint.pack(side="left")

        # ---- 接口配置 ----
        cfg = ttk.LabelFrame(self.root, text=self.T("api_frame"), padding=8)
        cfg.pack(fill="x", padx=14, pady=(4, 2))
        self._cfg_frame = cfg
        # 类型 + 模型行
        self.type_var = tk.StringVar(value="MT · GET")
        ttk.Label(cfg, text="Type:").grid(row=0, column=0, sticky="w")
        self.type_cmb = ttk.Combobox(cfg, textvariable=self.type_var,
                                     values=[n for n, _ in API_TYPES],
                                     width=13, state="readonly")
        self.type_cmb.grid(row=0, column=1, columnspan=2, sticky="w", padx=4, pady=2)
        ttk.Label(cfg, text="Model:").grid(row=0, column=3, sticky="e")
        self.model_var = tk.StringVar(value="")
        self.model_entry = ttk.Entry(cfg, textvariable=self.model_var, width=18)
        self.model_entry.grid(row=0, column=4, sticky="w", padx=4)
        self.lbl_url = ttk.Label(cfg, text=self.T("url"))
        self.lbl_url.grid(row=1, column=0, sticky="w")
        self.url_var = tk.StringVar(value=mt_config.DEFAULT_ENDPOINT)
        ttk.Entry(cfg, textvariable=self.url_var).grid(row=1, column=1, columnspan=3,
                                                       sticky="we", padx=4, pady=2)
        self.lbl_key = ttk.Label(cfg, text=self.T("key"))
        self.lbl_key.grid(row=2, column=0, sticky="w")
        self.key_var = tk.StringVar(value="")
        ttk.Entry(cfg, textvariable=self.key_var, show="*").grid(row=2, column=1,
                                                                 sticky="we", padx=4, pady=2)
        self.lbl_header = ttk.Label(cfg, text=self.T("header"))
        self.lbl_header.grid(row=2, column=3, sticky="e")
        self.hdr_var = tk.StringVar(value="Authorization")
        ttk.Entry(cfg, textvariable=self.hdr_var, width=18).grid(row=2, column=4,
                                                                 sticky="w", padx=4)
        self.save_btn = ttk.Button(cfg, text=self.T("save_env"), command=self.save_env)
        self.save_btn.grid(row=1, column=5, rowspan=2, padx=(8, 0), sticky="ns")
        self.lbl_api_hint = ttk.Label(cfg, text=self.T("api_hint"), style="Hint.TLabel")
        self.lbl_api_hint.grid(row=3, column=0, columnspan=6, sticky="w", pady=(4, 0))
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
        if env.get("MT_API_TYPE"):
            for n, v in API_TYPES:
                if v == env["MT_API_TYPE"]:
                    self.type_var.set(n)
        if env.get("MT_MODEL"):
            self.model_var.set(env["MT_MODEL"])

        # ---- 拖放区 ----
        drop_text = self.T("drop") + (self.T("drop_nodnd") if not HAS_DND else "")
        self.drop = tk.Label(self.root, text=drop_text, relief="flat",
                             bg=DROP_BG, fg="#4b5563", padx=16, pady=26,
                             font=("Microsoft YaHei UI", 12), cursor="hand2",
                             highlightthickness=2, highlightbackground=DROP_BORDER)
        self.drop.pack(fill="x", padx=14, pady=8)
        self.drop.bind("<Button-1>", lambda e: self.pick())
        self.drop.bind("<Enter>", lambda e: self.drop.config(highlightbackground=ACCENT))
        self.drop.bind("<Leave>", lambda e: self.drop.config(highlightbackground=DROP_BORDER))
        if HAS_DND:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", lambda e: self.on_drop(self._dnd_clean(e.data)))

        # ---- 进度区 ----
        prog = ttk.Frame(self.root, padding=(14, 2))
        prog.pack(fill="x")
        self.stage_var = tk.StringVar(value=self.T("waiting"))
        self.lbl_stage = ttk.Label(prog, textvariable=self.stage_var,
                                   font=("Microsoft YaHei UI", 10, "bold"),
                                   foreground=ACCENT)
        self.lbl_stage.pack(anchor="w")
        self.bar = ttk.Progressbar(prog, maximum=100, style="TProgressbar")
        self.bar.pack(fill="x", pady=5)
        self.detail_var = tk.StringVar(value="")
        ttk.Label(prog, textvariable=self.detail_var, style="Hint.TLabel").pack(anchor="w")

        # ---- 按钮区 ----
        btns = ttk.Frame(self.root, padding=(14, 4))
        btns.pack(fill="x")
        self.start_btn = ttk.Button(btns, text=self.T("start"), style="Accent.TButton",
                                    command=self.start, state="disabled")
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btns, text=self.T("cancel"), command=self.cancel_now,
                                     state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        self.open_btn = ttk.Button(btns, text=self.T("open_out"), command=self.open_out,
                                   state="disabled")
        self.open_btn.pack(side="left")

        # ---- 日志 ----
        self.logbox = ScrolledText(self.root, height=8, font=("Consolas", 9),
                                   state="disabled", bg="#ffffff", relief="flat",
                                   highlightthickness=1, highlightbackground="#e5e7eb")
        self.logbox.pack(fill="both", expand=True, padx=14, pady=(6, 12))

    # ---- 语言切换 ----
    def toggle_lang(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        mt_config.save_env({"MT_LANG": self.lang})
        self.root.title(self.T("title"))
        self.lang_btn.config(text=self.T("lang_btn"))
        self.lbl_src.config(text=self.T("src"))
        self.lbl_tgt.config(text=self.T("tgt"))
        self.ck_autonames.config(text=self.T("autonames"))
        self.lbl_names_hint.config(text=self.T("names_hint"))
        self._rebuild_texts()

    def _rebuild_texts(self):
        for w in (self.lbl_url, self.lbl_key, self.lbl_header, self.save_btn, self.lbl_api_hint):
            w.destroy()
        cfg = self._cfg_frame
        self.lbl_url = ttk.Label(cfg, text=self.T("url"))
        self.lbl_url.grid(row=1, column=0, sticky="w")
        self.lbl_key = ttk.Label(cfg, text=self.T("key"))
        self.lbl_key.grid(row=2, column=0, sticky="w")
        self.lbl_header = ttk.Label(cfg, text=self.T("header"))
        self.lbl_header.grid(row=2, column=3, sticky="e")
        self.save_btn = ttk.Button(cfg, text=self.T("save_env"), command=self.save_env)
        self.save_btn.grid(row=1, column=5, rowspan=2, padx=(8, 0), sticky="ns")
        self.lbl_api_hint = ttk.Label(cfg, text=self.T("api_hint"), style="Hint.TLabel")
        self.lbl_api_hint.grid(row=3, column=0, columnspan=6, sticky="w", pady=(4, 0))
        cfg.config(text=self.T("api_frame"))
        self.drop.config(text=self.T("drop") + (self.T("drop_nodnd") if not HAS_DND else ""))
        self.start_btn.config(text=self.T("start"))
        self.cancel_btn.config(text=self.T("cancel"))
        self.open_btn.config(text=self.T("open_out"))
        if not self.worker or not self.worker.is_alive():
            if self.stage_var.get() in (S["zh"]["waiting"], S["en"]["waiting"]):
                self.stage_var.set(self.T("waiting"))
            elif self.src_file and self.stage_var.get().startswith((S["zh"]["ready"][:3], S["en"]["ready"][:5])):
                self.stage_var.set(self.T("ready").format(os.path.basename(self.src_file)))

    @staticmethod
    def _dnd_clean(data):
        return data.strip("{}").split("} {")[0].strip()

    def log(self, msg):
        self.q.put(("log", msg))

    def on_drop(self, path):
        path = path.strip().strip('"')
        if not path.lower().endswith(".json"):
            # 不是 json → 尝试引擎识别（目录或 exe）
            eng, name, ok, reason = mt_config.detect_engine(path)
            if ok:
                extract = mt_config.ENGINE_EXTRACTORS.get(eng)
                if extract:
                    if messagebox.askyesno(
                            f"✅ {name}",
                            f"检测到 {name}，是否自动提取文本？\n\n"
                            f"将运行 {extract}（可能需要几分钟）"):
                        self._run_extractor(path, extract)
                        return
            else:
                messagebox.showwarning(
                    f"❌ {name} — 不支持",
                    f"引擎：{name}\n\n{reason}")
                self.log(f"[engine] {name}: 不支持 — {reason}")
                return
        self.set_file(path)

    def _run_extractor(self, game_path, script):
        """在线程中 import 提取脚本并调用 main()——避免 subprocess 在打包 exe 里打开新窗口"""
        base = mt_config.base_dir()
        script_path = os.path.join(base, script)
        if not os.path.exists(script_path):
            messagebox.showerror("Error", f"脚本不存在: {script_path}")
            return
        self.log(f"[extract] 运行 {script} {game_path}")
        self.stage_var.set("提取中… / Extracting…")
        self.bar["value"] = 0
        def worker():
            import importlib.util
            try:
                # 动态加载提取脚本
                mod_name = script.replace(".py", "")
                spec = importlib.util.spec_from_file_location(mod_name, script_path)
                mod = importlib.util.module_from_spec(spec)
                # 替换 sys.argv 让 main() 拿到游戏路径
                old_argv = sys.argv
                sys.argv = [script, game_path]
                spec.loader.exec_module(mod)
                # 调 main()
                mod.main()
                sys.argv = old_argv
                # 找最新生成的 *_extracted.json
                import glob as g
                cands = sorted(g.glob(os.path.join(base, "*_extracted*.json")),
                               key=os.path.getmtime, reverse=True)
                if cands:
                    newest = cands[0]
                    self.q.put(("extracted", newest))
                else:
                    self.q.put(("error", "提取完成但未找到输出文件"))
            except SystemExit:
                pass    # 提取脚本可能用 sys.exit
            except Exception as e:
                self.q.put(("error", traceback.format_exc()[-800:]))
        threading.Thread(target=worker, daemon=True).start()

    def pick(self):
        p = filedialog.askopenfilename(title=self.T("sel_file"),
                                       filetypes=[("JSON", "*.json"), ("Executable", "*.exe"),
                                                  ("All files", "*.*")])
        if not p:
            p = filedialog.askdirectory(title="Select game folder / 游戏目录")
        if p:
            self.on_drop(p)

    def set_file(self, p):
        self.src_file = p
        self.out_file = None
        self.stage_var.set(self.T("ready").format(os.path.basename(p)))
        self.detail_var.set(p)
        self.start_btn.config(state="normal")
        self.open_btn.config(state="disabled")
        self.drop.config(fg="#15803d")
        self.log(f"[file] {p}")

    def start(self):
        if not self.src_file or (self.worker and self.worker.is_alive()):
            return
        sl = dict(LANGS)[self.sl_var.get()]
        tl = dict(LANGS)[self.tl_var.get()]
        try:
            mt_config.build_url(self.url_var.get().strip() or mt_config.DEFAULT_ENDPOINT,
                                "test", sl, tl)
        except ValueError as e:
            messagebox.showerror(self.T("msg_badurl"), str(e))
            return
        h = hashlib.md5(self.src_file.encode()).hexdigest()[:8]
        work = os.path.join(mt_config.base_dir(), "mt_work", h)
        pipe = Pipe(self.src_file, work, sl, tl, self.cancel, self._cb, self.log,
                    endpoint=self.url_var.get().strip(),
                    api_key=self.key_var.get().strip(),
                    api_header=self.hdr_var.get().strip(),
                    auto_names=self.autonames_var.get(),
                    lang=self.lang,
                    api_type=dict(API_TYPES)[self.type_var.get()],
                    model=self.model_var.get().strip())
        self.cancel.clear()
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.drop.config(fg="#6b7280")
        self.log(self.T("log_start").format(self.sl_var.get(), self.tl_var.get()))
        self.worker = threading.Thread(target=self._work, args=(pipe,), daemon=True)
        self.worker.start()

    def _work(self, pipe):
        try:
            dst, ok, drop = pipe.run()
            self.q.put(("done", (dst, ok, drop)))
        except Cancel:
            self.q.put(("cancelled", None))
        except mt_config.ApiError as e:
            self.q.put(("error", e.args[0]))   # 友好双语提示，非 traceback
        except Exception:
            self.q.put(("error", traceback.format_exc()))

    def _cb(self, stage, done, total, note):
        self.q.put(("prog", (stage, done, total, note)))

    def cancel_now(self):
        self.cancel.set()
        self.log(self.T("log_cancel"))

    def open_out(self):
        if self.out_file and os.path.exists(self.out_file):
            os.startfile(os.path.dirname(self.out_file))

    def save_env(self):
        try:
            mt_config.save_env({
                "MT_ENDPOINT": self.url_var.get().strip(),
                "MT_API_KEY": self.key_var.get().strip(),
                "MT_API_HEADER": self.hdr_var.get().strip(),
                "MT_AUTO_NAMES": "1" if self.autonames_var.get() else "0",
                "MT_LANG": self.lang,
                "MT_API_TYPE": dict(API_TYPES)[self.type_var.get()],
                "MT_MODEL": self.model_var.get().strip(),
            })
            self.log(self.T("log_cfg").format(mt_config.env_path()))
            messagebox.showinfo(self.T("msg_saved"), self.T("msg_saved_b").format(mt_config.env_path()))
        except Exception as e:
            messagebox.showerror(self.T("msg_savefail"), str(e))

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
                    name = {"clean": self.T("stage_clean"), "trans": self.T("stage_trans"),
                            "apply": self.T("stage_apply")}[stage]
                    pct = done * 100 // max(total, 1)
                    self.stage_var.set(f"{name}  {done}/{total}  （{pct}%）")
                    self.bar["value"] = pct
                    self.detail_var.set(f"{note}    {pct}%")
                elif kind == "done":
                    dst, ok, drop = payload
                    self.out_file = dst
                    self.bar["value"] = 100
                    self.stage_var.set(self.T("done_stage"))
                    self.detail_var.set(f"ok={ok}, skipped={drop}")
                    self.log(f"[output] {dst}")
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.open_btn.config(state="normal")
                    self.drop.config(fg="#15803d")
                    messagebox.showinfo(self.T("msg_done_t"),
                                        self.T("msg_done_b").format(ok, drop, dst))
                elif kind == "cancelled":
                    self.stage_var.set(self.T("cancelled"))
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.log(self.T("log_cancelled"))
                elif kind == "extracted":
                    self.set_file(payload)
                    self.log(f"[extract] 提取完成，已加载: {payload}")
                elif kind == "error":
                    self.stage_var.set(self.T("error"))
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.log(payload)
                    messagebox.showerror(self.T("error"), payload[:1500])
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

def main():
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
