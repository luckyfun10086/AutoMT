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
import os, re, sys, json, urllib.parse

DEFAULT_ENDPOINT = ("https://clients5.google.com/translate_a/t"
                    "?client=dict-chrome-ex&sl={sl}&tl={tl}&q={q}")

ENV_KEYS = ("MT_ENDPOINT", "MT_API_KEY", "MT_API_HEADER", "MT_SL", "MT_TL", "MT_AUTO_NAMES")

def base_dir():
    """exe 旁边（PyInstaller 打包后 __file__ 在临时目录，须用 exe 自身位置）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def env_path():
    return os.path.join(base_dir(), ".env")

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

# ---------- 自动人名识别（按语言分治） ----------
# en 等拉丁文字：人名几乎总是首字母大写、几乎从不小写；普通词大小写混现
#                + 内置高频词库兜底（滤掉 thanks/sorry/doctor 这类习惯大写词）
# ja：片假名串 ≥3 字且高频 —— 日式游戏人名几乎全是片假名（硬特征），附带游戏术语停用表
# ru 等变格语言：同一人名有多个词形（Алиса/Алисы/Алисе），按大写前缀聚类合并
# zh/ko：无大小写、无假名 —— 无法零依赖可靠识别，跳过并提示用 names.txt
# 任何语言：names.txt 人工词条永远优先（含 =译名）
_AUTO_STOP = set("""i ok oh ah ha eh um hey you she he it they we the and but or not is are
was were be been do does did don cant can will would just so if then well now here there this
that these those what when where who how why yes no chapter part day days night gold silver
thanks sorry please hello goodbye today tomorrow yesterday maybe actually of course
mr mrs ms dr let get got go going come came take took make made know think see saw look want
need say said tell told ask asked feel felt find found give gave tell told never always ever
still even much many more most less least own same other another such only just quite very""".split())

# 英语高频词（经典 GSL 高频段 + 常见实词），把"习惯性大写的普通词"彻底滤掉
_EN_COMMON = set("""the be to of and a in that have i it for not on with he as you do at this
but his by from they we say her she or an will my one all would there their what so up out if
about who get which go me when make can like time no just him know take people into year your
good some could them see other than then now look only come its over think also back after use
two how our work first well way even new want because any these give day most us man thing
woman life child world school state family student group country problem hand part place case
week company system program question work government number night point home water room mother
area money story fact month lot right study book eye job word business issue side kind head
house service friend father power hour game line end member law car city community name
president team minute idea kid body information back parent face others level office door
health person art war history party result change morning reason research girl guide moment
air teacher force education foot boy age policy process music market sense nation plan college
interest death experience effect use class control care field development role effort rate
heart drug show leader light voice wife whole police mind price report decision son view
relationship town road arm difference value building action model season society tax director
position player record paper space ground form event official matter center couple site
project activity star table need court oil situation cost industry figure street image
itself phone either data cover quite picture clear practice piece land recent describe
product doctor wall patient worker news test movie certain north love personal open
support""".split())

# 日语：常见游戏术语片假名（这些是普通词不是人名）
_JA_KATA_STOP = set("""アイテム ダメージ ゴールド レベル メニュー スキル モンスター ゲーム
パーティー キャラクター ゲージ メッセージ システム イベント ミッション クエスト
セーブ ロード ボス アイコン サウンド データ ファイル ストーリー チャプター
バトル フィールド マジック ポーション エリア マップ キャンプ タウン ショップ
ホテル ダンジョン クラス ジョブ アビリティ チェスト キー アイテムボックス
レシピ テクニック コマンド ヘルプ セット アップ スタート エンド オープン
クローズ クリック タッチ パスワード ユーザー バージョン アップデート
ニュース インフォメーション ライブラリー ミュージック ボイス ボリューム
コスト パワー スピード ディフェンス アタック ヒール リカバリー チャンス
ピンチ ストップ リセット キャンセル オプション セレクト コンティニュー
プロローグ エピローグ シナリオ トーク テキスト ログ ヘッダー フッター
ウィンドウ アイコン バー バッジ トークン チェック レポート カテゴリー
タイプ ランク スコア ボーナス ペナルティ アイアン シルバー ブロンズ
ダイヤ ルビー サファイア エメラルド クリスタル オーブ リング アミュレット""".split())

# 俄语：句首高频词（防聚类误报）
_RU_STOP = set("""что как это они весь который когда даже если уже только очень можно нужно
быть он она они мы вы не да нет ну вот там здесь тогда зачем почему кто что-то
спасибо пожалуйста извини извините здравствуйте пока хорошо плохо может надо
скажи скажите знаю думаю посмотри""".split())

_KATA_RE = re.compile(r"[ァ-ヺー]{3,}")

def detect_names(texts, lang="en", min_count=2, min_ratio=0.65):
    """按语言自动发现专有名词候选。返回 [(name, count), ...] 按频率降序。"""
    from collections import Counter
    lang = (lang or "en").split("-")[0].lower()

    if lang == "ja":
        cnt = Counter()
        for t in texts:
            for w in _KATA_RE.findall(t):
                if w not in _JA_KATA_STOP:
                    cnt[w] += 1
        return [(w, c) for w, c in cnt.most_common() if c >= min_count]

    if lang in ("ru", "bg", "uk"):
        clusters = Counter()
        formcnt = Counter()
        for t in texts:
            for w in re.findall(r"[А-ЯЁ][а-яё]{3,}", t):
                clusters[w[:4]] += 1
                formcnt[w] += 1
        out = []
        for k, c in clusters.most_common():
            if c >= max(min_count, 3) and k.lower() not in _RU_STOP:
                members = [w for w in formcnt if w[:4] == k]
                best = max(members, key=lambda f: formcnt[f])  # 取最常见词形（多为原形）
                out.append((best, c))
        return out

    if lang in ("zh", "ko"):
        return []  # 无大小写/假名特征，零依赖无法可靠识别

    # 拉丁文字（en 等）
    cap, low, allcap = Counter(), Counter(), Counter()
    for t in texts:
        for w in re.findall(r"[A-Za-z][A-Za-z']*", t):
            if len(w) < 2:
                continue
            if w.isupper():
                allcap[w] += 1
            elif w[0].isupper():
                cap[w] += 1
            else:
                low[w] += 1
    out = []
    for w, c in cap.most_common():
        lw = w.lower()
        total = c + low.get(lw, 0)
        if (c >= min_count and c / total >= min_ratio
                and lw not in _AUTO_STOP and lw not in _EN_COMMON):
            out.append((w, c))
    for w, c in allcap.most_common():
        if c >= min_count and w.lower() not in _AUTO_STOP:
            out.append((w, c))
    return out

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
