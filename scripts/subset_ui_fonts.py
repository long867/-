"""Generate compact local Noto Sans UI subsets; prose uses system fallbacks."""

import re
from pathlib import Path
from shutil import copyfile

from fontTools import subset
from fontTools.merge import Merger
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


def main() -> None:
    """Bundle cached font subsets without bloating the render-blocking stylesheet."""
    root = Path(__file__).resolve().parents[1] / "frontend"
    package = root / "node_modules/@fontsource-variable/noto-sans-sc"
    texts = "".join(
        p.read_text(encoding="utf-8-sig")
        for folder in ["app", "components", "hooks"]
        for p in (root / folder).rglob("*.tsx")
    )
    needed = {ord(c) for c in texts if "\u3000" <= c <= "\uffef"}
    target = root / "public/fonts"
    target.mkdir(exist_ok=True)
    parts = []
    covered: set[int] = set()
    temporary = root.parent / "artifacts/font-subsets"
    temporary.mkdir(exist_ok=True)
    for block in package.joinpath("index.css").read_text().split("@font-face"):
        match = re.search(r"src: url\(\./(files/[^)]+)\)", block)
        if not match:
            continue
        font = TTFont(package / match[1])
        points = needed.intersection(font.getBestCmap())
        if not points:
            font.close()
            continue
        font = instantiateVariableFont(font, {"wght": 400}, inplace=True)
        options = subset.Options()
        options.flavor = "woff2"
        options.desubroutinize = True
        sub = subset.Subsetter(options=options)
        sub.populate(unicodes=points)
        sub.subset(font)
        name = Path(match[1]).name.replace("noto-sans-sc", "miningintel-sc")
        part = temporary / name.replace(".woff2", ".ttf")
        font.flavor = None
        font.save(part)
        font.close()
        parts.append(str(part))
        covered.update(points)
    merged = Merger().merge(parts)
    merged.flavor = "woff2"
    output = target / "miningintel-sc-ui.woff2"
    merged.save(output)
    display = subset.Subsetter(options=subset.Options())
    display_points = {ord(c) for c in "看见资源的流向，看清世界的动向。"}
    display.populate(unicodes=display_points)
    display.subset(merged)
    merged.flavor = "woff2"
    merged.save(target / "miningintel-display.woff2")
    merged.close()
    ranges = ",".join(f"U+{x:X}" for x in sorted(covered))
    css = (
        "@font-face{font-family:'MiningIntel Display';font-style:normal;"
        "font-weight:400;font-display:optional;"
        "src:url('/fonts/miningintel-display.woff2') format('woff2');}"
        "@font-face{font-family:'Noto Sans SC Variable';font-style:normal;"
        "font-weight:400;font-display:optional;"
        f"src:url('/fonts/{output.name}') format('woff2');unicode-range:{ranges};}}"
    )
    root.joinpath("app/fonts.css").write_text(css, encoding="utf-8")
    inter = root / "node_modules/@fontsource-variable/inter"
    latin_css = ""
    for weight in (400, 700):
        latin = TTFont(inter / "files/inter-latin-wght-normal.woff2")
        latin = instantiateVariableFont(latin, {"wght": weight}, inplace=True)
        latin_subset = subset.Subsetter(options=subset.Options())
        latin_subset.populate(
            unicodes=list(range(32, 127))
            + [0xA0, 0xA9, 0xB7, 0xD7, 0x2013, 0x2014, 0x2026, 0x2191, 0x2193, 0x2212]
        )
        latin_subset.subset(latin)
        latin.flavor = "woff2"
        destination = target / (
            "inter-latin.woff2" if weight == 400 else "inter-latin-bold.woff2"
        )
        latin.save(destination)
        latin.close()
        latin_css += (
            "@font-face{font-family:'Inter Variable';font-style:normal;"
            f"font-weight:{weight};font-display:optional;"
            f"src:url('/fonts/{destination.name}') format('woff2');"
            "unicode-range:U+0-FF,U+2000-206F,U+2191,U+2193,U+2212;}\n"
        )
    copyfile(inter / "LICENSE", target / "INTER-LICENSE.txt")
    css = latin_css + css
    root.joinpath("app/fonts.css").write_text(css, encoding="utf-8")
    target.joinpath("LICENSE.txt").write_text(
        package.joinpath("LICENSE").read_text(), encoding="utf-8"
    )
    for old in target.glob("miningintel-sc-*-wght-normal.woff2"):
        old.resolve().relative_to(target.resolve())
        old.unlink()
    print(
        f"Generated one UI font for {len(covered)} characters: "
        f"{output.stat().st_size} bytes"
    )


if __name__ == "__main__":
    main()
