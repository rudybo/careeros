import pytest

from app.agents.cv_tailor.agent import CVTailorError, enforce_base_facts
from app.schemas.cv import Education, ParsedCV, WorkExperience

BASE = ParsedCV(
    full_name="Rudy Botosso", email="r@x.it", phone="1", location="Milano",
    summary="Sviluppatore backend con Python e FastAPI.",
    skills=["Python", "FastAPI", "SQL"],
    work_experience=[
        WorkExperience(company="Acme", role="Backend Developer", start_date="2022", end_date=None,
                       description="Sviluppo API REST con Python e FastAPI su PostgreSQL."),
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
    assert [e.company for e in out.work_experience] == ["Acme"]
    assert out.work_experience[0].start_date == "2022" and out.work_experience[0].end_date is None


def test_no_valid_experience_raises():
    with pytest.raises(CVTailorError):
        enforce_base_facts(_tailored(work_experience=[WorkExperience(company="Google", role="CTO")]), BASE)


def test_invented_skills_and_certs_filtered():
    out = enforce_base_facts(_tailored(skills=["python", "Kubernetes", "SQL"],
                                       certifications=["AWS Cloud Practitioner", "CISSP"]), BASE)
    assert out.skills == ["python", "SQL"]
    assert out.certifications == ["AWS Cloud Practitioner"]


def test_description_with_invented_tech_falls_back_to_base():
    exps = [WorkExperience(company="Acme", role="Backend Developer",
                           description="Sviluppo API con Kubernetes e Terraform in produzione.")]
    out = enforce_base_facts(_tailored(work_experience=exps), BASE)
    assert out.work_experience[0].description == BASE.work_experience[0].description


def test_keyword_rewrite_without_new_tech_is_kept():
    exps = [WorkExperience(company="Acme", role="Backend Developer",
                           description="Progettazione di API REST scalabili con Python, FastAPI e PostgreSQL.")]
    out = enforce_base_facts(_tailored(work_experience=exps), BASE)
    assert out.work_experience[0].description.startswith("Progettazione di API REST")


def test_summary_with_invented_tech_falls_back():
    out = enforce_base_facts(_tailored(summary="Esperto di Kubernetes e Docker."), BASE)
    assert out.summary == BASE.summary


def _js_base() -> ParsedCV:
    return ParsedCV(
        full_name="A B", skills=["JavaScript"],
        work_experience=[WorkExperience(company="Acme", role="Dev", description="Sviluppo frontend con JavaScript.")],
    )


def test_tech_token_is_matched_whole_not_substring():
    base = _js_base()
    exps = [WorkExperience(company="Acme", role="Dev", description="Sviluppo backend con Java in produzione.")]
    out = enforce_base_facts(ParsedCV(full_name="A B", work_experience=exps), base)
    assert out.work_experience[0].description == "Sviluppo frontend con JavaScript."


def test_description_with_only_base_tokens_is_kept():
    base = _js_base()
    exps = [WorkExperience(company="Acme", role="Dev", description="Sviluppo frontend con javascript moderno.")]
    out = enforce_base_facts(ParsedCV(full_name="A B", work_experience=exps), base)
    assert out.work_experience[0].description == "Sviluppo frontend con javascript moderno."
