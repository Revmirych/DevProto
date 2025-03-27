def test_get_students_by_faculty_no_students():
    """Тест получения студентов факультета без студентов"""
    # Регистрируем и логиним пользователя
    client.post("/auth/register", json={
        "username": "facultyuser",
        "email": "faculty@example.com",
        "password": "facultypass"
    })
    login_response = client.post("/auth/token",
        data={"username": "facultyuser", "password": "facultypass"}
    )
    token = login_response.json()["access_token"]
    
    # Запрашиваем несуществующий факультет
    response = client.get("/students/faculty/NONEXISTENT",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    assert response.json() == []

def test_get_students_by_faculty_with_students():
    """Тест получения студентов факультета со студентами"""
    # Регистрируем и логиним пользователя
    client.post("/auth/register", json={
        "username": "facultyuser2",
        "email": "faculty2@example.com",
        "password": "facultypass2"
    })
    login_response = client.post("/auth/token",
        data={"username": "facultyuser2", "password": "facultypass2"}
    )
    token = login_response.json()["access_token"]
    
    # Сначала добавляем тестовых студентов
    client.post("/students/",
        json={
            "surname": "Тестов",
            "name": "Студент",
            "faculty": "ТЕСТФАК",
            "subject": "Тестология",
            "score": 100
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Запрашиваем студентов факультета
    response = client.get("/students/faculty/ТЕСТФАК",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    assert len(response.json()) > 0
    assert all(s["faculty"] == "ТЕСТФАК" for s in response.json())
