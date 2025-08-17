---
title: Hello World Bot
requirements: mako
options:
    allow_code_execution: True
---

~~~mako {#response}
${sorted([t for t, v in RESPONSE.items()])}
~~~

~~~json {#schema}
{
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"}
    },
    "required": ["name", "age"]
}
~~~

~~~markdown {#version_test .unittest }

# Create a person
> ['age', 'name']

~~~
