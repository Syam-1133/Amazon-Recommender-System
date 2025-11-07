"""
Advanced Amazon Product Search Engine
Supports complex queries with mathematical operators as required by the course project
"""
import pandas as pd
import numpy as np
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from difflib import SequenceMatcher
import operator

# Add src to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from utils.helpers import setup_logging, timing_decorator
from utils.config import PROCESSED_DATA_DIR, SEARCH_CONFIG

logger = setup_logging()


class SearchOperator:
    """Mathematical and comparison operators for search queries"""
    OPERATORS = {
        '>': operator.gt,
        '>=': operator.ge,
        '=': operator.eq,
        '==': operator.eq,
        '<': operator.lt,
        '<=': operator.le,
        '!=': operator.ne,
        'contains': lambda x, y: str(y).lower() in str(x).lower(),
        'startswith': lambda x, y: str(x).lower().startswith(str(y).lower()),
        'endswith': lambda x, y: str(x).lower().endswith(str(y).lower())
    }


class AmazonSearchEngine:
    """
    Advanced search engine for Amazon products with mathematical operators and complex queries
    
    Supports queries like:
    - Best n sellers of a certain category
    - Products with rating >= 4.5
    - Number of reviews > 100
    - Co-purchasing patterns analysis
    """
    
    def __init__(self):
        self.logger = setup_logging()
        self.products_df = None
        self.reviews_df = None
        self.categories_df = None
        self.similar_products_df = None
        self.load_data()
        
    @timing_decorator
    def load_data(self):
        """Load processed CSV data"""
        try:
            # Load all processed data files
            self.products_df = pd.read_csv(PROCESSED_DATA_DIR / "amazon_products.csv")
            self.reviews_df = pd.read_csv(PROCESSED_DATA_DIR / "amazon_reviews.csv")
            self.categories_df = pd.read_csv(PROCESSED_DATA_DIR / "amazon_categories.csv")
            self.similar_products_df = pd.read_csv(PROCESSED_DATA_DIR / "amazon_similar_products.csv")
            
            self.logger.info(f"Loaded {len(self.products_df):,} products")
            self.logger.info(f"Loaded {len(self.reviews_df):,} reviews")
            self.logger.info(f"Loaded {len(self.categories_df):,} category entries")
            self.logger.info(f"Loaded {len(self.similar_products_df):,} similar product relationships")
            
            # Create derived data for better search performance
            self._prepare_search_indices()
            
        except Exception as e:
            self.logger.error(f"Error loading data: {str(e)}")
            raise
    
    def _prepare_search_indices(self):
        """Prepare search indices and derived data"""
        try:
            # Add main category to products from categories data
            main_categories = self.categories_df.groupby('product_id')['category_path'].first().reset_index()
            main_categories['main_category'] = main_categories['category_path'].str.split(' > ').str[0]
            
            # Merge with products
            self.products_df = self.products_df.merge(
                main_categories[['product_id', 'main_category']], 
                left_on='id', 
                right_on='product_id', 
                how='left'
            )
            
            # Create search text for full-text search
            self.products_df['search_text'] = (
                self.products_df['title'].fillna('') + ' ' +
                self.products_df['group'].fillna('') + ' ' +
                self.products_df['main_category'].fillna('')
            ).str.lower()
            
            # Handle missing values
            self.products_df['avg_rating'] = self.products_df['avg_rating'].fillna(0)
            self.products_df['total_reviews'] = self.products_df['total_reviews'].fillna(0)
            self.products_df['salesrank'] = self.products_df['salesrank'].fillna(float('inf'))
            
            self.logger.info("Search indices prepared successfully")
            
        except Exception as e:
            self.logger.error(f"Error preparing search indices: {str(e)}")
    
    def search_best_sellers(self, category: str = None, n: int = 10) -> pd.DataFrame:
        """
        Find best n sellers of a certain category
        
        Args:
            category: Product category (Book, Music, DVD, Video) or None for all
            n: Number of top sellers to return
            
        Returns:
            DataFrame with top selling products
        """
        df = self.products_df.copy()
        
        # Filter by category if specified
        if category:
            if category.lower() in ['book', 'books']:
                df = df[df['group'].str.lower() == 'book']
            elif category.lower() in ['music', 'cd', 'cds']:
                df = df[df['group'].str.lower() == 'music']
            elif category.lower() in ['dvd', 'dvds']:
                df = df[df['group'].str.lower() == 'dvd']
            elif category.lower() in ['video', 'videos']:
                df = df[df['group'].str.lower() == 'video']
            else:
                # Try to match main category
                df = df[df['main_category'].str.contains(category, case=False, na=False)]
        
        # Sort by sales rank (lower is better) and get top n
        # Exclude products without valid sales rank (inf, NaN, negative values)
        df = df[
            (df['salesrank'] != float('inf')) & 
            (df['salesrank'] > 0) & 
            (df['salesrank'].notna())
        ]
        df = df.sort_values('salesrank').head(n)
        
        return df[['id', 'asin', 'title', 'group', 'salesrank', 'avg_rating', 'total_reviews']]
    
    def get_best_sellers(self, category: str = None, n: int = 10) -> pd.DataFrame:
        """
        Wrapper method for web app compatibility - gets best sellers with formatted columns
        
        Args:
            category: Product category or None for all
            n: Number of top sellers to return
            
        Returns:
            DataFrame with properly formatted columns for web app
        """
        # Get results from the main search method
        results = self.search_best_sellers(category=category, n=n)
        
        if results.empty:
            return results
        
        # Map columns to what the web app expects
        formatted_results = results.copy()
        formatted_results = formatted_results.rename(columns={
            'id': 'product_id',
            'group': 'category',
            'total_reviews': 'num_reviews'
        })
        
        # Add missing columns with default values
        formatted_results['brand'] = formatted_results.get('brand', '')
        formatted_results['price'] = formatted_results.get('price', 0.0)
        formatted_results['popularity_score'] = formatted_results['salesrank'].apply(
            lambda x: max(0, (1000000 - x) / 10000) if x != float('inf') else 0
        )
        
        return formatted_results
    
    def search_by_rating(self, operator_str: str, rating_value: float, limit: int = 100) -> pd.DataFrame:
        """
        Search products with rating comparison
        
        Args:
            operator_str: Comparison operator (>, >=, =, <, <=)
            rating_value: Rating value to compare against
            limit: Maximum number of results
            
        Returns:
            DataFrame with matching products
        """
        if operator_str not in SearchOperator.OPERATORS:
            raise ValueError(f"Unsupported operator: {operator_str}")
        
        df = self.products_df.copy()
        op_func = SearchOperator.OPERATORS[operator_str]
        
        # Apply rating filter
        mask = op_func(df['avg_rating'], rating_value)
        df = df[mask]
        
        # Sort by rating descending and limit results
        df = df.sort_values('avg_rating', ascending=False).head(limit)
        
        return df[['id', 'asin', 'title', 'group', 'avg_rating', 'total_reviews', 'salesrank']]
    
    def search_by_review_count(self, operator_str: str, review_count: int, limit: int = 100) -> pd.DataFrame:
        """
        Search products by number of reviews
        
        Args:
            operator_str: Comparison operator (>, >=, =, <, <=)
            review_count: Number of reviews to compare against
            limit: Maximum number of results
            
        Returns:
            DataFrame with matching products
        """
        if operator_str not in SearchOperator.OPERATORS:
            raise ValueError(f"Unsupported operator: {operator_str}")
        
        df = self.products_df.copy()
        op_func = SearchOperator.OPERATORS[operator_str]
        
        # Apply review count filter
        mask = op_func(df['total_reviews'], review_count)
        df = df[mask]
        
        # Sort by review count descending and limit results
        df = df.sort_values('total_reviews', ascending=False).head(limit)
        
        return df[['id', 'asin', 'title', 'group', 'total_reviews', 'avg_rating', 'salesrank']]
    
    def search_co_purchasing_users(self, product_asin: str) -> Dict[str, Any]:
        """
        Find customers who co-purchased same products as a given product
        
        Args:
            product_asin: ASIN of the product to analyze
            
        Returns:
            Dictionary with co-purchasing analysis
        """
        # Find similar products for the given ASIN
        similar_products = self.similar_products_df[
            self.similar_products_df['product_asin'] == product_asin
        ]['similar_asin'].tolist()
        
        if not similar_products:
            return {
                'product_asin': product_asin,
                'similar_products_count': 0,
                'co_purchasing_users': 0,
                'similar_products': []
            }
        
        # Find customers who reviewed the original product
        original_reviewers = self.reviews_df[
            self.reviews_df['product_asin'] == product_asin
        ]['customer_id'].unique()
        
        # Find customers who also reviewed similar products
        similar_reviewers = self.reviews_df[
            self.reviews_df['product_asin'].isin(similar_products)
        ]['customer_id'].unique()
        
        # Find intersection (co-purchasing users)
        co_purchasing_users = set(original_reviewers) & set(similar_reviewers)
        
        return {
            'product_asin': product_asin,
            'similar_products_count': len(similar_products),
            'co_purchasing_users': len(co_purchasing_users),
            'similar_products': similar_products[:10],  # Top 10 similar products
            'total_original_reviewers': len(original_reviewers),
            'total_similar_reviewers': len(similar_reviewers)
        }
    
    def advanced_search(self, query_params: Dict[str, Any]) -> pd.DataFrame:
        """
        Execute advanced search with multiple criteria
        
        Args:
            query_params: Dictionary containing search parameters
                - text: Text search in title/category
                - category: Product category filter
                - rating_op: Rating operator (>, >=, =, <, <=)
                - rating_value: Rating value
                - reviews_op: Reviews count operator
                - reviews_value: Reviews count value
                - limit: Maximum results
                
        Returns:
            DataFrame with search results
        """
        df = self.products_df.copy()
        
        # Text search
        if 'text' in query_params and query_params['text']:
            text = query_params['text'].lower()
            mask = df['search_text'].str.contains(text, na=False)
            df = df[mask]
        
        # Category filter
        if 'category' in query_params and query_params['category']:
            category = query_params['category'].lower()
            # Check if it's a main group category
            if category in ['book', 'music', 'dvd', 'video', 'toy', 'software', 'ce', 'video games', 'baby product', 'sports']:
                df = df[df['group'].str.lower() == category]
            else:
                # Fallback to main_category search for sub-categories
                df = df[df['main_category'].str.contains(category, case=False, na=False)]
        
        # Rating filter
        if 'rating_op' in query_params and 'rating_value' in query_params:
            op_str = query_params['rating_op']
            value = float(query_params['rating_value'])
            if op_str in SearchOperator.OPERATORS:
                op_func = SearchOperator.OPERATORS[op_str]
                mask = op_func(df['avg_rating'], value)
                df = df[mask]
        
        # Reviews count filter
        if 'reviews_op' in query_params and 'reviews_value' in query_params:
            op_str = query_params['reviews_op']
            value = int(query_params['reviews_value'])
            if op_str in SearchOperator.OPERATORS:
                op_func = SearchOperator.OPERATORS[op_str]
                mask = op_func(df['total_reviews'], value)
                df = df[mask]
        
        # Sort and limit results
        if len(df) > 0:
            # Sort by relevance (combination of rating and review count)
            # Handle invalid salesrank values (negative, inf, or NaN)
            valid_salesrank = df['salesrank'].copy()
            valid_salesrank = valid_salesrank.replace([-1, np.inf, -np.inf], np.nan)
            valid_salesrank = valid_salesrank.fillna(1000000)  # Default high rank for missing data
            
            df['relevance_score'] = (
                df['avg_rating'] * 0.4 + 
                np.log1p(df['total_reviews']) * 0.3 +
                (1.0 / (1.0 + valid_salesrank)) * 1000 * 0.3
            )
            df = df.sort_values('relevance_score', ascending=False)
            
            limit = query_params.get('limit', 50)
            df = df.head(limit)
            
            return df[['id', 'asin', 'title', 'group', 'main_category', 'avg_rating', 
                      'total_reviews', 'salesrank', 'relevance_score']]
        else:
            # Return empty DataFrame with proper columns
            return pd.DataFrame(columns=['id', 'asin', 'title', 'group', 'main_category', 
                                       'avg_rating', 'total_reviews', 'salesrank', 'relevance_score'])
    
    def get_category_statistics(self) -> pd.DataFrame:
        """
        Get statistics for each product category
        
        Returns:
            DataFrame with category statistics
        """
        stats = self.products_df.groupby('group').agg({
            'id': 'count',
            'avg_rating': 'mean',
            'total_reviews': 'sum',
            'salesrank': lambda x: (x != float('inf')).sum()
        }).round(2)
        
        stats.columns = ['total_products', 'avg_rating', 'total_reviews', 'products_with_salesrank']
        stats = stats.reset_index()
        stats = stats.sort_values('total_products', ascending=False)
        
        return stats
    
    def search_by_text(self, text: str, limit: int = 50) -> pd.DataFrame:
        """
        Simple text search in product titles and categories
        
        Args:
            text: Search text
            limit: Maximum number of results
            
        Returns:
            DataFrame with matching products
        """
        if not text:
            return pd.DataFrame()
        
        df = self.products_df.copy()
        text = text.lower()
        
        # Search in title and category
        mask = df['search_text'].str.contains(text, na=False)
        df = df[mask]
        
        # Calculate relevance score based on text match quality
        df['text_relevance'] = df['search_text'].apply(
            lambda x: SequenceMatcher(None, text, x).ratio()
        )
        
        # Sort by text relevance and other factors
        df['relevance_score'] = (
            df['text_relevance'] * 0.5 +
            (df['avg_rating'] / 5.0) * 0.3 +
            np.log1p(df['total_reviews']) / 10.0 * 0.2
        )
        
        df = df.sort_values('relevance_score', ascending=False).head(limit)
        
        return df[['id', 'asin', 'title', 'group', 'main_category', 'avg_rating', 
                  'total_reviews', 'relevance_score']]
    
    def get_product_details(self, product_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific product
        
        Args:
            product_id: Product ID or ASIN
            
        Returns:
            Dictionary with product details
        """
        # Try to find by ID first, then by ASIN
        product = self.products_df[self.products_df['id'] == product_id]
        if product.empty:
            product = self.products_df[self.products_df['asin'] == product_id]
        
        if product.empty:
            return {}
        
        product = product.iloc[0]
        
        # Get categories for this product
        categories = self.categories_df[
            self.categories_df['product_id'] == product['id']
        ]['category_path'].tolist()
        
        # Get similar products
        similar = self.similar_products_df[
            self.similar_products_df['product_asin'] == product['asin']
        ]['similar_asin'].tolist()
        
        # Get recent reviews
        recent_reviews = self.reviews_df[
            self.reviews_df['product_asin'] == product['asin']
        ].head(5)
        
        return {
            'id': product['id'],
            'asin': product['asin'],
            'title': product['title'],
            'group': product['group'],
            'main_category': product.get('main_category', ''),
            'avg_rating': product['avg_rating'],
            'total_reviews': product['total_reviews'],
            'salesrank': product['salesrank'],
            'categories': categories,
            'similar_products': similar[:10],
            'recent_reviews': recent_reviews.to_dict('records') if not recent_reviews.empty else []
        }


# Demo functions for testing
def demo_search_engine():
    """Demonstrate search engine capabilities with real Amazon data"""
    print("=== AMAZON SEARCH ENGINE DEMO ===\n")
    
    try:
        engine = AmazonSearchEngine()
        
        # 1. Best sellers in Books category
        print("1. Top 5 Best Sellers in Books:")
        results = engine.search_best_sellers(category="Book", n=5)
        if not results.empty:
            for _, product in results.iterrows():
                print(f"   {product['title'][:50]}... | Rank: {product['salesrank']} | Rating: {product['avg_rating']}")
        print()
        
        # 2. High-rated products
        print("2. Products with rating >= 4.5:")
        results = engine.search_by_rating(">=", 4.5, limit=5)
        if not results.empty:
            for _, product in results.iterrows():
                print(f"   {product['title'][:50]}... | Rating: {product['avg_rating']} | Reviews: {product['total_reviews']}")
        print()
        
        # 3. Products with many reviews
        print("3. Products with > 50 reviews:")
        results = engine.search_by_review_count(">", 50, limit=5)
        if not results.empty:
            for _, product in results.iterrows():
                print(f"   {product['title'][:50]}... | Reviews: {product['total_reviews']} | Rating: {product['avg_rating']}")
        print()
        
        # 4. Text search
        print("4. Text search for 'Harry Potter':")
        results = engine.search_by_text("Harry Potter", limit=5)
        if not results.empty:
            for _, product in results.iterrows():
                print(f"   {product['title'][:50]}... | Group: {product['group']} | Rating: {product['avg_rating']}")
        print()
        
        # 5. Category statistics
        print("5. Category Statistics:")
        stats = engine.get_category_statistics()
        for _, row in stats.iterrows():
            print(f"   {row['group']}: {row['total_products']:,} products | Avg Rating: {row['avg_rating']:.2f}")
        print()
        
        # 6. Advanced search
        print("6. Advanced search: Books with rating >= 4.0 and > 10 reviews:")
        results = engine.advanced_search({
            'category': 'Book',
            'rating_op': '>=',
            'rating_value': 4.0,
            'reviews_op': '>',
            'reviews_value': 10,
            'limit': 5
        })
        if not results.empty:
            for _, product in results.iterrows():
                print(f"   {product['title'][:50]}... | Rating: {product['avg_rating']} | Reviews: {product['total_reviews']}")
        
    except Exception as e:
        print(f"Error in demo: {str(e)}")


if __name__ == "__main__":
    demo_search_engine()