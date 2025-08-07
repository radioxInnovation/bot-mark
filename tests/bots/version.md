---
title: Compare Versions
---

~~~markdown {#version_test .unittest }

# Compare VERSION with botmark version – are they equal?
> YES

~~~

Response  
========         

~~~mako {#response}  
<%!
    import botmark
%>

${"YES" if VERSION == botmark.__version__ else "NO" }
~~~  
