from typing import Optional
from pydantic import BaseModel

class ProductCreate(BaseModel):
    id : int
    name : str
    email : str
    password : Optional[str] = None
    productname : str
    description : str
    price : float
    quantity : int

class ProductResponse(BaseModel):
    id : int
    name : str
    email : str
    productname : str
    description : str
    price : float
    quantity : int
    is_active : bool
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username : str
    password : str

class TokenResponse(BaseModel):
    access_token : str
    token_type : str

class TokenData(BaseModel):
    email : Optional[str] = None