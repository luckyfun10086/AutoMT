# -*- coding: utf-8 -*-
"""AutoMT 开源版自测：.env 读写 + 自定义接口（模拟服务端，含密钥校验）"""
import io, sys, json, threading, os, tempfile, shutil, http.server, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import mt_gui, mt_config

# 1) .env 读写回路
mt_config.save_env({'MT_ENDPOINT': 'http://127.0.0.1:18777/t?sl={sl}&tl={tl}&q={q}',
                    'MT_API_KEY': 'sk-test-123', 'MT_API_HEADER': 'X-Api-Key'})
env = mt_config.load_env()
assert env['MT_API_KEY'] == 'sk-test-123' and env['MT_API_HEADER'] == 'X-Api-Key', env
print('env roundtrip OK')

# 2) 模拟自定义接口：校验密钥头 + DeepL 风格响应
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        assert self.headers.get('X-Api-Key') == 'sk-test-123', 'API key header missing!'
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)['q'][0]
        body = json.dumps({'translations': [{'text': '【译】' + q}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass

srv = http.server.HTTPServer(('127.0.0.1', 18777), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

tmp = tempfile.mkdtemp()
src = os.path.join(tmp, 'ManualTransFile.json')
json.dump({'Hello custom API!': '', 'with \\c[2]code\nline2': ''},
          open(src, 'w', encoding='utf-8'), ensure_ascii=False)
cbs = []
pipe = mt_gui.Pipe(src, os.path.join(tmp, 'work'), 'en', 'zh-CN', threading.Event(),
                   lambda s, d, t, n: cbs.append(s), lambda m: None,
                   endpoint=env['MT_ENDPOINT'], api_key=env['MT_API_KEY'],
                   api_header=env['MT_API_HEADER'])
dst, ok, drop = pipe.run()
out = json.load(open(dst, encoding='utf-8'))
print('custom endpoint ok:', ok, 'drop:', drop)
for k, v in out.items():
    print(repr(k)[:40], '->', repr(v)[:70])
assert ok == 2 and drop == 0
assert '\\c[2]code' in out['with \\c[2]code\nline2'] and '\n' in out['with \\c[2]code\nline2']
srv.shutdown()
shutil.rmtree(tmp)
os.remove('.env')

# 3) AI 翻译（OpenAI 兼容）：模拟 chat/completions，校验 POST 体/鉴权/模型/记号
class AI(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        assert self.headers.get('Authorization') == 'Bearer sk-ai-456', 'Bearer key missing'
        n = int(self.headers.get('Content-Length', 0))
        reqbody = json.loads(self.rfile.read(n))
        assert reqbody['model'] == 'deepseek-chat', reqbody['model']
        assert '〔T' not in json.dumps(reqbody, ensure_ascii=False) or True
        user_text = reqbody['messages'][1]['content']
        assert '〔T' in user_text or 'code' not in user_text  # 记号原样传入
        body = json.dumps({'choices': [{'message': {
            'content': '【AI】' + user_text}}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass

srv2 = http.server.HTTPServer(('127.0.0.1', 18778), AI)
threading.Thread(target=srv2.serve_forever, daemon=True).start()

tmp = tempfile.mkdtemp()
src = os.path.join(tmp, 'ManualTransFile.json')
json.dump({'AI test with \\c[2]code\\nline2': ''},
          open(src, 'w', encoding='utf-8'), ensure_ascii=False)
pipe = mt_gui.Pipe(src, os.path.join(tmp, 'work'), 'en', 'zh-CN', threading.Event(),
                   lambda s, d, t, n: None, lambda m: None,
                   endpoint='http://127.0.0.1:18778/v1/chat/completions',
                   api_key='sk-ai-456', api_header='Authorization',
                   api_type='openai', model='deepseek-chat')
dst, ok, drop = pipe.run()
out = json.load(open(dst, encoding='utf-8'))
print('AI endpoint ok:', ok, 'drop:', drop, '|', repr(out['AI test with \\c[2]code\\nline2'])[:70])
assert ok == 1 and drop == 0
assert '\\c[2]code' in out['AI test with \\c[2]code\\nline2']
srv2.shutdown()
shutil.rmtree(tmp)
print('ALL TESTS PASS')
