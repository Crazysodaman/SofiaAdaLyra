"""Canonical recognized forms for deterministic environment queries."""
import re


_USER_REPORTED_LOCAL_TIME_RE = re.compile(
    r"\b(?:it(?:'s|\s+is)|its)\s+"
    r"(\d{1,2})(?::(\d{2}))?\s*"
    r"(am|pm)\s+(?:for\s+me|my\s+time|locally)\b",
    re.IGNORECASE,
)

_TIME_FORMS = frozenset(
    {
        "what time is it",
        "what time is it right now",
        "what's the time",
        "what is the current time",
        "current time",
        "time",
    }
)

_DATE_FORMS = frozenset(
    {
        "what date is it",
        "what's the date",
        "what is today's date",
        "what day is it",
        "what day is it today",
    }
)

_WEATHER_FORMS = frozenset(
    {
        "what's the weather",
        "whats the weather",
        "what is the weather",
        "what's the weather like",
        "whats the weather like",
        "what is the weather like",
        "what's the weather right now",
        "whats the weather right now",
        "what is the weather right now",
        "what's the weather today",
        "whats the weather today",
        "what is the weather today",
        "how's the weather today",
        "how is the weather today",
        "today's weather",
        "todays weather",
        "weather today",
        "how's the weather",
        "hows the weather",
        "how is the weather",
        "weather",
        "current weather",
    }
)

_LOCATION_FORMS = frozenset(
    {
        "where am i",
        "what is my location",
        "what's my location",
        "what is my current location",
        "what's my current location",
        "do you know where i am",
    }
)

_SOFIA_LOCATION_FORMS = frozenset(
    {
        "where are you",
        "what is your location",
        "what's your location",
        "what is your current location",
        "what's your current location",
        "do you know where you are",
    }
)

_USER_TIMEZONE_FORMS = frozenset(
    {
        "what is my timezone",
        "what's my timezone",
        "what timezone am i in",
        "what time zone am i in",
    }
)

_CONTEXT_TIMEZONE_FORMS = frozenset(
    {
        "what timezone are you using",
        "what time zone are you using",
        "what timezone is configured",
        "what time zone is configured",
    }
)

_FORECAST_FORMS = frozenset(
    {
        "what's the forecast",
        "what is the forecast",
        "what's the weather forecast",
        "what is the weather forecast",
    }
)

_TOMORROW_WEATHER_FORMS = frozenset(
    {
        "what's tomorrow's weather",
        "what is tomorrow's weather",
        "whats tomorrows weather",
        "what's the weather tomorrow",
        "what is the weather tomorrow",
        "how's the weather tomorrow",
        "how is the weather tomorrow",
        "what will the weather be tomorrow",
        "what's the forecast tomorrow",
        "what is the forecast tomorrow",
        "tomorrow's weather",
        "tomorrows weather",
        "weather tomorrow",
    }
)

_WEEKLY_FORECAST_FORMS = frozenset(
    {
        "what's the weekly forecast",
        "what is the weekly forecast",
        "weekly forecast",
        "weekly weather",
        "what's the weather this week",
        "what is the weather this week",
        "how's the weather this week",
        "how is the weather this week",
        "weather this week",
        "forecast this week",
        "what's this week's weather",
        "what is this week's weather",
        "this week's weather",
        "whats this weeks weather",
        "this weeks weather",
        "what's the 7 day forecast",
        "what is the 7 day forecast",
        "7 day forecast",
        "seven day forecast",
    }
)

_SUNRISE_FORMS = frozenset(
    {
        "when is sunrise",
        "what time is sunrise",
        "when does the sun rise",
    }
)

_SUNSET_FORMS = frozenset(
    {
        "when is sunset",
        "what time is sunset",
        "when does the sun set",
    }
)

_INDOOR_FORMS = frozenset(
    {
        "what's the indoor temperature",
        "what is the indoor temperature",
        "what's the temperature inside",
        "what is the temperature inside",
        "what's the indoor humidity",
        "what is the indoor humidity",
    }
)

_SEASON_FORMS = frozenset(
    {
        "what season is it",
        "what's the season",
        "what season are we in",
        "what is the current season",
    }
)

_DAYLIGHT_FORMS = frozenset(
    {
        "is it day",
        "is it daytime",
        "is it night",
        "is it nighttime",
        "is it dark outside",
        "is it light outside",
    }
)

_GENERIC_SOURCE_FOLLOWUP_FORMS = frozenset(
    {
        "where you pull the info",
        "where did you pull that info from",
        "where did you get that info",
        "where did you get the info",
        "where is that info from",
        "what source did you use",
        "what source are you using",
    }
)

_GENERIC_INDOOR_FOLLOWUP_FORMS = frozenset(
    {
        "what about inside",
        "how about inside",
        "and inside",
        "what's it like inside",
        "what is it like inside",
        "what about indoors",
        "how about indoors",
    }
)

_TEMPERATURE_UNIT_FORMS = frozenset(
    {
        "use f not c",
        "use f instead of c",
        "f not c",
        "fahrenheit not celsius",
        "use fahrenheit",
        "use fahrenheit not celsius",
        "use fahrenheit instead of celsius",
        "show fahrenheit",
        "show temperatures in fahrenheit",
        "why are you using celsius",
        "don't use celsius",
        "do not use celsius",
    }
)

_CONTEXT_SOURCE_FORMS = frozenset(
    {
        "explain your current environment context sources",
        "what are your current environment context sources",
        "what are your environment context sources",
        "what environment sources are you using",
        "where does your environment context come from",
        "where do you get your weather info",
        "where do you get the weather info",
        "where did you get that weather info",
        "where did you pull that weather info from",
        "what is your weather source",
        "what's your weather source",
        "what weather source are you using",
        "which weather source are you using",
        "what weather provider are you using",
        "which weather provider are you using",
        "where are you getting the weather from",
        "where are you getting weather from",
        "weather source",
    }
)
