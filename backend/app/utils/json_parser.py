import json
import re


def parse_json(text: str) -> dict:

    text = text.strip()

    # Remove ```json
    text = re.sub(
        r"^```json",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove starting ```
    text = re.sub(
        r"^```",
        "",
        text,
    )

    # Remove ending ```
    text = re.sub(
        r"```$",
        "",
        text,
    )

    return json.loads(text.strip())