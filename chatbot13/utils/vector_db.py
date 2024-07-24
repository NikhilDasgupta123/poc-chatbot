from sentence_transformers import SentenceTransformer
import faiss
from sqlalchemy.exc import SQLAlchemyError
from utils.database import Session, Product

# Initialize sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize FAISS index
dimension = 384
index = faiss.IndexFlatIP(dimension)

# Global variable to store all products
all_products = []

def add_products_to_vector_db():
    global all_products
    session = Session()
    try:
        products = session.query(Product).all()
        product_texts = [f"{p.name} " for p in products]
        embeddings = model.encode(product_texts)
        
        faiss.normalize_L2(embeddings)
        
        index.add(embeddings)
        all_products = products
        print(f"Added {len(products)} products to the vector database.")
        return products
    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return []
    finally:
        session.close()

def get_product_recommendations(product_name, limit=2):
    try:
        user_embedding = model.encode([product_name])
        faiss.normalize_L2(user_embedding)
        
        D, I = index.search(user_embedding, limit)
        
        recommendations = [f"Here are the top 2 product recommendations similar to {product_name}:"]
        for i, idx in enumerate(I[0], 1):
            product = all_products[idx]
            similarity_score = D[0][i-1]
            recommendations.append(f"{i}. Name: {product.name}, Price: ${product.price:.2f}, "
                                   f"Image URL: {product.image_url}, ")
        
        return "\n".join(recommendations)
    except Exception as e:
        return f"Error: {str(e)}"