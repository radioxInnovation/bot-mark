---
title: Simple Email Review Graph
model: gpt-5
---

# Main Agent

## System Prompt

~~~markdown {#system}
You are the **Main Agent**.  
Write a short, polite email to greet the recipient with "Hello World" and introduce yourself.  
Then pass your draft to the next agent in the graph for review.  
After getting the reviewed version back, update your email to address any feedback before sending the final version.
~~~

## Review Graph

> [*] refers to the main agent.  
> Initially the main agent writes the email.  
> The review agent gives feedback.  
> The main agent improves the email and outputs the final version.

~~~mermaid {#graph}
stateDiagram-v2
    [*] --> review_agent
    review_agent --> [*]
~~~

# Review Agent

~~~markdown {#review_agent .agent}
---
title: review_agent
---

```markdown {#response}
add emojis to start and end
```

~~~
