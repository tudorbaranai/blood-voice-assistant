"""Blood's screen: a full-screen window that pops up on "Hey Blood".

Two parts:
  - a tiny local web server: it serves the screen page and pushes live updates
    to it over a websocket (state, what you said, the answer, the voice level,
    a light that switched)
  - window control: an Edge window in "app mode" (no tabs, no address bar,
    its own private profile) that we show on the wake word and hide again
    afterwards, giving the focus back to whatever you were doing

The page is set in settings.toml ([screen] page). blood/screen.html is the plain
built-in one (a red orb). A design page (the Eclipse) is served with
screen_live.js added to its end, which plugs it into the live updates.

The moments the page gets, in order:
    sleep (hidden) -> wake ("Yes, Tudor?") -> listening -> thinking (heard) ->
    speaking (answer) -> idle -> done (the closing animation) -> sleep
    plus events: "device" (a light switched), "nohear", "error"

Try the look without talking, while the real Blood keeps running:
    .venv\\Scripts\\python.exe blood\\screen.py
    then open http://127.0.0.1:47203 in a browser (it plays two exchanges, in a loop)
"""
import asyncio
import ctypes
import ctypes.wintypes as wt
import json
import logging
import os
import pathlib
import re
import subprocess
import winreg

from websockets.asyncio.server import broadcast, serve
from websockets.datastructures import Headers
from websockets.http11 import Response

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
PORT = 47202
TITLE = "Blood"                                # the page's <title>; how we find the window
CLOSING = 2.6                                  # seconds the "done" animation takes before we hide
log = logging.getLogger("blood")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
SW_HIDE, SW_MINIMIZE, SW_SHOWMINNOACTIVE, SW_SHOW, SW_RESTORE = 0, 6, 7, 5, 9
ES_CONTINUOUS, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000002


def find_edge():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe") as key:
            return winreg.QueryValue(key, None)
    except OSError:
        return r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def find_window(pid=None):
    """Blood's Edge window: the one with the page's title, "Blood", or (in kiosk
    mode, whose title may differ) the main window of the Edge we started."""
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def check(hwnd, _):
        title = ctypes.create_unicode_buffer(64)
        cls = ctypes.create_unicode_buffer(64)
        user32.GetWindowTextW(hwnd, title, 64)
        user32.GetClassNameW(hwnd, cls, 64)
        if not cls.value.startswith("Chrome_WidgetWin"):
            return True
        if title.value == TITLE:
            found.insert(0, hwnd)
        elif pid and title.value and not user32.GetWindow(hwnd, 4):       # 4 = GW_OWNER: a main window
            owner = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid:
                found.append(hwnd)
        return True

    user32.EnumWindows(check, 0)
    return found[0] if found else None


def close_old_screens():
    """Close any Edge still running Blood's screen profile (from before a restart):
    a fresh one starts with the newest page and the right window mode. Only Edge
    with the BloodScreen profile is touched, never your own browser."""
    script = ("Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
              "? { $_.CommandLine -match 'BloodScreen' } | % { Stop-Process -Id $_.ProcessId -Force "
              "-ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", script], timeout=30,
                   creationflags=0x08000000)                            # no console window


def wake_display():
    """Switch the display on if it went to sleep: a tiny mouse nudge (1 pixel
    there and back) counts as "someone is here", and ask Windows to keep the
    display on while Blood is busy."""
    user32.mouse_event(0x0001, 1, 0, 0, 0)
    user32.mouse_event(0x0001, -1, 0, 0, 0)
    kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED)


def allow_display_sleep():
    kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def bring_to_front(hwnd):
    """Windows doesn't let background programs steal the focus. Pressing and
    releasing Alt (invisible) is the standard, harmless way to be allowed."""
    user32.ShowWindow(hwnd, SW_RESTORE if user32.IsIconic(hwnd) else SW_SHOW)   # minimized: un-minimize
    user32.keybd_event(0x12, 0, 0, 0)          # Alt down
    user32.keybd_event(0x12, 0, 2, 0)          # Alt up
    user32.SetForegroundWindow(hwnd)


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


