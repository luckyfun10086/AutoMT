# -*- coding: utf-8 -*-
"""AutoMT 配置层：.env 读写 + 自定义翻译接口支持。

隐私设计（开源友好）：
- 一切个人配置（自定义接口 URL / API Key / 请求头）都放 .env，.env 进 .gitignore
- 不填则使用内置免费端点（公开、无需密钥）
- 代码中不包含任何密钥、个人路径

.env 支持的变量：
    MT_ENDPOINT=https://xxx/translate?sl={sl}&tl={tl}&q={q}
        {sl}=源语言 {tl}=目标语言 {q}=URL编码后的原文，三个占位符必须出现 {q} 至少一次
    MT_API_KEY=你的密钥          （可选）
    MT_API_HEADER=Authorization  （可选，默认 Authorization，值以 Bearer 方式发送；
                                  指定其他头名则以原值发送）
响应格式自动识别：谷歌 /t 列表、DeepL {"translations":[{"text":..}]}、纯文本
"""
import os, re, json, urllib.parse

DEFAULT_ENDPOINT = ("https://clients5.google.com/translate_a/t"
                    "?client=dict-chrome-ex&sl={sl}&tl={tl}&q={q}")

ENV_KEYS = ("MT_ENDPOINT", "MT_API_KEY", "MT_API_HEADER", "MT_SL", "MT_TL")

def env_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

def load_env():
    """极简 .env 解析（无第三方依赖），不存在则返回空 dict"""
    cfg = {}
    p = env_path()
    if os.path.exists(p):
        for line in open(p, encoding="utf-8-sig"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k in ENV_KEYS:
                cfg[k] = v
    return cfg

def save_env(cfg):
    """把指定键写回 .env（保留原有注释与其他行）"""
    p = env_path()
    keep = []
    if os.path.exists(p):
        for line in open(p, encoding="utf-8-sig"):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s and s.partition("=")[0].strip() in cfg:
                continue
            keep.append(line.rstrip("\n"))
    while keep and not keep[-1]:
        keep.pop()
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        if keep:
            f.write("\n".join(keep) + "\n")
        for k in ENV_KEYS:
            if k in cfg and cfg[k]:
                f.write(f"{k}={cfg[k]}\n")

def build_url(endpoint, q, sl, tl):
    if "{q}" not in endpoint:
        raise ValueError("接口 URL 缺少 {q} 占位符（还需要 {sl} {tl} 可选占位符），"
                         "示例：https://xxx/t?sl={sl}&tl={tl}&q={q}")
    return (endpoint.replace("{sl}", urllib.parse.quote(sl or "auto"))
                    .replace("{tl}", urllib.parse.quote(tl or "zh-CN"))
                    .replace("{q}", urllib.parse.quote(q)))

def build_headers(api_key=None, api_header=None):
    if not api_key:
        return {}
    name = (api_header or "Authorization").strip() or "Authorization"
    if name.lower() == "authorization":
        return {name: f"Bearer {api_key}"}
    return {name: api_key}

def parse_response(raw):
    """自动识别常见机翻响应格式"""
    raw = raw.strip()
    try:
        d = json.loads(raw)
    except Exception:
        return raw  # 纯文本
    if isinstance(d, list):
        if d and isinstance(d[0], list):
            return "".join(x[0] if isinstance(x, list) else str(x) for x in d[0])
        return "".join(str(x) for x in d)
    if isinstance(d, dict):
        for path in (("translations",), ("data", "translations"), ("result",)):
            node = d
            ok = True
            for k in path:
                if isinstance(node, dict) and k in node:
                    node = node[k]
                else:
                    ok = False
                    break
            if ok and isinstance(node, list) and node and isinstance(node[0], dict):
                return "".join(str(t.get("text", t.get("translatedText", ""))) for t in node)
        for k in ("translatedText", "text", "result"):
            if isinstance(d.get(k), str):
                return d[k]
    return raw
