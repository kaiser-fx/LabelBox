class TestAuthAPI:
    def test_login_success(self, client, test_officer):
        response = client.post(
            "/auth/login",
            json={
                "email": test_officer.email,
                "password": "testpass123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["officer_id"] == test_officer.id
        assert data["name"] == test_officer.name
        assert data["email"] == test_officer.email
        assert data["jurisdiction"] == test_officer.jurisdiction

    def test_login_case_insensitive_email(self, client, test_officer):
        # Email should match regardless of case
        response = client.post(
            "/auth/login",
            json={
                "email": test_officer.email.upper(),
                "password": "testpass123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["officer_id"] == test_officer.id

    def test_login_invalid_email(self, client):
        response = client.post(
            "/auth/login",
            json={
                "email": "nobody@nic.in",
                "password": "somepassword",
            },
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_non_nic_domain_rejected(self, client):
        """Only @nic.in domain emails are accepted."""
        response = client.post(
            "/auth/login",
            json={
                "email": "hacker@gmail.com",
                "password": "somepassword",
            },
        )
        # Pydantic validator rejects non-nic.in domains with 422
        assert response.status_code == 422

    def test_login_wrong_password(self, client, test_officer):
        response = client.post(
            "/auth/login",
            json={
                "email": test_officer.email,
                "password": "completely_wrong_password",
            },
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_get_current_officer_success(self, client, test_officer, auth_headers):
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_officer.id
        assert data["email"] == test_officer.email
        assert data["name"] == test_officer.name

    def test_get_current_officer_unauthorized(self, client):
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_get_current_officer_invalid_token(self, client):
        response = client.get(
            "/auth/me", headers={"Authorization": "Bearer invalid.token.value"}
        )
        assert response.status_code == 401
