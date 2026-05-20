# https://chatgpt.com/share/6a0c2815-e7fc-8320-b452-8e5c84008b5d

from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI()


class Todo(BaseModel):
    id: int
    name: str
    completed: bool = False

@app.get("/")
def greet():
    return " welcome back srushti"


todos = [
    Todo(id=1, name="Learn Python", completed=False),
    Todo(id=2, name="Learn FastAPI", completed=False),
    Todo(id=3, name="Learn SQL", completed=False),
]

# get all todos
@app.get("/todos")
def get_todos():
    return todos


# get todos by id:
@app.get("/todos/{id}")
def get_todo_id(id:int):
    for todo in todos:
        if todo.id == id:
            return todo
        

# add todos
@app.post("/todos")
def add_todo(todo:Todo):
    todos.append(todo)
    return "product added successfully"

# update todos
@app.put("/todos/{id}")
def update_todos(id:int, todo:Todo):
    for i in range(len(todos)):
        if todos[i].id == id:
            todos[i] = todo
            return "Product added successfully"
        
    return "no product found"

#delete todo
@app.delete("/todos/{id}")
def del_product(id:int):
    for todo in todos:
        if todo.id == id:
            todos.remove(todo)
            return "Product deleted successfully"
        
    return "no product found"










