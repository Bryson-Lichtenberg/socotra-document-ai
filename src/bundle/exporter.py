"""Package a run folder as a ZIP: template, Socotra-shaped artifacts, validation, and assumptions."""

import io
import zipfile
from pathlib import Path

REQUIRED = ("ASSUMPTIONS.md", "template", "socotra", "validation")


def missing_artifacts(run_dir: Path) -> list[str]:
    return [name for name in REQUIRED if not (run_dir / name).exists()]


def export_zip(run_dir: Path, destination: Path | None = None) -> bytes:
    """Zip every file under run_dir. Returns the bytes and also writes destination when given."""
    missing = missing_artifacts(run_dir)
    if missing:
        raise FileNotFoundError(f"Run folder is missing {missing}; the export must include assumptions and artifacts.")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(run_dir.rglob("*")):
            if path.is_file() and path.suffix != ".zip":
                archive.write(path, Path(run_dir.name) / path.relative_to(run_dir))
    data = buffer.getvalue()
    if destination is not None:
        destination.write_bytes(data)
    return data
