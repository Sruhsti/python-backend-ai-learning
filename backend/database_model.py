from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base #This lets you create ORM classes - Without this, SQLAlchemy won’t know that your class represents a table.

# this defines how data is stored in the database, using Python classes that SQLAlchemy converts into SQL tables.
# Base is a special parent class -> think of it like "Rules that turn a Python class into a DB table”
# __tablename__ = "product" - >Tells SQLAlchemy table name in DB, Without this, SQLAlchemy won’t know where to store data
#database_model.Base.metadata.create_all(bind = engine) =>  Every class that inherits from Base automatically registers itself in Base.metadata, and create_all() creates a table for each registered class. SQLAlchemy only creates tables for models that are imported before create_all() is called.
Base = declarative_base()
class Product(Base):

    __tablename__ = "product"

    id = Column(Integer,primary_key=True, index = True)
    name = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    productname = Column(String(100))
    description = Column(String(255))
    price = Column(Float)
    quantity = Column(Integer)
    hashed_pwd = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)

   