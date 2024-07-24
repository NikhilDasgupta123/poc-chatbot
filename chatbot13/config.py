import os

# Database Config
db_user = "root"
db_password = "1234"
db_host = "localhost"
db_name = "ShopperAssistant"

DATABASE_URL = f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}/{db_name}"

# LLM configuration
llm_config = {
    "engine": "azoai-deploy-gpt35t",
    "model": "gpt-3.5-turbo",
    "temperature": 0.0,
    "azure_endpoint": "https://oai-ecirkle-dev-01.openai.azure.com/",
    "api_key": os.getenv("OPENAI_API_KEY"),
    "api_version": "2024-02-01",
}