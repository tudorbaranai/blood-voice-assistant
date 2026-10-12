# 02 · The brain: Ollama

## Goal
A local AI model that understands what you say and answers in a sentence or
two, fast enough for a conversation (about 1–3 s).

## Why Ollama
- Free, runs offline, and uses an NVIDIA graphics card automatically.
- Home Assistant has an official **Ollama** integration (chapter 04).
- Words: **Ollama** is the *program* that runs models. **Llama**, **Qwen**,
  … are *model families*. We run **Qwen 3** models in Ollama.

## Steps

### 1. Install
[ollama.com/download](https://ollama.com/download) → Windows → run `OllamaSetup.exe`.
It starts automatically with Windows (a llama icon in the tray) and updates itself.

> Running plain `ollama` with no model installed shows a menu of "launch"
> options for coding tools. You don't need any of them, and you don't need an account.

### 2. Squeeze more into the graphics memory
A 4 GB card is tight. These two settings shrink the model's working memory
with no noticeable quality loss. Run in PowerShell, once:
```powershell
setx OLLAMA_FLASH_ATTENTION 1
setx OLLAMA_KV_CACHE_TYPE q8_0
setx OLLAMA_CONTEXT_LENGTH 4096
```
Then restart Ollama: tray `^` → right-click the llama → **Quit Ollama**, start it
again from the Start menu, and open a **new** terminal.

### 3. Try models
```powershell
ollama run qwen3:4b-instruct --verbose     # our choice
ollama run qwen3:1.7b --verbose            # fastest, but weaker
ollama ps                                   # shows how much runs on the GPU
```
Ask it something, read the timings that `--verbose` prints, and type `/bye` to exit.

## Check it worked
`ollama ps` while a model is loaded:
```
NAME                 SIZE      PROCESSOR          CONTEXT
qwen3:4b-instruct    3.3 GB    27%/73% CPU/GPU    4096
```
**100% GPU is ideal.** A CPU/GPU split still works, just slower. A short answer
should take about 1–3 s.

## Which model? What we measured (GTX 1650 Ti 4 GB, 8 GB RAM)

| Model | Speed | Quality | Verdict |
|---|---|---|---|
| `qwen3:1.7b` | ~0.3–1 s, 100% GPU | invents facts (made up a scientist that doesn't exist), weak at dates | too unreliable |
| **`qwen3:4b-instruct`** | **~1–3 s**, ~27/73 CPU/GPU | honest, good with the calendar trick (chapter 04) | ✅ **chosen** |
| `qwen3:4b` (= the *thinking* edition) | 13 s for two sentences | thinks out loud first, ignores `/set nothink` | too slow |
| `qwen3:4b-thinking` | 11–235 s | the smartest (~7/10 on our trick questions) | far too slow for voice |

We compared them with our own bench: [`tests/compare-brains.ps1`](../../tests/compare-brains.ps1)
asks every model the same tricky questions ([`tests/questions-limits.txt`](../../tests/questions-limits.txt))
with the same instructions and writes a side-by-side table to `tests/results/`.
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests\compare-brains.ps1
```
Re-run it whenever a new small model comes out.

## What went wrong for us
| Problem | Cause | Fix |
|---|---|---|
| `qwen3:4b` kept "thinking" (long `<think>` text) even with `/set nothink`, 13 s per answer | the plain `qwen3:4b` tag is the **thinking** edition | use the tag **`qwen3:4b-instruct`** |
| The 4B model only partly fit on the 4 GB card (33% CPU / 67% GPU) | model + working memory > what Ollama will allocate | the `setx` settings above (→ 27/73). Good enough at ~1–3 s |
| The 1.7B model confidently made up facts | small models guess when unsure | moved to 4B, and the prompt (chapter 04) tells it to say "I'm not sure" |
| Home Assistant ran the model with context **8192**, overriding our 4096 → more spilled to the CPU | Home Assistant's agent has its own context setting | set **Context window size = 4096** in the Home Assistant agent (chapter 04) |
