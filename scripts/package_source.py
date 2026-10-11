"""Package reviewed source without environments, dependencies or secrets."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main() -> None:
    """Create a source archive and verify all entry CRCs."""
    root = Path(__file__).resolve().parents[1]
    archive = root.parent / "MiningIntel-source.zip"
    ignored = {
        ".git",
        ".venv",
        "node_modules",
        ".next",
        ".next-preview",
        ".next-upgrade",
        "__pycache__",
        ".ruff_cache",
        ".pytest_cache",
        "artifacts",
    }
    extensions = {
        ".py",
        ".ps1",
        ".toml",
        ".ini",
        ".mako",
        ".lock",
        ".ts",
        ".tsx",
        ".mjs",
        ".js",
        ".html",
        ".woff2",
        ".txt",
        ".json",
        ".css",
        ".md",
        ".yml",
        ".yaml",
        ".png",
        ".svg",
        ".sql",
        ".sh",
    }
    special = {".gitignore", ".dockerignore", ".env.example", "Dockerfile", ".gitkeep"}
    count = 0
    with ZipFile(archive, "w", ZIP_DEFLATED) as output:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if not path.is_file() or any(part in ignored for part in relative.parts):
                continue
            if path.name.startswith(".env") and path.name not in {
                ".env.example",
                ".env.production.example",
            }:
                continue
            if path.name == ".env.production.example":
                output.write(path, Path("miningintel") / relative)
                count += 1
                continue
            if path.name not in special and path.suffix not in extensions:
                continue
            output.write(path, Path("miningintel") / relative)
            count += 1
    with ZipFile(archive) as output:
        if output.testzip() is not None:
            raise RuntimeError("Archive CRC verification failed")
    print(f"Packaged {count} source files: {archive}")


if __name__ == "__main__":
    main()
