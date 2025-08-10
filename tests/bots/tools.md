---
title: Weather Tool Bot
subtitle: Simple Conversational AI for Weather Queries
abstract: A minimal test suite for a conversational AI bot that provides the current temperature, weather conditions, and forecasts for requested locations.
---

# System Prompt

~~~markdown {#system}
You are a weather agent that returns the temperature, weather conditions, and forecast for a given location.
~~~


Topics
======

| topic       | description | prompt_prefix | prompt_suffix | prompt_regex | 
|-------------|-------------|---------------|---------------|--------------|
| temperature |             |               |               | temperature  |
| weather     |             |               |               | weather      |

# Tools

## Get Temperature

~~~python {#get_temperature .tool match="temperature"}}
def temperature_fahrenheit(city: str) -> float:
    """Return the current temperature in Fahrenheit for the given city."""
    return 69.8
~~~

## Get Weather Conditions

~~~python {#get_conditions .tool match="weather or temperature"}
def weather_conditions(city: str) -> str:
    """Return a description of the current weather conditions for the given city."""
    return "Sunny with clear skies"
~~~

## Get Forecast

~~~python {#get_forecast .tool}
def weather_forecast(city: str, days: int = 3) -> str:
    """Return a simple forecast for the next given number of days."""
    return "Sunny"
~~~

~~~markdown {#version_test .unittest}


# What’s the temperature like in Berlin?
> .+"temperature_fahrenheit".+69[.]8.+

# What’s the weather like in Berlin?
> ^(?!.*"temperature_fahrenheit").*$

# Wie ist dr forecast in Berlin?
> .+"weather_forecast".+Sunny.+

~~~

# test

