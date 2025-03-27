import csv
from sqlalchemy import create_engine, Column, Integer, String, Float, select, func
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List

# Define the base for declarative models
Base = declarative_base()

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

    # New CRUD methods
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


# FastAPI setup
app = FastAPI()
db_manager = DatabaseManager()

# Dependency to get DB session
def get_db():
    db = db_manager.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/students/", response_model=Student)
def create_student(student: StudentCreate, db=Depends(get_db)):
    db_student = db_manager.insert_student(db, student.dict())
    if db_student is None:
        raise HTTPException(status_code=400, detail="Student could not be created")
    return db_student

@app.get("/students/", response_model=List[Student])
def read_students(skip: int = 0, limit: int = 100, db=Depends(get_db)):
    students = db_manager.get_all_students(db)
    return students[skip : skip + limit]

@app.get("/students/{student_id}", response_model=Student)
def read_student(student_id: int, db=Depends(get_db)):
    db_student = db_manager.get_student(db, student_id)
    if db_student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return db_student

@app.put("/students/{student_id}", response_model=Student)
def update_student(student_id: int, student: StudentUpdate, db=Depends(get_db)):
    db_student = db_manager.update_student(db, student_id, student.dict(exclude_unset=True))
    if db_student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return db_student

@app.delete("/students/{student_id}")
def delete_student(student_id: int, db=Depends(get_db)):
    success = db_manager.delete_student(db, student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deleted successfully"}

# Additional endpoints from previous functionality
@app.get("/students/faculty/{faculty_name}", response_model=List[Student])
def get_students_by_faculty(faculty_name: str, db=Depends(get_db)):
    return db_manager.get_students_by_faculty(db, faculty_name)

@app.get("/subjects/", response_model=List[str])
def get_unique_subjects(db=Depends(get_db)):
    return db_manager.get_unique_subjects(db)

@app.get("/faculty/{faculty_name}/average_score")
def get_average_score_by_faculty(faculty_name: str, db=Depends(get_db)):
    average = db_manager.get_average_score_by_faculty(db, faculty_name)
    return {"faculty": faculty_name, "average_score": average}

@app.get("/students/low_score/{subject}", response_model=List[Student])
def get_low_score_students(subject: str, threshold: int = 30, db=Depends(get_db)):
    return db_manager.get_low_score_students_by_subject(db, subject, threshold)


def main():
    # Initialize database
    db_generator = db_manager.get_db()
    db = next(db_generator)

    try:
        # Fill the database from CSV (only once if database is empty)
        count = db.query(Student).count()
        if count == 0:
            db_manager.fill_from_csv(db, r"c:\usr\python\DevProto\HomeWork4\students.csv")
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
