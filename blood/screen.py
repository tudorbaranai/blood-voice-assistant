"""Blood's screen: a full-screen window that pops up on "Hey Blood".

Two parts:
  - a tiny local web server: it serves screen.html and pushes live updates to
    it over a websocket (state, what you said, the answer, the voice level)
  - window control: an Edge window in "app mode" (no tabs, no address bar,
    its own private profile) that we show on the wake word and hide again
    afterwards, giving the focus back to whatever you were doing

Try the page in any browser while Blood runs: http://127.0.0.1:47202
"""
import asyncio
import ctypes
import ctypes.wintypes as wt
import json
import os
import pathlib
import subprocess
import winreg

from websockets.asyncio.server import broadcast, serve
from websockets.datastructures import Headers
from websockets.http11 import Response

HERE = pathlib.Path(__file__).resolve().parent
PORT = 47202
URL = f"http://127.0.0.1:{PORT}"
TITLE = "Blood"                                # the page's <title>; how we find the window

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
SW_HIDE, SW_SHOW = 0, 5
ES_CONTINUOUS, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000002


def find_edge():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe") as key:
            return winreg.QueryValue(key, None)
    except OSError:
        return r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def find_window():
    """The Edge app window shows just the page title, "Blood"."""
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def check(hwnd, _):
        title = ctypes.create_unicode_buffer(64)
        cls = ctypes.create_unicode_buffer(64)
        user32.GetWindowTextW(hwnd, title, 64)
        user32.GetClassNameW(hwnd, cls, 64)
        if title.value == TITLE and cls.value.startswith("Chrome_WidgetWin"):
            found.append(hwnd)
        return True

    user32.EnumWindows(check, 0)
    return found[0] if found else None


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
    user32.ShowWindow(hwnd, SW_SHOW)
    user32.keybd_event(0x12, 0, 0, 0)          # Alt down
    user32.keybd_event(0x12, 0, 2, 0)          # Alt up
    user32.SetForegroundWindow(hwnd)


class NoScreen:
    """Used when the screen is switched off in settings.toml: does nothing."""
    async def start(self): pass
    def send(self, **update): pass
    async def show(self): pass
    def done(self): pass


class Screen:
    def __init__(self, hide_after=10.0):
        self.hide_after = hide_after
        self.page = (HERE / "screen.html").read_bytes()
        self.clients = set()
        self.now = {"state": "idle", "heard": "", "answer": ""}   # sent to a page when it (re)connects
        self.hide_task = None
        self.previous = None                   # the window you were using before Blood popped up

    async def start(self):
        await serve(self._client, "127.0.0.1", PORT, process_request=self._http)
        if not find_window():
            self._open_window()
            for _ in range(50):                # wait up to 10 s for it, then hide it until needed
                await asyncio.sleep(0.2)
                if hwnd := find_window():
                    user32.ShowWindow(hwnd, SW_HIDE)
                    break

    def _open_window(self):
        profile = pathlib.Path(os.environ["LOCALAPPDATA"]) / "BloodScreen"
        subprocess.Popen([find_edge(), f"--app={URL}", f"--user-data-dir={profile}", "--start-fullscreen",
                          "--no-first-run", "--no-default-browser-check", "--disable-session-crashed-bubble"])

    def _http(self, connection, request):
        if request.path == "/ws":
            return None                        # the page's live connection
        return Response(200, "OK", Headers([("Content-Type", "text/html; charset=utf-8"),
                                            ("Content-Length", str(len(self.page))),
                                            ("Cache-Control", "no-store")]), self.page)

    async def _client(self, ws):
        self.clients.add(ws)
        try:
            await ws.send(json.dumps(self.now))
            await ws.wait_closed()
        finally:
            self.clients.discard(ws)

    def send(self, **update):
        """Update the page: state=..., heard=..., answer=..., level=..."""
        self.now.update({k: v for k, v in update.items() if k != "level"})
        broadcast(self.clients, json.dumps(update))

    async def show(self):
        """Wake word: screen on, window to the front, clear the old conversation."""
        if self.hide_task:
            self.hide_task.cancel()
        wake_display()
        self.send(state="wake", heard="", answer="")
        hwnd = find_window()
        if not hwnd:                           # you closed it: open a new one
            self._open_window()
            for _ in range(50):
                await asyncio.sleep(0.2)
                if hwnd := find_window():
                    break
        if hwnd and user32.GetForegroundWindow() != hwnd:
            self.previous = user32.GetForegroundWindow()
            bring_to_front(hwnd)

    def done(self):
        """Blood finished talking: hide in a few seconds (unless you speak again)."""
        self.send(state="idle")
        if self.hide_task:
            self.hide_task.cancel()
        self.hide_task = asyncio.create_task(self._hide_later())

    async def _hide_later(self):
        await asyncio.sleep(self.hide_after)
        if hwnd := find_window():
            user32.ShowWindow(hwnd, SW_HIDE)
        if self.previous:
            user32.SetForegroundWindow(self.previous)
            self.previous = None
        allow_display_sleep()


async def _demo():
    """Plays one pretend conversation, to check the look without talking.
    (Stop the real Blood first: it uses the same port.)"""
    import math
    screen = Screen(hide_after=3)
    await screen.start()
    await screen.show()

    async def phase(state, seconds, voice, **text):
        screen.send(state=state, **text)
        for i in range(int(seconds * 20)):
            screen.send(level=voice(i / 20))
            await asyncio.sleep(0.05)

    talk = lambda t: max(0.0, 0.6 * math.sin(t * 9) * math.sin(t * 2.3) + 0.2)
    await phase("speaking", 1.2, talk)                                  # "Yes, Tudor?"
    await phase("listening", 2.5, talk)                                 # you talk
    await phase("thinking", 2.5, lambda t: 0, heard="Who's better, Messi or Ronaldo?")
    await phase("speaking", 4.0, talk, answer="Most people would say Messi, for his consistency "
                                              "and record-breaking achievements.")
    screen.done()
    await asyncio.sleep(4)


if __name__ == "__main__":
    asyncio.run(_demo())
