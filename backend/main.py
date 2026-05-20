# uvicorn main:app --reload

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from models import ProductCreate, TokenData, ProductResponse, TokenResponse
from database import SessionLocal,engine
import database_model
from sqlalchemy.orm import session
from typing import Optional, List
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins = ["http://localhost:3000"],
    allow_methods = ["*"],
    allow_headers = ["*"]
)

SECRET_KEY = "srushtipatil@123"
ALGORITHM = "HS256"
TOKEN_EXPIRES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

database_model.Base.metadata.create_all(bind = engine)
Predifinedproducts = [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "productname": "phone", "description": "budget phone", "price": 99, "quantity": 10},
    {"id": 2, "name": "Bob", "email": "bob@example.com", "productname": "laptop", "description": "budget laptop", "price": 199, "quantity": 100},
    {"id": 3, "name": "Carol", "email": "carol@example.com", "productname": "pen", "description": "budget pen", "price": 10, "quantity": 15},
    {"id": 4, "name": "Dave", "email": "dave@example.com", "productname": "pencil", "description": "budget pencil", "price": 15, "quantity": 20},
]


#securtiy functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data:dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expires = datetime.utcnow() + expires_delta
    else:
        expires = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp":expires})
    encode_jwt =  jwt.encode(to_encode,SECRET_KEY,algorithm=ALGORITHM)
    return encode_jwt

def verify_access_token(token:str)->TokenData:
    try:
        payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token_data = TokenData(email=email)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    db = SessionLocal()
    count = db.query(database_model.Product).count()
    if count == 0:
        for product in Predifinedproducts:
            db.add(database_model.Product(**product))
        db.commit()
    db.close()

init_db()


def get_current_user(token: str = Depends(oauth2_scheme), db: session = Depends(get_db)):
    token_data = verify_access_token(token)
    user = db.query(database_model.Product).filter(database_model.Product.email == token_data.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def get_current_active_user(current_user: database_model.Product = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


#auth endpoints
@app.post("/token", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: session = Depends(get_db)):
    user = db.query(database_model.Product).filter(database_model.Product.email == form_data.username).first()
    if not user or not user.hashed_pwd or not verify_password(form_data.password, user.hashed_pwd):
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
        data={"sub":user.email},
        expires_delta=access_token_expires             
    )

    return {"access_token": access_token, "token_type": "bearer" }


@app.post("/register",response_model=ProductResponse )
def register_user(user:ProductCreate,db: session = Depends(get_db)):
    if not user.password:
        raise HTTPException(status_code=400, detail="Password is required for registration")
    db_user = db.query(database_model.Product).filter(database_model.Product.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    new_user = database_model.Product(
        id=user.id,
        name=user.name,
        email=user.email,
        productname=user.productname,
        description=user.description,
        price=user.price,
        quantity=user.quantity,
        hashed_pwd=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/")
def greet():
    return "hello, i am srushti.."


@app.get("/products")
def get_all_products(db:session = Depends(get_db), current_user: database_model.Product = Depends(get_current_active_user)):
    db_products = db.query(database_model.Product).all()
    return db_products

@app.get("/products/{id}")
def get_product_by_id(id:int,db:session = Depends(get_db), current_user: database_model.Product = Depends(get_current_active_user)):
    db_product = db.query(database_model.Product).filter(database_model.Product.id == id).first()
    if db_product:
        return db_product
    
    return "Product not found"

@app.post("/products")
def add_product(product: ProductCreate,db:session = Depends(get_db), current_user: database_model.Product = Depends(get_current_active_user)):
    db.add(database_model.Product(**product.model_dump(exclude={"password"})))
    db.commit()
    return product

@app.put("/products/{id}")
def update_product(id:int, product:ProductCreate,db:session = Depends(get_db), current_user: database_model.Product = Depends(get_current_active_user)):
    db_product = db.query(database_model.Product).filter(database_model.Product.id == id).first()
    if db_product:
        db_product.name = product.name
        db_product.description = product.description
        db_product.price = product.price
        db_product.quantity = product.quantity
        db.commit()
        return "Product Updated"
    else:
        return "No product found"

@app.delete("/products/{id}")
def del_product(id:int,db:session = Depends(get_db), current_user: database_model.Product = Depends(get_current_active_user)):
    db_product = db.query(database_model.Product).filter(database_model.Product.id == id).first()
    if db_product:
       db.delete(db_product)
       db.commit()
       return "Product deleted successfully"
    else:
        return "no product found"