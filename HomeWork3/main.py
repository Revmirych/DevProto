import csv
from sqlalchemy import create_engine, Column, Integer, String, Float, select
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError

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


from sqlalchemy import func

def main():
    db_manager = DatabaseManager()
    db_generator = db_manager.get_db()
    db = next(db_generator)

    # Fill the database from CSV (only once if database is empty)
    try:
        count = db.query(Student).count()
        if count == 0:
            db_manager.fill_from_csv(db, r"c:\usr\python\DevProto\HomeWork3\students.csv")
        else:
            print("Database already populated. Skipping fill_from_csv.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
         db.close()
    db_generator = db_manager.get_db()
    db = next(db_generator)

    # Test cases
    print("\nStudents from ФТФ:")
    for student in db_manager.get_students_by_faculty(db, "ФТФ"):
        print(student)

    print("\nUnique Subjects:")
    print(db_manager.get_unique_subjects(db))

    print("\nAverage score for ФПМИ:")
    print(db_manager.get_average_score_by_faculty(db, "ФПМИ"))

    print("\nStudents with score < 30 in Теор. Механика:")
    for student in db_manager.get_low_score_students_by_subject(db, "Теор. Механика"):
        print(student)
    
    db.close()
    

if __name__ == "__main__":
    main()
