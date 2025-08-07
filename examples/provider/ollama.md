---
title: Ollama Model Setup Demo
model:
  type: openai.OpenAIModel
  model_name: llama4
  provider:
    type: openai.OpenAIProvider
    base_url: http://localhost:11434
---

INFO
====

**Configuration Notes:**

- The `base_url` is set to the local Ollama endpoint (`http://localhost:11434`).
- You can omit the `base_url` field if the `OPENAI_BASE_URL` environment variable is set.

```markdown {#system}
You are a helpful assistant powered by Ollama's LLaMA 4 model.
```
