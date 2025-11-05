"""
Amazon Product Search Engine
"""
import pandas as pd
import numpy as np
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from difflib import SequenceMatcher

# Add src to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from utils.helpers import setup_logging, timing_decorator
from utils.config import PROCESSED_PRODUCTS_FILE, PROCESSED_RATINGS_FILE, SEARCH_CONFIG
from search.query_processor import SearchQuery, SearchFilter, ComparisonOperator, QueryProcessor

logger = setup_logging()


class AmazonSearchEngine:
    """Search engine for Amazon products with advanced query capabilities"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.query_processor = QueryProcessor()
        self.products_df = None
        self.ratings_df = None
        self.load_data()
        
    @timing_decorator
    def load_data(self):
        """Load processed data"""
        try:
            self.products_df = pd.read_parquet(PROCESSED_PRODUCTS_FILE)
            self.ratings_df = pd.read_parquet(PROCESSED_RATINGS_FILE)
            self.logger.info(f"Loaded {len(self.products_df)} products and {len(self.ratings_df)} ratings")
        except Exception as e:
            self.logger.error(f"Error loading data: {str(e)}")
            raise
    
    def search(self, query: SearchQuery) -> pd.DataFrame:
        """
        Execute a search query and return results
        
        Args:
            query: SearchQuery object containing search parameters
            
        Returns:
            DataFrame containing search results
        """
        # Start with all products
        results = self.products_df.copy()
        
        # Apply text search if provided
        if query.text_query:
            results = self._apply_text_search(results, query.text_query)
        
        # Apply filters
        for filter_obj in query.filters:
            results = self._apply_filter(results, filter_obj)
        
        # Sort results
        if query.sort_by:
            ascending = query.sort_order == 'asc'
            results = results.sort_values(by=query.sort_by, ascending=ascending)
        else:
            # Default sorting by relevance (avg_rating * num_reviews)
            if 'avg_rating' in results.columns and 'num_reviews' in results.columns:
                results['relevance_score'] = results['avg_rating'] * np.log1p(results['num_reviews'])
                results = results.sort_values('relevance_score', ascending=False)
        
        # Apply offset and limit
        if query.offset > 0:
            results = results.iloc[query.offset:]
        
        if query.limit:
            results = results.head(query.limit)
        
        return results
    
    def _apply_text_search(self, df: pd.DataFrame, text_query: str) -> pd.DataFrame:
        """Apply text-based search across title and description"""
        if not text_query:
            return df
        
        text_query = text_query.lower()
        search_columns = ['title', 'description', 'brand', 'category']
        
        # Create a combined text field for searching
        combined_text = df[search_columns].fillna('').apply(
            lambda x: ' '.join(x.values.astype(str)).lower(), axis=1
        )
        
        if SEARCH_CONFIG.get('enable_fuzzy_search', False):
            # Fuzzy search using similarity matching
            similarities = combined_text.apply(
                lambda x: self._calculate_text_similarity(text_query, x)
            )
            threshold = SEARCH_CONFIG.get('similarity_threshold', 0.3)
            mask = similarities >= threshold
            
            # Add similarity scores for ranking
            df_filtered = df[mask].copy()
            df_filtered['text_similarity'] = similarities[mask]
            return df_filtered.sort_values('text_similarity', ascending=False)
        else:
            # Exact substring matching
            mask = combined_text.str.contains(text_query, case=False, na=False)
            return df[mask]
    
    def _calculate_text_similarity(self, query: str, text: str) -> float:
        """Calculate similarity between query and text"""
        # Split into words and calculate overlap
        query_words = set(query.split())
        text_words = set(text.split())
        
        if not query_words:
            return 0.0
        
        # Jaccard similarity
        intersection = len(query_words.intersection(text_words))
        union = len(query_words.union(text_words))
        
        return intersection / union if union > 0 else 0.0
    
    def _apply_filter(self, df: pd.DataFrame, filter_obj: SearchFilter) -> pd.DataFrame:
        """Apply a single filter to the dataframe"""
        if filter_obj.field not in df.columns:
            return df
        
        column = df[filter_obj.field]
        
        if filter_obj.operator == ComparisonOperator.EQUALS:
            # For string fields, do case-insensitive comparison
            if column.dtype == 'object':  # String columns
                return df[column.str.lower() == str(filter_obj.value).lower()]
            else:
                return df[column == filter_obj.value]
        elif filter_obj.operator == ComparisonOperator.GREATER_THAN:
            return df[column > filter_obj.value]
        elif filter_obj.operator == ComparisonOperator.GREATER_EQUAL:
            return df[column >= filter_obj.value]
        elif filter_obj.operator == ComparisonOperator.LESS_THAN:
            return df[column < filter_obj.value]
        elif filter_obj.operator == ComparisonOperator.LESS_EQUAL:
            return df[column <= filter_obj.value]
        elif filter_obj.operator == ComparisonOperator.NOT_EQUAL:
            # For string fields, do case-insensitive comparison
            if column.dtype == 'object':  # String columns
                return df[column.str.lower() != str(filter_obj.value).lower()]
            else:
                return df[column != filter_obj.value]
        elif filter_obj.operator == ComparisonOperator.LIKE:
            # Case-insensitive pattern matching
            pattern = str(filter_obj.value).replace('%', '.*')
            return df[column.str.contains(pattern, case=False, na=False, regex=True)]
        elif filter_obj.operator == ComparisonOperator.IN:
            # Value should be a list for IN operator
            if isinstance(filter_obj.value, (list, tuple)):
                return df[column.isin(filter_obj.value)]
        
        return df
    
    def get_best_sellers(self, category: str = None, n: int = 10) -> pd.DataFrame:
        """
        Get best-selling products (highest rating * review count)
        
        Args:
            category: Optional category filter
            n: Number of results to return
            
        Returns:
            DataFrame with top-selling products
        """
        df = self.products_df.copy()
        
        if category:
            df = df[df['category'].str.contains(category, case=False, na=False)]
        
        # Calculate popularity score
        df['popularity_score'] = df['avg_rating'] * np.log1p(df['num_reviews'])
        
        return df.nlargest(n, 'popularity_score')[
            ['product_id', 'title', 'category', 'brand', 'price', 
             'avg_rating', 'num_reviews', 'popularity_score']
        ]
    
    def get_products_by_rating_range(self, min_rating: float, max_rating: float = 5.0) -> pd.DataFrame:
        """Get products within a specific rating range"""
        mask = (self.products_df['avg_rating'] >= min_rating) & (self.products_df['avg_rating'] <= max_rating)
        return self.products_df[mask]
    
    def get_products_by_price_range(self, min_price: float, max_price: float) -> pd.DataFrame:
        """Get products within a specific price range"""
        mask = (self.products_df['price'] >= min_price) & (self.products_df['price'] <= max_price)
        return self.products_df[mask]
    
    def search_by_category(self, category: str, limit: int = None) -> pd.DataFrame:
        """Search products by category"""
        mask = self.products_df['category'].str.contains(category, case=False, na=False)
        results = self.products_df[mask]
        
        if limit:
            results = results.head(limit)
            
        return results
    
    def get_category_statistics(self) -> Dict[str, Any]:
        """Get statistics by category"""
        stats = {}
        
        for category in self.products_df['category'].unique():
            cat_products = self.products_df[self.products_df['category'] == category]
            
            stats[category] = {
                'total_products': len(cat_products),
                'avg_price': cat_products['price'].mean(),
                'avg_rating': cat_products['avg_rating'].mean(),
                'total_reviews': cat_products['num_reviews'].sum(),
                'price_range': {
                    'min': cat_products['price'].min(),
                    'max': cat_products['price'].max()
                }
            }
        
        return stats
    
    def get_user_co_purchasing_stats(self, user_id: str) -> Dict[str, Any]:
        """Get co-purchasing statistics for a user"""
        user_ratings = self.ratings_df[self.ratings_df['user_id'] == user_id]
        
        if user_ratings.empty:
            return {'error': 'User not found'}
        
        user_products = user_ratings['product_id'].tolist()
        
        # Find other users who bought the same products
        co_purchasers = self.ratings_df[
            self.ratings_df['product_id'].isin(user_products) & 
            (self.ratings_df['user_id'] != user_id)
        ]['user_id'].value_counts()
        
        return {
            'user_id': user_id,
            'total_purchases': len(user_products),
            'co_purchasers_count': len(co_purchasers),
            'top_co_purchasers': co_purchasers.head(10).to_dict()
        }
    
    def advanced_search(self, 
                       text: str = None,
                       category: str = None,
                       min_price: float = None,
                       max_price: float = None,
                       min_rating: float = None,
                       brand: str = None,
                       sort_by: str = None,
                       sort_order: str = "asc",
                       limit: int = 20) -> pd.DataFrame:
        """
        Convenience method for advanced search with multiple parameters
        """
        query = self.query_processor.create_simple_query(
            text=text,
            category=category,
            min_price=min_price,
            max_price=max_price,
            min_rating=min_rating,
            brand=brand,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit
        )
        
        return self.search(query)
    
    def search_from_string(self, query_string: str) -> pd.DataFrame:
        """
        Search using a natural language query string
        
        Args:
            query_string: Natural language search query
            
        Returns:
            DataFrame with search results
        """
        query = self.query_processor.parse_query_string(query_string)
        return self.search(query)


def demo_search_engine():
    """Demonstrate search engine capabilities"""
    engine = AmazonSearchEngine()
    
    print("=== AMAZON SEARCH ENGINE DEMO ===\n")
    
    # 1. Simple text search
    print("1. Simple text search for 'electronics':")
    results = engine.advanced_search(text="electronics", limit=5)
    print(results[['title', 'category', 'price', 'avg_rating']].to_string())
    print()
    
    # 2. Category search
    print("2. Best sellers in Books category:")
    results = engine.get_best_sellers(category="Books", n=5)
    print(results[['title', 'price', 'avg_rating', 'num_reviews']].to_string())
    print()
    
    # 3. Price range search
    print("3. Products under $50:")
    results = engine.advanced_search(max_price=50, sort_by="price", limit=5)
    print(results[['title', 'category', 'price', 'avg_rating']].to_string())
    print()
    
    # 4. High-rated products
    print("4. High-rated products (>= 4.5):")
    results = engine.advanced_search(min_rating=4.5, sort_by="avg_rating", sort_order="desc", limit=5)
    print(results[['title', 'category', 'price', 'avg_rating']].to_string())
    print()
    
    # 5. Natural language search
    print("5. Natural language search 'books with price < 30':")
    results = engine.search_from_string("books with price < 30")
    print(f"Found {len(results)} results")
    if not results.empty:
        print(results[['title', 'category', 'price', 'avg_rating']].head().to_string())
    print()
    
    # 6. Category statistics
    print("6. Category statistics:")
    stats = engine.get_category_statistics()
    for category, stat in list(stats.items())[:3]:  # Show first 3 categories
        print(f"{category}: {stat['total_products']} products, avg price: ${stat['avg_price']:.2f}")


if __name__ == "__main__":
    demo_search_engine()