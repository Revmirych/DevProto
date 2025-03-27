import csv
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, func
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError

# Конфигурация
SECRET_KEY = "your-secret-key-here"  # В продакшене используйте надежный секретный ключ
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Базовые модели
Base = declarative_base()

# Модель пользователя для БД
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Integer, default=1)  # 1 - активен, 0 - неактивен

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

# Настройки аутентификации
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

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
        with open(csv_filepath, mode="r", encoding="utf-8") as csv_file:
            csv_reader = csv.DictReader(csv_file)
            line_count = 0
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
                self.insert_student(db, student_data)
                line_count += 1
            print(f"Processed {line_count} lines.")

    def get_students_by_faculty(self, db, faculty_name):
        students = db.query(Student).filter(Student.faculty == faculty_name).all()
        return students
    
    def get_unique_subjects(self, db):
        unique_subjects = db.query(Student.subject).distinct().all()
        return [subject[0] for subject in unique_subjects]

    def get_average_score_by_faculty(self, db, faculty_name):
        result = db.query(Student.faculty, func.avg(Student.score)).filter(Student.faculty == faculty_name).group_by(Student.faculty).first()
        if result:
             return result[1]
        return 0

    def get_low_score_students_by_subject(self, db, subject, threshold=30):
        students = db.query(Student).filter(Student.subject == subject, Student.score < threshold).all()
        return students

    def get_student(self, db, student_id: int):
        return db.query(Student).filter(Student.id == student_id).first()

    def get_all_students(self, db):
        return db.query(Student).all()

    def update_student(self, db, student_id: int, student_data: dict):
        db_student = db.query(Student).filter(Student.id == student_id).first()
        if not db_student:
            return None
        
        for key, value in student_data.items():
            if value is not None:
                setattr(db_student, key, value)
        
        db.commit()
        db.refresh(db_student)
        return db_student

    def delete_student(self, db, student_id: int):
        db_student = db.query(Student).filter(Student.id == student_id).first()
        if not db_student:
            return False
        
        db.delete(db_student)
        db.commit()
        return True

# Функции для аутентификации
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(db, username: str, password: str):
    user = db_manager.get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request, db=Depends(db_manager.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = request.cookies.get("access_token")
    if token is None:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = db_manager.get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.is_active != 1:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Инициализация приложения
app = FastAPI()
db_manager = DatabaseManager()

# Маршруты аутентификации
@app.post("/auth/register", response_model=UserBase)
def register(user: UserCreate, db=Depends(db_manager.get_db)):
    db_user = db_manager.get_user(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return db_manager.create_user(db, user)

@app.post("/auth/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db=Depends(db_manager.get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token")
    return response

# Защищенные маршруты (требуют аутентификации)
@app.post("/students/", response_model=Student)
def create_student(
    student: StudentCreate,
    current_user: User = Depends(get_current_active_user),
    db=Depends(db_manager.get_db)
):
    db_student = db_manager.insert_student(db, student.dict())
    if db_student is None:
        raise HTTPException(status_code=400, detail="Student could not be created")
    return db_student

@app.get("/students/", response_model=List[Student])
def read_students(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db=Depends(db_manager.get_db)
):
    students = db_manager.get_all_students(db)
    return students[skip : skip + limit]

@app.get("/students/{student_id}", response_model=Student)
def read_student(
    student_id: int,
    current_user: User = Depends(get_current_active_user),
    db=Depends(db_manager.get_db)
):
    db_student = db_manager.get_student(db, student_id)
    if db_student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return db_student

@app.put("/students/{student_id}", response_model=Student)
def update_student(
    student_id: int,
    student: StudentUpdate,
    current_user: User = Depends(get_current_active_user),
    db=Depends(db_manager.get_db)
):
    db_student = db_manager.update_student(db, student_id, student.dict(exclude_unset=True))
    if db_student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return db_student

@app.delete("/students/{student_id}")
def delete_student(
    student_id: int,
    current_user: User = Depends(get_current_active_user),
    db=Depends(db_manager.get_db)
):
    success = db_manager.delete_student(db, student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deleted successfully"}

# Дополнительные защищенные маршруты
@app.get("/students/faculty/{faculty_name}", response_model=List[Student])
def get_students_by_faculty(
    faculty_name: str,
    current_user: User = Depends(get_current_active_user),
    db=Depends(db_manager.get_db)
):
    return db_manager.get_students_by_faculty(db, faculty_name)

@app.get("/subjects/", response_model=List[str])
def get_unique_subjects(
    current_user: User = Depends(get_current_active_user),
    db=Depends(db_manager.get_db)
):
    return db_manager.get_unique_subjects(db)

@app.get("/faculty/{faculty_name}/average_score")
def get_average_score_by_faculty(
    faculty_name: str,
    current_user: User = Depends(get_current_active_user),
    db=Depends(db_manager.get_db)
):
    average = db_manager.get_average_score_by_faculty(db, faculty_name)
    return {"faculty": faculty_name, "average_score": average}

@app.get("/students/low_score/{subject}", response_model=List[Student])
def get_low_score_students(
    subject: str,
    threshold: int = 30,
    current_user: User = Depends(get_current_active_user),
    db=Depends(db_manager.get_db)
):
    return db_manager.get_low_score_students_by_subject(db, subject, threshold)

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
        
        # Заполняем данные студентов, если база пуста
        count = db.query(Student).count()
        if count == 0:
            db_manager.fill_from_csv(db, r"c:\usr\python\DevProto\HomeWork5\students.csv")
        else:
            print("Database already populated. Skipping fill_from_csv.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    main()
    uvicorn.run(app, host="0.0.0.0", port=8000)
