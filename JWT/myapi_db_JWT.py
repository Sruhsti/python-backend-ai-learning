from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from pydantic import BaseModel
from typing import Optional, List
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from datetime import datetime, timedelta

app = FastAPI(title="Integration with SQL") 

#security configurations
SECRET_KEY = "srushtipatil@123"
ALGORITHM = "HS256"
TOKEN_EXPIRES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") # here we are creating a password context using the bcrypt hashing algorithm. This will be used to hash the passwords before storing them in the database and to verify the passwords during login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # here we are creating an OAuth2PasswordBearer object which will be used to handle the authentication using OAuth2. tokenUrl="token" means that the token will be generated at the /token endpoint.OAuth2PasswordBearer() job is - read Authorization header -> extract Bearer token -> provide token to your function




# Database setup
# SQLAlchemy sends the pending SQL changes from memory to the database without permanently saving them.
# Think of it like this:
# add() → only keeps object in Python memory/session
# flush() → sends SQL query to DB
# commit() → permanently saves transaction
#bind = engine means that the sessionmaker will use the engine we created to connect to the database.


engine = create_engine("sqlite:///users.db", connect_args={"check_same_thread": False}) # here we are using sqlite database and creating a file named users.db in the current directory. connect_args={"check_same_thread": False} is used to allow multiple threads to access the database.check_same_thread=False is needed because FastAPI handles requests in multiple threads.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) #here we are creating a sessionmaker object which will be used to create a new session for each request. autocommit=False means that the changes will not be committed to the database until we explicitly call commit(). autoflush=False means that the changes will not be flushed(to the database until we explicitly call flush().

Base = declarative_base() # here we are creating a base class for our models. This will be used to create the tables in the database.

# database model
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True,nullable=False)
    role = Column(String(100), nullable=False)
    hashed_pwd = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)


Base.metadata.create_all(bind=engine) # here we are creating the tables in the database. bind=engine means that we are using the engine we created to connect to the database, create_all() will create the tables in the database based on the models we have defined.


#pydantic model
class UserCreate(BaseModel):
    name: str
    email: str
    role: str
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    class Config:
        from_attributes = True # here we are telling pydantic to read the data from the attributes of the SQLAlchemy model. This is necessary because the SQLAlchemy model has different attribute names than the pydantic model.

class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None


#security functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password) # here we are using the verify method of the password context to verify the plain password with the hashed password.

def get_password_hash(password):
    return pwd_context.hash(password) # here we are using the hash method of the password context to hash the password before storing it in the database.

def create_access_token(data:dict, expires_delta: Optional[timedelta]=None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encode_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encode_jwt


def verify_token(token:str)->TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email:str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token, could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return TokenData(email=email)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token, could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_db():
    db = SessionLocal() # here we are creating a new session for each request. SessionLocal() will create a new session using the sessionmaker we created earlier.
    try:
        yield db # here we are yielding the session to the endpoint function. This will allow us to use the session in the endpoint function and then close it after the request is completed.
    finally:
        db.close() # here we are closing the session after the request is completed. This is important to prevent memory leaks and to ensure that the database connection is properly closed.   


# auth dependencies -  this two function will be used as dependencies in the endpoints to get the current user and to check if the user is active or not. The get_current_user function will verify the token and return the user object from the database. The get_current_active_user function will check if the user is active or not and return the user object if the user is active, otherwise it will raise an HTTPException with a 404 status code.These are reusable guards that you plug into any route that needs authentication.
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    token_data = verify_token(token)
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user does not exist",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(
            status_code=404,
            detail="Inactive user"
        )
    return current_user


# Auth Endpoints
@app.post("/register", response_model=UserResponse)
def register_user(user:UserCreate,db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
         raise HTTPException(
            status_code=404,
            detail="User already exist"
        )
    
    hashed_password = get_password_hash(user.password)
    db_user = User(
        name = user.name,
        email = user.email,
        role = user.role,
        hashed_pwd = hashed_password
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/token", response_model=Token)
def login_with_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)): #OAuth2PasswordRequestForm — this is a special FastAPI form, that expects username and password as form fields (not JSON). This is the OAuth2 standard for login.# Depends() with no argument means FastAPI handles the form parsing automatically.
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_pwd):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
        )
    if not user.is_active:
       raise HTTPException(
            status_code=401,
            detail="Inactive user",
        )
    
    access_token_expires = timedelta(minutes=TOKEN_EXPIRES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}



