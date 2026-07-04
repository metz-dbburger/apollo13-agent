#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿波罗13号 Agent 演示 —— 《大模型没有手》配套代码
====================================================

1970年4月，休斯顿的工程师有全部的知识，却摸不到飞船一根手指头；
舱里的宇航员有手，却不知道该干什么。中间只有一条无线电。

这就是今天所有 AI Agent 的工作方式：

    休斯顿  = LLM（只会说话，没有手）
    机舱    = 运行时（唯一有手的地方，负责校验和执行）
    无线电  = function calling（一套喊话的规矩）
    任务日志 = 上下文（模型唯一的工作台）

三件套对照：
    手     -> execute()          模型喊话，机舱校验执行，不合格打回重说
    心跳   -> while 主循环        带三根绳子：验收写死 / 圈数上限 / CO2红线
    笔记本 -> messages + 便签压缩  台面有限，转多了要摘抄

用法：
    python3 houston.py --offline     # 不需要任何 API key，看机制（推荐先跑这个）
    python3 houston.py               # 让真的 LLM 来当休斯顿（OpenAI 兼容接口）

真 LLM 模式的环境变量：
    export API_KEY=你的key
    export BASE_URL=https://api.deepseek.com   # 或其他 OpenAI 兼容地址
    export MODEL=deepseek-chat                 # 或 qwen-plus / gpt-4o-mini 等
