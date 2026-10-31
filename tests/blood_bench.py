"""Blood test bench: talk to the brain the way Home Assistant does, and grade it.

It sends each test sentence to Ollama with:
  - your prompt (prompts/*.txt), with the calendar and clock filled in like Home Assistant does
  - Home Assistant's own hidden instructions and device list (copied from HA 2026.10.1's source)
  - the same tools Home Assistant offers (intent__HassTurnOn, intent__HassTurnOff,
    light__HassLightSet, homeassistant__GetLiveContext, ...)
It then plays Home Assistant: runs the tool calls on a pretend house, sends the
results back, and grades the final answer. Nothing real is switched.

The most important check is the LIE DETECTOR: if the answer claims something was
done ("Done, the light is on") but no switching tool actually succeeded, it fails.

Usage:
    python tests/blood_bench.py --prompt prompts/prompt_v12_devices.txt --label v12
    python tests/blood_bench.py --model qwen3:1.7b --label small --cat control,missing
    python tests/blood_bench.py --only 18,19,35 --repeat 3
    python tests/blood_bench.py --compare        # table of all saved runs
"""
import argparse
import datetime
import json
import pathlib
import re
import time
import urllib.request

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
RESULTS = HERE / "results"

# ---------------------------------------------------------------------------
# What Home Assistant 2026.10.1 adds to the prompt (copied from its source:
# components/homeassistant/llm.py and components/intent/llm.py)
# ---------------------------------------------------------------------------
DYNAMIC_CONTEXT_PROMPT = (
    "You ARE equipped to answer questions about the current state of\n"
    "the home by retrieving live context. This is a primary function. Do not state you lack the\n"
    "functionality if the question requires live data.\n"
    'If the user asks about device existence/type (e.g., "Do I have lights in the bedroom?"): Answer\n'
    "from the static context below.\n"
    'If the user asks about the CURRENT state, value, or mode (e.g., "Is the lock locked?",\n'
    '"Is the fan on?", "What mode is the thermostat in?", "What is the temperature outside?"):\n'
    "    1.  Recognize this requires live data.\n"
    "    2.  You MUST use the provided tool to retrieve live context. This tool will provide the needed "
    "real-time information (like temperature from the local weather, lock status, etc.).\n"
    '    3.  Use the tool\'s response** to answer the user accurately (e.g., "The temperature outside is '
    '[value from tool].").\n'
    "For general knowledge questions not about the home: Answer truthfully from internal knowledge.\n"
)
DEVICE_CONTROL_PROMPT = (
    "When controlling Home Assistant always call the intent tools. "
    "Use intent__HassTurnOn to lock and intent__HassTurnOff to unlock a lock. "
    "When controlling a device, prefer passing just name and domain. "
    "When controlling an area, prefer passing just area name and domain."
)

TARGET_PARAMS = {
    "name": {"type": "string", "description": "Name of a device or entity"},
    "area": {"type": "string", "description": "Name of an area"},
    "floor": {"type": "string", "description": "Name of a floor"},
    "domain": {"type": "array", "items": {"type": "string"}, "description": "Domain of devices/entities in an area"},
    "device_class": {"type": "array", "items": {"type": "string"}, "description": "Device class of devices/entities in an area"},
}


def tool(name, description, props):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": props, "required": []}}}


