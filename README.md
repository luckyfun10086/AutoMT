# AutoMT — MTool JSON Auto-Translator

**English** | [简体中文](README.zh-CN.md)

Auto-translates MTool-exported `ManualTransFile.json` files (a `{"source": "translation"}`
map where untranslated entries have empty values). Uses a free public translation endpoint
by default — **no API key, no quota, no content filtering**. Alternatively, plug in your
own translation API via the GUI (credentials stored in a local `.env`, never committed).

Validated on a 70,000+ string game text corpus.

## Download

Grab `AutoMT.exe` from the [**Releases**](https://github.com/luckyfun10086/AutoMT/releases)
page — a standalone Windows binary, no Python required. Everything (`.env`, `names.txt`,
`mt_work/`) is created next to the exe.

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

## Custom Translation API

Fill in the **Translation API** panel in the GUI:

- **URL**: use the `{sl}` (source lang), `{tl}` (target lang) and `{q}` (URL-encoded text)
  placeholders, e.g. `https://api.example.com/translate?source={sl}&target={tl}&text={q}`
- **Key / header**: sent as `Authorization: Bearer <key>` by default; name another header
  (e.g. `X-Api-Key`) to send the raw value
- **Save to .env** persists the setup; leave the default URL to use the free built-in
  endpoint (no key, batched 8 strings/request). Custom endpoints are requested one-by-one.
- Response formats auto-detected: Google `/t` list, DeepL-style
  `{"translations":[{"text":..}]}`, MyMemory `{"translatedText":..}`, plain text

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
- `names.example.txt` — names.txt template
- `_test_custom.py` / `_test_autonames.py` — self-tests (mock API, 4-language detection)

## License

MIT
