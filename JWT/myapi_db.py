from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, Column, Integer, String
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="Integration with SQL") 

# Database setup

# SQLAlchemy sends the pending SQL changes from memory to the database without permanently saving them.
# Think of it like this:
# add() → only keeps object in Python memory/session
# flush() → sends SQL query to DB
# commit() → permanently saves transaction
#bind = engine means that the sessionmaker will use the engine we created to connect to the database.


engine = create_engine("sqlite:///users.db", connect_args={"check_same_thread": False}) # here we are using sqlite database and creating a file named users.db in the current directory. connect_args={"check_same_thread": False} is used to allow multiple threads to access the database.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) #here we are creating a sessionmaker object which will be used to create a new session for each request. autocommit=False means that the changes will not be committed to the database until we explicitly call commit(). autoflush=False means that the changes will not be flushed(to the database until we explicitly call flush().

Base = declarative_base() # here we are creating a base class for our models. This will be used to create the tables in the database.

# database model
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True,nullable=False)
    role = Column(String(100), nullable=False)

Base.metadata.create_all(bind=engine) # here we are creating the tables in the database. bind=engine means that we are using the engine we created to connect to the database, create_all() will create the tables in the database based on the models we have defined.


#pydantic model
class UserCreate(BaseModel):
    name: str
    email: str
    role: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True # here we are telling pydantic to read the data from the attributes of the SQLAlchemy model. This is necessary because the SQLAlchemy model has different attribute names than the pydantic model.


def get_db():
    db = SessionLocal() # here we are creating a new session for each request. SessionLocal() will create a new session using the sessionmaker we created earlier.
    try:
        yield db # here we are yielding the session to the endpoint function. This will allow us to use the session in the endpoint function and then close it after the request is completed.
    finally:
        db.close() # here we are closing the session after the request is completed. This is important to prevent memory leaks and to ensure that the database connection is properly closed.   


@app.get("/users/", response_model=List[UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first() # here we are querying the database to get the user with the given id. db.query(User) will create a query object for the User model, filter(User.id == user_id) will filter the query to get the user with the given id, and first() will return the first result of the query.
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found") 
    return db_user # here we are returning the user object. The response_model=UserResonse in the endpoint decorator will automatically convert the SQLAlchemy model to the pydantic model before returning it in the response.

@app.post("/users", response_model=UserResponse)
def user_create(user:UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="User already exists!")
    
    #create a new user
    new_user = User(**user.model_dump())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id:int, user:UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()

    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    email_exists = db.query(User).filter(User.email == user.email,User.id != user_id).first()

    if email_exists:
        raise HTTPException(status_code=400, detail="Email already exists")

    db_user.name = user.name
    db_user.email = user.email
    db_user.role = user.role

    db.commit()
    db.refresh(db_user)
    return db_user 

@app.delete("/users/{user_id}")
def delete_user(user_id:int,db: Session = Depends(get_db) ):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found") 
    db.delete(db_user)
    db.commit()
    return {"message":"user deleted"}
