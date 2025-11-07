"""
Collaborative Filtering Recommendation System for Amazon Products
Analyzes co-purchasing patterns and user-item similarities
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict, Counter
import warnings
warnings.filterwarnings('ignore')

# Add src to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from utils.helpers import setup_logging, timing_decorator
from utils.config import PROCESSED_DATA_DIR, RECOMMENDER_CONFIG

logger = setup_logging()


class CollaborativeFilteringRecommender:
    """
    Advanced Collaborative Filtering Recommendation System
    
    Implements both user-based and item-based collaborative filtering
    using the real Amazon co-purchasing and review data
    """
    
    def __init__(self):
        self.logger = setup_logging()
        self.products_df = None
        self.reviews_df = None
        self.similar_products_df = None
        self.user_item_matrix = None
        self.product_similarity_matrix = None
        self.load_data()
        
    @timing_decorator
    def load_data(self):
        """Load processed CSV data and prepare recommendation matrices"""
        try:
            # Load all data files
            self.products_df = pd.read_csv(PROCESSED_DATA_DIR / "amazon_products.csv")
            self.reviews_df = pd.read_csv(PROCESSED_DATA_DIR / "amazon_reviews.csv")
            self.similar_products_df = pd.read_csv(PROCESSED_DATA_DIR / "amazon_similar_products.csv")
            
            self.logger.info(f"Loaded {len(self.products_df):,} products")
            self.logger.info(f"Loaded {len(self.reviews_df):,} reviews")
            self.logger.info(f"Loaded {len(self.similar_products_df):,} similar product relationships")
            
            # Prepare recommendation data structures
            self._prepare_recommendation_data()
            
        except Exception as e:
            self.logger.error(f"Error loading data: {str(e)}")
            raise
    
    def _prepare_recommendation_data(self):
        """Prepare data structures for recommendations"""
        try:
            # For demo purposes, use a sample of data to avoid memory issues
            sample_size = 100000  # Use 100K reviews for demo
            if len(self.reviews_df) > sample_size:
                self.logger.info(f"Using sample of {sample_size:,} reviews for demo")
                self.reviews_df = self.reviews_df.sample(n=sample_size, random_state=42)
            
            # Create user-item interaction matrix from reviews
            self._create_user_item_matrix()
            
            # Create product similarity mappings from co-purchase data
            self._create_product_similarity_data()
            
            self.logger.info("Recommendation data prepared successfully")
            
        except Exception as e:
            self.logger.error(f"Error preparing recommendation data: {str(e)}")
    
    def _create_user_item_matrix(self):
        """Create user-item interaction matrix from reviews"""
        # Filter reviews to include only users and items with minimum interactions
        min_interactions = RECOMMENDER_CONFIG.get('min_interactions', 5)
        
        # Count interactions per user and item
        user_counts = self.reviews_df['customer_id'].value_counts()
        item_counts = self.reviews_df['product_asin'].value_counts()
        
        # Filter to active users and popular items
        active_users = user_counts[user_counts >= min_interactions].index
        popular_items = item_counts[item_counts >= min_interactions].index
        
        # Create filtered interaction data
        filtered_reviews = self.reviews_df[
            (self.reviews_df['customer_id'].isin(active_users)) &
            (self.reviews_df['product_asin'].isin(popular_items))
        ]
        
        # Create pivot table (user-item matrix)
        self.user_item_matrix = filtered_reviews.pivot_table(
            index='customer_id',
            columns='product_asin', 
            values='rating',
            fill_value=0
        )
        
        self.logger.info(f"Created user-item matrix: {self.user_item_matrix.shape[0]} users × {self.user_item_matrix.shape[1]} items")
    
    def _create_product_similarity_data(self):
        """Create product similarity mappings from co-purchase data"""
        # Create a dictionary for fast similarity lookups
        self.product_similarities = defaultdict(list)
        
        for _, row in self.similar_products_df.iterrows():
            product_asin = row['product_asin']
            similar_asin = row['similar_asin']
            self.product_similarities[product_asin].append(similar_asin)
        
        self.logger.info(f"Created similarity mappings for {len(self.product_similarities)} products")
    
    @timing_decorator
    def recommend_for_user(self, customer_id: str, n_recommendations: int = 10) -> List[Dict[str, Any]]:
        """
        Generate recommendations for a specific user using collaborative filtering
        
        Args:
            customer_id: Customer ID to generate recommendations for
            n_recommendations: Number of recommendations to return
            
        Returns:
            List of recommended products with scores
        """
        if customer_id not in self.user_item_matrix.index:
            return self._cold_start_recommendations(n_recommendations)
        
        # Get user's ratings
        user_ratings = self.user_item_matrix.loc[customer_id]
        user_rated_items = user_ratings[user_ratings > 0].index.tolist()
        
        # Find similar users
        similar_users = self._find_similar_users(customer_id, n_users=20)
        
        # Generate recommendations based on similar users
        recommendations = self._generate_user_based_recommendations(
            customer_id, similar_users, user_rated_items, n_recommendations
        )
        
        return recommendations
    
    def _find_similar_users(self, customer_id: str, n_users: int = 20) -> List[Tuple[str, float]]:
        """Find users similar to the given customer"""
        user_ratings = self.user_item_matrix.loc[customer_id]
        similarities = []
        
        for other_user in self.user_item_matrix.index:
            if other_user != customer_id:
                other_ratings = self.user_item_matrix.loc[other_user]
                similarity = self._calculate_user_similarity(user_ratings, other_ratings)
                if similarity > 0:
                    similarities.append((other_user, similarity))
        
        # Sort by similarity and return top n
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:n_users]
    
    def _calculate_user_similarity(self, user1_ratings: pd.Series, user2_ratings: pd.Series) -> float:
        """Calculate cosine similarity between two users"""
        # Find common items
        common_items = (user1_ratings > 0) & (user2_ratings > 0)
        
        if common_items.sum() < 2:  # Need at least 2 common items
            return 0.0
        
        # Calculate cosine similarity
        user1_common = user1_ratings[common_items]
        user2_common = user2_ratings[common_items]
        
        dot_product = np.dot(user1_common, user2_common)
        norm1 = np.linalg.norm(user1_common)
        norm2 = np.linalg.norm(user2_common)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _generate_user_based_recommendations(self, customer_id: str, similar_users: List[Tuple[str, float]], 
                                           user_rated_items: List[str], n_recommendations: int) -> List[Dict[str, Any]]:
        """Generate recommendations based on similar users' preferences"""
        item_scores = defaultdict(float)
        item_weights = defaultdict(float)
        
        for similar_user, similarity in similar_users:
            similar_user_ratings = self.user_item_matrix.loc[similar_user]
            
            for item, rating in similar_user_ratings.items():
                if rating > 0 and item not in user_rated_items:
                    item_scores[item] += similarity * rating
                    item_weights[item] += similarity
        
        # Calculate weighted average scores
        recommendations = []
        for item in item_scores:
            if item_weights[item] > 0:
                score = item_scores[item] / item_weights[item]
                recommendations.append((item, score))
        
        # Sort by score and get top n
        recommendations.sort(key=lambda x: x[1], reverse=True)
        top_recommendations = recommendations[:n_recommendations]
        
        # Add product details
        result = []
        for asin, score in top_recommendations:
            product_info = self._get_product_info(asin)
            if product_info:
                product_info['recommendation_score'] = float(round(score, 3))
                result.append(product_info)
        
        return result
    
    @timing_decorator
    def recommend_similar_products(self, product_asin: str, n_recommendations: int = 10) -> List[Dict[str, Any]]:
        """
        Recommend products similar to a given product using co-purchasing data
        
        Args:
            product_asin: Product ASIN to find similar products for
            n_recommendations: Number of recommendations to return
            
        Returns:
            List of similar products with details
        """
        if product_asin not in self.product_similarities:
            return []
        
        similar_asins = self.product_similarities[product_asin][:n_recommendations]
        
        recommendations = []
        for similar_asin in similar_asins:
            product_info = self._get_product_info(similar_asin)
            if product_info:
                product_info['similarity_reason'] = 'co_purchased'
                recommendations.append(product_info)
        
        return recommendations
    
    def analyze_co_purchasing_patterns(self, product_asin: str) -> Dict[str, Any]:
        """
        Analyze co-purchasing patterns for a product
        
        Args:
            product_asin: Product ASIN to analyze
            
        Returns:
            Dictionary with co-purchasing analysis
        """
        # Get similar products
        similar_products = self.product_similarities.get(product_asin, [])
        
        if not similar_products:
            return {
                'product_asin': product_asin,
                'similar_products_count': 0,
                'co_purchase_analysis': {}
            }
        
        # Analyze categories of similar products
        similar_product_details = []
        categories = []
        
        for similar_asin in similar_products:
            product_info = self._get_product_info(similar_asin)
            if product_info:
                similar_product_details.append(product_info)
                if product_info.get('group'):
                    categories.append(product_info['group'])
        
        # Category distribution
        category_distribution = Counter(categories)
        
        # Find customers who reviewed both original and similar products
        original_reviewers = set(self.reviews_df[
            self.reviews_df['product_asin'] == product_asin
        ]['customer_id'].tolist())
        
        co_purchasing_users = 0
        for similar_asin in similar_products[:10]:  # Check top 10 similar products
            similar_reviewers = set(self.reviews_df[
                self.reviews_df['product_asin'] == similar_asin
            ]['customer_id'].tolist())
            co_purchasing_users += len(original_reviewers & similar_reviewers)
        
        return {
            'product_asin': product_asin,
            'similar_products_count': len(similar_products),
            'similar_products': similar_product_details[:10],
            'category_distribution': dict(category_distribution.most_common()),
            'estimated_co_purchasing_users': co_purchasing_users,
            'co_purchase_strength': min(co_purchasing_users / max(len(original_reviewers), 1), 1.0)
        }
    
    def get_trending_products(self, category: str = None, time_window: int = 30) -> List[Dict[str, Any]]:
        """
        Get trending products based on recent review activity
        
        Args:
            category: Product category filter
            time_window: Time window in days (not used as we don't have recent timestamps)
            
        Returns:
            List of trending products
        """
        # Calculate popularity score based on reviews and ratings
        product_stats = self.reviews_df.groupby('product_asin').agg({
            'rating': ['count', 'mean'],
            'helpful': 'sum'
        }).reset_index()
        
        product_stats.columns = ['asin', 'review_count', 'avg_rating', 'total_helpful']
        
        # Calculate trending score
        product_stats['trending_score'] = (
            product_stats['review_count'] * 0.4 +
            product_stats['avg_rating'] * product_stats['review_count'] * 0.4 +
            product_stats['total_helpful'] * 0.2
        )
        
        # Filter by category if specified
        if category:
            product_asins = self.products_df[
                self.products_df['group'].str.lower() == category.lower()
            ]['asin'].tolist()
            product_stats = product_stats[product_stats['asin'].isin(product_asins)]
        
        # Get top trending products
        top_trending = product_stats.nlargest(20, 'trending_score')
        
        result = []
        for _, row in top_trending.iterrows():
            product_info = self._get_product_info(row['asin'])
            if product_info:
                product_info['trending_score'] = round(row['trending_score'], 2)
                product_info['review_count'] = int(row['review_count'])
                result.append(product_info)
        
        return result
    
    def _get_product_info(self, asin: str) -> Optional[Dict[str, Any]]:
        """Get product information by ASIN"""
        product = self.products_df[self.products_df['asin'] == asin]
        
        if product.empty:
            return None
        
        product = product.iloc[0]
        
        # Handle missing values and provide defaults - convert all to native Python types
        title = str(product['title']) if pd.notna(product['title']) and product['title'] else f"Product {asin}"
        group = str(product['group']) if pd.notna(product['group']) and product['group'] else "Unknown"
        
        # Convert to native Python types to avoid JSON serialization issues
        try:
            avg_rating = float(product['avg_rating']) if pd.notna(product['avg_rating']) and product['avg_rating'] else 0.0
        except (ValueError, TypeError):
            avg_rating = 0.0
            
        try:
            total_reviews = int(product['total_reviews']) if pd.notna(product['total_reviews']) and product['total_reviews'] else 0
        except (ValueError, TypeError):
            total_reviews = 0
            
        try:
            salesrank = int(product['salesrank']) if pd.notna(product['salesrank']) and product['salesrank'] else 999999
        except (ValueError, TypeError):
            salesrank = 999999
        
        # Generate a reasonable price based on salesrank and category
        if salesrank <= 100:
            price = 29.99 + (salesrank * 0.1)  # Popular items: $30-40
        elif salesrank <= 1000:
            price = 19.99 + (salesrank * 0.01)  # Medium popularity: $20-30
        else:
            price = 9.99 + min(salesrank * 0.001, 20)  # Less popular: $10-30
        
        return {
            'asin': str(product['asin']),
            'id': int(product['id']) if pd.notna(product['id']) else 0,
            'title': title,
            'group': group,
            'avg_rating': float(avg_rating),
            'total_reviews': int(total_reviews),
            'salesrank': int(salesrank),
            'price': float(round(price, 2)),
            'num_reviews': int(total_reviews),  # Alias for frontend compatibility
            'predicted_rating': float(avg_rating + 0.1 if avg_rating > 0 else 3.5)  # Simple prediction
        }
    
    def _cold_start_recommendations(self, n_recommendations: int) -> List[Dict[str, Any]]:
        """Provide recommendations for new users (cold start problem)"""
        import random
        
        # Get popular products from different categories for diversity
        popular_by_category = {}
        for category in ['Book', 'Music', 'Video', 'DVD']:
            category_products = self.products_df[
                (self.products_df['group'] == category) &
                (self.products_df['total_reviews'] >= 5) &
                (self.products_df['avg_rating'] >= 3.5)
            ]
            if len(category_products) > 0:
                popular_by_category[category] = category_products.nlargest(20, 'total_reviews')
        
        # If no category data, fall back to overall popular products
        if not popular_by_category:
            popular_products = self.products_df[
                (self.products_df['total_reviews'] >= 10) &
                (self.products_df['avg_rating'] >= 4.0)
            ].nlargest(50, 'total_reviews')
        else:
            # Combine products from different categories
            all_category_products = []
            for products_df in popular_by_category.values():
                all_category_products.append(products_df)
            popular_products = pd.concat(all_category_products, ignore_index=True)
        
        # Randomly sample from popular products for diversity
        if len(popular_products) > n_recommendations:
            popular_products = popular_products.sample(n=n_recommendations, random_state=random.randint(1, 1000))
        
        recommendations = []
        for _, product in popular_products.iterrows():
            product_info = self._get_product_info(product['asin'])
            if product_info:
                product_info['recommendation_score'] = float(0.8)  # Default score for popular items
                product_info['reason'] = 'popular_item'
                recommendations.append(product_info)
        
        return recommendations[:n_recommendations]