TOOLS = [
    tool("intent__HassTurnOn", "Turns on/opens/presses a device or entity. For locks, this performs a 'lock' action. "
         "Use for requests like 'turn on', 'activate', 'enable', or 'lock'.", TARGET_PARAMS),
    tool("intent__HassTurnOff", "Turns off/closes a device or entity. For locks, this performs an 'unlock' action. "
         "Use for requests like 'turn off', 'deactivate', 'disable', or 'unlock'.", TARGET_PARAMS),
    tool("intent__HassCancelAllTimers", "Cancels all timers", {"area": {"type": "string"}}),
    tool("light__HassLightSet", "Sets the brightness percentage or color of a light", dict(TARGET_PARAMS, **{
        "brightness": {"type": "integer", "description": "The brightness percentage of the light between 0 and 100, "
                       "where 0 is off and 100 is fully lit"},
        "color": {"type": "string", "description": "Name of a color"},
        "temperature": {"type": "integer", "description": "Color temperature in Kelvin"}})),
    tool("homeassistant__GetLiveContext",
         "Provides real-time information about the CURRENT state, value, or mode of devices, sensors, entities, "
         "or areas. Use this tool for: 1. Answering questions about current conditions (e.g., 'Is the light on?'). "
         "2. As the first step in conditional actions (e.g., 'If the weather is rainy, turn off sprinklers' requires "
         "checking the weather first). You may filter for devices by name, domain, and area, including combining "
         "those filters. Prefer filtering by domain when searching for multiple devices of the same type.",
         {"name": {"type": "string", "description": "Filter entities by name or alias (case-insensitive)."},
          "domain": {"type": "string", "description": "Filter entities by domain (e.g. 'light', 'sensor'). "
                     "Accepts a single domain or a list."},
          "area": {"type": "string", "description": "Filter entities by area name or alias (case-insensitive)."}}),
]
MUTATING = {"intent__HassTurnOn", "intent__HassTurnOff", "light__HassLightSet"}


# ---------------------------------------------------------------------------
# Prompt rendering (the Jinja parts Home Assistant fills in)
# ---------------------------------------------------------------------------
def render_prompt(text, now):
    def calendar(m):
        in_days = "in {{ i }} days" in m.group(0)
        lines = []
        for i in range(29):
            d = now + datetime.timedelta(days=i)
            line = d.strftime("%A %d %B %Y") + (" (today)" if i == 0 else " (tomorrow)" if i == 1
                                                else f" (in {i} days)" if in_days else "")
            lines.append(line)
        return "\n" + "\n".join(lines)
    text = re.sub(r"\{%-?\s*for i in range\(0, 29\)\s*%\}.*?\{%-?\s*endfor\s*%\}", calendar, text, flags=re.S)
    text = re.sub(r'\{\{\s*now\(\)\.strftime\("([^"]*)"\)\s*\}\}', lambda m: now.strftime(m.group(1)), text)
    return text


def yaml_entities(devices, with_state=False, states=None):
    out = []
    for d in devices:
        names = ", ".join([d["name"]] + d.get("aliases", []))
        out.append(f"- names: {names}\n  domain: {d['domain']}")
        if with_state:
            st = states[d["name"]]
            out.append(f"  state: '{st['state']}'")
        out.append(f"  areas: {d['area']}")
        if with_state and d.get("dimmable") and states[d["name"]]["state"] == "on":
            out.append(f"  attributes:\n    brightness: {states[d['name']]['brightness']}")
    return "\n".join(out) + "\n"


def system_prompt(user_prompt, devices):
    api = (DYNAMIC_CONTEXT_PROMPT + "Static Context: An overview of the areas and the devices in this smart home:\n"
           + yaml_entities(devices) + "\n" + DEVICE_CONTROL_PROMPT)
    return user_prompt + "\n" + api


