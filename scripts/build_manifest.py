"""L2Rush: genera manifest.json de forma reproducible para el launcher v4.

Uso: python scripts/build_manifest.py --source files --output _site/manifest.json --version SEASON1-XXXX
Este archivo se ejecuta en GitHub Actions. No requiere dependencias externas.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MAX_FILE_SIZE = 20 * 1024 ** 3
RESERVED = {"con", "prn", "aux", "nul"} | {f"com{x}" for x in range(1, 10)} | {f"lpt{x}" for x in range(1, 10)}
PROTECTED_ROOT = {
    "config.json", "l2rushlauncher.exe", "main.py", "launcher", "resources",
    "tools", "tests", ".l2rush", "logs", "configurar_launcher_github.bat",
    "configurar_launcher_github.ps1",
}


def validate_relative_path(relative: str) -> None:
    if not relative or len(relative) > 1024 or "\\" in relative or relative.startswith("/") or "//" in relative:
        raise ValueError(f"Ruta no permitida: {relative!r}")
    if any(ord(c) < 32 for c in relative):
        raise ValueError(f"Ruta con caracteres de control: {relative!r}")
    parts = relative.split("/")
    for segment in parts:
        if (segment in ("", ".", "..") or segment.endswith((" ", "."))
                or any(char in segment for char in (":", "?", "#"))):
            raise ValueError(f"Ruta no permitida: {relative!r}")
        if segment.split(".", 1)[0].casefold() in RESERVED:
            raise ValueError(f"Nombre reservado de Windows: {relative!r}")
    if parts[0].casefold() in PROTECTED_ROOT:
        raise ValueError(f"Archivo protegido del launcher: {relative!r}")


def create_manifest(source: Path, version: str) -> dict:
    if not source.is_dir() or source.is_symlink():
        raise ValueError(f"La carpeta de parches no existe o es un enlace simbólico: {source}")
    source = source.resolve()
    entries: list[dict] = []
    seen: set[str] = set()
    for p in sorted(source.rglob("*")):
        if p.is_symlink():
            raise ValueError(f"Enlaces simbólicos prohibidos: {p}")
        if p.is_dir():
            continue
        if not p.is_file():
            raise ValueError(f"Entrada no admitida: {p}")
        relative = p.relative_to(source).as_posix()
        validate_relative_path(relative)
        folded = relative.casefold()
        if folded in seen:
            raise ValueError(f"Nombre duplicado/incompatible con Windows: {relative}")
        seen.add(folded)
        size = p.stat().st_size
        if size > MAX_FILE_SIZE:
            raise ValueError(f"Archivo demasiado grande: {relative}")
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        entries.append({"path": relative, "size": size, "sha256": h.hexdigest()})
        print(f"[{len(entries)}] {relative} - {size} bytes")
    result = {"schema": 1, "version": version, "base_path": "files/", "files": entries}
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--version", default="SEASON1-1.0.0")
    args = ap.parse_args()
    manifest = create_manifest(args.source, args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generado: {args.output} con {len(manifest['files'])} archivos")


if __name__ == "__main__":
    main()
