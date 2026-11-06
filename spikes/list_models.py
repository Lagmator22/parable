"""Lists the model IDs your GEMINI_API_KEY can use, and checks if a local Ollama server answers.

Run:  cd engine && uv run python ../spikes/list_models.py
Gemini flash and Gemma 4 models are marked with <<<. The key is never printed.
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from parable.config import get_settings  # noqa: E402

MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def interesting(model_id: str) -> bool:
    return ("gemini" in model_id and "flash" in model_id) or "gemma-4" in model_id


def list_google_models(key: str) -> None:
    models, token = [], ""
    while True:  # the list comes in pages
        r = httpx.get(MODELS_URL, headers={"x-goog-api-key": key}, params={"pageSize": 200, "pageToken": token},
                      timeout=30)
        if r.status_code != 200:
            print(f"Google answered HTTP {r.status_code}: the key may be wrong or not allowed.")
            return
        data = r.json()
        models += [m["name"].removeprefix("models/") for m in data.get("models", [])]
        token = data.get("nextPageToken", "")
        if not token:
            break
    for model_id in sorted(models):
        print(f"  {model_id}" + ("   <<<" if interesting(model_id) else ""))
    print(f"{len(models)} models. Put your pick in the repo-root .env as GEMINI_MODEL= or GEMMA_MODEL=")


def check_local(base_url: str) -> None:
    try:
        r = httpx.get(base_url.rstrip("/") + "/models", timeout=3)
        ids = [m["id"] for m in r.json().get("data", [])]
        print(f"Local server at {base_url} answers. Models: {', '.join(ids) or 'none installed'}")
    except Exception:
        print(f"No local server answering at {base_url} (start Ollama, or ignore this).")


def main() -> None:
    s = get_settings()
    if not s.gemini_api_key:
        print("No Gemini key yet. Paste it into the repo-root .env on the line: GEMINI_API_KEY=")
    else:
        print("Models this key can use:")
        list_google_models(s.gemini_api_key)
    check_local(s.local_llm_base_url)


if __name__ == "__main__":
    main()
