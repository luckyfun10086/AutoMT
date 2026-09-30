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
print('ALL TESTS PASS')