# Demo function for testing
def demo_collaborative_filtering():
    """Demonstrate collaborative filtering capabilities"""
    print("=== COLLABORATIVE FILTERING RECOMMENDER DEMO ===\n")
    
    try:
        recommender = CollaborativeFilteringRecommender()
        
        # 1. Get a sample customer ID from reviews
        sample_customer = recommender.reviews_df['customer_id'].iloc[1000]  # Get a customer with some history
        print(f"1. Recommendations for customer {sample_customer}:")
        recommendations = recommender.recommend_for_user(sample_customer, n_recommendations=5)
        for i, rec in enumerate(recommendations[:5], 1):
            print(f"   {i}. {rec['title'][:50]}... | Score: {rec['recommendation_score']} | Rating: {rec['avg_rating']}")
        print()
        
        # 2. Get a sample product ASIN
        sample_product = recommender.similar_products_df['product_asin'].iloc[0]
        print(f"2. Products similar to {sample_product}:")
        similar_products = recommender.recommend_similar_products(sample_product, n_recommendations=5)
        for i, prod in enumerate(similar_products[:5], 1):
            print(f"   {i}. {prod['title'][:50]}... | Group: {prod['group']} | Rating: {prod['avg_rating']}")
        print()
        
        # 3. Co-purchasing analysis
        print(f"3. Co-purchasing analysis for {sample_product}:")
        analysis = recommender.analyze_co_purchasing_patterns(sample_product)
        print(f"   Similar products: {analysis['similar_products_count']}")
        print(f"   Co-purchasing strength: {analysis['co_purchase_strength']:.3f}")
        if analysis['category_distribution']:
            print(f"   Top categories: {list(analysis['category_distribution'].keys())[:3]}")
        print()
        
        # 4. Trending products
        print("4. Trending Books:")
        trending = recommender.get_trending_products(category="Book")[:5]
        for i, prod in enumerate(trending, 1):
            print(f"   {i}. {prod['title'][:50]}... | Reviews: {prod['review_count']} | Trending Score: {prod['trending_score']}")
        
    except Exception as e:
        print(f"Error in demo: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    demo_collaborative_filtering()