# ---------------------------------------------------------------------------
# The pretend house: runs tool calls like Home Assistant would
# ---------------------------------------------------------------------------
class House:
    def __init__(self, devices, init):
        self.devices = devices
        self.states = {d["name"]: {"state": "off", "brightness": 100, "color": None} for d in devices}
        for name, st in (init or {}).items():
            self.states[name]["state"] = st

    def snapshot(self):
        return json.loads(json.dumps(self.states))

    def match(self, args):
        name, area = args.get("name"), args.get("area")
        domain = args.get("domain")
        if isinstance(domain, str):
            domain = [domain]
        cands = list(self.devices)
        if name:
            n = name.strip().lower()
            cands = [d for d in cands if n in [x.lower() for x in [d["name"]] + d.get("aliases", [])]]
            if not cands:
                return None, f"MatchFailedError: No device or entity named {name}"
        if area:
            cands = [d for d in cands if d["area"].lower() == area.strip().lower()]
            if not cands:
                return None, f"MatchFailedError: No area named {area}"
        if domain:
            cands = [d for d in cands if d["domain"] in domain]
            if not cands:
                return None, f"MatchFailedError: No entities of domain {', '.join(domain)} matched"
        if not (name or area or domain):
            return None, "MatchFailedError: No target given"
        return cands, None

    def run(self, fn, args):
        if fn == "homeassistant__GetLiveContext":
            devs = self.devices
            if args.get("name") or args.get("area") or args.get("domain"):
                devs, err = self.match(args)
                if err:
                    return False, {"error": "MatchFailedError", "error_text": err}
            return False, {"result": "Live Context: An overview of the areas and the devices in this smart home:\n"
                           + yaml_entities(devs, True, self.states)}
        if fn == "intent__HassCancelAllTimers":
            return False, {"error": "HomeAssistantError", "error_text": "No timers are running"}
        if fn not in MUTATING:
            return False, {"error": "ToolNotFound", "error_text": f"Unknown tool {fn}"}
        devs, err = self.match(args)
        if err:
            return False, {"error": "MatchFailedError", "error_text": err}
        if fn == "light__HassLightSet":
            if not all(d.get("dimmable") for d in devs):
                return False, {"error": "HomeAssistantError", "error_text": "Entity does not support brightness or color"}
            for d in devs:
                st = self.states[d["name"]]
                if "brightness" in args:
                    b = int(args["brightness"])
                    st["brightness"], st["state"] = b, ("off" if b == 0 else "on")
                if args.get("color") or args.get("temperature"):
                    st["color"] = str(args.get("color") or args.get("temperature")).lower()
                    st["state"] = "on"
        else:
            for d in devs:
                self.states[d["name"]]["state"] = "on" if fn == "intent__HassTurnOn" else "off"
        return True, {"speech": {}, "response_type": "action_done",
                      "data": {"targets": [], "success": [{"name": d["name"], "type": "entity",
                               "id": d["domain"] + "." + d["name"].lower().replace(" ", "_")} for d in devs],
                               "failed": []}}


# ---------------------------------------------------------------------------
# Talking to Ollama the way Home Assistant's Ollama integration does
# ---------------------------------------------------------------------------
MAX_TOKENS = 400  # answer length cap; a runaway answer is reported as a failure
EXTRA_OPTIONS = {}  # e.g. num_gpu / temperature, to try what a Modelfile would set


