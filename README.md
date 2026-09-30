# AutoMT — MTool JSON Auto-Translator

**English** | [简体中文](README.zh-CN.md)

Auto-translates MTool-exported `ManualTransFile.json` files (a `{"source": "translation"}`
map where untranslated entries have empty values). Uses a free public translation endpoint
by default — **no API key, no quota, no content filtering**. Alternatively, plug in your
own translation API via the GUI (credentials stored in a local `.env`, never committed).
Don't use MTool? See [Standalone RPG Maker extraction](#standalone-rpg-maker-extraction-no-mtool-needed) below.

> [MTool](https://mtool.app/) — the excellent game translation & modification tool this
> project was built for (closed-source, official site: mtool.app).

Validated on a 70,000+ string game text corpus.

## Download

Grab `AutoMT.exe` from the [**Releases**](https://github.com/luckyfun10086/AutoMT/releases)
page — a standalone Windows binary, no Python required. Everything (`.env`, `names.txt`,
`mt_work/`) is created next to the exe.

> **Quality & fair use**: the built-in free endpoint delivers basic machine-translation
> quality — fine for understanding a game, not for polished prose. For better results,
> configure a DeepL/LLM endpoint in the API panel below. The free endpoint is unofficial
> and may change or rate-limit at any time; if it ever does, the tool keeps working with
> any custom endpoint. Translate only content you have the right to use.

## GUI (recommended)

1. Pick **source → target language** at the top (English → Simplified Chinese by default)
2. **Drag & drop** your MTool-exported JSON into the window (or click to browse)
3. Click **Start** — live progress bar: ① Clean & mask → ② Translate (speed + ETA) →
   ③ Validate & apply
4. A dialog shows the output path when done; one click opens the folder

Any string that fails validation is automatically retranslated in segment-wise fallback
mode (tokens can never be lost). Cancel anytime — progress is resumable.

> Drag & drop inside the packaged exe works out of the box. Running from source needs
> `pip install tkinterdnd2` (falls back to a file picker without it).
>
> Rebuild the exe: `pip install pyinstaller && python -m PyInstaller --onefile --windowed --name AutoMT --collect-all tkinterdnd2 mt_gui.py`

Output: `yourfile_translated.json` next to the input — keys are exact original strings,
so MTool picks them up directly.

## Privacy & Security Design

- **Zero secrets in code**: no API keys, no personal paths anywhere in the repository
- **Personal config isolated**: endpoint URL / API key / header live in `.env`
  (excluded by `.gitignore`)
- **Local data isolated**: `mt_work/` workdirs, `names.txt`, `ManualTransFile*.json`
  game texts are all gitignored — your game content and terminology never leave the machine
- Before publishing your fork: `git status` should never list `.env`, `mt_work/`, or any json

## Translation APIs (two kinds)

Pick an **API type** in the GUI panel, fill in the fields, **Save to .env**.

### Type 1 — MT (traditional machine translation, `MT · GET`)

GET-template endpoints using `{sl}` / `{tl}` / `{q}` placeholders:

```
https://api.example.com/translate?source={sl}&target={tl}&text={q}
```

Supported / tested:

| Service | How |
|---------|-----|
| **Built-in free endpoint** (Google) | leave the default URL — no key, batched 8 strings/request, basic quality |
| **LibreTranslate** (self-host / public) | `https://libretranslate.com/translate?q={q}&source={sl}&target={tl}` + API key header `X-api-key` |
| **MyMemory** | `https://api.mymemory.translated.net/get?q={q}&langpair={sl}|{tl}` |
| **DeepLX** (self-hosted DeepL proxy) | `http://localhost:1188/translate?text={q}&source_lang={sl}&target_lang={tl}` |
| Any other GET API | craft the URL with the three placeholders; response auto-detected (Google list / `translations[]` / `translatedText` / plain text) |

### Type 2 — AI translation (`AI · OpenAI`)

OpenAI-compatible **chat/completions** endpoints (POST + JSON). Fill the full URL, your
API key and a model name — quality is dramatically better than MT, at API cost:

| Service | URL | Model example |
|---------|-----|---------------|
| **DeepSeek** | `https://api.deepseek.com/chat/completions` | `deepseek-chat` |
| **OpenAI** | `https://api.openai.com/v1/chat/completions` | `gpt-4o-mini` |
| **Kimi (Moonshot)** | `https://api.moonshot.cn/v1/chat/completions` | `moonshot-v1-8k` |
| **智谱 GLM** | `https://open.bigmodel.cn/api/paas/v4/chat/completions` | `glm-4-flash` |
| **OpenRouter** (Claude/Gemini/…) | `https://openrouter.ai/api/v1/chat/completions` | `anthropic/claude-3.5-haiku` |
| **Gemini** (OpenAI-compat) | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` | `gemini-2.0-flash` |
| **Ollama** (local, no key) | `http://localhost:11434/v1/chat/completions` | `qwen2.5:7b` |

**Error prompts & sensitive-word fallback**: connection problems are classified into
three kinds with clear bilingual messages — *fatal* (401 wrong key / 402 insufficient
balance / 404 bad model: stops immediately with a dialog, no wasted retries), *skip*
(content blocked by the provider's safety policy), and *retry* (429 rate-limit / network
hiccups: automatic backoff). Blocked strings are automatically **retried via the built-in
free MT endpoint** (which has no content filter) — lower quality than AI but far better
than leaving English; the run summary reports how many were salvaged. Disable with
`MT_FALLBACK=0`.

Equivalent `.env` keys are documented in [`.env.example`](.env.example).

## Proper-Noun Handling

### names.txt (optional, always takes priority)

One entry per line, two forms:

```
Alice=爱丽丝       masked, then restored as the Chinese translation (recommended)
Wonderland=仙境
Bob               masked, kept as-is
```

Masked terms are never machine-translated — **MT can never turn "Alice" into something
random** — and the `=` form guarantees a uniform translated name throughout.

### Automatic detection (zero-config, per-language, toggleable)

Without a names.txt, AutoMT detects proper nouns per source language and keeps them
consistent across the whole file:

| Source language | Method | Notes |
|-----------------|--------|-------|
| Latin-script (en, …) | Capitalization statistics + built-in common-word list | Names are almost always capitalized and never lowercase; common words appear both ways and are filtered, incl. habitually-capitalized words like *thanks/doctor* |
| **Japanese** | Repeated katakana runs | JRPG character names are almost always katakana (アリス、リチャード) — a hard signal; ships with a game-term stoplist (ダメージ/スキル etc.) |
| Russian & inflected | Capitalized-prefix clustering | Case variants (Алиса/Алису/Алисе) cluster into one name |
| Chinese / Korean | Skipped | No case/kana signal — the log suggests using names.txt |

Detected words and their counts are listed in the log for full transparency.
**Don't want this?** Uncheck "Auto-detect names" in the GUI (persisted via Save to .env),
or use `--no-auto-names` / `MT_AUTO_NAMES=0`. Names are then machine-translated like any
other text (more natural renderings, consistency not guaranteed). Manual names.txt entries
work in every mode.

## Standalone RPG Maker Extraction (no MTool needed)

**Supported engines:**

| Engine | Data location | Status |
|--------|---------------|--------|
| RPG Maker **MZ** | `data/` | ✅ fully supported |
| RPG Maker **MV** | `www/data/` (or `data/` in some distributions) | ✅ fully supported |
| **SRPG Studio** | `data.dts` (with `runtime.rts`/`environment.evs`) | ✅ fully supported — bridges [SRPG-ToolBox](https://github.com/Sinflower/SRPG-ToolBox) (MIT), auto-downloaded on first run |
| RPG Maker VX Ace / VX / XP | `.rvdata2` binary files | ❌ not supported (binary Marshal format) |
| Wolf RPG Editor | `.wolf` archives | ❌ not supported |

MV/MZ store all game text as plain JSON (`Map*.json`, `CommonEvents.json`,
`Troops.json`, …) — AutoMT reads and patches them directly, no third-party tool
required. For VX Ace and older engines, use MTool instead.

```
python rpg_extract.py <game-folder>     # → game.extracted.json
python mt_clean.py game.extracted.json  # ① mask
python mt_translate.py                  # ② translate (resumable)
python mt_apply.py game.extracted.json  # ③ restore → game.extracted_translated.json
python rpg_apply.py <game-folder> game.extracted_translated.json   # write back
```

What gets extracted: dialogue (code 401, consecutive lines merged into one block for
better quality), scrolling text (405), choices (102), actor name/nickname changes
(320/324), map display names — from `Map*.json`, `CommonEvents.json`, `Troops.json`.

Safety: `rpg_apply.py` backs up originals to `data_backup/` first, only replaces
exact-match blocks, and skips any block whose translated line count doesn't match —
the game can never be corrupted by a bad translation.

### SRPG Studio games

```
python srpg_extract.py <game-folder>   # auto: download tool → unpack → patch → collect
python mt_clean.py <game>_extracted.json
python mt_translate.py                 # MT or AI (set MT_API_TYPE=openai + model in .env)
python mt_apply.py <game>_extracted.json
python srpg_apply.py <game-folder> <game>_extracted_translated.json
```

Safety: original `data.dts` is backed up to `.automt.bak`; messages are re-chunked on
original line boundaries (mismatched line counts are skipped, original kept); if
`localization.dat` (official localization) is present it is disabled automatically —
it would otherwise override custom translations. Battle-tested on a 943 MB game
(6,985 strings extracted → 26 marker translations applied → repacked → re-parsed
to confirm).

## CLI (equivalent to the GUI)

```
python mt_clean.py [file]     ① clean & mask: codes/newlines/names → 〔Thash〕 tokens
python mt_translate.py        ② translate: batched endpoint requests (resumable)
python mt_apply.py [file]     ③ restore: unmask → validate → clean → write output
```

`mt_translate.py --seg` retranslates stubborn strings segment-wise (tokens can never be
lost). Defaults to `ManualTransFile.json` in the current directory.

## Key Mechanisms (battle-tested)

| Mechanism | Why |
|-----------|-----|
| Content-hash tokens 〔Txxxxxxxx〕 | Re-runs and incremental exports never invalidate prior work |
| Skip already-translated entries | Every stage is resumable |
| 8 strings/request + throttle + backoff | 47k strings in 2.5h without bans |
| `--seg` segment-wise mode | MT occasionally drops tokens; splitting on tokens makes that impossible |
| Count-based token validation | Catches lost/duplicated tokens even when the same token appears twice |
| Bracket-variant tolerance | MT normalizes 〔〕 to 【】（）[], adds spaces, fullwidth chars — all normalized back |
| Cleanup uses `[ \t]` only | `\s` eats real newlines (1,258 entries lost to this in testing) |
| Invalid-escape sanitization | MT injects `\ ` `\~` etc.; stripped against the engine-valid set |
| Failed entries stay empty | MTool falls back to the original text — never breaks the game |

## Typical Workflow

```
1. MTool → export ManualTransFile.json → copy into this folder
2. (optional) put the game's names/places into names.txt
3. python mt_clean.py
4. python mt_translate.py          # interrupt anytime, rerun to resume
5. python mt_apply.py
6. If "token lost" entries are reported:
   python mt_translate.py --seg    # retries only the stubborn ones
   python mt_apply.py
7. Import ManualTransFile_translated.json back into MTool
```

## Files

- `mt_gui.py` — GUI (also the PyInstaller entry point)
- `mt_clean.py` / `mt_translate.py` / `mt_apply.py` — the three CLI stages
- `mt_config.py` — config layer (.env I/O, URL building, response parsing, name detection)
- `rpg_extract.py` / `rpg_apply.py` — standalone RPG Maker MV/MZ extraction & write-back
- `names.example.txt` — names.txt template
- `_test_custom.py` / `_test_autonames.py` / `_test_rpg.py` — self-tests (mock API,
  4-language detection, extract/apply round-trip)

## License

MIT
