import requests
from bs4 import BeautifulSoup
import pandas as pd
import random
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from utils.database import Session, Product

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
            elif column_name == "Product Name":
                links = soup.find_all("a", class_=class_name)
                data_dict[column_name] = [link.get_text() for link in links]
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
    base_urls = [
        "https://www.flipkart.com/mobile-accessories/samsung~brand/pr?sid=tyy%2C4mr",
        "https://www.flipkart.com/mobile-accessories/samsung~brand/pr?sid=tyy,4mr",
        "https://www.flipkart.com/mobile-accessories/samsung~brand/pr?sid=tyy,4mr&otracker=categorytree&sort=relevance&start_url=BrowserLaunch_AMP"
    ]
    class_dict = {
        "wjcEIp": "Product Name",
        "Nx9bqj": "Product Price",
        "XQDdHH": "Product Review",
        "DByuf4": "Image URL"
    }
    
    all_products = pd.DataFrame()
    
    for url in base_urls:
        df = stripped_webpage_to_dataframe(url, class_dict)
        # Limit to 4 products per URL
        df = df.head(4)
        all_products = pd.concat([all_products, df], ignore_index=True)
        print(f"Scraped 4 products from {url}")
    
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
    
    return f"Scraped {len(base_urls)} URLs, added {new_products_count} new products."