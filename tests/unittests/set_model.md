---
title: test model
model:
  type: test.TestModel
---

# System Prompt

~~~mako {#system}
some system prompt
~~~

# A Simple Test

~~~markdown {#my_test .unittest }

# How are you?
> enabled

# What day is it today?
> enabled

# What day is it tomorrow?
> enabled

~~~

~~~mako {#response .disabled}
disabled
~~~

~~~mako {#response}
enabled
~~~
~~~mako {#response .disabled}
disabled
~~~

