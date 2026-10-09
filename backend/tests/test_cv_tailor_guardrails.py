import pytest

from app.agents.cv_tailor.agent import CVTailorError, enforce_base_facts
from app.schemas.cv import Education, ParsedCV, WorkExperience

BASE = ParsedCV(
    full_name="Rudy Botosso", email="r@x.it", phone="1", location="Milano",
    linkedin="https://linkedin.com/in/rudy",
    summary="Sviluppatore backend con Python e FastAPI.",
    skills=["Python", "FastAPI", "SQL"],
    work_experience=[
        WorkExperience(company="Acme", role="Backend Developer", start_date="2022", end_date=None,
                       description="Sviluppo API REST con Python e FastAPI su PostgreSQL.",
                       highlights=["Sviluppate API per oltre 15 aziende clienti",
                                   "Ridotto del 30% il tempo di risposta dei servizi",
                                   "Introdotta pipeline di test automatici con pytest",
                                   "Coordinato un team di 4 sviluppatori"]),
        WorkExperience(company="Beta", role="Junior Dev", start_date="2019", end_date="2022",
                       description="Manutenzione applicazioni interne."),
    ],
    education=[Education(institution="Uni Milano", degree="Laurea", field="Informatica", year="2019")],
    languages=["Italiano"], certifications=["AWS Cloud Practitioner"],
)


def _tailored(**over) -> ParsedCV:
    data = BASE.model_copy(deep=True)
    for k, v in over.items():
        setattr(data, k, v)
    return data


def test_identity_education_languages_come_from_base():
    out = enforce_base_facts(_tailored(full_name="Mario Rossi", email="evil@x.it", languages=["Klingon"],
                                       education=[Education(institution="MIT")]), BASE)
    assert out.full_name == "Rudy Botosso" and out.email == "r@x.it"
    assert out.languages == ["Italiano"] and out.education[0].institution == "Uni Milano"


def test_invented_company_dropped_and_dates_forced():
    exps = [
        WorkExperience(company="Acme", role="Backend Developer", start_date="1999", end_date="2000",
                       description="Sviluppo API REST con Python."),
        WorkExperience(company="Google", role="CTO", start_date="2020", description="Guida team."),
    ]
    out = enforce_base_facts(_tailored(work_experience=exps), BASE)
    assert [e.company for e in out.work_experience] == ["Acme", "Beta"]
    assert out.work_experience[0].start_date == "2022" and out.work_experience[0].end_date is None


def test_no_valid_experience_raises():
    with pytest.raises(CVTailorError):
        enforce_base_facts(_tailored(work_experience=[WorkExperience(company="Google", role="CTO")]), BASE)


def test_invented_skills_and_certs_filtered():
    out = enforce_base_facts(_tailored(skills=["python", "Kubernetes", "SQL"],
                                       certifications=["AWS Cloud Practitioner", "CISSP"]), BASE)
    assert out.skills == ["Python", "SQL"]
    assert out.certifications == ["AWS Cloud Practitioner"]


def test_description_from_llm_is_replaced_by_base_verbatim():
    exps = [WorkExperience(company="Acme", role="Backend Developer",
                           description="Sviluppo API con Kubernetes e Terraform in produzione.")]
    out = enforce_base_facts(_tailored(work_experience=exps), BASE)
    assert out.work_experience[0].description == BASE.work_experience[0].description


def test_empty_llm_description_means_empty():
    exps = [WorkExperience(company="Acme", role="Backend Developer", description="  ")]
    out = enforce_base_facts(_tailored(work_experience=exps), BASE)
    assert not out.work_experience[0].description


def test_invented_summary_replaced_by_base_verbatim():
    out = enforce_base_facts(_tailored(summary="Esperto di Kubernetes e Docker con 20 anni di esperienza."), BASE)
    assert out.summary == BASE.summary


def test_empty_summary_means_none():
    assert enforce_base_facts(_tailored(summary=""), BASE).summary is None
    assert enforce_base_facts(_tailored(summary=None), BASE).summary is None


def _acme(highlights, **kw) -> ParsedCV:
    return _tailored(work_experience=[WorkExperience(company="Acme", role="Backend Developer",
                                                     highlights=highlights, **kw)])


def _hl(out: ParsedCV) -> list[str]:
    return out.work_experience[0].highlights


