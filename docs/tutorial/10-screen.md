# 10 · The screen 🟡 designing

> This chapter is in progress: the design is being chosen. It will be rewritten
> with the real steps once it's built.

## Goal
A full-screen window on the laptop showing **what you said** (so you can check
Blood heard you right), **Blood's answer**, and an animation that moves with
the voice, so you can see it's **listening**, **thinking** or **speaking**.

## What's decided
- **It pops up on "Hey Blood"**, full screen, and hides itself ~10 s after
  Blood finishes, giving the focus back to whatever you were doing. The laptop
  stays usable for everything else.
- **A local web page** that the voice program feeds live (state, your words,
  the answer, the voice level), shown in a borderless Edge window with its own
  private profile. Animations are easy in a web page, and if the window crashes
  the voice keeps working. The same page could later run on a spare tablet.
- **Screen wake:** on the wake word, the program wakes the display (a one-pixel
  mouse nudge, there and back) and asks Windows to keep it on while Blood talks.
- Names are shown with their normal spelling, even though the voice uses a
  sound spelling.

## Choosing the design
[`blood/screen_designs.html`](../../blood/screen_designs.html) shows five
candidates, each playing a pretend conversation. Open it in a browser, press
**F11**, switch with keys **1–5**, and press **🎤 Use my mic** to make it react
to your own voice:

| # | Name | Inspired by | Your words and the answer |
|---|---|---|---|
| 1 | Blood Moon | ChatGPT's voice mode: a liquid orb that wobbles with the voice | chat bubbles under the orb |
| 2 | Crimson Glow | Gemini Live: a glow rising from the bottom edge | big live captions |
| 3 | Arc Reactor | Iron Man's Jarvis: spinning rings, a voice equalizer | a terminal-style log |
| 4 | Particle Sphere | sci-fi: a 3D ball of 700 points | film-style subtitles |
| 5 | Liquid Glass | modern phone apps: lava-lamp colours | a frosted-glass chat window |

The plumbing ([`blood/screen.py`](../../blood/screen.py)) exists but is
switched off (`[screen] enabled = false` in `settings.toml`) until the chosen
design is built: in my first test the window didn't come to the front yet.
