from fastapi.testclient import TestClient
from main import app
import pytest

client = TestClient(app)

def test_register_new_user():
    """Тест успешной регистрации нового пользователя"""
    response = client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass"
    })
    assert response.status_code == 200
    assert "username" in response.json()
    assert response.json()["username"] == "testuser"

def test_register_existing_user():
    """Тест попытки регистрации существующего пользователя"""
    # Сначала регистрируем пользователя
    client.post("/auth/register", json={
        "username": "existinguser",
        "email": "existing@example.com",
        "password": "existingpass"
    })
    
    # Пытаемся зарегистрировать того же пользователя снова
    response = client.post("/auth/register", json={
        "username": "existinguser",
        "email": "existing@example.com",
        "password": "existingpass"
    })
    assert response.status_code == 400
    assert "detail" in response.json()
    assert "already registered" in response.json()["detail"]
