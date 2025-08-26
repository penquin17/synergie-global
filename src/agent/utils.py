import json
from typing import Any


def parse_json_strict(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        # attempt to extract JSON block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                return None
        return None
