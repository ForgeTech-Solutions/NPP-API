"""Shared test fixtures and configuration."""
import pytest
import pytest_asyncio
import os
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.core.security import get_password_hash
from app.auth.models import User
from app.medicaments.models import Medicament  # noqa: F401 — must be imported so Base.metadata knows about it
from app.models.import_log import ImportLog  # noqa: F401

# Use file-based SQLite for tests (in-memory + aiosqlite doesn't share across connections)
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test.db")
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    """Provide test database session."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create tables before each test, drop after."""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """Provide a test database session."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession):
    """Create and return an admin user."""
    user = User(
        email="admin@test.com",
        hashed_password=get_password_hash("AdminTest123!"),
        role="ADMIN",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def lecteur_user(db_session: AsyncSession):
    """Create and return a lecteur user."""
    user = User(
        email="lecteur@test.com",
        hashed_password=get_password_hash("Lecteur123!"),
        role="LECTEUR",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client with DI overrides."""
    from app.main import app
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, admin_user):
    """Get admin JWT token."""
    response = await client.post("/auth/login", data={
        "username": "admin@test.com",
        "password": "AdminTest123!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def lecteur_token(client: AsyncClient, lecteur_user):
    """Get lecteur JWT token."""
    response = await client.post("/auth/login", data={
        "username": "lecteur@test.com",
        "password": "Lecteur123!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


def auth_header(token: str) -> dict:
    """Build authorization header."""
    return {"Authorization": f"Bearer {token}"}