def covers_screen(hwnd):
    """True when the window fills its whole monitor (taskbar included), like F11 does."""
    info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(info))
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    m = info.rcMonitor
    return (r.left, r.top, r.right, r.bottom) == (m.left, m.top, m.right, m.bottom)


async def fill_screen(hwnd):
    """Make the window full screen if it isn't (Edge forgets its start-up
    fullscreen sometimes): press F11 for it, the browser's own full-screen key."""
    await asyncio.sleep(0.3)                    # let it come to the front first
    if not covers_screen(hwnd) and user32.GetForegroundWindow() == hwnd:
        user32.keybd_event(0x7A, 0, 0, 0)       # F11 down
        user32.keybd_event(0x7A, 0, 2, 0)       # F11 up


KEYS = {"ctrl": 0x2, "control": 0x2, "alt": 0x1, "shift": 0x4, "win": 0x8}
NAMED = {f"f{i}": 0x6F + i for i in range(1, 13)} | {"space": 0x20, "esc": 0x1B}


def parse_hotkey(text):
    """ "ctrl+alt+b" -> (modifier flags, virtual key code)"""
    mods, vk = 0, None
    for part in text.lower().replace(" ", "").split("+"):
        if part in KEYS:
            mods |= KEYS[part]
        elif part in NAMED:
            vk = NAMED[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
    if vk is None:
        raise ValueError(f"can't read the hotkey {text!r}")
    return mods, vk


def listen_for_hotkey(text, on_press):
    """A keyboard shortcut that works everywhere in Windows (Blood itself has no
    window to press keys in). Runs in its own thread, as Windows requires."""
    import threading
    mods, vk = parse_hotkey(text)

    def run():
        if not user32.RegisterHotKey(None, 1, mods | 0x4000, vk):     # 0x4000: no auto-repeat
            log.info(f"Screen shortcut {text} is taken by another program, so it's off")
            return
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312:          # WM_HOTKEY
                on_press()

    threading.Thread(target=run, daemon=True, name="screen-hotkey").start()


def load_page(page, design):
    """The page as bytes. A design page gets its title set to "Blood" (so we can
    find the window), the design picked, and screen_live.js added at the end."""
    path = ROOT / page if page else HERE / "screen.html"
    if not path.exists():
        log.info(f"Screen page {page} not found, using the plain one (blood/screen.html)")
        path = HERE / "screen.html"
    html = path.read_text(encoding="utf-8")
    if path != HERE / "screen.html":
        live = (HERE / "screen_live.js").read_text(encoding="utf-8")
        html = re.sub(r"<title>.*?</title>", f"<title>{TITLE}</title>", html, count=1, flags=re.S)
        pick = f"<script>history.replaceState(null, '', '?design={design}');</script>" if design else ""
        head, _, tail = html.rpartition("</body>")     # rpartition: the page's own scripts mention </body> too
        html = head.replace("<body>", "<body>" + pick, 1) + f"<script>\n{live}\n</script>\n</body>" + tail
    return html.encode("utf-8")


class NoScreen:
    """Used when the screen is switched off in settings.toml: does nothing."""
    async def start(self): pass
    def send(self, **update): pass
    def event(self, kind, **device): pass
    async def show(self): pass
    def done(self): pass
    def hide_now(self): pass
    async def toggle(self): pass


class Screen:
    def __init__(self, hide_after=10.0, page="", design="", greeting="", port=PORT, window=True, hotkey="",
                 kiosk=True, stay_open=True):
        self.hide_after = hide_after
        self.stay_open = stay_open             # True: the window never goes away, it just turns black
        self.hotkey = hotkey
        self.kiosk = kiosk                     # Edge kiosk mode: full screen, no title bar, no buttons
        self.edge = None                       # the Edge process we started
        self.by_hand = False                   # opened with the shortcut: stays until you close it
        self.port, self.window = port, window
        self.url = f"http://127.0.0.1:{port}"
        self.page = load_page(page, design)
        self.clients = set()
        self.now = {"state": "sleep", "heard": "", "answer": ""}   # sent to a page when it (re)connects
        if greeting:
            self.now["greeting"] = greeting
        self.hide_task = None
        self.previous = None                   # the window you were using before Blood popped up

    async def start(self):
        await serve(self._client, "127.0.0.1", self.port, process_request=self._http)
        if self.window and self.hotkey:
            loop = asyncio.get_running_loop()
            listen_for_hotkey(self.hotkey, lambda: loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.toggle())))
        if self.window:
            await asyncio.to_thread(close_old_screens)
            if hwnd := await self._open_window():
                # until "Hey Blood": minimized (still in Alt+Tab), or hidden completely
                user32.ShowWindow(hwnd, SW_SHOWMINNOACTIVE if self.stay_open else SW_HIDE)
            else:
                log.info("The screen window didn't appear (it will be tried again on the wake word)")

    def _find(self):
        return find_window(self.edge.pid if self.edge and self.edge.poll() is None else None)

    async def _open_window(self):
        """Start Edge with the page and wait up to 15 s for its window."""
        profile = pathlib.Path(os.environ["LOCALAPPDATA"]) / "BloodScreen"
        mode = ([f"--kiosk", self.url, "--edge-kiosk-type=fullscreen"] if self.kiosk
                else [f"--app={self.url}", "--start-fullscreen"])
        self.edge = subprocess.Popen([find_edge(), *mode, f"--user-data-dir={profile}", "--no-first-run",
                                      "--no-default-browser-check", "--disable-session-crashed-bubble",
                                      "--autoplay-policy=no-user-gesture-required"])
        for _ in range(75):
            await asyncio.sleep(0.2)
            if hwnd := self._find():
                return hwnd
        return None

    def _http(self, connection, request):
        if request.path == "/ws":
            return None                        # the page's live connection
        if request.path.split("?")[0] not in ("/", "/index.html"):
            return Response(404, "Not Found", Headers([("Content-Length", "0")]), b"")
        return Response(200, "OK", Headers([("Content-Type", "text/html; charset=utf-8"),
                                            ("Content-Length", str(len(self.page))),
                                            ("Cache-Control", "no-store")]), self.page)

    async def _client(self, ws):
        self.clients.add(ws)
        try:
            await ws.send(json.dumps(self.now))
            async for raw in ws:               # the page sends its errors, and Esc / F9
                try:
                    m = json.loads(raw)
                except ValueError:
                    continue
                if m.get("hide"):
                    self.hide_now()
                elif m.get("error"):
                    log.info(f"Screen page error: {m['error']}")
        finally:
            self.clients.discard(ws)

    def send(self, **update):
        """Update the page: state=..., heard=..., answer=..., level=..."""
        self.now.update({k: v for k, v in update.items() if k in ("state", "heard", "answer")})
        broadcast(self.clients, json.dumps(update))

    def event(self, kind, **device):
        """A moment: "device" (name=..., value="on"/"off"), "nohear" or "error"."""
        update = {"event": kind}
        if device:
            update["device"] = device
        broadcast(self.clients, json.dumps(update))

    def _cancel_hide(self):
        if self.hide_task and self.hide_task is not asyncio.current_task():
            self.hide_task.cancel()
        self.hide_task = None

    async def _to_front(self):
        """Screen on, the window up front and full screen (opened again if you closed it)."""
        wake_display()
        hwnd = self._find() or await self._open_window()       # you closed it (Alt+F4): open a new one
        if not hwnd:
            return
        if user32.GetForegroundWindow() != hwnd:
            self.previous = user32.GetForegroundWindow()
            bring_to_front(hwnd)
        if not self.kiosk:                     # kiosk is always full screen; F11 there would undo it
            await fill_screen(hwnd)

    async def show(self):
        """Wake word: a fresh exchange on the page, the window up front."""
        self._cancel_hide()
        self.by_hand = False
        self.send(state="wake", heard="", answer="")
        if self.window:
            await self._to_front()

    def done(self):
        """Blood finished talking: wait a few seconds (unless you speak again),
        play the closing, then turn black (or hide). Opened with the shortcut: it stays."""
        self.send(state="idle")
        self._cancel_hide()
        if not self.by_hand:
            self.hide_task = asyncio.create_task(self._hide_later())

    async def _hide_later(self):
        await asyncio.sleep(self.hide_after)
        self.send(state="done")                # the Eclipse goes dark, the ring is the last ember
        await asyncio.sleep(CLOSING)
        if self.stay_open:
            self._black()                      # the window stays where it is, black; Alt+Tab away from it
        else:
            self.hide_now()

    def _black(self):
        self._cancel_hide()
        self.by_hand = False
        self.previous = None
        if self.window:
            allow_display_sleep()
        self.send(state="sleep", heard="", answer="")

    def hide_now(self):
        """Esc / F9 / the shortcut: black, and out of the way (minimized, still in
        Alt+Tab), or hidden with the focus given back when stay_open is off."""
        previous = self.previous
        self._black()
        if not self.window:
            return
        hwnd = self._find()
        if hwnd and self.stay_open:
            user32.ShowWindow(hwnd, SW_MINIMIZE)        # Windows moves on to the window you used before
        elif hwnd:
            user32.ShowWindow(hwnd, SW_HIDE)
            if previous and user32.IsWindow(previous):
                user32.SetForegroundWindow(previous)

    async def toggle(self):
        """The shortcut: bring the screen up, or put it away if it's already in front."""
        hwnd = self._find()
        if hwnd and user32.GetForegroundWindow() == hwnd and not user32.IsIconic(hwnd):
            self.hide_now()
            return
        self._cancel_hide()
        self.by_hand = True
        if self.now["state"] == "sleep":
            self.send(state="idle")
        await self._to_front()


