"""Record reproducible Lighthouse measurements and enforce the mobile target."""

import argparse
import json
from pathlib import Path
from statistics import median


def measurement(path: Path) -> dict:
    """Keep scores, standard simulation settings and numeric paint metrics."""
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("runtimeError"):
        raise RuntimeError(result["runtimeError"])
    return {
        "lighthouse_version": result["lighthouseVersion"],
        "fetch_time": result["fetchTime"],
        "url": result["finalDisplayedUrl"],
        "scores": {
            key: round(value["score"] * 100)
            for key, value in result["categories"].items()
        },
        "metrics": {
            name: result["audits"][name]["numericValue"]
            for name in (
                "first-contentful-paint",
                "largest-contentful-paint",
                "total-blocking-time",
                "cumulative-layout-shift",
            )
        },
        "settings": {
            key: result["configSettings"][key]
            for key in (
                "formFactor",
                "throttlingMethod",
                "throttling",
                "screenEmulation",
            )
        },
    }


def main() -> None:
    """Summarize every supplied run; never omit a failed measurement."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mobile", nargs="+", type=Path, required=True)
    parser.add_argument("--desktop", type=Path, required=True)
    args = parser.parse_args()
    mobile = [measurement(path) for path in args.mobile]
    output = {
        "environment": "Windows / Edge / Next.js production standalone / real API",
        "mobile_runs": mobile,
        "mobile_median_lcp_ms": median(
            item["metrics"]["largest-contentful-paint"] for item in mobile
        ),
        "desktop": measurement(args.desktop),
        "baseline_phase4_mobile": {"performance": 92, "lcp_ms": 3316.89},
        "limits": "Local simulated measurements; real devices and networks vary.",
    }
    for item in mobile:
        assert item["settings"]["throttlingMethod"] == "simulate"
        assert item["settings"]["formFactor"] == "mobile"
        assert item["scores"]["performance"] > 90
        assert item["metrics"]["largest-contentful-paint"] < 2000
    target = Path(__file__).resolve().parents[1] / "docs/phase5-performance.json"
    target.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Mobile LCP median: {output['mobile_median_lcp_ms']:.2f} ms; target passed")


if __name__ == "__main__":
    main()
