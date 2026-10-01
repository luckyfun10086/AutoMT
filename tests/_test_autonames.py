# -*- coding: utf-8 -*-
"""自动人名识别 + 全流程测试"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engines"))

import io, sys, json, threading, os, tempfile, shutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import mt_config, mt_gui

# 1) detect_names 单测
texts = [
    "Alice went to the market. She bought apples.",
    "Alice met Bob at the tower.",
    "Bob said Alice is kind, but bob never shares.",
    "The magic sword glows with magic.",
    "Alice! Watch out! HP and MP are low!",
    "HP restored. MP is full.",
]
names = mt_config.detect_names(texts, "en", min_count=2)
detected = [w for w, c in names]
print("识别结果:", detected)
assert "Alice" in detected, "Alice 应被识别（从不小写）"
assert "Bob" in detected, "Bob 应被识别"
assert "magic" not in [w.lower() for w in detected], "magic 不应识别（大小写混现）"
assert "She" not in detected and "The" not in detected, "普通词不应识别"
assert "Thanks" not in detected and "Please" not in detected, "高频词库应滤掉习惯大写词"
print("detect_names 英语单测 ✓")

# 日语：片假名检测
ja = [
    "アリスは剣を構えた。",
    "アリス、しっかりして！",
    "リチャードがアリスを見つめた。",
    "リチャードは笑った。",
    "ダメージを受けた！ダメージが大きい！",
    "スキルを覚えた。",
]
ja_names = [w for w, c in mt_config.detect_names(ja, "ja", min_count=2)]
print("日语识别:", ja_names)
assert "アリス" in ja_names, "アリス 应识别"
assert "リチャード" in ja_names, "リチャード 应识别"
assert "ダメージ" not in ja_names and "スキル" not in ja_names, "游戏术语应排除"
print("detect_names 日语单测 ✓")

# 俄语：变格聚类
ru = [
    "Алиса пошла домой.",
    "Я видел Алису вчера.",
    "Подарим Алисе цветы.",
    "Это Алисин дом.",
]
ru_names = [w for w, c in mt_config.detect_names(ru, "ru")]
print("俄语识别:", ru_names)
assert any(w.startswith("Алис") for w in ru_names), "Алиса 各变格应聚为一簇"
print("detect_names 俄语单测 ✓")

# 中韩：应返回空
assert mt_config.detect_names(["张三打李四。"], "zh") == []
assert mt_config.detect_names(["김철수가 갔다."], "ko") == []
print("detect_names 中韩跳过 ✓")

# 2) 端到端（无 names.txt，纯自动识别 + 默认端点翻1条）
tmp = tempfile.mkdtemp()
src = os.path.join(tmp, "ManualTransFile.json")
json.dump({"Alice went home.": "", "Alice is tired.": ""}, open(src, "w", encoding="utf-8"),
          ensure_ascii=False)
pipe = mt_gui.Pipe(src, os.path.join(tmp, "work"), "en", "zh-CN", threading.Event(),
                   lambda s, d, t, n: None, lambda m: print("[log]", m))
dst, ok, drop = pipe.run()
out = json.load(open(dst, encoding="utf-8"))
print("结果:", out)
assert ok == 2
assert "Alice" in out["Alice went home."], "开启识别时应保持原文 Alice"
shutil.rmtree(tmp)

# 3) 关闭自动识别：人名交给机翻
tmp = tempfile.mkdtemp()
src = os.path.join(tmp, "ManualTransFile.json")
json.dump({"Alice went home.": ""}, open(src, "w", encoding="utf-8"), ensure_ascii=False)
pipe = mt_gui.Pipe(src, os.path.join(tmp, "work"), "en", "zh-CN", threading.Event(),
                   lambda s, d, t, n: None, lambda m: print("[log]", m), auto_names=False)
dst, ok, drop = pipe.run()
out = json.load(open(dst, encoding="utf-8"))
print("关闭识别结果:", out)
assert ok == 1
v = out["Alice went home."]
assert "Alice" not in v or "爱丽丝" in v, "关闭识别后人名由机翻处理"
print("ALL TESTS PASS")
