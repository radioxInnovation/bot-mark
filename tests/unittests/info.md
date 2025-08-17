---
title: Info
version: 1.0
requirements: mako
options:
    allow_code_execution: True 
---

:::: info
some info
::::

~~~markdown {#version_test .unittest }

# any question...
> <p>some info</p>

~~~

Response  
========         

~~~mako {#response}
${INFO}
~~~
