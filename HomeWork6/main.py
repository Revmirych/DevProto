import csv
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, func
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError
import redis
from fastapi.responses import JSONResponse
import json
import os
from functools import wraps

# Конфигурация
SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_CACHE_EXPIRE = 300  # 5 минут

# Инициализация Redis
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

# Базовые модели
Base = declarative_base()

# Модель пользователя для БД
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Integer, default=1)

# Модель студента
class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    surname = Column(String, index=True)
    name = Column(String, index=True)
    faculty = Column(String, index=True)
    subject = Column(String, index=True)
    score = Column(Integer)

    def __repr__(self):
        return f"<Student(surname={self.surname}, name={self.name}, faculty={self.faculty}, subject={self.subject}, score={self.score})>"

# Pydantic модели
class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class StudentCreate(BaseModel):
    surname: str
    name: str
    faculty: str
    subject: str
    score: int

class StudentUpdate(BaseModel):
    surname: str = None
    name: str = None
    faculty: str = None
    subject: str = None
    score: int = None

class DeleteStudentsRequest(BaseModel):
    student_ids: List[int]

class CSVImportRequest(BaseModel):
    file_path: str

# Настройки аутентификации
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Декоратор для кеширования
def cache_response(key_prefix: str, expire: int = REDIS_CACHE_EXPIRE):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Генерация ключа кеша на основе параметров запроса
            request = kwargs.get('request')
            cache_key = f"{key_prefix}:{request.url.path}"
            
            # Попытка получить данные из кеша
            cached_data = redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            
            # Если данных нет в кеше, выполняем функцию
            response = await func(*args, **kwargs)
            
            # Сохраняем результат в кеш
            redis_client.setex(cache_key, expire, json.dumps(response))
            
            return response
        return wrapper
    return decorator

class DatabaseManager:
    def __init__(self, db_url="sqlite:///./students.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_db(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Методы для работы с пользователями
    def get_user(self, db, username: str):
        return db.query(User).filter(User.username == username).first()

    def create_user(self, db, user: UserCreate):
        hashed_password = pwd_context.hash(user.password)
        db_user = User(
            username=user.username,
            email=user.email,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    # Методы для работы со студентами
    def insert_student(self, db, student_data):
        db_student = Student(**student_data)
        try:
            db.add(db_student)
            db.commit()
            db.refresh(db_student)
            return db_student
        except IntegrityError as e:
            db.rollback()
            print(f"Error inserting student: {e}")
            return None

    def fill_from_csv(self, db, csv_filepath):
        try:
            with open(csv_filepath, mode="r", encoding="utf-8") as csv_file:
                csv_reader = csv.DictReader(csv_file)
                line_count = 0
                inserted_count = 0
                for row in csv_reader:
                    if line_count == 0:
                        line_count += 1
                        continue
                    student_data = {
                        "surname": row["Фамилия"],
                        "name": row["Имя"],
                        "faculty": row["Факультет"],
                        "subject": row["Курс"],
                        "score": int(row["Оценка"]),
                    }
                    if self.insert_student(db, student_data):
                        inserted_count += 1
                    line_count += 1
                print(f"Processed {line_count} lines, inserted {inserted_count} students.")
                return inserted_count
        except Exception as e:
            print(f"Error processing CSV file: {e}")
            return 0

    def delete_students(self, db, student_ids: List[int]):
        try:
            result = db.query(Student).filter(Student.id.in_(student_ids)).delete(synchronize_session=False)
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            print(f"Error deleting students: {e}")
            return 0

    # Остальные методы остаются без изменений
    # ... (get_students_by_faculty, get_unique_subjects и т.д.)

# Инициализация приложения
app = FastAPI()
db_manager = DatabaseManager()

# Фоновые задачи
def process_csv_import(file_path: str):
    db = next(db_manager.get_db())
    try:
        inserted_count = db_manager.fill_from_csv(db, file_path)
        # Очищаем кеш после изменения данных
        redis_client.flushdb()
        return inserted_count
    finally:
        db.close()

def process_students_deletion(student_ids: List[int]):
    db = next(db_manager.get_db())
    try:
        deleted_count = db_manager.delete_students(db, student_ids)
        # Очищаем кеш после изменения данных
        redis_client.flushdb()
        return deleted_count
    finally:
        db.close()

# Эндпойнты для фоновых задач
@app.post("/students/import-from-csv")
async def import_from_csv(
    request: CSVImportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=400, detail="File not found")
    
    background_tasks.add_task(process_csv_import, request.file_path)
    return {"message": "CSV import started in background"}

@app.post("/students/delete-batch")
async def delete_students_batch(
    request: DeleteStudentsRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    if not request.student_ids:
        raise HTTPException(status_code=400, detail="No student IDs provided")
    
    background_tasks.add_task(process_students_deletion, request.student_ids)
    return {"message": "Batch deletion started in background"}

# Пример защищенного эндпойнта с кешированием
@app.get("/students/", response_model=List[Student])
@cache_response("students_list")
async def read_students(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db=Depends(db_manager.get_db)
):
    students = db_manager.get_all_students(db)
    return students[skip : skip + limit]

# Остальные эндпойнты с добавлением кеширования
@app.get("/students/faculty/{faculty_name}", response_model=List[Student])
@cache_response("students_by_faculty")
async def get_students_by_faculty(
    request: Request,
    faculty_name: str,
    current_user: User = Depends(get_current_active_user),
    db=Depends(db_manager.get_db)
):
    return db_manager.get_students_by_faculty(db, faculty_name)

@app.get("/subjects/", response_model=List[str])
@cache_response("unique_subjects")
async def get_unique_subjects(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db=Depends(db_manager.get_db)
):
    return db_manager.get_unique_subjects(db)


def main():
    # Инициализация базы данных
    db_generator = db_manager.get_db()
    db = next(db_generator)

    try:
        # Создаем тестового пользователя, если его нет
        if not db_manager.get_user(db, "admin"):
            db_manager.create_user(db, UserCreate(
                username="admin",
                email="admin@example.com",
                password="admin"
            ))
        
        # Проверяем подключение к Redis
        redis_client.ping()
        print("Connected to Redis successfully")
    except redis.ConnectionError:
        print("Failed to connect to Redis")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
   
