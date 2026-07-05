# 阿波罗13号 Agent 演示 🚀

**[English](README.md) | 简体中文**

**《大模型没有手》配套代码。一个文件，看懂 AI Agent 的全部骨架。**

1970年4月，休斯顿的工程师有全部的知识，却摸不到飞船一根手指头；舱里的宇航员有手，却不知道该干什么。中间只有一条无线电。

这就是今天所有 AI Agent 的工作方式：

| 阿波罗13号 | Agent 系统 | 代码里的位置 |
|---|---|---|
| 休斯顿（有脑无手） | LLM | `houston_llm()` / `houston_offline()` |
| 机舱（有手） | 运行时 | `execute()` |
| 无线电喊话+复诵 | function calling + 参数校验 | `TOOLS` + `execute()` 里的打回逻辑 |
| 一步步指挥 | 循环（心跳） | `main()` 里的 for 循环 |
| 任务日志 | 上下文（工作台） | `messages` |
| 状态板摘抄 | 便签压缩 | `compact()` |
| 硬性验收标准 | 防"假完工" | `report_done` 的拒收逻辑 |

## 快速开始

**不需要任何 API key，先看机制（推荐）：**

```bash
python3 houston.py --offline
```

你会看到一场完整的救援：休斯顿逐步指挥机组收集材料、组装转接盒。剧本里埋了两次经典翻车：

- **第4轮**，休斯顿喊"拿一只袜子"，这个演示的材料清单里没有袜子，机舱打回重说（**工具幻觉**。历史小注：真实任务的通话记录里，袜子确实被提过一嘴，是堵旁路孔的备选之一，机组最后塞的是毛巾；核心装置从头到尾不靠袜子）
- **第7轮**，材料还没齐它就报告完工，地面按验收标准拒收（**假完工**）

**让真的 LLM 来当休斯顿（任何 OpenAI 兼容接口）：**

```bash
pip install openai

export API_KEY=你的key
export BASE_URL=https://api.deepseek.com   # 或其他兼容地址
export MODEL=deepseek-chat                 # 或 qwen-plus / gpt-4o-mini 等

python3 houston.py
```

真模型每次跑出来的路线都不一样，有时也会喊出不存在的工具、也会提前报完工，正好观察机舱怎么把它打回去。

## 这个演示想说明什么

1. **大模型没有手。** 它全程只输出文字。真正取材料、装设备的是 `execute()`，模型连一个按钮都没按过。
2. **Agent 不是新物种，是一个循环。** 主循环不到三十行：模型说话，是喊话就校验执行、结果回贴，到验收标准或撞到绳子（圈数/红线）就停。
3. **手比脑更需要规矩。** 校验、打回、拒收、上限，这些"不信任模型"的部分，才是 agent 工程的主体。

真实的阿波罗13号"信箱"改装：材料是指令舱的方形滤芯、塑料袋、塑封提示卡、宇航服软管和灰胶带，CAPCOM Joe Kerwin 用了约一小时把步骤逐条念上太空。参考 [NASA Apollo Flight Journal](https://www.nasa.gov/history/afj/ap13fj/15day4-mailbox.html)。

## License

MIT
