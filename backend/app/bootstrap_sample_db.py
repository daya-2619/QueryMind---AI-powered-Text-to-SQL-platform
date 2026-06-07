import sys
import os
import random
import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# Append parent directory of app/ to system path to support absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bootstrap_sample_db")

# Sample data
CITIES = ["Kolkata", "Mumbai", "Delhi", "Bengaluru", "Chennai", "New York", "London", "Tokyo"]
COUNTRIES = ["India", "India", "India", "India", "India", "USA", "UK", "Japan"]
CATEGORIES = ["Electronics", "Clothing", "Home & Kitchen", "Books", "Sports"]

FIRST_NAMES = ["Aarav", "Ananya", "John", "Sarah", "Yuki", "David", "Priya", "Rahul", "Emma", "Ken"]
LAST_NAMES = ["Sharma", "Das", "Smith", "Johnson", "Sato", "Miller", "Patel", "Kumar", "Jones", "Tanaka"]

PRODUCT_NAMES = {
    "Electronics": ["Smartphone X", "Wireless Headphones", "Laptop Pro", "Smart Watch", "Bluetooth Speaker"],
    "Clothing": ["Classic T-Shirt", "Denim Jacket", "Running Shoes", "Woolen Sweater", "Leather Belt"],
    "Home & Kitchen": ["Coffee Maker", "Air Fryer", "Chef Knife Set", "Blender Duo", "Ceramic Mug Set"],
    "Books": ["SQL Guidebook", "AI Revolution", "Mystery Novel", "Cookbook Masterclass", "Historical Biography"],
    "Sports": ["Yoga Mat", "Dumbbell Set", "Water Bottle", "Tennis Racket", "Running Socks"]
}

