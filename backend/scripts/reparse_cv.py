"""Ri-parsa un CV da PDF/DOCX e aggiorna la riga CV (raw_text + parsed_data).

Uso (da backend/):  python -m scripts.reparse_cv --pdf PATH [--cv-id 1] [--linkedin URL] [--dry-run]
Non avvia nessuna analisi.
"""
import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.cv_repository import CVRepository
from app.schemas.cv import ParsedCV
from app.services.cv_extractor import extract_text
from app.services.ollama_service import parse_cv_with_ollama


def _build_summary(cv: ParsedCV) -> tuple[str, list[str], int]:
    lines = [
        f"Name: {cv.full_name}",
        f"LinkedIn: {cv.linkedin}",
        f"Skills: {len(cv.skills)}",
        f"Experiences: {len(cv.work_experience)}",
    ]
    warnings: list[str] = []
    total = 0
    for i, e in enumerate(cv.work_experience, 1):
        n = len(e.highlights)
        total += n
        lines.append(f"  {i}. {e.role} | {e.company} | {e.start_date}-{e.end_date} | {n} highlights")
        if not e.role or not e.company:
            warnings.append(f"WARNING: experience #{i} has empty role or company")
        if n == 0:
            warnings.append(f"WARNING: experience #{i} ({e.role} | {e.company}) has zero highlights")
    lines.append(f"Total highlights: {total}")
    lines.extend(warnings)
    return "\n".join(lines), warnings, total


async def reparse(
    pdf_path: str, cv_id: int, linkedin: str | None, dry_run: bool, session: AsyncSession
) -> dict:
    path = Path(pdf_path)
    raw_text = extract_text(path.name, path.read_bytes())
    parsed = await parse_cv_with_ollama(raw_text)
    cv = ParsedCV(**parsed)
    if not cv.linkedin and linkedin:
        cv.linkedin = linkedin
    data = cv.model_dump()
    summary, warnings, total = _build_summary(cv)

    saved = False
    if not dry_run:
        repo = CVRepository(session)
        if await repo.update_raw_text(cv_id, raw_text) is None:
            raise ValueError(f"CV {cv_id} non trovato")
        await repo.update_parsed_data(cv_id, data)  # imposta status 'parsed'
        saved = True
    return {"parsed": data, "summary": summary, "warnings": warnings,
            "total_highlights": total, "saved": saved}


async def _amain(args: argparse.Namespace) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        res = await reparse(args.pdf, args.cv_id, args.linkedin, args.dry_run, session)
    print(res["summary"])
    print("DRY RUN: nothing saved" if not res["saved"] else f"Saved to CV {args.cv_id}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", required=True, help="Percorso del CV (PDF/DOCX)")
    ap.add_argument("--cv-id", type=int, default=1)
    ap.add_argument("--linkedin", help="URL LinkedIn: usato SOLO come fallback se il parsing non lo trova")
    ap.add_argument("--dry-run", action="store_true", help="Stampa senza salvare")
    asyncio.run(_amain(ap.parse_args()))


if __name__ == "__main__":
    main()
