from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Date, Boolean, ForeignKey, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Customer(Base):
    __tablename__ = 'Customer'
    customer_id = Column(Integer, primary_key=True)
    first_name = Column(String(255))
    last_name = Column(String(255))
    email = Column(String(255))
    phone_number = Column(String(255))
    address = Column(String(255))
    orders = relationship("Order", back_populates="customer")

class ProductOrder(Base):
    __tablename__ = 'ProductOrder'
    product_id = Column(Integer, primary_key=True)
    product_name = Column(String(255))
    price = Column(Numeric(10, 2))
    availability = Column(Boolean)
    specifications = Column(Text)
    orders = relationship("Order", back_populates="product")

class Order(Base):
    __tablename__ = 'Order'
    order_id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('Customer.customer_id'))
    product_id = Column(Integer, ForeignKey('ProductOrder.product_id'))
    order_date = Column(Date)
    status = Column(String(255))
    quantity = Column(Integer)
    total_price = Column(Numeric(10, 2))
    customer = relationship("Customer", back_populates="orders")
    product = relationship("ProductOrder", back_populates="orders")
    shipment = relationship("Shipment", back_populates="order", uselist=False)

class Shipment(Base):
    __tablename__ = 'Shipment'
    shipment_id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('Order.order_id'))
    shipment_date = Column(Date)
    estimated_arrival = Column(Date)
    current_status = Column(String(255))
    error_details = Column(Text)
    order = relationship("Order", back_populates="shipment")

class Product(Base):
    __tablename__ = 'Product'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    price = Column(Float)
    review = Column(String(255))
    image_url = Column(String(255))