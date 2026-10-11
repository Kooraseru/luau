"""Local switch artifacts use the repository's existing ignored build directory."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "build" / "switch"
BYTECODE = ARTIFACTS / "bytecode"
GENERATED = ARTIFACTS / "generated"
