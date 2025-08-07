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

~~~mako {#response}
${sorted([t for t, v in TOPICS.items() if v])}
~~~

Unit Test
=========

~~~markdown {#version_test .unittest}

# Hello, Alice
> ['any', 'greeting']

# Number: 123
> ['any', 'number_check']

# Email: user@example.com
> ['any', 'email_format']

# It’s time to say goodbye
> ['any', 'goodbye_check']

~~~