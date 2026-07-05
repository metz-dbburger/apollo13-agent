#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apollo 13 Agent Demo -- "The Model Has No Hands"
====================================================

April 1970. The engineers in Houston had all the knowledge in the world,
but couldn't touch the spacecraft. The astronauts had hands, but didn't
know what to build. Between them: one radio loop.

That is exactly how every AI agent works today:

    Houston     = the LLM (talks, has no hands)
    The cabin   = the runtime (the only place with hands; validates & executes)
    The radio   = function calling (an agreed protocol for shouting orders)
    Mission log = the context window (the model's only workbench)

The three parts, mapped to code:

    Hands     -> execute()            the model calls, the cabin validates,
                                      executes, and reads back; bad calls
                                      get rejected ("say again")
    Heartbeat -> the main loop        with three safety ropes: hard acceptance
                                      criteria / turn cap / CO2 red line
    Notebook  -> messages + compact() the workbench is finite; long runs get
                                      compacted into sticky notes

Usage:
    python3 houston.py --offline     # no API key needed -- watch the mechanics
    python3 houston.py               # let a real LLM play Houston
                                     # (any OpenAI-compatible API)

Environment variables for live mode:
    export API_KEY=your_key
    export BASE_URL=https://api.deepseek.com   # or any compatible endpoint
    export MODEL=deepseek-chat                 # or qwen-plus / gpt-4o-mini ...
"""

import argparse
import json
import os
import sys

# ============================================================
# 1. The spacecraft (the real world: the model can never touch
#    this dict -- only the cabin's hands can change it)
# ============================================================

SHIP = {
    "co2": 7.6,             # CO2 partial pressure, mmHg
    "co2_red_line": 15.0,   # cross this and the mission fails
    "co2_rise": 0.5,        # per-turn increase
    "materials": ["duct tape", "plastic bag", "manual cover", "suit hose"],
    "collected": [],        # what the crew has brought to hand
    "assembled": False,     # is the adapter built?
    "installed": False,     # is it installed?
}

MAX_TURNS = 20              # safety rope #1: turn cap


# ============================================================
# 2. The tool list (physically just a few paragraphs of text,
#    placed in front of the model next to the task)
# ============================================================

TOOLS = [
    {"type": "function", "function": {
        "name": "get_telemetry",
        "description": "Read cabin telemetry: CO2 level, red line, mission status",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "list_materials",
        "description": "Ask the crew to report what materials are available on board",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "use_material",
        "description": "Ask the crew to fetch one material and keep it at hand. One item per call.",
        "parameters": {"type": "object",
                       "properties": {"item": {"type": "string", "description": "material name"}},
                       "required": ["item"]}}},
    {"type": "function", "function": {
        "name": "assemble_mailbox",
        "description": "Direct the crew to assemble the adapter ('the mailbox') from the materials at hand (requires all four materials collected first)",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "install_scrubber",
        "description": "Install the assembled adapter onto the environmental control system (requires assembly first)",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "report_done",
        "description": "Report mission complete to the ground. Note: the ground audits against hard acceptance criteria -- it is not done just because you say so.",
        "parameters": {"type": "object",
                       "properties": {"summary": {"type": "string", "description": "one-line summary"}},
                       "required": ["summary"]}}},
]

TOOL_NAMES = {t["function"]["name"] for t in TOOLS}


# ============================================================
# 3. The cabin (the runtime: the only place with hands)
#    Every call gets validated -> executed -> read back here
# ============================================================

def execute(name: str, args: dict) -> tuple[str, bool]:
    """Returns (result_text, mission_accepted). Bad calls are rejected here."""

    # Validation, gate 1: tool hallucination (calling a tool that doesn't exist)
    if name not in TOOL_NAMES:
        return (f"Rejected, say again: there is no tool named '{name}'. "
                f"Available tools: {sorted(TOOL_NAMES)}"), False

    if name == "get_telemetry":
        return (f"Telemetry: CO2 {SHIP['co2']:.1f} mmHg (red line {SHIP['co2_red_line']}); "
                f"adapter assembled={'yes' if SHIP['assembled'] else 'no'}, "
                f"installed={'yes' if SHIP['installed'] else 'no'}"), False

    if name == "list_materials":
        remain = [m for m in SHIP["materials"] if m not in SHIP["collected"]]
        return (f"Crew reports materials available on board: {remain}; "
                f"already at hand: {SHIP['collected']}"), False

    if name == "use_material":
        item = (args or {}).get("item", "")
        # Validation, gate 2: the argument points at something that doesn't exist
        # (the historical record has no sock in it, by the way)
        if item not in SHIP["materials"]:
            return (f"Crew readback failed, say again: there is no '{item}' on board. "
                    f"Available materials: {SHIP['materials']}"), False
        if item in SHIP["collected"]:
            return f"'{item}' is already at hand, no need to fetch it again.", False
        SHIP["collected"].append(item)
        return (f"Readback confirmed. Crew has retrieved '{item}'. "
                f"Now at hand: {SHIP['collected']}"), False

    if name == "assemble_mailbox":
        missing = [m for m in SHIP["materials"] if m not in SHIP["collected"]]
        if missing:
            return f"Cannot assemble, still missing: {missing}. Collect them first.", False
        SHIP["assembled"] = True
        return ("Readback confirmed. The 'mailbox' adapter is assembled. "
                "Astonishingly ugly, but it looks like it will work."), False

    if name == "install_scrubber":
        if not SHIP["assembled"]:
            return "Cannot install: the adapter has not been assembled yet.", False
        SHIP["installed"] = True
        SHIP["co2_rise"] = -2.0   # once installed, CO2 starts falling
        return ("Readback confirmed. Adapter connected to the environmental "
                "control system. The gauge starts ticking down."), False

    if name == "report_done":
        # Safety rope #2: acceptance criteria are hard-coded --
        # we do not take the model's word for it (anti "fake done")
        if not SHIP["installed"]:
            return ("Ground refuses sign-off: acceptance criteria are "
                    "'adapter installed AND CO2 falling'. Not met. Continue."), False
        return f"Ground confirms sign-off. Crew summary: {(args or {}).get('summary', '')}", True

    return "Unknown error", False


# ============================================================
# 4. The sticky note (half of the notebook: when the workbench
#    fills up, compress old process into conclusions)
# ============================================================

def compact(messages: list) -> list:
    """Keep the task and the last few turns; compress everything older into one note."""
    if len(messages) <= 12:
        return messages
    head, tail = messages[:1], messages[-6:]          # the task itself + last 6 entries
    note = {"role": "user", "content":
            f"[STICKY NOTE: earlier steps compacted] materials at hand: {SHIP['collected']}; "
            f"assembled={'yes' if SHIP['assembled'] else 'no'}; "
            f"installed={'yes' if SHIP['installed'] else 'no'}."}
    print("      ~ workbench nearly full, compacted into one sticky note")
    return head + [note] + tail


# ============================================================
# 5. Houston (two kinds: one that follows a script,
#    and a real LLM)
# ============================================================

OFFLINE_SCRIPT = [
    ("First, look at the cabin situation.",             "get_telemetry",    {}),
    ("Check what materials are available on board.",    "list_materials",   {}),
    ("Start collecting. Duct tape first.",              "use_material",     {"item": "duct tape"}),
    ("Grab a sock to plug the gap.",                    "use_material",     {"item": "sock"}),        # tool hallucination: no sock in the record
    ("Copy that. Plastic bag instead.",                 "use_material",     {"item": "plastic bag"}),
    ("Take the manual cover for the side panel.",       "use_material",     {"item": "manual cover"}),
    ("That should be enough. Reporting done.",          "report_done",      {"summary": "materials mostly ready"}),  # fake done: will be refused
    ("Understood, continuing. Get the suit hose.",      "use_material",     {"item": "suit hose"}),
    ("All four collected. Assemble the mailbox.",       "assemble_mailbox", {}),
    ("Install it on the environmental control system.", "install_scrubber", {}),
    ("CO2 confirmed falling. Reporting mission complete.", "report_done",   {"summary": "mailbox installed, CO2 dropping"}),
]


def houston_offline(turn: int):
    """A scripted Houston: no API key needed; use it to watch the mechanics."""
    if turn - 1 < len(OFFLINE_SCRIPT):
        return OFFLINE_SCRIPT[turn - 1]
    return ("...", "report_done", {"summary": "signing off"})


def houston_llm(client, model, messages):
    """A real LLM plays Houston. It only ever outputs text --
    the button-pressing happens in the cabin."""
    resp = client.chat.completions.create(
        model=model, messages=messages, tools=TOOLS, temperature=0.2)
    msg = resp.choices[0].message
    if msg.tool_calls:
        call = msg.tool_calls[0]
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        return (msg.content or "", call.function.name, args)
    return (msg.content or "", None, None)


# ============================================================
# 6. The heartbeat (the main loop -- the entire agent skeleton
#    is this one block)
# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="run the scripted demo, no API key required")
    args = ap.parse_args()

    client = model = None
    if not args.offline:
        try:
            from openai import OpenAI
        except ImportError:
            sys.exit("pip install openai first, or run with --offline (zero dependencies)")
        key = os.environ.get("API_KEY")
        if not key:
            sys.exit("Missing API_KEY env var. No key? Run: python3 houston.py --offline")
        client = OpenAI(api_key=key,
                        base_url=os.environ.get("BASE_URL", "https://api.deepseek.com"))
        model = os.environ.get("MODEL", "deepseek-chat")

    print("=" * 60)
    print(" Apollo 13 · Agent Demo | Houston = LLM, Cabin = Runtime")
    print("=" * 60)

    # The notebook: the task goes onto the workbench first
    messages = [{"role": "user", "content":
                 "You are Houston Mission Control. CO2 in the lunar module is rising "
                 "and the crew is in danger. You cannot touch anything on the "
                 "spacecraft -- you can only direct the crew step by step through "
                 "tool calls. Goal: assemble the CO2 adapter ('the mailbox') from "
                 "materials on board and install it. Give one instruction at a time, "
                 "wait for the cabin readback, then give the next. "
                 "Call report_done when everything is finished."}]

    calls = rejects = compacts_n = 0
    done = False
    turn = 0

    for turn in range(1, MAX_TURNS + 1):                        # the heartbeat
        SHIP["co2"] = max(0.0, SHIP["co2"] + SHIP["co2_rise"])  # the real world doesn't wait
        print(f"\n-- Turn {turn} | CO2 {SHIP['co2']:.1f} mmHg (red line {SHIP['co2_red_line']}) --")

        if SHIP["co2"] >= SHIP["co2_red_line"]:                 # safety rope #3: red line
            print("\n[RED] CO2 crossed the red line. Mission failed.")
            break

        # The model speaks (the only thing it ever does)
        if args.offline:
            thought, tool, targs = houston_offline(turn)
        else:
            thought, tool, targs = houston_llm(client, model, messages)

        if thought:
            print(f"  [HOUSTON/LLM] {thought}")

        if tool is None:                                        # no call, just words
            messages.append({"role": "assistant", "content": thought})
            continue

        # A call -> the cabin validates & executes -> result pasted back (the hands)
        calls += 1
        print(f"  [CALL]        {tool}({json.dumps(targs, ensure_ascii=False)})")
        result, done = execute(tool, targs)
        if any(k in result for k in ("Rejected", "refuses", "Cannot", "failed")):
            rejects += 1
        print(f"  [CABIN/RUNTIME] {result}")

        messages.append({"role": "assistant", "content": thought or "",
                         "tool_calls": [{"id": f"c{turn}", "type": "function",
                                         "function": {"name": tool,
                                                      "arguments": json.dumps(targs, ensure_ascii=False)}}]})
        messages.append({"role": "tool", "tool_call_id": f"c{turn}", "content": result})

        before = len(messages)
        messages = compact(messages)                            # the notebook: compaction
        compacts_n += 1 if len(messages) < before else 0

        if done:
            print("\n[GREEN] Ground confirms: mission complete.")
            break

    print("\n" + "=" * 60)
    print(f" THE THREE PARTS | Hands:     {calls} calls, {rejects} rejected/refused")
    print(f"                 | Heartbeat: {turn} turns (cap {MAX_TURNS})")
    print(f"                 | Notebook:  {compacts_n} compactions, {len(messages)} messages on the bench")
    print(f" OUTCOME | CO2 {SHIP['co2']:.1f} mmHg | {'mission complete [OK]' if done else 'incomplete [X]'}")
    print("=" * 60)
    print(" The smartest people on the ground never laid a finger on the spacecraft.")
    print(" They just made every single sentence precise enough.")


if __name__ == "__main__":
    main()