def get_db_engine():
    """Returns engine for the target database URL."""
    db_url = settings.TARGET_DATABASE_URL
    logger.info(f"Target Database URL: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        
    return create_engine(db_url, connect_args=connect_args)

def create_tables(engine):
    """Drops existing tables and creates new sample tables."""
    with engine.begin() as conn:
        logger.info("Dropping existing sample tables if any...")
        
        # Disable foreign key checks to prevent drop errors
        if engine.dialect.name == "sqlite":
            conn.execute(text("PRAGMA foreign_keys = OFF;"))
        elif engine.dialect.name == "postgresql":
            # For Postgres we can just run DROP TABLE ... CASCADE
            pass
            
        tables = ["reviews", "order_items", "orders", "products", "customers"]
        for t in tables:
            try:
                if engine.dialect.name == "postgresql":
                    conn.execute(text(f"DROP TABLE IF EXISTS {t} CASCADE;"))
                else:
                    conn.execute(text(f"DROP TABLE IF EXISTS {t};"))
            except Exception as e:
                logger.warning(f"Error dropping table {t}: {e}")

        logger.info("Creating tables...")

        # Create Customers table
        conn.execute(text("""
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                first_name VARCHAR(50) NOT NULL,
                last_name VARCHAR(50) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                city VARCHAR(50) NOT NULL,
                country VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Create Products table
        conn.execute(text("""
            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY,
                product_name VARCHAR(100) NOT NULL,
                category VARCHAR(50) NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                stock_quantity INTEGER NOT NULL
            );
        """))

        # Create Orders table
        conn.execute(text("""
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                order_date TIMESTAMP NOT NULL,
                total_amount DECIMAL(10, 2) NOT NULL,
                status VARCHAR(20) NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );
        """))

        # Create Order Items table
        conn.execute(text("""
            CREATE TABLE order_items (
                order_item_id INTEGER PRIMARY KEY,
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            );
        """))

        # Create Reviews table
        conn.execute(text("""
            CREATE TABLE reviews (
                review_id INTEGER PRIMARY KEY,
                product_id INTEGER,
                customer_id INTEGER,
                rating INTEGER CHECK (rating BETWEEN 1 AND 5),
                review_text TEXT,
                review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(product_id),
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );
        """))

        if engine.dialect.name == "sqlite":
            conn.execute(text("PRAGMA foreign_keys = ON;"))
            
        logger.info("Tables created successfully.")

def populate_data(engine):
    """Populates the database with realistic sample data."""
    # Seed for reproducibility
    random.seed(42)
    
    with engine.begin() as conn:
        logger.info("Inserting mock data...")
        
        # 1. Customers
        customers_data = []
        for i in range(1, 16):
            idx = random.randint(0, len(CITIES) - 1)
            city = CITIES[idx]
            country = COUNTRIES[idx]
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            email = f"{first_name.lower()}.{last_name.lower()}{i}@example.com"
            # Distribute signup dates over the last 18 months
            created_days_ago = random.randint(10, 540)
            signup_date = datetime.now() - timedelta(days=created_days_ago)
            
            customers_data.append({
                "customer_id": i,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "city": city,
                "country": country,
                "created_at": signup_date.strftime("%Y-%m-%d %H:%M:%S")
            })
            
            conn.execute(text("""
                INSERT INTO customers (customer_id, first_name, last_name, email, city, country, created_at)
                VALUES (:customer_id, :first_name, :last_name, :email, :city, :country, :created_at)
            """), customers_data[-1])

        # 2. Products
        products_data = []
        product_id_counter = 1
        for category in CATEGORIES:
            names = PRODUCT_NAMES[category]
            for name in names:
                price = round(random.uniform(10.0, 1200.0), 2)
                stock = random.randint(5, 150)
                p_item = {
                    "product_id": product_id_counter,
                    "product_name": name,
                    "category": category,
                    "price": price,
                    "stock_quantity": stock
                }
                products_data.append(p_item)
                
                conn.execute(text("""
                    INSERT INTO products (product_id, product_name, category, price, stock_quantity)
                    VALUES (:product_id, :product_name, :category, :price, :stock_quantity)
                """), p_item)
                
                product_id_counter += 1

        # 3. Orders & Order Items
        order_item_id_counter = 1
        for order_id in range(1, 31):
            customer = random.choice(customers_data)
            # Spread orders over the last 12 months
            days_ago = random.randint(1, 365)
            order_date = datetime.now() - timedelta(days=days_ago)
            status = random.choices(["Completed", "Shipped", "Pending", "Cancelled"], weights=[70, 15, 10, 5])[0]
            
            # Select 1 to 4 random products for this order
            num_products = random.randint(1, 4)
            ordered_products = random.sample(products_data, num_products)
            
            total_amount = 0.0
            order_items_to_insert = []
            
            for p in ordered_products:
                qty = random.randint(1, 3)
                unit_price = p["price"]
                item_total = round(unit_price * qty, 2)
                total_amount += item_total
                
                order_items_to_insert.append({
                    "order_item_id": order_item_id_counter,
                    "order_id": order_id,
                    "product_id": p["product_id"],
                    "quantity": qty,
                    "unit_price": unit_price
                })
                order_item_id_counter += 1
            
            total_amount = round(total_amount, 2)
            
            # Insert Order
            conn.execute(text("""
                INSERT INTO orders (order_id, customer_id, order_date, total_amount, status)
                VALUES (:order_id, :customer_id, :order_date, :total_amount, :status)
            """), {
                "order_id": order_id,
                "customer_id": customer["customer_id"],
                "order_date": order_date.strftime("%Y-%m-%d %H:%M:%S"),
                "total_amount": total_amount,
                "status": status
            })
            
            # Insert Order Items
            for item in order_items_to_insert:
                conn.execute(text("""
                    INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price)
                    VALUES (:order_item_id, :order_id, :product_id, :quantity, :unit_price)
                """), item)

        # 4. Reviews
        for review_id in range(1, 16):
            product = random.choice(products_data)
            customer = random.choice(customers_data)
            rating = random.randint(3, 5) # Mostly positive reviews
            review_text = random.choice([
                "Excellent product, highly recommended!",
                "Decent quality for the price.",
                "Met my expectations.",
                "Amazing customer support and fast delivery.",
                "Good, but could be improved.",
                "Absolutely love it!"
            ])
            days_ago = random.randint(1, 100)
            review_date = datetime.now() - timedelta(days=days_ago)
            
            conn.execute(text("""
                INSERT INTO reviews (review_id, product_id, customer_id, rating, review_text, review_date)
                VALUES (:review_id, :product_id, :customer_id, :rating, :review_text, :review_date)
            """), {
                "review_id": review_id,
                "product_id": product["product_id"],
                "customer_id": customer["customer_id"],
                "rating": rating,
                "review_text": review_text,
                "review_date": review_date.strftime("%Y-%m-%d %H:%M:%S")
            })
            
        logger.info("Mock data inserted successfully.")

def main():
    try:
        engine = get_db_engine()
        create_tables(engine)
        populate_data(engine)
        logger.info("Sample e-commerce database bootstrapped successfully!")
    except Exception as e:
        logger.error(f"Error bootstrapping database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
