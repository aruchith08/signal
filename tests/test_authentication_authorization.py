"""
Comprehensive Test Suite for Authentication, Role Authorization, and IDOR Prevention
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.database import Base, get_db
from apps.api.main import app
from apps.api.models.user import User, UserProfile
from apps.api.core.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from shared.utils import parse_iso_datetime


class TestAuthenticationAndAuthorization(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async def override_get_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.transport = ASGITransport(app=app)

        # Seed 3 distinct users: Alice (regular), Bob (regular), Carol (reviewer), Dan (admin)
        async with self.session_factory() as session:
            self.user_alice = User(
                email="alice@test.dev",
                username="alice",
                full_name="Alice Student",
                hashed_password=hash_password("Password123!"),
                role="user",
                is_active=True,
                is_superuser=False,
            )
            self.user_bob = User(
                email="bob@test.dev",
                username="bob",
                full_name="Bob Developer",
                hashed_password=hash_password("Password123!"),
                role="user",
                is_active=True,
                is_superuser=False,
            )
            self.user_carol = User(
                email="carol@test.dev",
                username="carol",
                full_name="Carol Reviewer",
                hashed_password=hash_password("Password123!"),
                role="reviewer",
                is_active=True,
                is_superuser=False,
            )
            self.user_dan = User(
                email="dan@test.dev",
                username="dan",
                full_name="Dan Admin",
                hashed_password=hash_password("Password123!"),
                role="admin",
                is_active=True,
                is_superuser=True,
            )
            session.add_all([self.user_alice, self.user_bob, self.user_carol, self.user_dan])
            await session.flush()

            # Add profiles
            session.add(UserProfile(user_id=self.user_alice.id, degree="B.Tech Alice"))
            session.add(UserProfile(user_id=self.user_bob.id, degree="B.Tech Bob"))
            await session.commit()

            self.alice_id = self.user_alice.id
            self.bob_id = self.user_bob.id
            self.carol_id = self.user_carol.id
            self.dan_id = self.user_dan.id

        # Generate tokens
        self.alice_token = create_access_token({"sub": self.alice_id, "username": "alice", "role": "user"})
        self.bob_token = create_access_token({"sub": self.bob_id, "username": "bob", "role": "user"})
        self.carol_token = create_access_token({"sub": self.carol_id, "username": "carol", "role": "reviewer"})
        self.dan_token = create_access_token({"sub": self.dan_id, "username": "dan", "role": "admin"})

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.engine.dispose()

    # --- Unit tests for Password & Token utilities ---

    def test_password_hashing_and_verification(self):
        plain = "superSecretPassword123"
        pw_hash = hash_password(plain)
        self.assertNotEqual(plain, pw_hash)
        self.assertTrue(verify_password(plain, pw_hash))
        self.assertFalse(verify_password("wrongPassword", pw_hash))
        self.assertFalse(verify_password("", pw_hash))
        self.assertFalse(verify_password(plain, ""))

    def test_jwt_token_creation_and_expiration(self):
        # Valid token
        token = create_access_token({"sub": "test-user-1", "role": "user"}, expires_delta=timedelta(minutes=10))
        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "test-user-1")
        self.assertEqual(payload["role"], "user")

        # Expired token
        expired_token = create_access_token({"sub": "test-user-1"}, expires_delta=timedelta(seconds=-10))
        with self.assertRaises(Exception) as ctx:
            decode_access_token(expired_token)
        self.assertIn("expired", str(ctx.exception).lower())

    # --- Integration tests for Auth Router ---

    async def test_register_new_user_success(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "newuser@test.dev",
                    "username": "newuser",
                    "password": "ValidPassword999",
                    "full_name": "New User",
                    "role": "user",
                },
            )
            self.assertEqual(resp.status_code, 201)
            data = resp.json()
            self.assertIn("access_token", data)
            self.assertEqual(data["token_type"], "bearer")
            self.assertEqual(data["user"]["email"], "newuser@test.dev")
            self.assertEqual(data["user"]["username"], "newuser")
            self.assertEqual(data["user"]["role"], "user")

    async def test_register_duplicate_email_fails(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "alice@test.dev",
                    "username": "different_alice",
                    "password": "ValidPassword999",
                },
            )
            self.assertEqual(resp.status_code, 400)
            self.assertIn("already exists", resp.json()["detail"].lower())

    async def test_login_success_with_json_and_form(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # Login via JSON
            resp = await client.post(
                "/api/v1/auth/login",
                json={"username": "alice", "password": "Password123!"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("access_token", data)
            self.assertEqual(data["user"]["username"], "alice")

            # Login via email identifier
            resp_email = await client.post(
                "/api/v1/auth/login",
                json={"username": "alice@test.dev", "password": "Password123!"},
            )
            self.assertEqual(resp_email.status_code, 200)

            # Login via OAuth2 Form Data
            resp_form = await client.post(
                "/api/v1/auth/login",
                data={"username": "alice", "password": "Password123!"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            self.assertEqual(resp_form.status_code, 200)

    async def test_login_invalid_password_fails(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"username": "alice", "password": "WrongPassword!"},
            )
            self.assertEqual(resp.status_code, 401)
            self.assertIn("invalid username or password", resp.json()["detail"].lower())

    async def test_login_nonexistent_user_fails(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"username": "ghost_user", "password": "Password123!"},
            )
            self.assertEqual(resp.status_code, 401)

    async def test_auth_me_endpoint(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # Valid Bearer token
            resp = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {self.alice_token}"},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["username"], "alice")

            # Unauthenticated
            resp_unauth = await client.get("/api/v1/auth/me")
            self.assertEqual(resp_unauth.status_code, 401)

            # Invalid Bearer token
            resp_bad = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer bad.token.value"},
            )
            self.assertEqual(resp_bad.status_code, 401)

    # --- IDOR & Isolation Tests ---

    async def test_idor_cross_user_profile_access_forbidden(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # Alice attempts to access Bob's profile using Alice's token -> 403 Forbidden
            resp = await client.get(
                f"/api/v1/users/{self.bob_id}/profile",
                headers={"Authorization": f"Bearer {self.alice_token}"},
            )
            self.assertEqual(resp.status_code, 403)
            self.assertIn("cannot access", resp.json()["detail"].lower())

            # Alice accesses her own profile -> 200 OK
            resp_own = await client.get(
                f"/api/v1/users/{self.alice_id}/profile",
                headers={"Authorization": f"Bearer {self.alice_token}"},
            )
            self.assertEqual(resp_own.status_code, 200)
            self.assertEqual(resp_own.json()["degree"], "B.Tech Alice")

            # Admin Dan accesses Bob's profile -> 200 OK (admin override allowed)
            resp_admin = await client.get(
                f"/api/v1/users/{self.bob_id}/profile",
                headers={"Authorization": f"Bearer {self.dan_token}"},
            )
            self.assertEqual(resp_admin.status_code, 200)
            self.assertEqual(resp_admin.json()["degree"], "B.Tech Bob")

    async def test_idor_cross_user_preferences_mutation_forbidden(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # Alice attempts to mutate Bob's notification preferences -> 403 Forbidden
            resp = await client.put(
                f"/api/v1/users/{self.bob_id}/preferences",
                json={"min_relevance_score": 95},
                headers={"Authorization": f"Bearer {self.alice_token}"},
            )
            self.assertEqual(resp.status_code, 403)

    async def test_idor_cross_user_saved_opportunities_forbidden(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # Alice attempts to view Bob's saved opportunities -> 403 Forbidden
            resp = await client.get(
                f"/api/v1/users/{self.bob_id}/saved",
                headers={"Authorization": f"Bearer {self.alice_token}"},
            )
            self.assertEqual(resp.status_code, 403)

    # --- Role-Based Access Control Tests ---

    async def test_reviewer_queue_role_authorization(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # Regular user Alice attempts to access reviewer queue -> 403 Forbidden
            resp_alice = await client.get(
                "/api/v1/verification/review-queue",
                headers={"Authorization": f"Bearer {self.alice_token}"},
            )
            self.assertEqual(resp_alice.status_code, 403)
            self.assertIn("reviewer or admin role required", resp_alice.json()["detail"].lower())

            # Reviewer Carol accesses reviewer queue -> 200 OK
            resp_carol = await client.get(
                "/api/v1/verification/review-queue",
                headers={"Authorization": f"Bearer {self.carol_token}"},
            )
            self.assertEqual(resp_carol.status_code, 200)

            # Admin Dan accesses reviewer queue -> 200 OK
            resp_dan = await client.get(
                "/api/v1/verification/review-queue",
                headers={"Authorization": f"Bearer {self.dan_token}"},
            )
            self.assertEqual(resp_dan.status_code, 200)

    # --- Date Parsing & Connector Completeness Tests ---

    def test_robust_date_parsing_formats(self):
        # 1. ISO string with Z
        dt1 = parse_iso_datetime("2026-09-26T15:30:00Z")
        self.assertIsNotNone(dt1)
        self.assertEqual(dt1.year, 2026)
        self.assertEqual(dt1.month, 9)
        self.assertEqual(dt1.tzinfo, timezone.utc)

        # 2. ISO string with offset
        dt2 = parse_iso_datetime("2026-09-26T21:00:00+05:30")
        self.assertIsNotNone(dt2)

        # 3. Epoch milliseconds timestamp
        dt3 = parse_iso_datetime(1780000000000)
        self.assertIsNotNone(dt3)
        self.assertEqual(dt3.tzinfo, timezone.utc)

        # 4. Standard date string
        dt4 = parse_iso_datetime("2026-10-15")
        self.assertIsNotNone(dt4)
        self.assertEqual(dt4.day, 15)

        # 5. Invalid input returns None
        self.assertIsNone(parse_iso_datetime(None))
        self.assertIsNone(parse_iso_datetime("not-a-date"))
        self.assertIsNone(parse_iso_datetime(""))
