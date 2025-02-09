from fastapi import FastAPI, HTTPException  
from pydantic import BaseModel  
import ast  
import operator  

app = FastAPI()  

# Хранит текущее выражение  
current_expression = ""  

# Функция для безопасного выполнения математического выражения  
def eval_expression(expr: str) -> float:  
    try:  
        # Используем ast для безопасного парсинга выражений  
        node = ast.parse(expr, mode='eval')  
        return eval(compile(node, '', mode='eval'))  
    except Exception as e:  
        raise HTTPException(status_code=400, detail=str(e))  

class Operation(BaseModel):  
    a: float  
    b: float  
    op: str  

@app.post("/add/")  
def add(operation: Operation):  
    return {"result": operation.a + operation.b}  

@app.post("/subtract/")  
def subtract(operation: Operation):  
    return {"result": operation.a - operation.b}  

@app.post("/multiply/")  
def multiply(operation: Operation):  
    return {"result": operation.a * operation.b}  

@app.post("/divide/")  
def divide(operation: Operation):  
    if operation.b == 0:  
        raise HTTPException(status_code=400, detail="Division by zero")  
    return {"result": operation.a / operation.b}  

@app.post("/create_expression/")  
def create_expression(expr: str):  
    global current_expression  
    current_expression = expr  
    return {"expression": current_expression}  

@app.get("/current_expression/")  
def get_current_expression():  
    return {"current_expression": current_expression}  

@app.post("/evaluate/")  
def evaluate_expression():  
    if not current_expression:  
        raise HTTPException(status_code=400, detail="No expression to evaluate")  
    return {"result": eval_expression(current_expression)}  

if __name__ == "__main__":  
    import uvicorn  
    uvicorn.run(app, host="127.0.0.1", port=8000)  
