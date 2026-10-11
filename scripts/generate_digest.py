"""Build a current-period grounded brief without dispatching outbound email."""

import argparse
import asyncio
import json

from app.services.digest_service import generate_digest

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kind", choices=["daily", "weekly", "monthly"], default="weekly"
    )
    args = parser.parse_args()
    print(json.dumps(asyncio.run(generate_digest(args.kind)), ensure_ascii=False))
