# BotMark – Structured Chatbots in Markdown

**BotMark** is a framework for defining, running, and documenting chatbots using plain Markdown — independent of any specific LLM or backend.

It enables a **single-source-of-truth** approach: chatbot logic, user guidance, data schema, and response formatting are all written in one Markdown file, which can be directly executed, tested, or exported.

---

## ✨ At a Glance

| Feature                        | Description                                                                 |
|-------------------------------|-----------------------------------------------------------------------------|
| ✅ Markdown-based              | Bot definitions live in a structured Markdown format.                       |
| ✅ LLM-agnostic                | Works with any LLM (e.g. OpenAI, Claude, local models).                     |
| ✅ Executable in Python        | Easily run bots using the `botmark` Python package.                         |
| ✅ Single source of truth      | One file defines bot behavior, schema, and user docs.                       |
| ✅ Multi-bot support           | Load multiple bots via folder-based setup.                                  |
| ✅ Easy export                 | Generate Word, HTML, or PDF docs using Pandoc.                              |

---

## 📦 Installation

You can install **BotMark** via pip:

```bash
pip install git+https://github.com/radioxInnovation/bot-mark.git
```

> Requires **Python 3.11+**

## 📘 What is BotMark?

BotMark is a format and Python runtime for defining chatbots declaratively.  
Instead of writing behavior in code, you define:

- The **system prompt** (what the LLM should do)
- The **data schema** (what inputs the bot expects)
- The **response template** (how to render output for the user)

All of this is contained in a **single `.md` file**, making it versionable, testable, and human-readable.

## 🧪 Example BotMark File

```markdown
---
title: Hello World Bot
abstract: >
  A minimal test suite for a conversational AI bot that always responds with "Hello World!" regardless of the input. 
---

~~~markdown {#response}
Hello World 🌍
~~~

```

## 🐍 Using `BotManager` in Python

### 1. From a **folder of bots**

> Loads bots from a folder like `bots/`.  
> Required for any named model (e.g. `"foo"` loads `bots/foo.md`).

```python
from botmark import BotManager

# Load all bot models from a folder
bot = BotManager(bot_dir="bots/")  # bots/foo.md → model: "foo"

msg = {
  "model": "foo",
  "messages": [{ "role": "user", "content": "Hi there" }]
}
print(bot.respond(msg))
```

---

### 2. Using a **default model** (name, string, or `StringIO`)

> You can pass a model name (`"foo"`), a full markdown string, or a file-like object (`io.StringIO`)  
> ⚠️ If a model name is used, `bot_dir` is required to locate it.

```python
from botmark import BotManager
import io

# Option 1: Use model name (requires bot_dir)
bot = BotManager(default_model="foo", bot_dir="bots/")  # loads bots/foo.md


# Option 2: Use file-like object (e.g. StringIO)
bot = BotManager(default_model=io.StringIO("```markdown {#response}\nHello World!\n```"))

msg = {
  "messages": [{ "role": "user", "content": "Hello" }]
}
print(bot.respond(msg))
```

---

### 3. From a **system prompt only** (no model lookup)

> 🛡️ Requires: `allow_system_prompt_fallback=True`  
> Useful for temporary inline bots via system message.

```python
from botmark import BotManager

bot = BotManager(allow_system_prompt_fallback=True)

msg = {
  "model": "",  # or missing
  "messages": [
    { "role": "system", "content": "```markdown {#response}\nHello World!\n```" },
    { "role": "user", "content": "Hello" }
  ]
}
print(bot.respond(msg))
```

---

## 🔁 Combine Folder + Inline

> Combine stable folder-based bots with dynamic inline usage.

```python
from botmark import BotManager

bot = BotManager(bot_dir="bots/", allow_system_prompt_fallback=True)

msg = {
  "model": "nonexistent-model",  # fallback to system prompt
  "messages": [
    { "role": "system", "content": "```markdown {#response}\nHello World!\n```" },
    { "role": "user", "content": "Hello" }
  ]
}
print(bot.respond(msg))
```

---

## ⚠️ Security Note

System-prompt fallback is **disabled by default**.  
To allow fallback to an inline system prompt, use:

```python
BotManager(allow_system_prompt_fallback=True)
```

## 🌐 LLM Agnostic

BotMark does not rely on a specific LLM.
It structures instructions and output templates that **any LLM** can follow — including OpenAI, Claude, Mistral, or your own local model.

* Swap LLMs without changing the bot definition.
* Run evaluation or A/B tests using the same `.md` file.

## 📤 Exporting Documentation

Since everything is written in Markdown, you can export bot definitions and user docs via [Pandoc](https://pandoc.org):

### Export user documentation (with Lua filter)

```bash
pandoc botname.md --lua-filter=extract_userdoc.lua --toc -o userdoc.docx
```

### Export full bot definition

```bash
pandoc botname.md --toc -o complete_bot.docx
```

> This approach enforces **consistency** and reduces duplication across code and documentation.

## ✅ Summary

BotMark is ideal for teams who want:

* Transparent and maintainable chatbot definitions
* LLM vendor flexibility
* Better developer–writer collaboration
* Clean exportable documentation
* One file to define everything — the system, the data, and the output

> 🧩 **Define once. Run anywhere. Document effortlessly.**

## 🔓 License

MIT – use freely, modify openly, contribute happily.
