import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AtsKeywordItem
from app.repositories.roadmap_repository import _fingerprint


def _present(keyword: str, text: str) -> bool:
    """True se la keyword compare nel testo (confine di parola, case-insensitive)."""
    if not keyword or not text:
        return False
    return re.search(r"\b" + re.escape(keyword.lower()) + r"\b", text.lower()) is not None


# Varianti/sinonimi → forma canonica (chiavi e valori normalizzati, minuscolo).
# Serve a riconoscere keyword equivalenti in lingue diverse o riformulate.
_SYNONYMS = {
    "intelligenza artificiale": "artificial intelligence",
    "ia": "artificial intelligence",
    "ai": "artificial intelligence",
    "apprendimento automatico": "machine learning",
    "sicurezza informatica": "cybersecurity",
    "cyber security": "cybersecurity",
    "tecnologie cloud": "cloud computing",
    "cloud": "cloud computing",
    "gestione di progetti it": "project management",
    "gestione progetti it": "project management",
    "gestione di progetti": "project management",
    "gestione progetti": "project management",
    "gestione del rischio": "risk management",
    "architettura di sistema": "system architecture",
    "internet delle cose": "iot",
    "internet of things": "iot",
    "scienza dei dati": "data science",
    "analisi dei dati": "data analytics",
}

# Parole "qualificatore": non cambiano il concetto base, vanno rimosse prima
# del confronto (es. "cybersecurity avanzata"/"cybersecurity framework" →
# "cybersecurity").
_QUALIFIERS = {
    "avanzata", "avanzato", "avanzate", "avanzati",
    "framework", "methodology", "metodologia", "metodologie",
    "base", "fondamentali", "fondamenti", "approfondita", "approfondito",
}


def _normalize(text: str) -> str:
    norm = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", norm).strip()


def _canonical(keyword: str) -> str:
    """Chiave canonica per riconoscere keyword equivalenti anche se in lingue
    diverse o con qualificatori. Es: 'Cybersecurity Avanzata' e 'cybersecurity
    framework' → 'cybersecurity'; 'intelligenza artificiale' e 'artificial
    intelligence' → 'artificial intelligence'; 'agile' e 'agile methodology' →
    'agile'."""
    norm = _SYNONYMS.get(_normalize(keyword), _normalize(keyword))
    tokens = [t for t in norm.split() if t not in _QUALIFIERS]
    norm = " ".join(tokens)
    return _SYNONYMS.get(norm, norm)


class AtsKeywordRepository:
    """Lista keyword ATS a livello di CARRIERA (unica, non per singolo CV).
    Il cv_id sui record indica solo da quale CV è emersa la keyword."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> list[AtsKeywordItem]:
        result = await self._session.execute(
            select(AtsKeywordItem).order_by(AtsKeywordItem.created_at.asc())
        )
        return list(result.scalars().all())

    async def set_status(self, item_id: int, status: str) -> AtsKeywordItem | None:
        item = await self._session.get(AtsKeywordItem, item_id)
        if item is None:
            return None
        item.status = status
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def mark_present_as_added(self, cv_text: str) -> int:
        """Segna come 'added' (con data) le keyword 'todo'/'gap' ora presenti nel CV.
        È l'auto-rilevamento: ad ogni nuovo CV, ciò che hai inserito risulta fatto."""
        items = await self.get_all()
        marked = 0
        for it in items:
            if it.status in ("todo", "gap") and _present(it.keyword, cv_text):
                it.status = "added"
                marked += 1
        if marked:
            await self._session.commit()
        return marked

    async def merge_keywords(self, cv_id: int, keywords: list[dict], cv_text: str = "") -> int:
        """Aggiunge come 'todo' solo le keyword nuove: non già in lista (per fingerprint)
        e non già presenti nel CV. Ritorna quante ne ha aggiunte."""
        existing = await self.get_all()
        seen = {it.fingerprint for it in existing}
        added = 0
        for kw in keywords:
            keyword = (kw.get("keyword") or "").strip()
            if not keyword:
                continue
            fp = _fingerprint(keyword)
            if fp in seen or _present(keyword, cv_text):
                continue
            seen.add(fp)
            self._session.add(AtsKeywordItem(
                cv_id=cv_id,
                keyword=keyword,
                reason=kw.get("reason"),
                status="todo",
                fingerprint=fp,
            ))
            added += 1
        if added:
            await self._session.commit()
        return added

    async def replace_todos(self, cv_id: int, keywords: list[dict], cv_text: str = "") -> int:
        """Sostituisce le keyword 'todo' con quelle dell'ultima analisi. Mantiene
        'added'/'ignored'/'gap' (storico). Dedup per chiave CANONICA (gestisce
        coppie IT/EN, qualificatori e radici comuni) e scarta le keyword la cui
        forma canonica è già presente nel CV o già gestita. Ritorna i nuovi todo."""
        existing = await self.get_all()
        kept_canon: set[str] = set()
        for it in existing:
            if it.status in ("added", "ignored", "gap"):
                kept_canon.add(_canonical(it.keyword))
            else:
                await self._session.delete(it)

        seen = set(kept_canon)
        added = 0
        for kw in keywords:
            keyword = (kw.get("keyword") or "").strip()
            if not keyword:
                continue
            canon = _canonical(keyword)
            if not canon or canon in seen:
                continue
            if _present(canon, cv_text) or _present(keyword, cv_text):
                continue
            seen.add(canon)
            self._session.add(AtsKeywordItem(
                cv_id=cv_id,
                keyword=keyword,
                reason=kw.get("reason"),
                status="todo",
                fingerprint=canon,
            ))
            added += 1
        await self._session.commit()
        return added

    async def get_handled(self) -> list[str]:
        """Keyword aggiunte/ignorate/segnate come gap — da non riproporre a Minerva."""
        items = await self.get_all()
        return [it.keyword for it in items if it.status in ("added", "ignored", "gap")]
