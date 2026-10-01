# -*- coding: utf-8 -*-
"""AI 批量翻译自测
==================
1. 批量主路径：mock 返回乱序 items（按 id 对齐）→ Pipe 全链路
2. 上下文注入：请求体含 ctx（前文/后文）；MT_CONTEXT=0 关闭
3. 等长校验：返回条数不符 → 重试 → 降级逐条
4. 记号保持：批量译文里 〔T..〕 原样
运行：python _test_aibatch.py
"""
import io, sys, json, threading, os, tempfile, shutil, http.server, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'engines'))
import mt_gui, mt_config

FAILS = []

def check(name, cond, info=""):
    print(("✓ " if cond else "✗ ") + name + (f"  {info}" if info and not cond else ""))
    if not cond:
        FAILS.append(name)

PORT = 18790
requests_seen = []

class AI(http.server.BaseHTTPRequestHandler):
    mode = "batch"          # batch / broken / single
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n))
        user = req["messages"][1]["content"]
        try:
            requests_seen.append(json.loads(user))
        except Exception:
            requests_seen.append({"raw": user})   # 逐条降级请求是纯文本

        def send(obj):
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        if AI.mode == "batch":
            items = requests_seen[-1]["items"]
            # 乱序 + markdown 围栏 + 字段名用 translation —— 全方位解析考验
            out = [{"id": it["id"], "translation": "【批】" + it["text"]}
                   for it in reversed(items)]
            send({"choices": [{"message": {
                "content": "```json\n" + json.dumps({"items": out},
                                                    ensure_ascii=False) + "\n```"}}]})
        elif AI.mode == "broken":
            send({"choices": [{"message": {"content": "抱歉我不知道怎么输出"}}]})
        else:   # single：逐条原文回显（供降级路径）
            send({"choices": [{"message": {"content": "【单】" + user}}]})

    def log_message(self, *a):
        pass

srv = http.server.HTTPServer(("127.0.0.1", PORT), AI)
threading.Thread(target=srv.serve_forever, daemon=True).start()
EP = f"http://127.0.0.1:{PORT}/v1/chat/completions"

def run_pipe(texts, ctx_default=True):
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "game_extracted.json")
    json.dump({k: "" for k in texts}, open(src, "w", encoding="utf-8"), ensure_ascii=False)
    if not ctx_default:
        mt_config.save_env({"MT_CONTEXT": "0"})
    try:
        pipe = mt_gui.Pipe(src, os.path.join(tmp, "w"), "en", "zh-CN", threading.Event(),
                           lambda s, d, t, n: None, lambda m: None,
                           endpoint=EP, api_key="k", api_type="openai", model="m")
        dst, ok, drop = pipe.run()
        return json.load(open(dst, encoding="utf-8")), pipe, tmp
    finally:
        if not ctx_default:
            mt_config.save_env({"MT_CONTEXT": "1"})
            # 清掉测试写入的 MT_CONTEXT 行
            p = mt_config.env_path()
            lines = [l for l in open(p, encoding="utf-8") if not l.startswith("MT_CONTEXT")]
            open(p, "w", encoding="utf-8", newline="\n").writelines(lines)

# ---------- 1+2+4 批量主路径 + 上下文 + 记号 ----------
AI.mode = "batch"
requests_seen.clear()
texts = [f"Line number {i} with 〔T{i:08x}〕 token" for i in range(1, 31)]
out, pipe, tmp = run_pipe(texts)
check("批量主路径全链路", all(out[k].startswith("【批】") for k in texts))
check("记号原样保留", all(f"〔T{i:08x}〕" in out[k] for i, k in
                        zip(range(1, 31), texts)))
check("批量打包（24/组 → 30条=2组）", len(requests_seen) == 2, str(len(requests_seen)))
first = requests_seen[0]["items"]
check("请求含 id+text", all(("id" in it and "text" in it) for it in first))
check("上下文注入（前文/后文）", any("ctx" in it and "前文" in it["ctx"] for it in first))
check("中间条目有前后文", "前文" in first[3].get("ctx", "") and "后文" in first[3].get("ctx", ""))
print("  批量请求组数:", len(requests_seen), "| 首组条数:", len(first))
shutil.rmtree(tmp, ignore_errors=True)