"""

import argparse
import json
import os
import sys

# ============================================================
# 一、飞船（真实世界：模型永远碰不到这里，只有机舱的手能动它）
# ============================================================

SHIP = {
    "co2": 7.6,            # 二氧化碳分压 mmHg
    "co2_red_line": 15.0,  # 红线：到这就失败
    "co2_rise": 0.5,       # 每轮上升
    "materials": ["胶带", "塑料袋", "手册封面", "登月服软管"],  # 船上真实有的东西
    "collected": [],       # 已取到手边的
    "assembled": False,    # 转接盒是否拼好
    "installed": False,    # 是否装上
}

MAX_TURNS = 20             # 绳子之一：圈数上限

# ============================================================
# 二、工具清单（物理上就是几段文字，会和任务一起摆在模型眼前）
# ============================================================

TOOLS = [
    {"type": "function", "function": {
        "name": "get_telemetry",
        "description": "读取舱内遥测：CO2浓度、红线、已用轮数",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "list_materials",
        "description": "让机组报告船上可用的材料清单",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "use_material",
        "description": "让机组去取一样材料放到手边。一次取一样。",
        "parameters": {"type": "object",
                       "properties": {"item": {"type": "string", "description": "材料名称"}},
                       "required": ["item"]}}},
    {"type": "function", "function": {
        "name": "assemble_mailbox",
        "description": "指挥机组把手边的材料组装成转接盒（需要先集齐全部四样材料）",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "install_scrubber",
        "description": "把组装好的转接盒装到环控系统上（需要先完成组装）",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "report_done",
        "description": "向地面报告任务完成。注意：地面按硬性验收标准审核，不是你说完成就完成。",
        "parameters": {"type": "object",
                       "properties": {"summary": {"type": "string", "description": "一句话总结"}},
                       "required": ["summary"]}}},
]

TOOL_NAMES = {t["function"]["name"] for t in TOOLS}


# ============================================================
# 三、机舱（运行时：全程唯一有手的地方）
#     每一次喊话都在这里被 校验 -> 执行 -> 复诵
# ============================================================

def execute(name: str, args: dict) -> tuple[str, bool]:
    """返回 (结果文本, 任务是否验收通过)。不合格的喊话在这里被打回。"""

    # 校验第一关：工具幻觉（喊了一个不存在的工具）
    if name not in TOOL_NAMES:
        return f"打回重说：没有『{name}』这个工具。可用工具：{sorted(TOOL_NAMES)}", False

    if name == "get_telemetry":
        return (f"遥测：CO2 {SHIP['co2']:.1f} mmHg（红线 {SHIP['co2_red_line']}）；"
                f"转接盒组装={'完成' if SHIP['assembled'] else '未完成'}，"
                f"安装={'完成' if SHIP['installed'] else '未完成'}"), False

    if name == "list_materials":
        remain = [m for m in SHIP["materials"] if m not in SHIP["collected"]]
        return f"机组报告，船上可取的材料：{remain}；已在手边：{SHIP['collected']}", False

    if name == "use_material":
        item = (args or {}).get("item", "")
        # 校验第二关：参数指向不存在的东西（史料里可没有袜子）
        if item not in SHIP["materials"]:
            return (f"机舱复诵失败，打回重说：船上没有『{item}』。"
                    f"可用材料只有：{SHIP['materials']}"), False
        if item in SHIP["collected"]:
            return f"『{item}』已经在手边了，不用重复取。", False
        SHIP["collected"].append(item)
        return f"复诵确认。机组已取得『{item}』。手边现有：{SHIP['collected']}", False

    if name == "assemble_mailbox":
        missing = [m for m in SHIP["materials"] if m not in SHIP["collected"]]
        if missing:
            return f"无法组装，还缺材料：{missing}。先取齐。", False
        SHIP["assembled"] = True
        return "复诵确认。转接盒『信箱』组装完成，丑得惊人，但看起来能用。", False

    if name == "install_scrubber":
        if not SHIP["assembled"]:
            return "无法安装：转接盒还没组装。", False
        SHIP["installed"] = True
        SHIP["co2_rise"] = -2.0   # 装上之后，CO2 开始往下掉
        return "复诵确认。转接盒已接入环控系统。仪表读数开始一格一格往下走。", False

    if name == "report_done":
        # 绳子之二：验收标准写死，不听模型自己宣布（防"假完工"）
        if not SHIP["installed"]:
            return ("地面拒绝收工：验收标准是『转接盒安装完成且CO2下降』，"
                    "当前未达成。请继续。"), False
        return f"地面确认收工。机组总结：{(args or {}).get('summary', '')}", True

    return "未知错误", False


# ============================================================
# 四、便签（笔记本的一半：台面快满时，把旧过程压缩成结论）
# ============================================================

def compact(messages: list) -> list:
    """保留任务和最近几轮，把更早的过程压缩成一张便签。"""
    if len(messages) <= 12:
        return messages
    head, tail = messages[:1], messages[-6:]          # 任务本身 + 最近6条
    note = {"role": "user", "content":
            f"【便签：更早的过程已压缩】手边材料：{SHIP['collected']}；"
            f"组装={'完成' if SHIP['assembled'] else '未完成'}；"
            f"安装={'完成' if SHIP['installed'] else '未完成'}。"}
    print("      〰️ 台面快满，压缩成便签一张")
    return head + [note] + tail


# ============================================================
# 五、休斯顿（两种：照剧本演的，和真的 LLM）
# ============================================================

OFFLINE_SCRIPT = [
    ("先看一眼舱内情况。",                     "get_telemetry",     {}),
    ("查一下船上有什么材料可用。",             "list_materials",    {}),
    ("开始收集。先拿胶带。",                   "use_material",      {"item": "胶带"}),
    ("再拿一只袜子来堵缝。",                   "use_material",      {"item": "袜子"}),   # 工具幻觉：史料里没有袜子
    ("收到，改用塑料袋。",                     "use_material",      {"item": "塑料袋"}),
    ("拿手册封面来做侧板。",                   "use_material",      {"item": "手册封面"}),
    ("差不多了，先报个完工。",                 "report_done",       {"summary": "材料已基本备齐"}),  # 假完工：会被拒收
    ("明白，继续。取登月服软管。",             "use_material",      {"item": "登月服软管"}),
    ("四样齐了，开始组装转接盒。",             "assemble_mailbox",  {}),
    ("装到环控系统上。",                       "install_scrubber",  {}),
    ("确认CO2下降，正式报告完工。",            "report_done",       {"summary": "信箱已安装，CO2回落"}),
]


def houston_offline(turn: int):
    """照剧本演的休斯顿：不需要API key，用来看清机制。"""
    if turn - 1 < len(OFFLINE_SCRIPT):
        return OFFLINE_SCRIPT[turn - 1]
    return ("……", "report_done", {"summary": "收工"})


def houston_llm(client, model, messages):
    """真的 LLM 当休斯顿。它输出的永远只是文字，按按钮的是机舱。"""
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
# 六、心跳（主循环。整个 agent 的骨架就这一段）
# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="不用API key，照剧本演一遍看机制")
    args = ap.parse_args()

    client = model = None
    if not args.offline:
        try:
            from openai import OpenAI
        except ImportError:
            sys.exit("先 pip install openai，或者用 --offline 模式（无需任何依赖）")
        key = os.environ.get("API_KEY")
        if not key:
            sys.exit("缺 API_KEY 环境变量。没有key就跑：python3 houston.py --offline")
        client = OpenAI(api_key=key,
                        base_url=os.environ.get("BASE_URL", "https://api.deepseek.com"))
        model = os.environ.get("MODEL", "deepseek-chat")

    print("=" * 60)
    print(" 阿波罗13号 · Agent演示 ｜ 休斯顿=LLM，机舱=运行时")
    print("=" * 60)

    # 笔记本：任务先上台面
    messages = [{"role": "user", "content":
                 "你是休斯顿任务控制中心。登月舱CO2浓度正在上升，机组有生命危险。"
                 "你碰不到飞船上的任何东西，只能通过工具指令一步步指挥机组。"
                 "目标：用船上现有材料组装CO2转接盒（信箱）并安装。"
                 "每次只下一条指令，收到机舱复诵后再下一条。全部完成后调用report_done。"}]

    calls = rejects = compacts_n = 0
    done = False

    for turn in range(1, MAX_TURNS + 1):                       # 心跳
        SHIP["co2"] = max(0.0, SHIP["co2"] + SHIP["co2_rise"]) # 真实世界不等人
        print(f"\n—— 第 {turn} 轮 ｜ CO2 {SHIP['co2']:.1f} mmHg（红线 {SHIP['co2_red_line']}）——")

        if SHIP["co2"] >= SHIP["co2_red_line"]:                # 绳子之三：红线
            print("\n🔴 CO2 越过红线。任务失败。")
            break

        # 模型说话（它做的唯一一件事）
        if args.offline:
            thought, tool, targs = houston_offline(turn)
        else:
            thought, tool, targs = houston_llm(client, model, messages)

        if thought:
            print(f"  【休斯顿·LLM】 {thought}")

        if tool is None:                                       # 没喊话，只说了人话
            messages.append({"role": "assistant", "content": thought})
            continue

        # 喊话 -> 机舱校验执行 -> 结果回贴（手）
        calls += 1
        print(f"  【喊话】 {tool}({json.dumps(targs, ensure_ascii=False)})")
        result, done = execute(tool, targs)
        if "打回" in result or "拒绝" in result or "无法" in result:
            rejects += 1
        print(f"  【机舱·运行时】 {result}")

        messages.append({"role": "assistant", "content": thought or "",
                         "tool_calls": [{"id": f"c{turn}", "type": "function",
                                         "function": {"name": tool,
                                                      "arguments": json.dumps(targs, ensure_ascii=False)}}]})
        messages.append({"role": "tool", "tool_call_id": f"c{turn}", "content": result})

        before = len(messages)
        messages = compact(messages)                           # 笔记本：便签压缩
        compacts_n += 1 if len(messages) < before else 0

        if done:
            print("\n🟢 地面确认：任务完成。")
            break

    print("\n" + "=" * 60)
    print(f" 三件套统计 ｜ 手：喊话{calls}次，其中被打回/拒收{rejects}次")
    print(f"            ｜ 心跳：共{turn}轮（上限{MAX_TURNS}）")
    print(f"            ｜ 笔记本：便签压缩{compacts_n}次，台面现存{len(messages)}条")
    print(f" 结局 ｜ CO2 {SHIP['co2']:.1f} mmHg ｜ {'任务完成 ✅' if done else '未完成 ❌'}")
    print("=" * 60)
    print(" 地面上最聪明的人，从头到尾没碰到飞船一根手指头。")
    print(" 他们只是把每一句话，都说得足够准。")


if __name__ == "__main__":
    main()
