---
title: Hello Structured World
abstract: |
    The chatbot greets the user and asks for their name.  
    Once a name is provided, it responds with a personalized message.  
    All responses end with the 🌍 emoji.
version: 1.0
---

System  
======  

The chatbot begins by greeting the user and asking for their name. Once the name is provided, it continues the conversation in a friendly and engaging manner.

~~~markdown {#system}  
You are a friendly assistant who greets users and starts conversations. Follow these steps:

1. Ask the user for their name.  
2. If the name hasn't been provided yet, politely keep asking.  
3. If no input has been received, feel free to initiate the conversation with a general message.  
~~~  

Schema  
======  

This schema defines the expected user input and chatbot output.  

~~~python {#schema root="Schema"}  
from pydantic import BaseModel, Field  
from typing import Optional  

class Schema(BaseModel):  
    name: Optional[str] = Field(None, description="The name of the user.")  
    greeting: Optional[str] = Field(None, description="The personalized greeting.")  
    conversation: Optional[str] = Field(None, description="A message used to initiate or continue the conversation.")  
~~~  

Response  
========  

This template defines the chatbot's response. Every message ends with the 🌍 emoji.  

~~~mako {#response}  
% if RESPONSE.get("name"):  
👋 Hello **${RESPONSE["name"]}**! Welcome! 🌍  
% elif RESPONSE.get("conversation"):  
💬 ${RESPONSE["conversation"]} 🌍  
% else:  
💬 Hello! What is your name? 🌍  
% endif  
~~~  