# ---------- 上下文关闭 ----------
AI.mode = "batch"
requests_seen.clear()
out, pipe, tmp = run_pipe(["only one line here"], ctx_default=False)
check("MT_CONTEXT=0 → 无 ctx 字段",
      all("ctx" not in it for it in requests_seen[0]["items"]))
shutil.rmtree(tmp, ignore_errors=True)

# ---------- 3 等长校验降级：broken → 重试耗尽 → 半组 → 逐条 ----------
AI.mode = "broken"
# broken 批量响应非法 → _ai_group 重试3次 → 半组递归(depth 3 上限) → 逐条 mt_one，
# 而 mt_one 走 translate_once（非批量）→ AI.mode 仍 broken 会对逐条也返回非法内容！
# 所以 broken 模式下逐条也失败——为了只测"降级到逐条"，第 N 次请求起切换 single：
orig_do_POST = AI.do_POST
calls = {"n": 0}
def switchy_do_POST(self):
    calls["n"] += 1
    if calls["n"] >= 5:      # 3次组重试 + 1 次半组后切逐条
        AI.mode = "single"
    orig_do_POST(self)
AI.do_POST = switchy_do_POST
out, pipe, tmp = run_pipe([f"degrade test {i}" for i in range(4)])
AI.do_POST = orig_do_POST
check("结构不符→降级逐条成功", all(v.startswith("【单】") for v in out.values()),
      str(list(out.values())))
check("降级计数", pipe.ai_degraded >= 4, str(pipe.ai_degraded))
shutil.rmtree(tmp, ignore_errors=True)

# ---------- 5 降级路径回归（旧 _test_custom 的语义）：skip 组→逐条 ----------
class SK(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        user = json.loads(self.rfile.read(n))["messages"][1]["content"]

        def send(code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        if "BLOCKSKIP" in user:
            send(400, {"error": {"message": "Content blocked by content policy"}})
        elif user.lstrip().startswith("{"):
            items = json.loads(user)["items"]
            out = [{"id": it["id"], "zh": "【批】" + it["text"]} for it in items]
            send(200, {"choices": [{"message": {
                "content": json.dumps({"items": out}, ensure_ascii=False)}}]})
        else:   # 逐条降级请求（纯文本）
            send(200, {"choices": [{"message": {"content": "【单】" + user}}]})
    def log_message(self, *a):
        pass

srv2 = http.server.HTTPServer(("127.0.0.1", PORT + 1), SK)
threading.Thread(target=srv2.serve_forever, daemon=True).start()
tmp = tempfile.mkdtemp()
src = os.path.join(tmp, "f.json")
json.dump({"hello": "", "BLOCKSKIP bad": "", "world": ""}, open(src, "w", encoding="utf-8"),
          ensure_ascii=False)
pipe = mt_gui.Pipe(src, os.path.join(tmp, "w"), "en", "zh-CN", threading.Event(),
                   lambda s, d, t, n: None, lambda m: None,
                   endpoint=f"http://127.0.0.1:{PORT+1}/v1/chat/completions",
                   api_key="k", api_type="openai", model="m", fallback=False)
dst, ok, drop = pipe.run()
out = json.load(open(dst, encoding="utf-8"))
check("组内敏感词→降级逐条→只拦那一条",
      (out["hello"].startswith("【批】") or out["hello"].startswith("【单】"))
      and out["BLOCKSKIP bad"] == ""
      and (out["world"].startswith("【批】") or out["world"].startswith("【单】")), str(out))
shutil.rmtree(tmp, ignore_errors=True)
srv2.shutdown()
srv.shutdown()

print()
if FAILS:
    print(f"✗ {len(FAILS)} 项失败: {FAILS}")
    sys.exit(1)
print("ALL TESTS PASS")
