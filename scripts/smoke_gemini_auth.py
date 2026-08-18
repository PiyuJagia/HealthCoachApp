"""Live Gemini auth smoke test (Phase E3.0). Not part of the offline test suite."""

from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv
from google import genai

MODEL = "gemini-3.6-flash"
PROMPT = "Respond with exactly: ADK_SETUP_OK"


def main() -> int:
    load_dotenv()
    if not os.getenv("GOOGLE_API_KEY", "").strip():
        print("FAIL: GOOGLE_API_KEY is not set in the environment.")
        return 1

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    started = time.perf_counter()
    try:
        response = client.models.generate_content(model=MODEL, contents=PROMPT)
    except Exception as exc:  # noqa: BLE001 — smoke test must surface full auth errors
        print(f"FAIL: Gemini request failed for model={MODEL}")
        print(repr(exc))
        return 1

    latency_ms = round((time.perf_counter() - started) * 1000)
    text = (response.text or "").strip()
    success = text == "ADK_SETUP_OK" or "ADK_SETUP_OK" in text
    print(f"model={MODEL}")
    print(f"success={'yes' if success else 'no'}")
    print(f"response={text!r}")
    print(f"latency_ms={latency_ms}")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
