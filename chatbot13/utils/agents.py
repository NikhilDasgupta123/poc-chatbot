from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.core.memory import ChatMemoryBuffer
import re
from config import llm_config
from utils.database import Session, Customer, Order, ProductOrder
from utils.vector_db import get_product_recommendations
from sqlalchemy import and_

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
    except Exception as e:
        return f"Database error: {str(e)}"
    finally:
        session.close()




def get_customer_service_info(query_type, order_id=None):
    session = Session()
    try:
        if query_type == "return_policy":
            return "Our return policy allows returns within 30 days of purchase for a full refund."
        elif query_type == "refund_status" and order_id:
            order = session.query(Order).filter(Order.order_id == order_id).first()
            if order:
                if order.status == "Refunded":
                    return f"The refund for order {order_id} has been processed."
                else:
                    return f"No refund has been processed for order {order_id}."
            else:
                return f"Order {order_id} not found."
        elif query_type == "order_status" and order_id:
            order = session.query(Order).filter(Order.order_id == order_id).first()
            if order:
                return f"The status of order {order_id} is: {order.status}"
            else:
                return f"Order {order_id} not found."
        else:
            return "I'm sorry, I couldn't find the information you're looking for."
    except Exception as e:
        return f"An error occurred: {str(e)}"
    finally:
        session.close()



def get_product_specs():
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
        
        product_specs = []
        for order in orders:
            product_specs.append(f"Product ID: {order.product.product_id}, "
                                 f"Product Name: {order.product.product_name}, "
                                 f"Product Price: {order.product.price}, "
                                 f"Product Specifications: {order.product.specifications}, ")
        
        return "\n".join(product_specs)
    except Exception as e:
        return f"Database error: {str(e)}"
    finally:
        session.close()




get_john_doe_orders_tool = FunctionTool.from_defaults(fn=get_john_doe_orders)
get_product_recommendations_tool = FunctionTool.from_defaults(
    fn=get_product_recommendations,
    name="get_product_recommendations",
    description="Get product recommendations based on a product name"
)

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

get_product_specs_tool = FunctionTool.from_defaults(fn=get_product_specs)



product_query_system_message = """You are a Product Query Agent specialized in providing information about product specifications.

Your primary function is to retrieve and present product specifications for items in the database.

When interacting with users:
- Use the get_product_specs function to retrieve product specifications. You can provide a product name as an argument, or leave it empty to get all products.
- If asked about a specific product, use that product name as an argument to get_product_specs.
- If asked about all products, call get_product_specs without arguments.
- Present the information clearly, separating details for each product if multiple are returned.
- If no products are found, inform the user politely.
- If a user's query is unclear, ask for clarification to ensure you provide the most relevant information.

Your goal is to assist users in understanding the specifications of products in the database."""

product_query_agent = ReActAgent.from_tools(
    [get_product_specs_tool], 
    llm=AzureOpenAI(**llm_config),
    memory=ChatMemoryBuffer.from_defaults(token_limit=1500),
    verbose=True,
    system_prompt=product_query_system_message
)

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
[List the top 2 recommendations with name, price, and image URL]

Maintain this format for each product found in the order history.

Your goal is to provide relevant product recommendations based on the products in the customer's order history. Always include the name, price, and image URL for each recommended product."""

recommendation_agent = ReActAgent.from_tools(
    [get_product_recommendations_tool], 
    llm=AzureOpenAI(**llm_config),
    memory=ChatMemoryBuffer.from_defaults(token_limit=1500),
    verbose=True,
    system_prompt=recommendation_system_message
)





get_customer_service_info_tool = FunctionTool.from_defaults(
    fn=get_customer_service_info,
    name="get_customer_service_info",
    description="Get customer service information such as return policy, refund status, or order status"
)

customer_service_system_message = """You are a Customer Service Agent specialized in handling return, refund, and other customer service inquiries.

Your primary functions are:
1. Provide information about the return policy.
2. Check the status of refunds for specific orders.
3. Check the status of orders.
4. Handle general customer service inquiries.

When interacting with users:
- For return policy inquiries, use the get_customer_service_info function with "return_policy" as the query_type.
- For refund status inquiries, use the get_customer_service_info function with "refund_status" as the query_type and provide the order_id.
- For order status inquiries, use the get_customer_service_info function with "order_status" as the query_type and provide the order_id.
- For other inquiries, try to provide helpful information based on the available data.
- If a user's query is unclear, ask for clarification to ensure you provide the most relevant information.

Your goal is to assist users with their customer service needs efficiently and accurately."""

customer_service_agent = ReActAgent.from_tools(
    [get_customer_service_info_tool], 
    llm=AzureOpenAI(**llm_config),
    memory=ChatMemoryBuffer.from_defaults(token_limit=1500),
    verbose=True,
    system_prompt=customer_service_system_message
)




# Update the agents dictionary
agents = {
    "order_history": order_agent,
    "product_query": product_query_agent,
    "product_recommendations": recommendation_agent,
    "customer_service":customer_service_agent
}

def extract_product_names(order_response):
    pattern = r"for the (.*?)[,.]|Product: (.*?)[,.]"
    matches = re.findall(pattern, order_response)
    return [match[0] or match[1] for match in matches if match[0] or match[1]]

def run_agents():
    print("Agents are ready to provide information about orders, product specifications, and product recommendations. Type 'exit' to end the conversation.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            print("Ending conversation.")
            break
        
        # Get the response from the Order History Agent
        order_response = agents["order_history"].chat(user_input)
        print("\nOrder History Agent:")
        print(f"Agent: {order_response.response}")
        
        # Get the response from the Product Query Agent
        product_query_response = agents["product_query"].chat(user_input)
        print("\nProduct Query Agent:")
        print(f"Agent: {product_query_response.response}")
        
        # Pass the order history response to the Product Recommendations Agent
        print("\nProduct Recommendations Agent:")
        recommendation_input = f"Order History Agent's response: {order_response.response}\n\nProvide recommendations based on the products in this order history."
        recommendation_response = agents["product_recommendations"].chat(recommendation_input)
        print(recommendation_response.response)

