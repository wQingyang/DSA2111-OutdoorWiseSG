
import json
import os
import re

from openai import OpenAI

from .models import ParsedRouteRequest


SYSTEM_PROMPT = """
You are the natural language route parser for OutdoorWise,
a running route recommendation application in Singapore.

Convert the user's request into one JSON object.

Required keys:
- location: string or null
- target_distance_km: number
- target_difficulty: integer from 1 to 5
- preferences: object containing:
  - prefer_green: boolean
  - prefer_quiet: boolean
  - avoid_steps: boolean

Difficulty:
1 = very easy
2 = comfortable/easy
3 = moderate
4 = challenging
5 = very challenging

Defaults:
distance = 5 km
difficulty = 3
prefer_green = true
prefer_quiet = true
avoid_steps = true

If a preference is explicitly rejected, set it to false.
Convert distances expressed in metres to kilometres.
Do not invent GPS coordinates.
Do not invent a location when none is provided.
Return JSON only, without markdown.
"""


def parse_route_request(user_text: str) -> ParsedRouteRequest:
    if not user_text.strip():
        raise ValueError("Route description cannot be empty.")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=30.0,
        max_retries=1,
    )

    response = client.chat.completions.create(
        model=os.getenv(
            "OPENROUTER_MODEL", "openrouter/free"
        ),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        temperature=0,
        max_tokens=1200,
    )

    if not response.choices:
        raise ValueError("LLM returned no choices.")
    content = response.choices[0].message.content

    if not content:
        raise ValueError("LLM returned an empty response.")

    # Remove optional Markdown code fences.
    content = content.strip()
    content = re.sub(
        r"^```(?:json)?\s*", "", content, flags=re.I
    )
    content = re.sub(r"\s*```$", "", content)

    data = json.loads(content)

    return ParsedRouteRequest.model_validate(data)