async def _preview():
    """Plays pretend conversations on its own port, in a loop, without any window
    control, so the look can be checked in a browser while the real Blood runs."""
    import math
    import tomllib
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    cfg = tomllib.loads((HERE / "settings.toml").read_text(encoding="utf-8")).get("screen", {})
    screen = Screen(hide_after=2, page=cfg.get("page", ""), design=cfg.get("design", ""),
                    greeting="Yes, Tudor?", port=PORT + 1, window=False)
    await screen.start()
    print(f"Preview on {screen.url}  (Ctrl+C to stop)")

    async def phase(state, seconds, voice=None, **text):
        screen.send(state=state, **text)
        for i in range(int(seconds * 20)):
            screen.send(level=round(voice(i / 20), 3) if voice else 0)
            await asyncio.sleep(0.05)

    talk = lambda t: max(0.0, 0.6 * math.sin(t * 9) * math.sin(t * 2.3) + 0.2)
    while True:
        await asyncio.sleep(2)
        await screen.show()
        await phase("wake", 1.3, talk)                                       # "Yes, Tudor?"
        await phase("listening", 2.2, talk)
        await phase("thinking", 1.2, heard="Turn off the main light.")
        screen.event("device", name="Main light", value="off")
        await phase("speaking", 2.5, talk, answer="The main light is off.")
        screen.done()
        await asyncio.sleep(1.5)
        await screen.show()                                                  # a follow-up before it hides
        await phase("wake", 1.3, talk)
        await phase("listening", 2.5, talk)
        await phase("thinking", 2.0, heard="Who won more Ballon d'Ors, Messi or Ronaldo?")
        await phase("speaking", 4.0, talk, answer="Messi, with eight. Ronaldo has five.")
        screen.done()
        await asyncio.sleep(2 + CLOSING + 3)


if __name__ == "__main__":
    asyncio.run(_preview())
