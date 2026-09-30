"""The LLM-only ablation code paths can't hit the real API in CI; exercise them with the fake client."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

from app.pipeline import compliance  # noqa: E402


def test_full_llm_plan_maps_ids_to_catalog(make_engine, siis_rows):
    import ablations  # type: ignore[import-not-found]

    def plan(system, user):
        return {
            "goal": "Follow these steps to perform this Touch Lag Troubleshooting",
            "title": "Touch response lag",
            "score": 0.9,
            "actions": [
                {"actionName": "Turn Off Touch Sensitivity", "description": "It will turn off touch sensitivity",
                 "category": "auto", "stepGroups": [{"steps": ["Open Settings.", "Tap Display."], "deeplink_id": "DL-0125"}]},
                {"actionName": "Made Up", "description": "It will do something made up",
                 "category": "auto", "stepGroups": [{"steps": ["Tap Foo."], "deeplink_id": "DL-9999"}]},
            ],
        }

    eng, fake = make_engine({"FLPlan": plan})
    row = next(r for r in siis_rows if r["id"] == "row_21")
    resp = ablations.full_llm_plan(eng, row["original_query"], row["siis_response"])
    first = resp["contexts"][0]["actions"][0]["stepGroups"][0]["actionableDeeplink"]
    assert first["deeplink"] == eng.catalog.by_id["DL-0125"]["deeplink"]
    errs = compliance.violations(resp, eng.catalog.all_uris)
    assert any(e.startswith("catalog") for e in errs)  # the invented id is caught, which is the point of the ablation
    assert fake.calls == ["FLPlan"]
