from bs4 import BeautifulSoup
import requests
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Date, Boolean, ForeignKey, Numeric, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import SQLAlchemyError
from llama_index.llms.azure_openai import AzureOpenAI
import os
from dotenv import load_dotenv
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.chat_engine.types import ChatMessage
import random
from sentence_transformers import SentenceTransformer
import faiss
import re

load_dotenv()
os.environ["OPENAI_API_KEY"] = "e125adf912704e61afef50706b6f2f1f"

# LLM configuration
llm_config = {
    "engine": "azoai-deploy-gpt35t",
    "model": "gpt-3.5-turbo",
    "temperature": 0.0,
    "azure_endpoint": "https://oai-ecirkle-dev-01.openai.azure.com/",
    "api_key": "e125adf912704e61afef50706b6f2f1f",
    "api_version": "2024-02-01",
}

# Database Config
db_user = "root"
db_password = "1234"
db_host = "localhost"
db_name = "ShopperAssistant"

# Database setup
DATABASE_URL = f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}/{db_name}"
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# Database models
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
    specs = Column(Text)
    image_url = Column(String(255))

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)







# Scraping functions
def query_database(query, params=None):
    session = Session()
    try:
        if params:
            result = session.execute(text(query), params).fetchall()
        else:
            result = session.execute(text(query)).fetchall()
        return result
    except SQLAlchemyError as e:
        return f"Database error: {str(e)}"
    finally:
        session.close()

def product_exists(session, name):
    query = text(f"SELECT COUNT(*) FROM Product WHERE name = :name")
    result = session.execute(query, {"name": name}).scalar()
    return result > 0

def stripped_webpage_to_dataframe(webpage, class_dict):
    response = requests.get(webpage)
    html_content = response.text
    def strip_html_tags(html_content, class_dict):
        soup = BeautifulSoup(html_content, "html.parser")
        data_dict = {}
       
        for class_name, column_name in class_dict.items():
            if column_name == "Image URL":
                imgs = soup.find_all("img", class_=class_name)
                data_dict[column_name] = [img.get('src') for img in imgs]
            else:
                divs = soup.find_all("div", class_=class_name)
                text_list = [div.get_text() for div in divs]
                data_dict[column_name] = text_list
        
        max_len = max(len(lst) for lst in data_dict.values())
       
        for column_name, text_list in data_dict.items():
            if len(text_list) < max_len:
                text_list.extend([None] * (max_len - len(text_list)))
       
        rows = zip(*[data_dict[column_name] for column_name in class_dict.values()])
        filtered_rows = [row for row in rows if all(cell is not None for cell in row)]
        filtered_data_dict = {column_name: [row[i] for row in filtered_rows] for i, column_name in enumerate(class_dict.values())}
        return filtered_data_dict

    data_dict = strip_html_tags(html_content, class_dict)
    df = pd.DataFrame(data_dict)
    print(f"Scraped {len(df)} products from {webpage}")
    return df

def scrape_and_store_data():
    base_url = "https://www.flipkart.com/mobiles/~mobile-phones-under-rs20000/pr?sid=tyy%2C4io&page="
    class_dict = {
        "KzDlHZ": "Product Name",
        "Nx9bqj _4b5DiR": "Product Price",
        "XQDdHH": "Product Review",
        "_6NESgJ": "Product Specs",
        "DByuf4": "Image URL"
    }
    
    # Randomly select start and end pages
    start_page = random.randint(1, 8)
    end_page = random.randint(start_page + 1, min(start_page + 2, 10))
    
    print(f"Scraping pages {start_page} to {end_page}")
    
    all_products = pd.DataFrame()
    
    for page in range(start_page, end_page + 1):
        url = base_url + str(page)
        df = stripped_webpage_to_dataframe(url, class_dict)
        all_products = pd.concat([all_products, df], ignore_index=True)
    
    session = Session()
    new_products_count = 0
    try:
        for _, row in all_products.iterrows():
            name = row['Product Name']
            if not product_exists(session, name):
                product = Product(
                    name=name,
                    price=float(row['Product Price'].replace('₹', '').replace(',', '')),
                    review=row['Product Review'],
                    specs=row['Product Specs'],
                    image_url=row['Image URL']
                )
                session.add(product)
                new_products_count += 1
        session.commit()
        print(f"Added {new_products_count} new products to the database.")
    except Exception as e:
        session.rollback()
        print(f"An error occurred while adding products: {str(e)}")
    finally:
        session.close()
    
    return f"Scraped pages {start_page} to {end_page}, added {new_products_count} new products."





# Initialize sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize FAISS index
dimension = 384
index = faiss.IndexFlatIP(dimension)

# Function to add products to the vector database
def add_products_to_vector_db():
    session = Session()
    try:
        products = session.query(Product).all()
        product_texts = [f"{p.name} {p.specs}" for p in products]
        embeddings = model.encode(product_texts)
        
        faiss.normalize_L2(embeddings)
        
        index.add(embeddings)
        print(f"Added {len(products)} products to the vector database.")
        return products
    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return []
    finally:
        session.close()

