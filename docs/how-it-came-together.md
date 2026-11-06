# How Blood came together

The timeline and the lessons that didn't fit in the README. The prompt lessons
are still in the [README](../README.md#the-system-prompt-the-part-that-mattered-most).

## Other things I learned

- **Anything that changes goes at the end of the prompt.** Ollama reuses the
  start of a prompt between questions, up to the first character that differs.
  With the clock (to the minute) at the top, the whole prompt was re-read on
  every question: 4–7 s per answer. Moving it to the bottom fixed it.
  ([chapter 04](tutorial/04-connect-brain-and-prompt.md))
- **...and then the clock had to go completely.** The conversation comes *after*
  the prompt, so once the voice program kept a long conversation, every new
  minute made the brain re-read all of it: 12–18 s per answer. Now there's no
  clock (Home Assistant answers the time itself), and a fresh conversation
  starts after 2 minutes of silence.
- **Check how a training tool cuts your clips.** openWakeWord treats the *end*
  of each clip as the wake word. My recordings had 1.4 s of silence after the
  phrase, so the model learned the silence, and got worse. Also: keep some
  recordings out of training, and test on those.
  ([chapter 09](tutorial/09-wake-word-and-voice-program.md))
- **Home Assistant quietly overrides the context size.** It asks Ollama for
  8192 tokens, which pushed 36% of the model onto the slow CPU. Setting 4096
  brought that to 27%, and forcing every layer onto the 4 GB GPU took the
  average answer from 3.4 s to 1.4 s with the same prompt.
- **Small and fast isn't enough.** `qwen3:1.7b` answered in under a second but
  happily described the made-up toaster scientist. The "thinking" models were
  smarter but took 11–235 s. `llama3.2:3b` just wasn't my style.
  `qwen3:4b-instruct` was the middle: not brilliant, honest, under 2 s.
  ([chapter 02](tutorial/02-brain-ollama.md))
- **Tuning the mic beat switching engines.** Mic volume to 100 and the Realtek
  "effects" off took word errors on five test sentences from 14% to 3%, a bigger
  gain than any engine change. With the boost lowered to 0 dB, a short re-test
  got every word right.
  ([chapter 05](tutorial/05-ear-speech-to-text.md))

## Timeline

| When (2026) | What happened |
|---|---|
| 5 Oct | Tried local models on my everyday laptop. Qwen felt better than Llama. |
| 6–8 Oct | Set up the Asus to run 24/7 and installed Home Assistant OS in a VM on it. The first install hung at 5% for half an hour; switching the VM's network from bridged to NAT fixed it. |
| 9–12 Oct | Benchmarked models and moved from `qwen3:1.7b` to `qwen3:4b-instruct`. Chose the ear and the voice, tuned the mic. |
| 13 Oct | First light switched by Home Assistant. Surprise: the bulb I thought was a Philips Hue was a WiZ, so the Bluetooth setup I'd just done wasn't needed. |
| 24 Oct | Smart plug working locally (installed by hand, because the community store's GitHub login was broken). Built the bench with the lie detector, prompts v8 → v12, all layers on the GPU. |
| 2 Nov | "Hey Blood": trained my own wake word on Google Colab (after eight notebook fixes), recorded 200 clips of my voice, and found out the hard way how training cuts them. Wrote the voice program, took it from 12–18 s to ~2 s per answer, prompt v13, and set it to start by itself at login. |
| 3 Nov | Chose the screen design, the Eclipse, and had Claude render its God Hand in Blender. |
| 4 Nov | Wired the screen into the voice program (Edge kiosk, a hand that reacts to the real light), follow-up questions without "Hey Blood", and found the brain's memory limit the hard way. |