@app.get("/profile", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.get("/verify-token", response_model=TokenData)
def verify_token_endpoint(current_user: User = Depends(get_current_active_user)):
    return {
        "valid": True,
        "user":{
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "role": current_user.role,
        }
    }


@app.get("/users/", response_model=List[UserResponse])
def get_all_users(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return db.query(User).all()

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int,current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first() # here we are querying the database to get the user with the given id. db.query(User) will create a query object for the User model, filter(User.id == user_id) will filter the query to get the user with the given id, and first() will return the first result of the query.
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found") 
    return db_user # here we are returning the user object. The response_model=UserResonse in the endpoint decorator will automatically convert the SQLAlchemy model to the pydantic model before returning it in the response.

@app.post("/users", response_model=UserResponse)
def user_create(user:UserCreate,current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="User already exists!")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(
        name = user.name,
        email = user.email,
        role = user.role,
        hashed_pwd = hashed_password
    )
    
    #create a new user
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id:int, update_user:UserCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()

    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    email_exists = db.query(User).filter(User.email == update_user.email,User.id != user_id).first()

    if email_exists:
        raise HTTPException(status_code=400, detail="Email already exists")

    db_user.name = update_user.name
    db_user.email = update_user.email
    db_user.role = update_user.role

    db.commit()
    db.refresh(db_user)
    return db_user 

@app.delete("/users/{user_id}")
def delete_user(user_id:int,current_user: User = Depends(get_current_active_user),db: Session = Depends(get_db) ):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete yourself") 
    db.delete(db_user)
    db.commit()
    return {"message":"user deleted"}































# Pydantic models serve as a validation + serialization layer between HTTP and your database.
# what does this means
# Great question. Let me break this sentence into two parts.

# What is a "layer between HTTP and your database"?
# When a request comes in and when a response goes out, the data passes through 3 zones:


# HTTP Request (raw JSON)
#         ↓
#    Pydantic Model   ← THE LAYER
#         ↓
#   SQLAlchemy Model (database)
# Pydantic sits in the middle and acts as a gatekeeper in both directions.

# Part 1: Validation (Input side — HTTP → Database)
# When a client sends this JSON to /register:


# {
#   "name": "Srushti",
#   "email": 12345,
#   "role": "admin"
# }
# Without Pydantic, this raw data would go straight to your database — wrong types, missing fields and all.

# With UserCreate (Pydantic model), FastAPI checks:

# Is name a string? ✅
# Is email a string? ❌ — it's an integer → automatically rejected with a 422 error before your code even runs
# Is password present? ❌ — missing → rejected

# class UserCreate(BaseModel):
#     name: str       # must be string
#     email: str      # must be string
#     role: str       # must be string
#     password: str   # must be string — REQUIRED
# So "validation" means: Pydantic checks that incoming data has the right shape and types before it touches your database.

# Part 2: Serialization (Output side — Database → HTTP)
# Your database returns a SQLAlchemy User object. It looks like this internally:


# User(id=1, name="Srushti", email="s@gmail.com", role="admin",
#      hashed_pwd="$2b$12$xyz...", is_active=True)
# You cannot send a SQLAlchemy object directly over HTTP — HTTP only understands text/JSON. Also, you must not send hashed_pwd back to the client.

# UserResponse handles both problems:


# class UserResponse(BaseModel):
#     id: int
#     name: str
#     email: str
#     role: str
#     is_active: bool
#     # hashed_pwd is NOT here — so it's never included in the response
# FastAPI uses this model to:

# Convert the SQLAlchemy object → plain Python dict → JSON
# Include only the fields defined in UserResponse — hashed_pwd is silently dropped
# So "serialization" means: converting a complex Python object (SQLAlchemy model) into a simple format (JSON) that can be sent over HTTP.

# One line summary
# Term	Direction	Purpose
# Validation	HTTP → Database	Reject bad/wrong/missing input before it reaches DB
# Serialization	Database → HTTP	Convert DB objects to JSON and control what fields are exposed

# Client sends JSON
#     → Pydantic validates it (wrong? → rejected)
#     → Your code + database runs
#     → Pydantic serializes the result (converts object → JSON, hides sensitive fields)
# → Client receives clean JSON
# Pydantic is the layer that makes sure garbage doesn't go in and sensitive data doesn't come out.





