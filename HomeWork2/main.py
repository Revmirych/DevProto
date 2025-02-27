from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, validator
from datetime import date
import json
import os

app = FastAPI()

# Модель Pydantic для валидации данных
class Appeal(BaseModel):
    last_name: str
    first_name: str
    birth_date: date
    phone_number: str
    email: EmailStr

    # Валидация фамилии
    @validator('last_name')
    def validate_last_name(cls, v):
        if not v.isalpha() or not v.istitle():
            raise ValueError('Фамилия должна начинаться с заглавной буквы и содержать только кириллицу')
        return v

    # Валидация имени
    @validator('first_name')
    def validate_first_name(cls, v):
        if not v.isalpha() or not v.istitle():
            raise ValueError('Имя должно начинаться с заглавной буквы и содержать только кириллицу')
        return v

    # Валидация номера телефона
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if not v.startswith('+') or not v[1:].isdigit():
            raise ValueError('Номер телефона должен начинаться с "+" и содержать только цифры')
        return v

# Эндпоинт для приема данных
@app.post("/submit_appeal/")
async def submit_appeal(appeal: Appeal):
    # Преобразуем данные в словарь
    appeal_data = appeal.dict()
    
    # Сохраняем данные в JSON-файл
    file_name = f"{appeal.last_name}_{appeal.first_name}.json"
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(appeal_data, f, ensure_ascii=False, indent=4)
    
    return {"message": "Обращение успешно сохранено", "file_name": file_name}

# Запуск сервера
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