def get_product_recommendations(product_name, limit=5):
    try:
        user_embedding = model.encode([product_name])
        faiss.normalize_L2(user_embedding)
        
        D, I = index.search(user_embedding, limit)
        
        recommendations = [f"Here are the top 5 product recommendations similar to {product_name}:"]
        for i, idx in enumerate(I[0], 1):
            product = all_products[idx]
            similarity_score = D[0][i-1]
            recommendations.append(f"{i}. Name: {product.name}, Price: ${product.price:.2f}, "
                                   f"Review: {product.review}, Specs: {product.specs}, "
                                   f"Image URL: {product.image_url}, "  # Added this line
                                   f"Similarity Score: {similarity_score:.4f}")
        
        return "\n".join(recommendations)
    except Exception as e:
        return f"Error: {str(e)}"




def get_john_doe_orders():
    session = Session()
    try:
        john_doe = session.query(Customer).filter(
            Customer.first_name == "John",
            Customer.last_name == "Doe"
        ).first()
        
        if not john_doe:
            return "Customer John Doe not found in the database."
        
        orders = session.query(Order).filter(Order.customer_id == john_doe.customer_id).all()
        
        if not orders:
            return "No orders found for John Doe."
        
        order_details = []
        for order in orders:
            shipment_info = f", Shipment Status: {order.shipment.current_status}" if order.shipment else ""
            order_details.append(f"Order ID: {order.order_id}, Product: {order.product.product_name}, "
                                 f"Price: ${order.total_price}, Date: {order.order_date}, "
                                 f"Status: {order.status}{shipment_info}")
        
        return "\n".join(order_details)
    except SQLAlchemyError as e:
        return f"Database error: {str(e)}"
    finally:
        session.close()

# Create Tools
get_john_doe_orders_tool = FunctionTool.from_defaults(fn=get_john_doe_orders)
get_product_recommendations_tool = FunctionTool.from_defaults(
    fn=get_product_recommendations,
    name="get_product_recommendations",
    description="Get product recommendations based on a product name"
)

# Create Order Agent
order_agent_system_message = """You are an Order Information Agent specialized in providing information about John Doe's orders.

Your primary function is to retrieve and present John Doe's order history, including details about products ordered, prices, dates, and shipment information when available.

When interacting with users:
- Provide clear and concise information about John Doe's orders.
- Always include the full product name in your response, prefixed with "Product:".
- Include shipment details when available.
- If asked about any other customer, politely explain that you only have information about John Doe.
- If a user's query is unclear, ask for clarification to ensure you provide the most relevant information.

Your goal is to assist users in understanding John Doe's purchase history."""

order_agent = ReActAgent.from_tools(
    [get_john_doe_orders_tool], 
    llm=AzureOpenAI(**llm_config),
    memory=ChatMemoryBuffer.from_defaults(token_limit=1500),
    verbose=True,
    system_prompt=order_agent_system_message
)

# Create Recommendation Agent
recommendation_system_message = """You are a Product Recommendation Agent, specialized in providing product recommendations based on products mentioned in order histories.

Your primary function is to analyze the Order History Agent's response, extract product names, and provide recommendations for similar products.

When processing the Order History Agent's response:
1. Read the response carefully.
2. Extract all product names mentioned in the order history.
3. For each product found, use the get_product_recommendations function to find similar products.
4. Present the recommendations in a clear, organized manner.

Your responses should follow this format:
Thought: [Your analysis of the Order History Agent's response]
Action: get_product_recommendations
Action Input: [Extracted product name]
Observation: [The output from the get_product_recommendations function]
Thought: [Your analysis of the recommendations]
Human: Based on the order history, here are some product recommendations:
[List the top recommendations with brief descriptions, including the image URL]

Maintain this format for each product found in the order history.

Your goal is to provide relevant product recommendations based on the products in the customer's order history. Always include the image URL for each recommended product."""

recommendation_agent = ReActAgent.from_tools(
    [get_product_recommendations_tool], 
    llm=AzureOpenAI(**llm_config),
    memory=ChatMemoryBuffer.from_defaults(token_limit=1500),
    verbose=True,
    system_prompt=recommendation_system_message
)

# Update the agents dictionary
agents = {
    "order_history": order_agent,
    "product_recommendations": recommendation_agent
}

def extract_product_names(order_response):
    pattern = r"for the (.*?)[,.]|Product: (.*?)[,.]"
    matches = re.findall(pattern, order_response)
    return [match[0] or match[1] for match in matches if match[0] or match[1]]

def run_agents():
    print("Agents are ready to provide information about orders and product recommendations. Type 'exit' to end the conversation.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            print("Ending conversation.")
            break
        
        # Get the response from the Order History Agent
        order_response = agents["order_history"].chat(user_input)
        print("\nOrder History Agent:")
        print(f"Agent: {order_response.response}")
        
        # Pass the order history response to the Product Recommendations Agent
        print("\nProduct Recommendations Agent:")
        recommendation_input = f"Order History Agent's response: {order_response.response}\n\nProvide recommendations based on the products in this order history."
        recommendation_response = agents["product_recommendations"].chat(recommendation_input)
        print(recommendation_response.response)
        return recommendation_response.response

if __name__ == "__main__":
    print("Starting data scraping process...")
    scrape_result = scrape_and_store_data()
    print(scrape_result)
    
    print("Initializing vector database...")
    all_products = add_products_to_vector_db()
    
    print("Starting chat interface...")
    run_agents()