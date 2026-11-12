"""API tests: patients, uploads, analysis, notes, reports, and images."""

from app.tests.conftest import png_bytes


def create_patient(client, first="Ada", last="Lovelace"):
    response = client.post(
        "/api/patients",
        json={"first_name": first, "last_name": last, "date_of_birth": "1970-01-02"},
    )
    assert response.status_code == 201
    return response.json()


def upload(client, patient_id=None, content=None, name="slice.png", content_type="image/png"):
    data = {"patient_id": patient_id} if patient_id else {}
    return client.post(
        "/api/upload",
        files={"scan": (name, content or png_bytes(), content_type)},
        data=data,
    )


def test_patients_are_listed_by_last_name(client):
    create_patient(client, "Grace", "Hopper")
    create_patient(client, "Alan", "Turing")
    create_patient(client, "Ada", "Lovelace")
    names = [p["last_name"] for p in client.get("/api/patients").json()]
    assert names == ["Hopper", "Lovelace", "Turing"]


def test_a_patient_needs_a_name(client):
    response = client.post(
        "/api/patients", json={"first_name": "", "last_name": "X", "date_of_birth": "1970-01-01"}
    )
    assert response.status_code == 422


def test_upload_creates_an_analyzed_case(client, classifier):
    patient = create_patient(client)
    response = upload(client, patient["id"], name="My Scan (1).png")
    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] == patient["id"]
    assert body["filename"] == "My Scan _1.png"
    assert classifier.calls == 1

    detail = client.get(f"/api/cases/{body['case_id']}").json()
    assert detail["case"]["status"] == "analyzed"
    assert detail["patient"]["id"] == patient["id"]
    result = detail["analysis_result"]
    assert result["flagged"] is True
    assert result["subtype"] == "large_cell_carcinoma"
    assert result["model"]["runtime"] == "Fake runtime (server)"
    assert detail["case"]["cancer_probability"] == result["cancer_probability"]

    cases = client.get(f"/api/patients/{patient['id']}").json()["cases"]
    assert [c["id"] for c in cases] == [body["case_id"]]


def test_upload_rejects_other_files(client):
    assert (
        upload(
            client, content=b"%PDF-1.4", name="x.pdf", content_type="application/pdf"
        ).status_code
        == 400
    )
    assert upload(client, content=b"not a png", name="x.png").status_code == 400
    assert upload(client, patient_id="patient-missing").status_code == 404
    assert client.get("/api/cases").json() == []


def test_upload_without_the_model_leaves_the_case_pending(client, classifier):
    classifier.available = False
    case_id = upload(client).json()["case_id"]
    assert client.get(f"/api/cases/{case_id}").json()["case"]["status"] == "pending"
    response = client.post(f"/api/analyze/{case_id}")
    assert response.status_code == 503
    assert "not available" in response.json()["detail"]


def test_analyze_stores_the_result(client, classifier):
    classifier.available = False
    case_id = upload(client).json()["case_id"]
    classifier.available = True
    response = client.post(f"/api/analyze/{case_id}")
    assert response.status_code == 200
    assert response.json()["case_id"] == case_id
    assert client.get(f"/api/cases/{case_id}").json()["case"]["status"] == "analyzed"
    assert client.post("/api/analyze/missing").status_code == 404


def test_the_image_is_served_as_uploaded(client):
    content = png_bytes(32, 32, 200)
    case_id = upload(client, content=content).json()["case_id"]
    response = client.get(f"/api/cases/{case_id}/image")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == content
    assert client.get("/api/cases/missing/image").status_code == 404


def test_replacing_the_scan_resets_the_read_and_keeps_the_notes(client):
    case_id = upload(client).json()["case_id"]
    assert (
        client.put(f"/api/cases/{case_id}/notes", json={"notes": "Compare with prior"}).status_code
        == 200
    )
    response = client.put(
        f"/api/cases/{case_id}/replace-scan",
        files={"scan": ("new.jpg", png_bytes(40, 40), "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "new.jpg"
    detail = client.get(f"/api/cases/{case_id}").json()
    assert detail["case"]["status"] == "pending"
    assert detail["case"]["cancer_probability"] is None
    assert detail["analysis_result"] is None
    assert detail["notes"] == "Compare with prior"


def test_deleting_a_case_removes_its_image(client, storage):
    case_id = upload(client).json()["case_id"]
    image = storage.image_path(case_id)
    assert image.exists()
    assert client.delete(f"/api/cases/{case_id}").status_code == 200
    assert not image.exists()
    assert client.get(f"/api/cases/{case_id}").status_code == 404
    assert client.delete(f"/api/cases/{case_id}").status_code == 404


def test_a_patient_with_cases_cannot_be_deleted(client):
    patient = create_patient(client)
    case_id = upload(client, patient["id"]).json()["case_id"]
    assert client.delete(f"/api/patients/{patient['id']}").status_code == 400
    client.delete(f"/api/cases/{case_id}")
    assert client.delete(f"/api/patients/{patient['id']}").status_code == 200
    assert client.get(f"/api/patients/{patient['id']}").status_code == 404


def test_cases_can_be_assigned_to_a_patient(client):
    first = upload(client).json()["case_id"]
    second = upload(client).json()["case_id"]
    patient = create_patient(client)
    for case_id in (first, second):
        response = client.post(f"/api/cases/{case_id}/assign/{patient['id']}")
        assert response.status_code == 200
        assert response.json()["patient_id"] == patient["id"]
    assert len(client.get(f"/api/patients/{patient['id']}").json()["cases"]) == 2
    assert client.post(f"/api/cases/{first}/assign/patient-missing").status_code == 404


def test_the_report_carries_the_read_and_the_notes(client):
    patient = create_patient(client)
    case_id = upload(client, patient["id"]).json()["case_id"]
    response = client.post(f"/api/report/{case_id}", json={"notes": "Follow up in 3 months."})
    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        f'attachment; filename="lungscan_report_{case_id[:8]}.txt"'
    )
    report = response.text
    assert "Patient:      Ada Lovelace, born 1970-01-02" in report
    assert "the model reads this slice as cancer" in report
    assert "Large cell carcinoma" in report
    assert "Follow up in 3 months." in report
    assert "not a medical device" in report
    assert client.get(f"/api/cases/{case_id}").json()["notes"] == "Follow up in 3 months."
