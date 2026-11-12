"""Storage tests: persistence, old data, and the sample slices."""

import json

from app.services.storage import Storage
from app.tests.conftest import SAMPLES_DIR, png_bytes


def test_data_survives_a_restart(tmp_path):
    first = Storage(tmp_path / "data", tmp_path / "uploads")
    patient = first.create_patient("p1", "Ada", "Lovelace", "1970-01-02")
    first.create_case("c1", "slice.png", patient.id)
    first.save_image("c1", png_bytes(), ".png")
    first.save_notes("c1", "notes")

    second = Storage(tmp_path / "data", tmp_path / "uploads")
    assert second.get_patient("p1") == patient
    assert second.get_case("c1").patient_id == "p1"
    assert second.get_notes("c1") == "notes"
    assert second.image_path("c1").read_bytes() == png_bytes()


def test_results_in_the_old_format_are_dropped(tmp_path):
    storage = Storage(tmp_path / "data", tmp_path / "uploads")
    case = storage.create_case("c1", "slice.png")
    storage.cases["c1"] = case.model_copy(update={"status": "analyzed"})
    storage._save()
    old = {"c1": {"case_id": "c1", "nodules": [], "summary": "Analysis complete"}}
    (tmp_path / "data" / "results.json").write_text(json.dumps(old))

    reloaded = Storage(tmp_path / "data", tmp_path / "uploads")
    assert reloaded.get_analysis_result("c1") is None
    assert reloaded.get_case("c1").status == "pending"


def test_seeding_adds_the_samples_with_their_reads(tmp_path):
    storage = Storage(tmp_path / "data", tmp_path / "uploads", SAMPLES_DIR, seed=True)
    manifest = json.loads((SAMPLES_DIR / "samples.json").read_text())
    assert len(storage.get_all_patients()) == len(manifest["patients"])
    cases = storage.get_all_cases()
    assert len(cases) == len(manifest["cases"])
    # The last sample in the manifest is the newest, at the top of the worklist.
    assert cases[0].id == manifest["cases"][-1]["id"]
    for case in cases:
        assert case.status == "analyzed"
        assert case.dataset_label
        assert storage.image_path(case.id).exists()
        assert storage.get_analysis_result(case.id).cancer_probability == case.cancer_probability

    # Seeding happens once: a restart keeps what is there.
    storage.delete_case(cases[0].id)
    again = Storage(tmp_path / "data", tmp_path / "uploads", SAMPLES_DIR, seed=True)
    assert len(again.get_all_cases()) == len(manifest["cases"]) - 1
