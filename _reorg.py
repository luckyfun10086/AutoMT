# -*- coding: utf-8 -*-
"""engines/*.py 统一路径自举：项目根（mt_config）+ 自身目录（同包引擎模块）"""
import os, re

ENG = "engines"
BOOT_OLD = "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))"
BOOT_NEW = ("_ENG = os.path.dirname(os.path.abspath(__file__))\n"
            "sys.path.insert(0, os.path.dirname(_ENG))    # 项目根：mt_config 等\n"
            "sys.path.insert(0, _ENG)                     # 引擎同目录：krkr_xp3 等")

for f in sorted(os.listdir(ENG)):
    if not f.endswith(".py"):
        continue
    p = os.path.join(ENG, f)
    s = open(p, encoding="utf-8").read()
    if BOOT_OLD in s:
        s = s.replace(BOOT_OLD, BOOT_NEW, 1)
    else:
        # 无自举的：插在第一个非 docstring 的 import 之前（sys/os 需已导入——
        # 这些文件顶部都有 import ... sys ... os；找首个顶层 import 行前插入）
        m = re.search(r"^(import|from) ", s, re.M)
        ins = ("import os as _os, sys as _sys\n"
               "_ENG = _os.path.dirname(_os.path.abspath(__file__))\n"
               "_sys.path.insert(0, _os.path.dirname(_ENG))\n"
               "_sys.path.insert(0, _ENG)\n\n")
        # 用带 os/sys 的标准写法（文件本身都 import 了 os,sys？unity_extract ✓ rpg ✓ srpg ✓）
        ins = BOOT_NEW + "\n"
        assert m, p
        s = s[:m.start()] + "import os, sys\n" + ins + s[m.start():]
    open(p, "w", encoding="utf-8", newline="\n").write(s)
    print(p, "✓")
