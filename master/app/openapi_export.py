import json
import sys

from .main import create_app

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    with open(out, "w") as f:
        json.dump(create_app().openapi(), f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
