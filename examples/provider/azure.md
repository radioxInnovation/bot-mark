---
title: Azure OpenAI Model Setup Demo
model:
  type: openai.OpenAIModel
  model_name: gpt-4.1-mini
  provider:
    type: azure.AzureProvider
    azure_endpoint: https://<your-resource-name>.cognitiveservices.azure.com/
    api_version: 20xx-xx-xx-preview
    api_key: your-api-key
---

INFO
====

**Configuration Notes:**

- `azure_endpoint` can be omitted if the `AZURE_OPENAI_ENDPOINT` environment variable is set.
- `api_version` can be omitted if the `OPENAI_API_VERSION` environment variable is set.
- `api_key` can be omitted if the `AZURE_OPENAI_API_KEY` environment variable is set.

Ensure these environment variables are configured properly in your environment if you choose not to specify the values directly.

```markdown {#system}
You are a helpful assistant powered by Azure's deployment of OpenAI's GPT-4.1-mini model.
```
