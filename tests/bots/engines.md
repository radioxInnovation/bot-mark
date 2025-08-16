---
title: Topic Echo Bot
---

Topics
======

| topic           | description                 | prompt_prefix  | prompt_suffix  | prompt_regex                                        |
| --------------- | --------------------------- | -------------- | -------------- | --------------------------------------------------- |
| greeting        | Detect greeting format      | Hello,         |                |                                                     |
| number_check    | Match single number pattern | Number:        |                |                                                     |
| email_format    | Detect email format         |                |                | Email: *[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+.[a-zA-Z0-9]+ |
| goodbye_check   | Detect goodbye phrase       |                |     goodbye    |                                                     |
| any             | Matches any non-empty input |                |                |                            .+                       |

Responses
=========

~~~mako {#response match="greeting or email_format"}
mako: ${sorted([t for t, v in TOPICS.items() if v])}
~~~

~~~jinja2 {#response  match="number_check"}
jinja2: {{ TOPICS | dictsort | selectattr('1') | map(attribute=0) | list }}
~~~

~~~fstring {#response  match="goodbye_check"}
fstring: {sorted([t for t, v in TOPICS.items() if v])}
~~~

~~~format {#response}
format: {TOPICS}
~~~



Unit Test
=========

~~~markdown {#version_test .unittest}

# Hello, Alice
> mako: ['any', 'greeting']

# Number: 123
> jinja2: ['any', 'number_check']

# Email: user@example.com
> mako: ['any', 'email_format']

# It’s time to say goodbye
> fstring: ['any', 'goodbye_check']

# Just a random note
> *format: .+any.+*

~~~

