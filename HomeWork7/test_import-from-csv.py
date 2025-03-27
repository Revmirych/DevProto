import os
import tempfile

def test_import_csv_success():
    """Тест успешного импорта из CSV"""
    # Создаем временный CSV файл
    csv_content = """Фамилия,Имя,Факультет,Курс,Оценка
Иванов,Иван,ФТФ,Математика,90
Петров,Петр,ФПМИ,Физика,85"""
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
        tmp.write(csv_content)
        tmp_path = tmp.name
    
    # Регистрируем и логиним пользователя
    client.post("/auth/register", json={
        "username": "csvuser",
        "email": "csv@example.com",
        "password": "csvpass"
    })
    login_response = client.post("/auth/token",
        data={"username": "csvuser", "password": "csvpass"}
    )
    token = login_response.json()["access_token"]
    
    # Отправляем запрос на импорт
    response = client.post("/students/import-from-csv",
        json={"file_path": tmp_path},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Удаляем временный файл
    os.unlink(tmp_path)
    
    assert response.status_code == 200
    assert "message" in response.json()
    assert "started in background" in response.json()["message"]

def test_import_csv_file_not_found():
    """Тест импорта с несуществующим файлом"""
    # Регистрируем и логиним пользователя
    client.post("/auth/register", json={
        "username": "csvuser2",
        "email": "csv2@example.com",
        "password": "csvpass2"
    })
    login_response = client.post("/auth/token",
        data={"username": "csvuser2", "password": "csvpass2"}
    )
    token = login_response.json()["access_token"]
    
    # Отправляем запрос с несуществующим путем
    response = client.post("/students/import-from-csv",
        json={"file_path": "/nonexistent/file.csv"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert "detail" in response.json()
    assert "File not found" in response.json()["detail"]
