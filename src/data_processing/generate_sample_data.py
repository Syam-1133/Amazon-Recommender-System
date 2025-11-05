"""
Sample data generator for Amazon Recommender System
Creates synthetic Amazon-like data for development and testing
"""
import json
import random
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.config import RAW_DATA_DIR, PROCESSED_DATA_DIR
from utils.helpers import setup_logging

logger = setup_logging()

# Sample data for generation
CATEGORIES = [
    "Books", "Electronics", "Movies & TV", "Music", "Home & Kitchen",
    "Sports & Outdoors", "Tools & Home Improvement", "Toys & Games",
    "Clothing, Shoes & Jewelry", "Health & Personal Care"
]

SUBCATEGORIES = {
    "Books": ["Fiction", "Non-fiction", "Children's Books", "Textbooks", "Comics"],
    "Electronics": ["Computers", "Cell Phones", "Cameras", "Audio & Video", "Gaming"],
    "Movies & TV": ["Action", "Comedy", "Drama", "Horror", "Documentary"],
    "Music": ["Rock", "Pop", "Classical", "Jazz", "Country"],
    "Home & Kitchen": ["Furniture", "Kitchen & Dining", "Bedding", "Bath", "Storage"],
}

BRANDS = [
    "Amazon", "Sony", "Apple", "Samsung", "Microsoft", "Nintendo", "Dell",
    "HP", "Canon", "Nikon", "KitchenAid", "Hamilton Beach", "Cuisinart"
]

SAMPLE_TITLES = [
    "The Great Adventure", "Ultimate Guide to Success", "Wireless Headphones",
    "Professional Camera", "Gaming Console", "Kitchen Mixer", "Smart Phone",
    "Laptop Computer", "Running Shoes", "Cooking Set", "Mystery Novel",
    "Science Textbook", "Action Movie", "Classical Music Collection"
]


def generate_product_data(num_products: int = 10000):
    """Generate synthetic product data"""
    logger.info(f"Generating {num_products} synthetic products")
    
    products = []
    
    for i in range(num_products):
        product_id = f"B{str(i).zfill(8)}"
        category = random.choice(CATEGORIES)
        subcategory = random.choice(SUBCATEGORIES.get(category, [category]))
        
        product = {
            "asin": product_id,
            "title": f"{random.choice(SAMPLE_TITLES)} {i+1}",
            "description": f"High-quality {subcategory.lower()} product with excellent features",
            "price": round(random.uniform(9.99, 999.99), 2),
            "brand": random.choice(BRANDS) if random.random() > 0.3 else None,
            "categories": [[category, subcategory]],
            "salesRank": {category: random.randint(1, 100000)} if random.random() > 0.5 else {},
            "imUrl": f"https://images.amazon.com/images/P/{product_id}.jpg",
            "related": {
                "also_bought": [f"B{str(random.randint(0, num_products-1)).zfill(8)}" 
                              for _ in range(random.randint(0, 5))],
                "also_viewed": [f"B{str(random.randint(0, num_products-1)).zfill(8)}" 
                              for _ in range(random.randint(0, 3))]
            }
        }
        
        products.append(product)
    
    return products


def generate_review_data(products: list, num_reviews: int = 50000):
    """Generate synthetic review data"""
    logger.info(f"Generating {num_reviews} synthetic reviews")
    
    reviews = []
    user_ids = [f"A{str(i).zfill(10)}" for i in range(1000)]  # 1000 unique users
    
    for i in range(num_reviews):
        product = random.choice(products)
        user_id = random.choice(user_ids)
        
        # Generate ratings with realistic distribution (skewed toward higher ratings)
        rating = np.random.choice([1, 2, 3, 4, 5], p=[0.05, 0.05, 0.15, 0.35, 0.40])
        
        review = {
            "reviewerID": user_id,
            "asin": product["asin"],
            "reviewerName": f"Customer_{user_id[-4:]}",
            "helpful": [random.randint(0, 10), random.randint(0, 15)],
            "reviewText": f"This is a {'great' if rating >= 4 else 'okay' if rating >= 3 else 'poor'} product. "
                         f"{'Highly recommend!' if rating >= 4 else 'Could be better.' if rating >= 3 else 'Not satisfied.'}",
            "overall": float(rating),
            "summary": f"{'Excellent' if rating >= 4 else 'Good' if rating >= 3 else 'Poor'} product",
            "unixReviewTime": random.randint(1000000000, 1600000000),  # Random timestamp
            "reviewTime": f"{random.randint(1, 12):02d} {random.randint(1, 28)}, {random.randint(2015, 2023)}"
        }
        
        reviews.append(review)
    
    return reviews


def save_sample_data():
    """Generate and save sample data"""
    logger.info("Starting sample data generation")
    
    # Generate products
    products = generate_product_data(5000)  # Start with 5000 products
    
    # Save products as JSON lines format (common for Amazon datasets)
    products_file = RAW_DATA_DIR / "sample_products.json"
    with open(products_file, 'w') as f:
        for product in products:
            f.write(json.dumps(product) + '\n')
    
    logger.info(f"Saved {len(products)} products to {products_file}")
    
    # Generate reviews
    reviews = generate_review_data(products, 25000)  # 25000 reviews
    
    # Save reviews as JSON lines format
    reviews_file = RAW_DATA_DIR / "sample_reviews.json"
    with open(reviews_file, 'w') as f:
        for review in reviews:
            f.write(json.dumps(review) + '\n')
    
    logger.info(f"Saved {len(reviews)} reviews to {reviews_file}")
    
    # Create processed versions as DataFrames
    products_df = pd.DataFrame(products)
    reviews_df = pd.DataFrame(reviews)
    
    # Flatten categories for easier processing
    products_df['main_category'] = products_df['categories'].apply(
        lambda x: x[0][0] if x and len(x) > 0 and len(x[0]) > 0 else "Unknown"
    )
    products_df['sub_category'] = products_df['categories'].apply(
        lambda x: x[0][1] if x and len(x) > 0 and len(x[0]) > 1 else "Unknown"
    )
    
    # Save processed data
    products_df.to_parquet(PROCESSED_DATA_DIR / "sample_products.parquet")
    reviews_df.to_parquet(PROCESSED_DATA_DIR / "sample_reviews.parquet")
    
    logger.info("Sample data generation completed")
    
    # Print summary statistics
    print(f"\nDataset Summary:")
    print(f"Products: {len(products)}")
    print(f"Reviews: {len(reviews)}")
    print(f"Unique users: {reviews_df['reviewerID'].nunique()}")
    print(f"Average rating: {reviews_df['overall'].mean():.2f}")
    print(f"Categories: {', '.join(products_df['main_category'].unique())}")


if __name__ == "__main__":
    save_sample_data()