def test_login_success():
    """Тест успешного входа и получения токена"""
    # Сначала регистрируем пользователя
    client.post("/auth/register", json={
        "username": "loginuser",
        "email": "login@example.com",
        "password": "loginpass"
    })
    
    # Пытаемся войти
    response = client.post("/auth/token",
        data={"username": "loginuser", "password": "loginpass"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_wrong_password():
    """Тест входа с неправильным паролем"""
    # Регистрируем пользователя
    client.post("/auth/register", json={
        "username": "wrongpassuser",
        "email": "wrongpass@example.com",
        "password": "correctpass"
    })
    
    # Пытаемся войти с неправильным паролем
    response = client.post("/auth/token",
        data={"username": "wrongpassuser", "password": "wrongpass"}
    )
    assert response.status_code == 401
    assert "detail" in response.json()
    assert "Incorrect username or password" in response.json()["detail"]
