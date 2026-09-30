# -*- coding: utf-8 -*-
"""
AutoMT 第二步：提交翻译（谷歌免费端点）
======================================
读取 mt_work/masked.json，用 Chrome 词典扩展同款免费端点批量机翻。

核心经验（来自实弹项目）：
1. clients5.google.com 端点不审查内容、无需密钥；一次请求可带多条 q（实测 8 条/请求）
2. 节流 0.45~0.95 秒/请求 + 随机抖动 + 5 次指数退避重试 —— 跑 4.7 万条无封禁
3. 每 10 组落盘一次，中断随时可续（重跑自动跳过已翻条目）
4. 记号偶发被机翻丢弃/变形（括号被规范化等）—— 对付顽固条目用 --seg 分段模式：
   按记号切开只翻纯文本段、原位拼回，记号 100% 不可能丢

用法：
    python mt_translate.py           # 批量模式（默认，快）
    python mt_translate.py --seg     # 分段模式（慢但记号绝不丢，用于扫尾）
"""
import json, re, sys, io, time, random, urllib.request, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import mt_config

IN = "mt_work/masked.json"
ENV = mt_config.load_env()
SL = ENV.get("MT_SL", "en")
TL = ENV.get("MT_TL", "zh-CN")
ENDPOINT = ENV.get("MT_ENDPOINT", "").strip() or mt_config.DEFAULT_ENDPOINT
API_TYPE = ENV.get("MT_API_TYPE", "get")
MODEL = ENV.get("MT_MODEL", "")
HEADERS = mt_config.build_headers(ENV.get("MT_API_KEY"), ENV.get("MT_API_HEADER"))
BUILTIN = API_TYPE == "get" and ENDPOINT == mt_config.DEFAULT_ENDPOINT
SEG = "--seg" in sys.argv
segre = re.compile(r"(〔T[0-9a-f]{8}〕)")

def mt(text, tries=5):
    for a in range(tries):
        try:
            return mt_config.translate_once(
                text, SL, TL, endpoint=ENDPOINT,
                api_key=ENV.get("MT_API_KEY"), api_header=ENV.get("MT_API_HEADER"),
                api_type=API_TYPE, model=MODEL)
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(3 + 3 * a + random.random() * 2)

def mt_batch(qs, tries=5):
    if not BUILTIN:
        return [mt(q) for q in qs]
    url = (ENDPOINT.replace("{sl}", SL).replace("{tl}", TL).replace("&q={q}", "")
           + "".join("&q=" + urllib.parse.quote(q) for q in qs))
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            if isinstance(d, list) and len(d) == len(qs):
                return [str(x) for x in d]
            raise ValueError("shape mismatch")
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(3 + 3 * a + random.random() * 2)

def main():
    data = json.load(open(IN, encoding="utf-8"))
    keys = [k for k, v in data.items() if not (isinstance(v, str) and v.strip())]
    total = len(keys)
    print(f"待翻: {total} 条 ({'分段' if SEG else '批量'}模式)", flush=True)
    t0 = time.time()
    done = 0
    if SEG:
        for n, k in enumerate(keys):
            parts = segre.split(k)
            out = []
            for p in parts:
                if segre.fullmatch(p) or not p.strip():
                    out.append(p)
                else:
                    out.append(mt(p))
                    time.sleep(0.15)
            data[k] = "".join(out)
            done += 1
            if n % 50 == 0:
                json.dump(data, open(IN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                rate = done / (time.time() - t0)
                print(f"{done}/{total} ({rate:.1f}/s eta {(total-done)/rate/60:.0f}分)", flush=True)
    else:
        B = 8
        for gi in range(0, len(keys), B):
            group = keys[gi:gi + B]
            if len("".join(group)) > 6000:
                group = group[:max(1, len(group) // 2)]
            try:
                vals = mt_batch(group)
            except Exception:
                vals = [mt([g]) if False else mt(g) for g in group]  # 逐条兜底
            for k, v in zip(group, vals):
                data[k] = v
            done += len(group)
            if (gi // B) % 10 == 0:
                json.dump(data, open(IN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                rate = done / (time.time() - t0)
                eta = (total - done) / rate / 60 if rate > 0 else -1
                print(f"{done}/{total} ({rate:.1f}/s eta {eta:.0f}分)", flush=True)
            time.sleep(0.45 + random.random() * 0.5)
    json.dump(data, open(IN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"完成 {done}/{total}，用时 {(time.time()-t0)/60:.1f} 分钟")
    print("下一步: python mt_apply.py")

if __name__ == "__main__":
    main()
