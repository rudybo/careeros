"""Lo storico stati deve registrare ogni transizione, anche quelle scritte
dagli agenti (update_optimization → "ready") e non solo update_status."""
import json

from app.repositories.application_repository import ApplicationRepository


async def _make_app(db_session):
    repo = ApplicationRepository(db_session)
    record = await repo.create(
        cv_id=1,
        company="ACME",
        role="Dev",
        job_description="jd",
    )
    return repo, record


async def test_update_optimization_registra_ready_nello_storico(db_session):
    repo, record = await _make_app(db_session)
    await repo.update_status(record.id, "analyzing")

    updated = await repo.update_optimization(record.id, {"match_score": 42})

    assert updated.status == "ready"
    hist = json.loads(updated.status_history)
    assert [h["status"] for h in hist] == ["analyzing", "ready"]
    assert hist[-1]["at"]


async def test_update_status_non_duplica_stato_identico(db_session):
    repo, record = await _make_app(db_session)
    await repo.update_status(record.id, "applied")
    updated = await repo.update_status(record.id, "applied")

    hist = json.loads(updated.status_history)
    assert [h["status"] for h in hist] == ["applied"]