def test_linkedin_forced_from_base():
    out = enforce_base_facts(_tailored(linkedin="https://evil.example/x"), BASE)
    assert out.linkedin == "https://linkedin.com/in/rudy"


def test_reworded_highlight_snaps_to_exact_base_highlight():
    out = enforce_base_facts(_acme(["Coordinato un team di 4 sviluppatori backend"]), BASE)
    assert _hl(out) == ["Coordinato un team di 4 sviluppatori"]


def test_highlight_with_invented_number_snaps_to_base_text():
    out = enforce_base_facts(_acme(["Sviluppate API per oltre 40 aziende clienti"]), BASE)
    assert _hl(out) == ["Sviluppate API per oltre 15 aziende clienti"]
    assert "40" not in str(out.work_experience)


def test_invented_highlight_dropped_and_order_and_dedup_kept():
    hl = ["Gestione completa del magazzino logistico internazionale",
          "Ridotto del 30% i tempi di risposta dei servizi",
          "Coordinato un team di 4 sviluppatori",
          "Ridotto del 30% il tempo di risposta dei servizi"]
    assert _hl(enforce_base_facts(_acme(hl), BASE)) == [
        "Ridotto del 30% il tempo di risposta dei servizi", "Coordinato un team di 4 sviluppatori"]


def test_fallback_to_first_three_base_highlights():
    out = enforce_base_facts(_acme(["Gestione magazzino robotizzato", "Usato Kubernetes ovunque"]), BASE)
    assert _hl(out) == BASE.work_experience[0].highlights[:3]


def test_no_fallback_when_base_has_no_highlights():
    exps = [WorkExperience(company="Beta", role="Junior Dev", highlights=["Manutenzione applicazioni con 77 team"])]
    out = enforce_base_facts(_tailored(work_experience=exps), BASE)
    assert out.work_experience[0].highlights == []


def test_highlights_of_unmatched_experience_not_kept():
    exps = [WorkExperience(company="Google", role="CTO", highlights=["Coordinato un team di 4 sviluppatori"]),
            WorkExperience(company="Acme", role="Backend Developer")]
    out = enforce_base_facts(_tailored(work_experience=exps), BASE)
    assert [e.company for e in out.work_experience] == ["Acme", "Beta"]
    assert "Google" not in str(out.work_experience)


def test_highlights_capped_at_six():
    base = BASE.model_copy(deep=True)
    base.work_experience[0].highlights = [f"Risultato numero {n} sviluppo applicazioni" for n in range(1, 9)]
    hl = [f"Risultato numero {n} sviluppo applicazioni" for n in range(1, 9)]
    out = enforce_base_facts(_acme(hl), base)
    assert _hl(out) == hl[:6]


def test_prompt_mentions_highlights_and_linkedin():
    from app.agents.cv_tailor.agent import _SYSTEM_PROMPT
    assert "highlights" in _SYSTEM_PROMPT and "linkedin" in _SYSTEM_PROMPT


# --- progetti personali ---
_P1 = "81-Flow: piattaforma multi-azienda sviluppata in Python (NiceGUI, PostgreSQL) per conformità 81/2008"
_P2 = "CareerOS: applicazione web in Python che con 4 agenti AI aiuta la ricerca del lavoro"
PBASE = BASE.model_copy(update={"projects": [_P1, _P2]})


def _ptail(projects=None, omit_key=False) -> ParsedCV:
    data = {"full_name": "Rudy Botosso", "work_experience": [
        {"company": "Acme", "role": "Backend Developer", "highlights": ["Sviluppate API per oltre 15 aziende clienti"]}]}
    if not omit_key:
        data["projects"] = projects or []
    return ParsedCV(**data)


def test_reworded_project_snaps_to_base_verbatim_in_llm_order():
    out = enforce_base_facts(_ptail(["CareerOS: applicazione web in Python con 7 agenti AI per il lavoro",
                                     "81-Flow: piattaforma multi-azienda in Python con NiceGUI e PostgreSQL"]), PBASE)
    assert out.projects == [_P2, _P1]


def test_invented_project_dropped():
    assert enforce_base_facts(_ptail(["Gestione magazzino con robot industriali autonomi"]), PBASE).projects == []


