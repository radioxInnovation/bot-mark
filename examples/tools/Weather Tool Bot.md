---
title: Weather Tool Bot
subtitle: Simple Conversational AI for Weather Queries
abstract: A minimal test suite for a conversational AI bot that provides the current temperature, weather conditions, and forecasts for requested locations.
---

<!-- model: gpt-5 -->

# Introduction

## Hint

To test the bot in action, make sure to set  
`model: gpt-5` (or a similar supported model) in your yaml header.

## Info

:::: info

This document describes a simple test setup for a conversational AI "Weather Tool Bot."  
The bot responds to user queries about weather information, including the current temperature, conditions, and forecast.  
It uses a set of tools (Python functions) to return static values for demonstration purposes.

::::

## System Prompt

~~~markdown {#system}
You are a weather agent that returns the temperature, weather conditions, and forecast for a given location.
~~~

# Tools

## Get Temperature

~~~python {#get_temperature .tool}
def temperature_fahrenheit(city: str) -> float:
    """Return the current temperature in Fahrenheit for the given city."""
    return 69.8
~~~

## Get Weather Conditions

~~~python {#get_conditions .tool}
def weather_conditions(city: str) -> str:
    """Return a description of the current weather conditions for the given city."""
    return "Sunny with clear skies"
~~~

## Get Forecast

~~~python {#get_forecast .tool}
def weather_forecast(city: str, days: int = 3) -> list[str]:
    """Return a simple forecast for the next given number of days."""
    return ["Sunny", "Partly Cloudy", "Light Rain"]
~~~
