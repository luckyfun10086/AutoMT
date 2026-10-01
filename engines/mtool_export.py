# -*- coding: utf-8 -*-
"""
MTool 兼容导出
==============
把 OmniTrans 的译文 json 转成 MTool 的 ManualTransFile.json（运行时挂载用）。

格式本就同构（{"原文": "译文"}），差异在"键形态"：MTool 运行时拦截的文本
与静态提取的块存在形态差（选项逐项 vs 合并块、行首控制码、\.\, 停顿码等）。
本工具在原键之外追加变体键（多出的键 MTool 查不到也无害，不会覆盖原键）：

  ① 行拆分   ：多行键按行拆成单键（覆盖 MTool 逐项拦截的选项/短行）
  ② 行首剥离 ：剥掉行首 RPG 控制码（\C[2] 等）
  ③ 全码剥离 ：去掉全文控制码与停顿码（\c[n] \v[n] \. \, \! 等）

用法：
    python mtool_export.py <译文json> [--dir <游戏目录>] [-o <输出路径>]
不传 -o 时：--dir 给了 → <游戏目录>\\ManualTransFile.json；否则输出在输入旁。
"""
import os, sys, io, json, re, argparse

_ENG = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_ENG))    # 项目根：mt_config 等
sys.path.insert(0, _ENG)                     # 引擎同目录：krkr_xp3 等
import mt_config

# RPG 系控制码：\C[n] \c[27] \V[1] \N[4] \I[9] \fs[20] \fb[..] 等 + 停顿/速度码
CODE = r"\\[A-Za-z]{1,3}(?:\[[^\]\n]*\])?|\\[.,!^${}|]"
CODE_RE = re.compile(CODE)
LEAD_RE = re.compile(rf"^(?:{CODE})+")       # 锚定行首（按行切分后逐行处理）
NL = "\n"


def strip_lead(s):
    """剥掉行首（含换行后每行行首）的控制码"""
    return NL.join(LEAD_RE.sub("", ln) for ln in s.split(NL))


def strip_all(s):
    """去掉全文控制码"""
    return CODE_RE.sub("", s)


def build(tr):
    """{原文:译文} → MTool 兼容字典（原键优先，变体不覆盖）"""
    out = {}
    for orig, zh in tr.items():
        if not isinstance(orig, str) or not isinstance(zh, str) or not zh.strip():
            continue
        if orig not in out:
            out[orig] = zh
        # ① 行拆分（行数对齐时逐行配对；不齐时整译放首行）
        po, pv = orig.split(NL), zh.split(NL)
        if len(po) > 1:
            if len(po) == len(pv):
                pairs = zip(po, pv)
            else:
                pairs = [(po[0], zh)] + [(ln, "") for ln in po[1:]]
            for kl, vl in pairs:
                kl = kl.strip("\r")
                if kl.strip() and kl not in out and vl.strip():
                    out[kl] = vl
        # ② 行首码剥离
        k2, v2 = strip_lead(orig), strip_lead(zh)
        if k2.strip() and k2 != orig and k2 not in out and v2.strip():
            out[k2] = v2
        # ③ 全码剥离
        k3, v3 = strip_all(orig), strip_all(zh)
        if k3.strip() and k3 != orig and k3 != k2 and k3 not in out and v3.strip():
            out[k3] = v3
    return out


def main(argv=None):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("translated", help="OmniTrans 译文 json（*_translated.json）")
    ap.add_argument("--dir", dest="game_dir", default=None,
                    help="游戏目录（默认输出其下的 ManualTransFile.json）")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args(argv)
    tr = mt_config.load_loose_json(a.translated)
    out = build(tr)
    dst = a.out or (os.path.join(a.game_dir, "ManualTransFile.json")
                    if a.game_dir else
                    os.path.join(os.path.dirname(os.path.abspath(a.translated)),
                                 "ManualTransFile.json"))
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    n_orig = sum(1 for k in out if k in tr)
    print(f"导出 {len(out)} 键（原键 {n_orig} + 变体 {len(out)-n_orig}）→ {dst}")
    print("MTool 用法：确保该文件在游戏目录且名为 ManualTransFile.json，用「与工具一同启动.bat」启动即可")


if __name__ == "__main__":
    main()
