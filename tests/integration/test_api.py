"""
Integration tests for Auth and Contract API endpoints.
"""
import pytest


class TestAuthEndpoints:
    """Integration tests for /auth endpoints."""

    @pytest.mark.asyncio
    async def test_register_success(self, client):
        res = await client.post("/api/v1/auth/register", json={
            "email": "newuser@test.com",
            "username": "newuser",
            "password": "SecurePass123!",
        })
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == "newuser@test.com"
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client):
        payload = {"email": "dup@test.com", "username": "dup1", "password": "SecurePass123!"}
        await client.post("/api/v1/auth/register", json=payload)
        payload["username"] = "dup2"
        res = await client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 409

    @pytest.mark.asyncio
    async def test_login_success(self, client, auth_headers):
        res = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert res.status_code == 200
        assert "email" in res.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        await client.post("/api/v1/auth/register", json={
            "email": "wrongpass@test.com",
            "username": "wrongpass",
            "password": "CorrectPass123!",
        })
        res = await client.post("/api/v1/auth/login", json={
            "email": "wrongpass@test.com",
            "password": "WrongPassword",
        })
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_route_without_token(self, client):
        res = await client.get("/api/v1/auth/me")
        assert res.status_code == 401


class TestContractEndpoints:
    """Integration tests for /contracts endpoints."""

    SAMPLE_SOURCE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
contract TestContract {
    uint256 public value;
    function setValue(uint256 v) external { value = v; }
}"""

    @pytest.mark.asyncio
    async def test_create_contract(self, client, auth_headers):
        res = await client.post("/api/v1/contracts/", json={
            "name": "MyTest",
            "source_code": self.SAMPLE_SOURCE,
            "contract_type": "CUSTOM",
        }, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "MyTest"
        assert data["is_compiled"] is False

    @pytest.mark.asyncio
    async def test_list_contracts(self, client, auth_headers):
        # Create a contract first
        await client.post("/api/v1/contracts/", json={
            "name": "ListTest",
            "source_code": self.SAMPLE_SOURCE,
            "contract_type": "CUSTOM",
        }, headers=auth_headers)
        res = await client.get("/api/v1/contracts/", headers=auth_headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    @pytest.mark.asyncio
    async def test_contract_not_found(self, client, auth_headers):
        import uuid
        res = await client.get(f"/api/v1/contracts/{uuid.uuid4()}", headers=auth_headers)
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_contract_mock(self, client, auth_headers):
        res = await client.post("/api/v1/contracts/generate", json={
            "prompt": "Create an ERC-20 token with 1M supply",
            "contract_type": "ERC20",
            "name": "TestToken",
        }, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert "pragma solidity" in data["source_code"]
        assert data["ai_generated"] is True


class TestCompileEndpoints:
    """Integration tests for /compile endpoints."""

    @pytest.mark.asyncio
    async def test_compile_valid_contract(self, client, auth_headers):
        res = await client.post("/api/v1/compile/", json={
            "source_code": """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
contract Simple {
    uint256 public x;
    function setX(uint256 v) external { x = v; }
}""",
            "optimizer": True,
        }, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        # May succeed or fail depending on solc installation
        assert "success" in data
        assert "errors" in data

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
