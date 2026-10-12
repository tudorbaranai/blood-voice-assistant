# 10 · The screen ⬜ planned

> This chapter is a plan. It will be rewritten with the real steps once it's built.

## Goal
A full-screen window on the laptop showing **what you said**, **Blood's answer**,
and an animation for **listening / thinking / speaking**. The screen wakes up
on "Hey Blood".

## Plan
- Part of the voice program from chapter 09: either a simple Python window, or a
  local web page in a borderless browser window.
- States: **idle** (dark or a clock) → **listening** (pulsing circle) →
  **thinking** (spinner) → **speaking** (a wave synced to the voice) → back to
  idle after about 10 s.
- **Screen wake:** on the wake word, the program tells Windows there's "user
  activity", which switches the display on. Afterwards Windows turns it off
  again as usual.
- Names are shown with their normal spelling, even though the voice uses a
  phonetic one.
