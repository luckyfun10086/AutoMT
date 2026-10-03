# -*- coding: utf-8 -*-
"""load_loose_json // 注释剥离回归测试。

背景：Wolf 提取的游戏文本键可以 "//" 开头（注释型台词），旧正则方案
把字符串内的 // 当行尾注释砍掉，导致 JSONDecodeError "Expecting ':'"。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mt_config import _strip_json_comments, load_loose_json  # noqa: E402

FAILED = []


def check(name, got, want):
    ok = got == want
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  got={got!r} want={want!r}"))
    if not ok:
        FAILED.append(name)


def strip(txt):
    return json.loads(_strip_json_comments(txt), strict=False)


# ---- 真实事故形态：键以 // 开头（Wolf 注释型台词） ----
check("键以//开头", strip('{"//※港口：随机事件": ""}'), {"//※港口：随机事件": ""})
check("键//含URL样式", strip('{"//周末感染率99%": "", "b": "1"}'),
      {"//周末感染率99%": "", "b": "1"})

# ---- 注释应被剥离的场景（MTool 导出头等） ----
check("整行注释", strip('// MTool export\n{"a": "1"}'), {"a": "1"})
check("多行整行注释", strip('// x\n// y\n{"a": "1"}'), {"a": "1"})
check("行尾注释", strip('{\n  "a": "1" // trailing\n}'), {"a": "1"})
check("行尾注释带逗号", strip('{"a": "1", // c\n "b": "2"}'), {"a": "1", "b": "2"})
check("数组内注释", strip('["a", // mid\n "b"]'), ["a", "b"])
check("注释后无换行", strip('{"a": "1"} // eof'), {"a": "1"})

# ---- 字符串内的 // 必须保留 ----
check("值内//", strip('{"k": "http://x // y"}'), {"k": "http://x // y"})
check("值尾//", strip('{"k": "text//"}'), {"k": "text//"})
check("值中双斜杠URL", strip('{"k": "https://a.b/c"}'), {"k": "https://a.b/c"})
check("转义引号后//", strip('{"k": "a\\"b // c"}'), {"k": 'a"b // c'})
check("转义反斜杠后//", strip('{"k": "a\\\\//b"}'), {"k": "a\\//b"})
check("注释标记紧邻引号前", strip('{"a": "x","b": "y" // c\n}'), {"a": "x", "b": "y"})

# ---- 其他宽容特性不回归 ----
check("无注释", strip('{"k": "v"}'), {"k": "v"})
check("控制字符", strip('{"k": "a\tb"}'), {"k": "a\tb"})

# ---- 文件级：BOM + 注释混合 ----
tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_loose.json")
with open(tmp, "w", encoding="utf-8-sig", newline="\r\n") as f:
    f.write('// header\r\n{"//键": "值", "k": "v" // tail\r\n}')
check("BOM+CRLF+注释(文件)", load_loose_json(tmp), {"//键": "值", "k": "v"})
os.remove(tmp)

print()
if FAILED:
    print(f"失败 {len(FAILED)} 项: {FAILED}")
    sys.exit(1)
print("全部通过")
