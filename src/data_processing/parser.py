"""
Amazon data parser and preprocessor
"""
import pandas as pd
import numpy as np
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add src to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from utils.helpers import setup_logging, timing_decorator, validate_dataframe
from utils.config import (
    RAW_DATA_DIR, PROCESSED_DATA_DIR, 
    SAMPLE_PRODUCTS_FILE, SAMPLE_RATINGS_FILE,
    PROCESSED_PRODUCTS_FILE, PROCESSED_RATINGS_FILE
)

logger = setup_logging()


class AmazonDataParser:
    """Parser for Amazon product and rating data"""
    
    def __init__(self):
        self.logger = setup_logging()
        
    @timing_decorator
    def create_sample_data(self):
        """Create sample Amazon-like data for development"""
        self.logger.info("Creating sample Amazon data...")
        
        # Create sample products data
        np.random.seed(42)
        n_products = 10000
        
        categories = ['Books', 'Electronics', 'Clothing', 'Home', 'Sports', 'Movies', 'Music']
        brands = ['Amazon', 'Apple', 'Samsung', 'Nike', 'Sony', 'Microsoft', 'Google'] + [f'Brand_{i}' for i in range(20)]
        
        products_data = {
            'product_id': [f'B{str(i).zfill(9)}' for i in range(n_products)],
            'title': [f'Product Title {i}' for i in range(n_products)],
            'category': np.random.choice(categories, n_products),
            'brand': np.random.choice(brands, n_products),
            'price': np.random.uniform(5.99, 299.99, n_products).round(2),
            'avg_rating': np.random.uniform(1.0, 5.0, n_products).round(1),
            'num_reviews': np.random.poisson(50, n_products),
            'description': [f'This is a great product in category {cat}' 
                          for cat in np.random.choice(categories, n_products)],
            'sales_rank': np.random.randint(1, 100000, n_products)
        }
        
        products_df = pd.DataFrame(products_data)
        products_df.to_csv(SAMPLE_PRODUCTS_FILE, index=False)
        self.logger.info(f"Created sample products data: {SAMPLE_PRODUCTS_FILE}")
        
        # Create sample ratings data
        n_users = 2000
        n_ratings = 50000
        
        ratings_data = {
            'user_id': np.random.choice([f'U{str(i).zfill(7)}' for i in range(n_users)], n_ratings),
            'product_id': np.random.choice(products_df['product_id'], n_ratings),
            'rating': np.random.choice([1, 2, 3, 4, 5], n_ratings, p=[0.05, 0.1, 0.2, 0.35, 0.3]),
            'timestamp': np.random.randint(1000000000, 1700000000, n_ratings)
        }
        
        ratings_df = pd.DataFrame(ratings_data)
        # Remove duplicates (same user rating same product multiple times)
        ratings_df = ratings_df.drop_duplicates(subset=['user_id', 'product_id'])
        ratings_df.to_csv(SAMPLE_RATINGS_FILE, index=False)
        self.logger.info(f"Created sample ratings data: {SAMPLE_RATINGS_FILE}")
        
        return products_df, ratings_df
    
    @timing_decorator
    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load or create sample data"""
        try:
            # Try to load existing data
            if SAMPLE_PRODUCTS_FILE.exists() and SAMPLE_RATINGS_FILE.exists():
                self.logger.info("Loading existing sample data...")
                products_df = pd.read_csv(SAMPLE_PRODUCTS_FILE)
                ratings_df = pd.read_csv(SAMPLE_RATINGS_FILE)
            else:
                self.logger.info("Sample data not found. Creating new data...")
                products_df, ratings_df = self.create_sample_data()
                
            self.logger.info(f"Loaded products: {len(products_df):,} rows")
            self.logger.info(f"Loaded ratings: {len(ratings_df):,} rows")
            
            return products_df, ratings_df
            
        except Exception as e:
            self.logger.error(f"Error loading data: {str(e)}")
            raise
    
    @timing_decorator
    def clean_products_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate products data"""
        self.logger.info("Cleaning products data...")
        
        # Required columns
        required_cols = ['product_id', 'title', 'category']
        if not validate_dataframe(df, required_cols):
            raise ValueError(f"Missing required columns: {required_cols}")
        
        # Clean data
        df = df.copy()
        
        # Remove duplicates
        initial_count = len(df)
        df = df.drop_duplicates(subset=['product_id'])
        self.logger.info(f"Removed {initial_count - len(df)} duplicate products")
        
        # Clean text fields
        text_columns = ['title', 'description', 'brand']
        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].replace('nan', '')
        
        # Clean numeric fields
        if 'price' in df.columns:
            df['price'] = pd.to_numeric(df['price'], errors='coerce')
            df = df[df['price'] > 0]  # Remove invalid prices
        
        if 'avg_rating' in df.columns:
            df['avg_rating'] = pd.to_numeric(df['avg_rating'], errors='coerce')
            df['avg_rating'] = df['avg_rating'].clip(1.0, 5.0)  # Ensure ratings are in valid range
        
        if 'num_reviews' in df.columns:
            df['num_reviews'] = pd.to_numeric(df['num_reviews'], errors='coerce').fillna(0).astype(int)
        
        # Create price ranges
        if 'price' in df.columns:
            df['price_range'] = pd.cut(df['price'], 
                                     bins=[0, 20, 50, 100, 200, float('inf')],
                                     labels=['Under $20', '$20-50', '$50-100', '$100-200', 'Over $200'])
        
        self.logger.info(f"Cleaned products data: {len(df)} rows remaining")
        return df
    
    @timing_decorator
    def clean_ratings_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate ratings data"""
        self.logger.info("Cleaning ratings data...")
        
        # Required columns
        required_cols = ['user_id', 'product_id', 'rating']
        if not validate_dataframe(df, required_cols):
            raise ValueError(f"Missing required columns: {required_cols}")
        
        # Clean data
        df = df.copy()
        
        # Remove duplicates (keep latest rating)
        if 'timestamp' in df.columns:
            df = df.sort_values('timestamp').drop_duplicates(subset=['user_id', 'product_id'], keep='last')
        else:
            df = df.drop_duplicates(subset=['user_id', 'product_id'])
        
        # Ensure valid ratings
        df['rating'] = pd.to_numeric(df['rating'], errors='coerce')
        df = df[(df['rating'] >= 1) & (df['rating'] <= 5)]
        
        # Remove users/items with too few interactions
        min_interactions = 5
        
        # Count interactions per user and product
        user_counts = df['user_id'].value_counts()
        product_counts = df['product_id'].value_counts()
        
        # Filter users and products with sufficient interactions
        valid_users = user_counts[user_counts >= min_interactions].index
        valid_products = product_counts[product_counts >= min_interactions].index
        
        df = df[df['user_id'].isin(valid_users) & df['product_id'].isin(valid_products)]
        
        self.logger.info(f"Cleaned ratings data: {len(df)} ratings, "
                        f"{df['user_id'].nunique()} users, {df['product_id'].nunique()} products")
        
        return df
    
    @timing_decorator
    def process_and_save_data(self):
        """Process and save cleaned data"""
        # Load raw data
        products_df, ratings_df = self.load_data()
        
        # Clean data
        clean_products = self.clean_products_data(products_df)
        clean_ratings = self.clean_ratings_data(ratings_df)
        
        # Filter products to only include those with ratings
        rated_products = clean_ratings['product_id'].unique()
        clean_products = clean_products[clean_products['product_id'].isin(rated_products)]
        
        # Save processed data
        clean_products.to_parquet(PROCESSED_PRODUCTS_FILE, index=False)
        clean_ratings.to_parquet(PROCESSED_RATINGS_FILE, index=False)
        
        self.logger.info(f"Saved processed products to: {PROCESSED_PRODUCTS_FILE}")
        self.logger.info(f"Saved processed ratings to: {PROCESSED_RATINGS_FILE}")
        
        return clean_products, clean_ratings
    
    def get_data_statistics(self, products_df: pd.DataFrame, ratings_df: pd.DataFrame):
        """Print data statistics"""
        print("\n=== DATA STATISTICS ===")
        print(f"Products: {len(products_df):,}")
        print(f"Ratings: {len(ratings_df):,}")
        print(f"Users: {ratings_df['user_id'].nunique():,}")
        print(f"Categories: {products_df['category'].nunique()}")
        print(f"Average rating: {ratings_df['rating'].mean():.2f}")
        print(f"Rating distribution:")
        print(ratings_df['rating'].value_counts().sort_index())
        print(f"\nTop categories:")
        print(products_df['category'].value_counts().head())
        if 'price' in products_df.columns:
            print(f"\nPrice statistics:")
            print(products_df['price'].describe())


def main():
    """Main function to process Amazon data"""
    parser = AmazonDataParser()
    
    try:
        # Process data
        products_df, ratings_df = parser.process_and_save_data()
        
        # Show statistics
        parser.get_data_statistics(products_df, ratings_df)
        
        logger.info("Data processing completed successfully")
        
    except Exception as e:
        logger.error(f"Error processing data: {str(e)}")
        raise


if __name__ == "__main__":
    main()