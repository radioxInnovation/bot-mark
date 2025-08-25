---
title: Info
version: 1.0
requirements: mako
options:
    allow_code_execution: True 
---

~~~markdown {#info }
some info
~~~

~~~markdown {#version_test .unittest }

# any question...
> some info

~~~

Response  
========         

~~~mako {#response}
${BLOCKS["info"].get("content")}
~~~
