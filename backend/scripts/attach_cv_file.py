"""Allega il file originale (PDF/DOCX) a un CV gia' presente, verificando che sia lo stesso documento.

Uso (da backend/):  python -m scripts.attach_cv_file --cv-id 1 --file PATH [--force]
"""
import argparse
import asyncio
import difflib
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.cv_repository import CVRepository
from app.services.cv_extractor import extract_text

_MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_COMPARE_CHARS = 3000


def _similarity(a: str, b: str) -> float:
    a = " ".join(a.split())[:_COMPARE_CHARS]
    b = " ".join(b.split())[:_COMPARE_CHARS]
    if not a or not b:
        return 0.0
    m = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if m.quick_ratio() < 0.5:
        return m.quick_ratio()
    return m.ratio()


async def attach(
    cv_id: int, pdf_path: str, session: AsyncSession, min_similarity: float = 0.85, force: bool = False
) -> dict:
    repo = CVRepository(session)
    cv = await repo.get_by_id(cv_id)
    if cv is None:
        raise ValueError(f"CV {cv_id} non trovato")
    path = Path(pdf_path)
    content = path.read_bytes()
    ratio = _similarity(extract_text(path.name, content), cv.raw_text)
    if ratio < min_similarity and not force:
        return {"attached": False, "similarity": ratio, "size": 0}
    mime = _MIME_BY_EXT.get(path.suffix.lower(), "application/octet-stream")
    await repo.attach_file(cv_id, content, mime)
    return {"attached": True, "similarity": ratio, "size": len(content)}


async def _amain(args: argparse.Namespace) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        res = await attach(args.cv_id, args.file, session, force=args.force)
    if res["attached"]:
        print(f"Attached to CV {args.cv_id}: {res['size']} bytes (similarity {res['similarity']:.2f})")
    else:
        print(f"REFUSED: similarity {res['similarity']:.2f} < 0.85. Use --force to attach anyway.")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cv-id", type=int, required=True)
    ap.add_argument("--file", required=True, help="Percorso del CV (PDF/DOCX)")
    ap.add_argument("--force", action="store_true", help="Allega anche se il testo non corrisponde")
    asyncio.run(_amain(ap.parse_args()))


if __name__ == "__main__":
    main()
