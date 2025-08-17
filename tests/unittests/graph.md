---
title: Graph Usage
requirements: mako
options:
    allow_code_execution: True
---

# Main Agent

## Response

~~~mako {#response}
${QUERY}->main\
~~~

## Graph

~~~mermaid {#graph}
stateDiagram-v2
    [*] --> agent_1
    agent_1 --> agent_2
    agent_2 --> [*]
~~~

# Agent 1

~~~markdown {#agent_1 .agent}
---
title: agent_1
---

```mako {#response}
${QUERY}->agent_1\
```
~~~


# Agent 2

~~~markdown {#agent_2 .agent}
---
title: agent_2
---

```mako {#response}
${QUERY}->agent_2\
```

~~~

# A Simple Test

~~~markdown {#graph_test .unittest }

# Hello
> Hello->main->agent_1->agent_2->main

~~~
