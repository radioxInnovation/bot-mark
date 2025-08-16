---
title: Hello World Bot
---

~~~mako {#response}
${sorted([t for t, v in RESPONSE.items()])}
~~~

~~~python {#schema}
class Schema(BaseModel):
    name: str
    age: int
~~~

~~~markdown {#version_test .unittest }

# Create a person
> *.+*

~~~
