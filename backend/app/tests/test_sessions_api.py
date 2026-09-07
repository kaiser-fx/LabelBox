from datetime import datetime, timezone

from app.db.models.scan import Scan
from app.db.models.violation import Violation


class TestSessionsAPI:
    def test_create_session_unauthorized(self, client):
        response = client.post(
            "/sessions",
            json={"store_name": "SuperMart", "location": "Connaught Place, New Delhi"},
        )
        assert response.status_code == 401

    def test_create_session_success(self, client, test_officer, auth_headers):
        payload = {
            "store_name": "Spencer's Retail Store #14",
            "location": "Saket District Centre, New Delhi",
        }
        response = client.post("/sessions", json=payload, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["store_name"] == payload["store_name"]
        assert data["location"] == payload["location"]
        assert data["officer_id"] == test_officer.id
        assert "id" in data
        assert "started_at" in data

    def test_create_session_empty_store_name(self, client, auth_headers):
        response = client.post(
            "/sessions",
            json={"store_name": "   ", "location": "Anywhere"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_get_session_by_id_success(self, client, auth_headers):
        # Create a session first
        create_res = client.post(
            "/sessions",
            json={"store_name": "Big Bazaar #2", "location": "Janakpuri"},
            headers=auth_headers,
        )
        assert create_res.status_code == 201
        session_id = create_res.json()["id"]

        # Fetch it
        get_res = client.get(f"/sessions/{session_id}", headers=auth_headers)
        assert get_res.status_code == 200
        data = get_res.json()
        assert data["id"] == session_id
        assert data["store_name"] == "Big Bazaar #2"
        assert data["location"] == "Janakpuri"

    def test_get_session_unauthorized(self, client):
        response = client.get("/sessions/some-session-id")
        assert response.status_code == 401

    def test_get_nonexistent_session(self, client, auth_headers):
        response = client.get("/sessions/nonexistent-session-id", headers=auth_headers)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_sessions_for_officer(self, client, auth_headers):
        # Create 2 sessions
        client.post(
            "/sessions",
            json={"store_name": "Store Alpha", "location": "North Delhi"},
            headers=auth_headers,
        )
        client.post(
            "/sessions",
            json={"store_name": "Store Beta", "location": "South Delhi"},
            headers=auth_headers,
        )

        # List them
        list_res = client.get("/sessions", headers=auth_headers)
        assert list_res.status_code == 200
        sessions = list_res.json()
        assert len(sessions) >= 2
        store_names = [s["store_name"] for s in sessions]
        assert "Store Alpha" in store_names
        assert "Store Beta" in store_names

    def test_session_report_aggregates_scan_status_and_violations(
        self, client, db_session, test_officer, auth_headers
    ):
        session_response = client.post(
            "/sessions",
            json={"store_name": "Report Store", "location": "Pune"},
            headers=auth_headers,
        )
        session_id = session_response.json()["id"]
        compliant_scan = Scan(
            session_id=session_id,
            captured_at=datetime.now(timezone.utc),
            status="completed",
        )
        noncompliant_scan = Scan(
            session_id=session_id,
            captured_at=datetime.now(timezone.utc),
            status="completed",
        )
        failed_scan = Scan(
            session_id=session_id,
            captured_at=datetime.now(timezone.utc),
            status="failed",
        )
        db_session.add_all([compliant_scan, noncompliant_scan, failed_scan])
        db_session.flush()
        db_session.add_all([
            Violation(
                scan_id=noncompliant_scan.id,
                rule_id="6_1_e",
                severity="major",
                citation="Rule 6(1)(e)",
                reason="MRP was not detected.",
            ),
            Violation(
                scan_id=noncompliant_scan.id,
                rule_id="6_1_a",
                severity="major",
                citation="Rule 6(1)(a)",
                reason="Net quantity was not detected.",
            ),
        ])
        db_session.commit()

        response = client.get(f"/sessions/{session_id}/report", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_scans"] == 3
        assert data["completed_scans"] == 2
        assert data["failed_scans"] == 1
        assert data["compliant_scans"] == 1
        assert data["scans_with_violations"] == 1
        assert data["total_violations"] == 2
        assert data["violations_by_rule"] == {"6_1_a": 1, "6_1_e": 1}
