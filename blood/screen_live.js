/* Blood's screen, live: plugs a design page (the Eclipse) into the voice program.
 *
 * screen.py adds this to the end of the design page when it serves it. The page
 * on its own plays a pretend conversation; this script stops that and feeds it
 * the real moments instead, over a websocket from blood.py:
 *   { state, heard, answer, level, event, device, greeting }
 * It also hides the design page's buttons and labels, ignores its keys, and
 * reports page errors back to Blood's log (the window has no console to read).
 */
(() => {
  "use strict";
  const style = document.createElement("style");
  style.textContent = "#label, #controls { display: none !important; } body, body.pointer { cursor: none !important; }";
  document.head.appendChild(style);

  let ws = null;
  const tell = m => { try { ws && ws.readyState === 1 && ws.send(JSON.stringify(m)); } catch (e) {} };

  // Esc or F9 hides the screen. The design page's own keys (1-4 switch designs,
  // arrows step the demo, M = mic) are for trying it out, so they're switched off.
  addEventListener("keydown", e => {
    e.stopImmediatePropagation();
    if (e.key === "Escape" || e.key === "F9") { e.preventDefault(); tell({ hide: true }); }
  }, true);

  window.update({ state: "sleep" });           // stop the demo now, before the first message arrives

  // A follow-up question: the last exchange moves up into the history, like after "Hey Blood"
  function next() {
    const a = Blood.api;
    if (a.heard || a.answer) {
      a.history.push({ heard: a.heard, answer: a.answer });
      a.history = a.history.slice(-3); a.historyAge = 0;
    }
    window.update({ heard: "", answer: "" });
  }

  const report = text => tell({ error: text });
  addEventListener("error", e => report(`${e.message} (${(e.filename || "").split("/").pop()}:${e.lineno})`));
  addEventListener("unhandledrejection", e => report(String(e.reason)));

  function connect() {
    ws = new WebSocket(`ws://${location.host}/ws`);
    ws.onmessage = e => {
      const m = JSON.parse(e.data);
      if (m.greeting) Blood.api.greeting = m.greeting;
      if (m.next) next();
      window.update(m);
    };
    ws.onclose = () => setTimeout(connect, 1000);   // Blood restarted: reconnect
  }
  connect();
})();
