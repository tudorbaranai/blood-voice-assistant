# 10 · The screen

> The design is the **Eclipse** (below), and it is wired into the voice program:
> it comes up on "Hey Blood", follows the conversation, and the God Hand grips
> the sun when a light really goes off. The wiring is at the end of the chapter.

## Goal
A full-screen window on the laptop showing **what you said** (so you can check
Blood heard you right), **Blood's answer**, and an animation that moves with
the voice, so you can see it's **listening**, **thinking** or **speaking**.

## What's decided
- **It comes up on "Hey Blood"**, full screen, and ~10 s after Blood finishes
  it plays its closing and turns **black**. The window stays open (I switch
  away with Alt+Tab), so the next "Hey Blood" brings it back without waiting
  for it to load. The laptop stays usable for everything else.
- **A local web page** that the voice program feeds live (state, your words,
  the answer, the voice level, a light that switched), shown in an Edge window
  in **kiosk mode**: full screen, no title bar, no buttons. Animations are easy
  in a web page, and if the window crashes the voice keeps working. The same
  page could later run on a spare tablet.
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

## The design I chose: the Eclipse

After the five sci-fi candidates I went another way: manga. Four animated
designs were drawn in plain canvas (a river, an ensō, an eclipse, the Brand),
and the **Eclipse** won: a black sun over a crimson valley, the sky a slow
whirlpool, the corona leaning in while you talk and flaring while Blood talks.
When Blood switches a light off, a colossal hand rises out of the ground and
grips the sun; while it holds, the sky fills with screaming souls.

The final page is one offline file:
[`docs/design/manga-v3/blood-manga-v3.html`](../design/manga-v3/blood-manga-v3.html).
Open it in a browser, press **3** for the Eclipse, **←/→** to step through the
pretend conversation (the hand plays about 6.4 s in), **🎤 Use my mic** to make
it react to you. Add `?at=7.5` to the address for a frozen still of any moment.
[`storyboard-eclipse.png`](../design/manga-v3/storyboard-eclipse.png) shows the
whole conversation in sixteen frames.

It leans on Berserk's imagery (the Eclipse, the God Hand); that is why it lives
under `docs/design/` as fan art and not in `blood/`.

## How the God Hand was made (Blender, driven by Claude)

The first hands were drawn with canvas shapes and never stopped looking like
boxes and tubes. A real hand needed a real 3D model, so the hand is
**pre-rendered in Blender** and the page only plays the frames. Here is the
chain, in the order it was built; everything in it is free.

**1. Claude inside Blender.** Blender 5.2 ran on the laptop with the
*MCP for Blender* add-on, which lets Claude Code run Python inside the live
Blender, look through its camera, and try again. Every step below was done
that way, with me approving the stills between rounds. The scripts it wrote
are in [`docs/design/manga-v3/blender/`](../design/manga-v3/blender/).

**2. A hand with real anatomy.** The mesh comes from **MakeHuman**, through its
Blender add-on MPFB (installed from Blender's own extensions site; the human it
makes is CC0). It builds a whole rigged person; a mask by bone weights keeps
only the right forearm and hand. MakeHuman's shape targets made the fingers
thicker, the forearm shorter and more muscular, the wrist narrower; a small
shape key swells the mounds of the palm. The skin is near-black with a crimson
subsurface glow, plus aged-skin wrinkles and pores as a bump.

**3. Where the sun is.** One Blender unit is the sun's radius. The camera is
solved so the sun lands on a known pixel, and the hand is placed by its knuckle
line and scaled by its knuckle span. The page then draws the frames with the
same rule: scale = the sun's radius on screen divided by the sun's radius in
the render. That is why the hand sits on the sun at any window size.

**4. A grab, not a fist.** Each finger is posed by geometry: it runs straight
from its knuckle to the ball, then curls along a circle around it, each finger
in its own plane so they stay apart; the pinky and the thumb hook the sides,
the three middle fingers come over the top. The thumb presses in where its
wrap is capped. The order the fingers close in is the page's own choreography
(ring first, index last, thumb from a quarter of the way), so one number, how
closed the grip is, selects a frame.

**5. Two layers.** The palm hangs behind the sun; the fingers come in front
of it. The hand is rendered twice: the whole hand, drawn under the black disc,
and only what lies nearer than the sun's plane (a camera-only holdout plane
cuts everything behind it), drawn over the disc and the corona. That is how the
fingers close over the light.

**6. Light.** A ring of fire where the sun is (invisible to the camera), two
rim lights behind, a broad dim sky glow, a warm touch from below, and one faint
crimson light from the viewer's side so the forms read. Nothing frontal and
bright: the hand stays a silhouette with burning edges.

**7. Frames into the page.** Twenty-four poses from open to gripped, two layers
each, rendered with Cycles on the GTX 1650 Ti (about sixteen minutes), packed
to WebP by Blender's own Python (no extra tools), and embedded in the page as
data URLs, about 1 MB in total. Stills work because the page waits for the
frames before it draws.

