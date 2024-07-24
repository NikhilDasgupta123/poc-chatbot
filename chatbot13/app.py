from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from utils.database import Base, engine
from utils.scraper import scrape_and_store_data
from utils.vector_db import add_products_to_vector_db
from utils.agents import order_agent, product_query_agent, recommendation_agent, customer_service_agent

load_dotenv()

app = Flask(__name__)

# Initialize the database and vector database
Base.metadata.create_all(engine)
print("1. Starting data scraping process...")
scrape_result = scrape_and_store_data()
print(scrape_result)
print("\n2. Data stored in Product table database.")
print("\n3. Initializing vector database...")
add_products_to_vector_db()
print("Data stored in vector database.")

@app.route('/')
def index():
    return render_template('index.html')

def run_agents(user_input):
    # Get the response from the Order History Agent
    order_response = order_agent.chat(user_input)
    order_history = order_response.response
    
    # Get the response from the Product Query Agent
    product_query_response = product_query_agent.chat(user_input)
    product_specs = product_query_response.response
    
    # Pass the order history response to the Product Recommendations Agent
    recommendation_input = f"Order History Agent's response: {order_history}\n\nProvide recommendations based on the products in this order history."
    recommendation_response = recommendation_agent.chat(recommendation_input)
    recommendations_raw = recommendation_response.response

   # Split the recommendations into separate components
    recommendations = []
    lines = recommendations_raw.split('\n')
    current_recommendation = {}
    
    for line in lines:
        line = line.strip()
        if line.startswith(('1.', '2.')):
            if current_recommendation:
                recommendations.append(current_recommendation)
            current_recommendation = {'name': line.split('. ', 1)[1] if '. ' in line else line}
        elif ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            if key == 'name':
                current_recommendation['name'] = value
            elif key == 'price':
                current_recommendation['price'] = value
            elif key in ['image url', 'image']:
                if value.startswith('[Image]'):
                    current_recommendation['image_url'] = value.split('(')[1].rstrip(')')
                else:
                    current_recommendation['image_url'] = value

    if current_recommendation:
        recommendations.append(current_recommendation)
    
    # Remove any recommendations without a name
    recommendations = [r for r in recommendations if 'name' in r]
    
    print(recommendations)

    # Get the response from the Customer Service Agent
    customer_service_response = customer_service_agent.chat(user_input)
    customer_service_info = customer_service_response.response

    return order_history, product_specs, recommendations,customer_service_info
    


@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message', '')
    
    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    # Run the agents
    order_history, product_specs, recommendations,customer_service = run_agents(user_input)

    response = {
        "order_history": order_history,
        "product_specs": product_specs,
        "recommendations": recommendations,
        "customer_service":customer_service
    }

    return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True)