def test_unrelated_project_dropped_and_dedup_and_cap():
    out = enforce_base_facts(_ptail(["Gestione magazzino con robot industriali autonomi", _P1, _P1.upper(), _P2,
                                     _P2]), PBASE)
    assert out.projects == [_P1, _P2]
    three = PBASE.model_copy(update={"projects": [_P1, _P2, "Terzo: servizio Python con agenti AI e PostgreSQL"]})
    out = enforce_base_facts(_ptail(three.projects), three)
    assert len(out.projects) == 2


def test_empty_projects_key_means_omitted_missing_key_falls_back_to_first():
    assert enforce_base_facts(_ptail([]), PBASE).projects == []
    assert enforce_base_facts(_ptail(omit_key=True), PBASE).projects == [_P1]
    assert enforce_base_facts(_ptail(omit_key=True), BASE).projects == []


def test_base_projects_serialized_in_tailor_message():
    import asyncio
    from unittest.mock import AsyncMock, patch
    from app.agents.cv_tailor import agent
    mock = AsyncMock(return_value=PBASE.model_dump_json())
    with patch.object(agent, "chat", mock):
        out = asyncio.run(agent.tailor(PBASE, "annuncio python"))
    assert _P1 in mock.call_args.kwargs["messages"][1]["content"]
    assert out.projects == [_P1, _P2]


def test_prompt_mentions_projects():
    from app.agents.cv_tailor.agent import _SYSTEM_PROMPT
    assert '"projects"' in _SYSTEM_PROMPT and "personal project" in _SYSTEM_PROMPT.lower()


def test_prompt_is_verbatim_only():
    from app.agents.cv_tailor.agent import _SYSTEM_PROMPT
    assert "ONLY select, reorder and omit" in _SYSTEM_PROMPT and "EXACTLY, character for character" in _SYSTEM_PROMPT


# --- storico lavorativo mai perso ---
_OLD = WorkExperience(company="Robinson Srl", role="Analista Programmatore", start_date="1994", end_date="1998",
                      description="Sviluppo gestionale. " + "Dettaglio lungo. " * 20,
                      highlights=["Realizzato gestionale ordini"])
HBASE = BASE.model_copy(update={"work_experience": [*BASE.work_experience, _OLD]})


def test_omitted_base_experiences_readded_without_highlights_in_base_order():
    exps = [WorkExperience(company="Acme", role="Backend Developer", highlights=["Coordinato un team di 4 sviluppatori"])]
    out = enforce_base_facts(_tailored(work_experience=exps), HBASE)
    assert [e.company for e in out.work_experience] == ["Acme", "Beta", "Robinson Srl"]
    beta, old = out.work_experience[1], out.work_experience[2]
    assert beta.highlights == [] and beta.description == "Manutenzione applicazioni interne."
    assert (beta.start_date, beta.end_date) == ("2019", "2022")
    assert old.highlights == [] and old.description is None
    assert (old.start_date, old.end_date) == ("1994", "1998")


def test_llm_reordered_experiences_end_in_base_order():
    exps = [WorkExperience(company="Beta", role="Junior Dev"),
            WorkExperience(company="Acme", role="Backend Developer")]
    out = enforce_base_facts(_tailored(work_experience=exps), BASE)
    assert [e.company for e in out.work_experience] == ["Acme", "Beta"]


def test_at_least_one_valid_llm_experience_still_required():
    with pytest.raises(CVTailorError):
        enforce_base_facts(_tailored(work_experience=[]), BASE)


def test_prompt_requires_keeping_all_experiences():
    from app.agents.cv_tailor.agent import _SYSTEM_PROMPT
    assert "ALL work_experience" in _SYSTEM_PROMPT


# --- derivazione di description e summary dal base ---

def _beta_base() -> ParsedCV:
    base = BASE.model_copy(deep=True)
    base.work_experience[1] = WorkExperience(company="Beta", role="Junior Dev", start_date="2019", end_date="2022")
    return base


def test_description_empty_in_base_stays_empty_even_if_llm_invents():
    exps = [WorkExperience(company="Beta", role="Junior Dev",
                           description="Supporto alla gestione operativa dell'infrastruttura aziendale.")]
    out = enforce_base_facts(_tailored(work_experience=exps), _beta_base())
    beta = next(e for e in out.work_experience if e.company == "Beta")
    assert not beta.description


def test_skill_spelling_canonicalized_and_deduped():
    out = enforce_base_facts(_tailored(skills=["python", "PYTHON", "sql"]), BASE)
    assert out.skills == ["Python", "SQL"]