**8. The souls.** Page-side canvas: twelve screaming skulls drawn once in ink
onto a sprite sheet, and 170 souls whose places are a pure function of the
moment's age, born behind the hand and flying up and outward. With everything
on screen a frame costs about 1.7 ms.

**9. Taken out.** The lava road on the valley floor and the thread of blood
from the sun to the ground. Both still exist behind a switch at the top of the
design file.

To re-render the hand after changing a number in `hand_config.json`:
`blender\make_hand.ps1` (renders, packs, rebuilds the page, re-shoots the
stills). It needs Blender at `D:\Blender` and the saved scene
`assets/hand/hand.blend`, which stays on the laptop.

## Wiring it in

### How it fits together
```
blood.py ──(moments)──▶ screen.py ──websocket──▶ the Eclipse page in Edge (kiosk)
   ▲                        │
   └── ha.py DeviceWatch ◀── Home Assistant: "a light switched"
```
- [`blood/screen.py`](../../blood/screen.py) is a tiny local web server on
  `127.0.0.1:47202` (nothing outside the laptop can reach it). It serves the
  page set in `settings.toml` and pushes every moment to it.
- The design page plays a pretend conversation on its own. Before serving it,
  `screen.py` adds [`blood/screen_live.js`](../../blood/screen_live.js) to its
  end: that stops the demo, hides the design page's buttons, switches off its
  keys, and feeds it the real moments through the `update()` hook the design
  engine already had for this.
- **The God Hand needs to know a light really went off**, not just that Blood
  said so. `DeviceWatch` in [`blood/ha.py`](../../blood/ha.py) keeps one
  websocket open to Home Assistant and listens for lights and plugs switching
  on or off, but only while Blood is handling a request. Switching from the
  phone app at other times doesn't move the screen. The hand rises only for
  **off**.

### The moments the page gets
| Moment | When | What the Eclipse does |
|---|---|---|
| `wake` | "Hey Blood" | a flash, the sun ignites, "Yes, Tudor?" |
| `listening` | you talk | the corona leans in with your voice |
| `thinking` | your words are sent | the sky spins faster, your words appear |
| `speaking` | Blood answers | the corona flares with its voice, the answer appears |
| event `device` | a light switched **off** | the hand rises and grips the sun, the souls fly |
| event `nohear` / `error` | nothing understood / Home Assistant unreachable | the sun flickers / a full eclipse |
| `idle` → `done` → `sleep` | ~10 s after the answer | the closing (the sun sinks), then black |

A follow-up question (chapter 09) moves the last exchange up into the history,
like a chat.

### Settings (`[screen]` in `settings.toml`)
| Setting | What it does |
|---|---|
| `enabled` | the screen on or off |
| `page`, `design` | which page and design; `page = ""` is the plain red orb (`blood/screen.html`) |
| `kiosk` | `true`: Edge kiosk mode, really full screen. `false`: a normal app window |
| `stay_open` | `true`: after a conversation the window stays, black. `false`: it hides |
| `hide_after` | seconds after the answer before the closing starts |
| `hotkey` | brings the screen up or puts it away from anywhere (default **Ctrl+Alt+B**) |

In the screen, **Esc** or **F9** puts it away: black and minimized, still in
Alt+Tab. **Alt+F4** closes it for real; the next "Hey Blood" opens a new one.
A global F9 was not an option: it would take F9 away from every other program.

### Try the look without talking
```powershell
.venv\Scripts\python.exe blood\screen.py
```
then open `http://127.0.0.1:47203` in a browser. It plays two exchanges in a
loop on its own port, so the real Blood can keep running.

### Check it worked
- Say "Hey Blood, turn off the main light": the screen comes up full screen,
  the hand grips the sun, and the screen turns black ~12 s later.
- `logs\blood.log` gets a line `Screen page error: ...` if the page itself
  breaks. No such lines means the page is fine.

### What went wrong for me
| Problem | Cause | Fix |
|---|---|---|
| Nothing changed after editing the code | Blood was still running the version it started with | restart it (`tools\blood-restart.cmd`) after every change |
| The window wasn't full screen | an Edge **app window** remembers its last size (a normal window with a title bar) and ignores "start full screen"; I had also minimized it, and "show" doesn't un-minimize | **kiosk mode**, and "restore" instead of "show" for a minimized window |
| In kiosk mode the window wasn't found | its title is "Blood - [InPrivate] - Microsoft Edge", not "Blood" | find it by the Edge process Blood started |
| Kiosk is 1 pixel shorter than the screen | Edge's own kiosk layout | the "press F11 if it's not full screen" check is off in kiosk mode, or it would undo kiosk |
| The page crashed in a hidden browser tab | a hidden window reports a size of 0 × 0, so the sun's radius was 0, and 0 ÷ 0 broke a gradient before the animation started | the engine uses the screen's size until the window has its own |
| The drawn hand instead of the Blender one | the hand frames failed to decode while the page was hidden | try again every few seconds instead of falling back for good |
| A 2–3 s wait before the screen appeared | the window was hidden between requests and had to come back | keep it open and black (`stay_open`), so it only has to come to the front |
