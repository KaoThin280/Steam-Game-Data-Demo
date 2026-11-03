"""Container probe: HTTP 200 with degraded dependencies is not healthy."""
import json
import sys
from urllib.request import urlopen


def check_health(url: str) -> bool:
    try:
        with urlopen(url, timeout=4) as response:
            return response.status == 200 and json.load(response).get("status") == "healthy"
    except (OSError, ValueError, AttributeError):
        return False


if __name__ == "__main__":
    sys.exit(0 if len(sys.argv) == 2 and check_health(sys.argv[1]) else 1)