def chat(host, model, messages, ctx):
    body = {"model": model, "messages": messages, "tools": TOOLS, "stream": False,
            "keep_alive": -1, "options": {"num_ctx": ctx, "num_predict": MAX_TOKENS, **EXTRA_OPTIONS}}
    if not model.endswith("+think"):
        body["think"] = False
    else:
        body["model"] = model[:-6]
    req = urllib.request.Request(f"{host}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    resp = json.load(urllib.request.urlopen(req, timeout=600))
    msg = resp["message"]
    msg["_runaway"] = resp.get("done_reason") == "length"
    return msg


def run_turn(host, model, ctx, messages, house, log):
    """One user turn, with up to 5 tool rounds. Returns the final text."""
    final = ""
    for _ in range(5):
        msg = chat(host, model, messages, ctx)
        if msg.get("_runaway"):
            log.append({"tool": "RUNAWAY", "args": {}, "ok": False, "error": "answer hit the length cap"})
        calls = msg.get("tool_calls") or []
        text = (msg.get("content") or "").strip()
        messages.append({"role": "assistant", "content": msg.get("content") or "", **({"tool_calls": calls} if calls else {})})
        if text:
            final = text
        if not calls:
            break
        for c in calls:
            fn = c["function"]["name"]
            args = c["function"].get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            ok, result = house.run(fn, args)
            log.append({"tool": fn, "args": args, "ok": ok, "error": result.get("error_text")})
            messages.append({"role": "tool", "content": json.dumps(result), "tool_name": fn})
    return final


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------
NON_LATIN = re.compile(r"[Ѐ-ӿ؀-ۿ぀-ヿ㐀-鿿가-힯ᄀ-ᇿ]")
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")
MARKDOWN = re.compile(r"(^\s*([-*•]|\d+[.)])\s)|\*\*|^#", re.M)
CLAIMS_ACTION = re.compile(r"\b(done|turned|switched|i've|i have|has been|have been|is now|are now|now (on|off)|"
                           r"i'll (turn|switch|set|dim)|i will (turn|switch|set|dim)|turning (on|off)|switching (on|off)|"
                           r"dimmed|brightened|set (it|the|to)|changed)\b", re.I)
REFUSAL = re.compile(r"(not sure|subjective|complex topic|many opinions|i can't|i cannot|i'm unable|i am unable|"
                     r"don't have (that|this|enough) information|no information)", re.I)
NEGATIVE = re.compile(r"(can.t|cannot|can not|don.t control|do not control|not set up|not connected|not part of|not in (your|the) (home|list)|don't have|do not have|couldn't|could not|not find|no device|"
                      r"not able|unable|doesn't exist|does not exist|isn't|is not|not available|don't see|"
                      r"no such|not found|only control|only have|there is no|there's no|aren't any|no .* (in|connected))", re.I)
SAYS_ON = re.compile(r"\b(yes|is on|are on|it's on|they're on|currently on|turned on|still on)\b", re.I)
SAYS_OFF = re.compile(r"\b(no|is off|are off|it's off|they're off|currently off|not on|turned off|still off)\b", re.I)


def says_state(text, truth_on):
    t = text.lower()
    on, off = bool(SAYS_ON.search(t)), bool(SAYS_OFF.search(t))
    if truth_on:
        return on and not re.search(r"\b(is off|are off|not on|it's off|they're off)\b", t)
    return off and not re.search(r"\b(is on|are on|it's on|they're on)\b", t)


def grade(case, text, before, after, calls_last, calls_all, today):
    problems = []
    t = text.lower()
    fill = {"{today_weekday}": today.strftime("%A").lower(),
            "{plus10_weekday}": (today + datetime.timedelta(days=10)).strftime("%A").lower()}
    calls_last = [c for c in calls_last if c["tool"] != "RUNAWAY"] + [c for c in calls_last if c["tool"] == "RUNAWAY"]
    succeeded_last = [c for c in calls_last if c["ok"]]
    succeeded_all = [c for c in calls_all if c["ok"]]
    changed = {n for n in after if after[n] != before[n]}
    exp = case["expect"]

    if any(c["tool"] == "RUNAWAY" for c in calls_all):
        problems.append("RUNAWAY: endless answer (hit the length cap)")
    if not text:
        problems.append("empty answer")
    if NON_LATIN.search(text):
        problems.append("non-English letters")
    if EMOJI.search(text):
        problems.append("emoji")
    if MARKDOWN.search(text):
        problems.append("markdown/list formatting")
    if "let me know" in t:
        problems.append("filler ending")
    lie = bool(CLAIMS_ACTION.search(text)) and not succeeded_last and exp not in ("state",)
    if lie and exp != "no_change":
        problems.append("LIE: claims an action but no switch tool succeeded")

    if exp == "act":
        for n, st in case.get("final", {}).items():
            if after[n]["state"] != st:
                problems.append(f"{n} should be {st}, is {after[n]['state']}")
        if case.get("final_any_on") and not any(after[n]["state"] == "on" for n in case["final_any_on"]):
            problems.append("nothing was turned on")
        if "brightness" in case and after["Main light"]["brightness"] != case["brightness"]:
            problems.append(f"brightness should be {case['brightness']}, is {after['Main light']['brightness']}")
        if "brightness_below" in case and after["Main light"]["brightness"] >= case["brightness_below"]:
            problems.append("not dimmed")
        if "color" in case and case["color"] not in str(after["Main light"]["color"]):
            problems.append(f"colour not set to {case['color']}")
        if not succeeded_all:
            problems.append("no switch tool succeeded")
    elif exp in ("no_change", "state", "refuse"):
        if changed:
            problems.append(f"changed devices it shouldn't: {', '.join(sorted(changed))}")
        if exp == "state" and not says_state(text, case["truth"] == "yes"):
            problems.append(f"wrong/unclear state answer (truth: {case['truth']})")
        if exp == "refuse":
            if CLAIMS_ACTION.search(text) and not NEGATIVE.search(text):
                problems.append("LIE: claims it did something that doesn't exist")
            elif not NEGATIVE.search(text) and "?" not in text:
                problems.append("doesn't say it can't")
    elif exp == "ask_or_act":
        if changed:
            bad = [n for n in changed if n not in case.get("allowed_on", []) or after[n]["state"] != "on"]
            if bad:
                problems.append(f"changed the wrong device: {', '.join(bad)}")
        elif "?" not in text:
            problems.append("neither acted nor asked")
    elif exp == "lenient":
        if case.get("only_off") and any(after[n]["state"] == "on" and before[n]["state"] == "off" for n in after):
            problems.append("turned something ON")
        if case.get("only_off_or_dim") and any(
                after[n]["state"] == "on" and (before[n]["state"] == "off" or after[n]["brightness"] > before[n]["brightness"])
                for n in after):
            problems.append("made it brighter")
        if case.get("consistent_last"):
            n = case["consistent_last"]
            if not says_state(text, after[n]["state"] == "on"):
                problems.append(f"answer doesn't match reality ({n} is {after[n]['state']})")

    if case.get("must_any") and not any(fill.get(w, w).lower() in t for w in case["must_any"]):
        problems.append("missing expected content (" + " / ".join(fill.get(w, w) for w in case["must_any"][:4]) + ")")
    for w in case.get("must_all", []):
        if w.lower() not in t:
            problems.append(f"missing '{w}'")
    for w in case.get("must_not", []):
        if w.lower() in t:
            problems.append(f"should not say '{w}'")
    if case.get("min_hits") and sum(h in t for h in case["hits"]) < case["min_hits"]:
        problems.append(f"fewer than {case['min_hits']} correct items")
    if case.get("no_refusal") and REFUSAL.search(text):
        problems.append("refused / 'not sure'")
    return problems


# ---------------------------------------------------------------------------
def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="prompts/prompt_v12_devices.txt")
    ap.add_argument("--model", default="qwen3:4b-instruct", help="add +think to switch thinking on")
    ap.add_argument("--label", default=None)
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--ctx", type=int, default=4096)
    ap.add_argument("--cases", default=str(HERE / "blood_bench_cases.json"))
    ap.add_argument("--only", default="", help="comma-separated case ids")
    ap.add_argument("--cat", default="", help="comma-separated categories")
    ap.add_argument("--repeat", type=int, default=1, help="run each case N times (catches flaky answers)")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--num-gpu", type=int, default=None, help="layers on the GPU (99 = all)")
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()

    global MAX_TOKENS
    MAX_TOKENS = a.max_tokens
    if a.num_gpu is not None:
        EXTRA_OPTIONS["num_gpu"] = a.num_gpu
    if a.temperature is not None:
        EXTRA_OPTIONS["temperature"] = a.temperature
    RESULTS.mkdir(exist_ok=True)
    if a.compare:
        rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RESULTS.glob("bench-*.json"))]
        print(f"{'run':38} {'pass':>9} {'lies':>5} {'avg s':>6}  per category")
        for r in rows:
            cats = " ".join(f"{c}:{v[0]}/{v[1]}" for c, v in r["by_cat"].items())
            print(f"{r['label'][:38]:38} {r['passed']:>4}/{r['total']:<4} {r['lies']:>5} {r['avg_s']:>6}  {cats}")
        return

    spec = json.loads(pathlib.Path(a.cases).read_text(encoding="utf-8"))
    devices, cases = spec["devices"], spec["cases"]
    if a.only:
        ids = {int(x) for x in a.only.split(",")}
        cases = [c for c in cases if c["id"] in ids]
    if a.cat:
        cats = set(a.cat.split(","))
        cases = [c for c in cases if c["cat"] in cats]

    now = datetime.datetime.now()
    prompt_path = (ROOT / a.prompt) if not pathlib.Path(a.prompt).is_absolute() else pathlib.Path(a.prompt)
    sysmsg = system_prompt(render_prompt(prompt_path.read_text(encoding="utf-8"), now), devices)
    label = a.label or f"{prompt_path.stem}-{a.model}"
    print(f"Bench: {label}  ({len(cases)} cases x {a.repeat})  model={a.model}  prompt={prompt_path.name}")

    # warm-up (loads the model, caches the prompt), not timed
    chat(a.host, a.model, [{"role": "system", "content": sysmsg}, {"role": "user", "content": "Hi"}], a.ctx)

    rows, times = [], []
    for case in cases:
        for rep in range(a.repeat):
            house = House(devices, case.get("init"))
            before = house.snapshot()
            messages = [{"role": "system", "content": sysmsg}]
            turns = case["say"] if isinstance(case["say"], list) else [case["say"]]
            calls_all, text, t0 = [], "", time.time()
            try:
                for turn in turns:
                    calls_last = []
                    messages.append({"role": "user", "content": turn})
                    text = run_turn(a.host, a.model, a.ctx, messages, house, calls_last)
                    calls_all += calls_last
                problems = grade(case, text, before, house.snapshot(), calls_last, calls_all, now)
            except Exception as e:  # noqa: BLE001
                problems, calls_last = [f"ERROR {e}"], []
            secs = (time.time() - t0) / len(turns)
            times.append(secs)
            ok = not problems
            rows.append({"id": case["id"], "cat": case["cat"], "say": " >> ".join(turns), "ok": ok,
                         "problems": problems, "text": text, "secs": round(secs, 1),
                         "tools": [f"{c['tool'].split('__')[-1]}({', '.join(f'{k}={v}' for k, v in c['args'].items())})"
                                   f"{'' if c['ok'] or c['tool'].endswith('GetLiveContext') else ' FAILED'}" for c in calls_all]})
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] #{case['id']:<3} {case['cat']:<10} {secs:5.1f}s  {turns[-1][:45]:45} -> {text[:70]!r}"
                  + ("" if ok else f"  <-- {'; '.join(problems)}"))

    passed = sum(r["ok"] for r in rows)
    lies = sum(any("LIE" in p for p in r["problems"]) for r in rows)
    by_cat = {}
    for r in rows:
        v = by_cat.setdefault(r["cat"], [0, 0])
        v[0] += r["ok"]
        v[1] += 1
    avg = round(sum(times) / max(len(times), 1), 1)
    print(f"\nRESULT {label}: {passed}/{len(rows)} passed, {lies} lies, avg {avg}s, worst {max(times, default=0):.1f}s")
    print("  " + "  ".join(f"{c} {v[0]}/{v[1]}" for c, v in by_cat.items()))

    stamp = now.strftime("%Y-%m-%d_%H-%M")
    summary = {"label": label, "model": a.model, "prompt": prompt_path.name, "time": stamp, "passed": passed,
               "total": len(rows), "lies": lies, "avg_s": avg, "worst_s": round(max(times), 1), "by_cat": by_cat,
               "rows": rows}
    safe = re.sub(r"[^\w.-]+", "_", label)
    (RESULTS / f"bench-{safe}-{stamp}.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    md = [f"# Blood bench: {label} ({stamp})", "",
          f"Model `{a.model}`, prompt `{prompt_path.name}`. **{passed}/{len(rows)} passed, {lies} lies**, "
          f"avg {avg} s, worst {max(times):.1f} s.", "",
          "| Category | Passed |", "|---|---|"] + [f"| {c} | {v[0]}/{v[1]} |" for c, v in by_cat.items()] + [
          "", "| # | Cat | Result | Said | Tools used | Answer | Problems | s |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['id']} | {r['cat']} | {'✅' if r['ok'] else '❌'} | {r['say']} | {'<br>'.join(r['tools']) or '-'} | "
                  f"{r['text'].replace('|', '/').replace(chr(10), ' ')} | {'; '.join(r['problems'])} | {r['secs']} |")
    (RESULTS / f"bench-{safe}-{stamp}.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
