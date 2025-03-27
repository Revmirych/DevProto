def test_get_students_unauthorized():
    """Тест доступа без авторизации"""
    response = client.get("/students/")
    assert response.status_code == 401
    assert "detail" in response.json()
    assert "Not authenticated" in response.json()["detail"]

def test_get_students_authorized():
    """Тест получения списка студентов с авторизацией"""
    # Регистрируем и логиним пользователя
    client.post("/auth/register", json={
        "username": "studentuser",
        "email": "student@example.com",
        "password": "studentpass"
    })
    login_response = client.post("/auth/token",
        data={"username": "studentuser", "password": "studentpass"}
    )
    token = login_response.json()["access_token"]
    
    # Получаем список студентов с токеном
    response = client.get("/students/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
