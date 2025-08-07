----
title: OpenAI Provider Setup Demo
model:
  type: openai.OpenAIModel
  model_name: gpt-4.1-mini
  provider:
    type: openai.OpenAIProvider
    api_key: your-api-key
----

INFO
====

**Configuration Notes:**

- The `api_key` does **not need to be specified** if the `OPENAI_API_KEY` environment variable is set.
- The `type` field can also be set to `openai.OpenAIResponsesModel` as an alternative.


```markdown {#system}
You are a helpful assistant powered by OpenAI's GPT-4.1-mini model.
```
