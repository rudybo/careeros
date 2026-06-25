"""Unit tests for Cover Letter guardrails — no Ollama required."""
import pytest
from app.agents.cover_letter.agent import _apply_guardrails, CoverLetterError
from app.schemas.cv import ParsedCV, WorkExperience


def _make_cv(name: str = "Rudy Botosso") -> ParsedCV:
    return ParsedCV(
        full_name=name, email="rudy@test.com", phone=None, summary=None,
        skills=["Python"], languages=["Italian"],
        work_experience=[WorkExperience(company="Acme", role="Dev", start_date="2022", end_date=None, description=None)],
        education=[], certifications=[],
    )


VALID_LETTER = (
    "Gentile Responsabile Selezione,\n\n"
    "Mi candido con grande entusiasmo per il ruolo di Python Developer presso TechCorp, "
    "posizione che ho scoperto attraverso il vostro annuncio online e che corrisponde "
    "perfettamente al mio percorso professionale e alle mie ambizioni di crescita nel settore IT.\n\n"
    "Ho maturato oltre cinque anni di esperienza come sviluppatore backend, lavorando con "
    "FastAPI e Python in contesti aziendali complessi e ad alto carico. Durante la mia "
    "esperienza in Acme ho gestito progetti critici con team distribuiti internazionalmente, "
    "contribuendo alla progettazione di architetture microservizi scalabili e all'ottimizzazione "
    "delle performance delle API REST. La mia capacità di lavorare sia in autonomia sia in team "
    "agile mi ha permesso di consegnare soluzioni di qualità nei tempi previsti.\n\n"
    "Le mie competenze in Python avanzato, FastAPI e nella gestione di database relazionali si "
    "allineano perfettamente ai requisiti del ruolo. Sono inoltre esperto nella scrittura di "
    "test automatizzati e nella cultura DevOps, elementi che ritengo fondamentali per garantire "
    "la qualità del software in produzione. Porterei in TechCorp una mentalità orientata alla "
    "qualità e alla collaborazione continua con il business.\n\n"
    "Rimango a disposizione per un colloquio conoscitivo in qualsiasi momento si ritenga "
    "opportuno e sono disponibile anche a sessioni tecniche di approfondimento.\n\n"
    "Cordiali saluti,\nRudy Botosso"
)


def _make_result(full_text: str = VALID_LETTER, subject: str = "Candidatura per il ruolo di Python Developer - Rudy Botosso") -> dict:
    return {"subject": subject, "full_text": full_text}


# ─── minimum length ────────────────────────────────────────────────────────────

def test_rejects_too_short_letter():
    cv = _make_cv()
    with pytest.raises(CoverLetterError, match="troppo breve"):
        _apply_guardrails({"subject": "X", "full_text": "Ciao. Mi candido."}, cv, "TechCorp", "Dev")


def test_accepts_long_enough_letter():
    cv = _make_cv()
    result = _apply_guardrails(_make_result(), cv, "TechCorp", "Python Developer")
    assert "full_text" in result


# ─── name injection ────────────────────────────────────────────────────────────

def test_adds_name_if_missing():
    cv = _make_cv("Mario Rossi")
    letter_without_name = VALID_LETTER.replace("Rudy Botosso", "il candidato")
    result = _apply_guardrails(_make_result(full_text=letter_without_name), cv, "TechCorp", "Dev")
    assert "Mario Rossi" in result["full_text"]


def test_keeps_name_if_present():
    cv = _make_cv("Rudy Botosso")
    result = _apply_guardrails(_make_result(), cv, "TechCorp", "Python Developer")
    word_count = result["full_text"].lower().count("rudy botosso")
    assert word_count >= 1


# ─── subject fix ──────────────────────────────────────────────────────────────

def test_fixes_missing_role_in_subject():
    cv = _make_cv()
    result = _apply_guardrails(_make_result(subject="Candidatura generica"), cv, "TechCorp", "Senior Dev")
    assert "Senior Dev" in result["subject"]
    assert "Rudy Botosso" in result["subject"]


def test_keeps_correct_subject():
    cv = _make_cv()
    result = _apply_guardrails(_make_result(), cv, "TechCorp", "Python Developer")
    assert result["subject"] == "Candidatura per il ruolo di Python Developer - Rudy Botosso"


# ─── language fix ─────────────────────────────────────────────────────────────

def test_fixes_cursa_in_letter():
    cv = _make_cv()
    letter = VALID_LETTER + " Si consiglia di cursa un corso di formazione."
    result = _apply_guardrails(_make_result(full_text=letter), cv, "TechCorp", "Python Developer")
    assert "cursa" not in result["full_text"]
    assert "corso" in result["full_text"]
