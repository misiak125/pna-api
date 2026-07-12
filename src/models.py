from src import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    brand = Column(String(64), nullable=False)
    model = Column(String(64), nullable=False)
    colour = Column(String(64), nullable=False)
    added_on = Column(DateTime, nullable=False)
    price = Column(Float)
    old_price = Column(Float)
    year = Column(Integer, nullable=False)
    state = Column(String(64))
    order_id = Column(String(64))
    expected_delivery = Column(DateTime)
    history = Column(String(1000), nullable=False)
    deleted = Column(Boolean, nullable=False, default=False)

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String(128), nullable=False)
    phone = Column(String(32))
    email = Column(String(128))
    added_on = Column(DateTime, nullable=False) 
    pesel = Column(String(16))
    nip = Column(String(16))
    adress = Column(String(128))
    company_name = Column(String(128))
    history = Column(String(1000), nullable=False)
    deleted = Column(Boolean, nullable=False, default=False)

class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False)
    customer_id=Column(ForeignKey("customers.id"))
    product_id=Column(ForeignKey("products.id"))
    advance = Column(Float, nullable=False)
    adnotation = Column(String(1000))
    adnotation_pub = Column(String(1000), default="")
    form = Column(Boolean) #0=zaliczka 1=zadatek
    paid = Column(Boolean)
    delivery = Column(Boolean)
    term = Column(String(128))
    payment_method = Column(String(128))
    string_order_id = Column(String(128))
    history = Column(String(3000), nullable=False)
    deleted = Column(Boolean, nullable=False, default=False)
    
class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True)
    name = Column(String(64),  nullable=False, unique=True)

class Model(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True)
    brand_id = Column(ForeignKey("brands.id"))
    name = Column(String(64) , nullable=False)
    namehash = Column(String(128), nullable=False, unique=True)

class Colour(Base):
    __tablename__ = "colours"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True)

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    key = Column(String(128), unique=True, nullable=False)
    username = Column(String(128), nullable=False)

class AppState(Base):
    __tablename__ = "app_state"

    id = Column(Integer, primary_key=True)
    last_update = Column(DateTime, default=datetime.now)