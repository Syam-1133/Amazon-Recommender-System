"""
Collaborative Filtering Recommendation System
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

# Add src to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from utils.helpers import setup_logging, timing_decorator
from utils.config import PROCESSED_PRODUCTS_FILE, PROCESSED_RATINGS_FILE, RECOMMENDER_CONFIG
from recommendation.similarity import SimilarityCalculator

logger = setup_logging()


class CollaborativeFilteringRecommender:
    """Collaborative filtering recommendation system"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.similarity_calculator = SimilarityCalculator()
        self.products_df = None
        self.ratings_df = None
        self.user_item_matrix = None
        self.user_similarity_matrix = None
        self.item_similarity_matrix = None
        self.load_data()
        
    @timing_decorator
    def load_data(self):
        """Load processed data"""
        try:
            self.products_df = pd.read_parquet(PROCESSED_PRODUCTS_FILE)
            self.ratings_df = pd.read_parquet(PROCESSED_RATINGS_FILE)
            self.logger.info(f"Loaded {len(self.products_df)} products and {len(self.ratings_df)} ratings")
            
            # Create user-item matrix
            self.create_user_item_matrix()
            
        except Exception as e:
            self.logger.error(f"Error loading data: {str(e)}")
            raise
    
    @timing_decorator
    def create_user_item_matrix(self):
        """Create user-item ratings matrix"""
        self.user_item_matrix = self.ratings_df.pivot(
            index='user_id', 
            columns='product_id', 
            values='rating'
        )
        self.logger.info(f"Created user-item matrix: {self.user_item_matrix.shape}")
    
    @timing_decorator
    def compute_similarities(self, method: str = "cosine"):
        """Compute user and item similarity matrices"""
        self.logger.info(f"Computing similarities using {method} method...")
        
        # User-user similarity
        self.user_similarity_matrix = self.similarity_calculator.user_similarity(
            self.user_item_matrix, method=method
        )
        
        # Item-item similarity
        self.item_similarity_matrix = self.similarity_calculator.item_similarity(
            self.user_item_matrix, method=method
        )
        
        self.logger.info("Similarity matrices computed successfully")
    
    def user_based_recommendations(self, user_id: str, n_recommendations: int = 10) -> List[Tuple[str, float]]:
        """
        Generate recommendations using user-based collaborative filtering
        
        Args:
            user_id: Target user ID
            n_recommendations: Number of recommendations to generate
            
        Returns:
            List of (product_id, predicted_rating) tuples
        """
        if user_id not in self.user_item_matrix.index:
            self.logger.warning(f"User {user_id} not found in ratings data")
            return self.get_popular_items(n_recommendations)
        
        if self.user_similarity_matrix is None:
            self.compute_similarities()
        
        # Get similar users
        similar_users = self.similarity_calculator.get_similar_users(
            user_id, self.user_similarity_matrix, top_k=50
        )
        
        if not similar_users:
            return self.get_popular_items(n_recommendations)
        
        # Get user's rated items
        user_ratings = self.user_item_matrix.loc[user_id]
        rated_items = user_ratings.dropna().index.tolist()
        
        # Calculate predicted ratings for unrated items
        predictions = {}
        all_items = self.user_item_matrix.columns
        
        for item in all_items:
            if item not in rated_items:
                predicted_rating = self._predict_rating_user_based(
                    user_id, item, similar_users
                )
                if predicted_rating is not None:
                    predictions[item] = predicted_rating
        
        # Sort by predicted rating and return top N
        sorted_predictions = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
        return sorted_predictions[:n_recommendations]
    
    def item_based_recommendations(self, user_id: str, n_recommendations: int = 10) -> List[Tuple[str, float]]:
        """
        Generate recommendations using item-based collaborative filtering
        
        Args:
            user_id: Target user ID
            n_recommendations: Number of recommendations to generate
            
        Returns:
            List of (product_id, predicted_rating) tuples
        """
        if user_id not in self.user_item_matrix.index:
            self.logger.warning(f"User {user_id} not found in ratings data")
            return self.get_popular_items(n_recommendations)
        
        if self.item_similarity_matrix is None:
            self.compute_similarities()
        
        # Get user's ratings
        user_ratings = self.user_item_matrix.loc[user_id]
        rated_items = user_ratings.dropna()
        
        if rated_items.empty:
            return self.get_popular_items(n_recommendations)
        
        # Calculate predicted ratings for unrated items
        predictions = {}
        all_items = self.user_item_matrix.columns
        
        for item in all_items:
            if item not in rated_items.index:
                predicted_rating = self._predict_rating_item_based(
                    item, rated_items
                )
                if predicted_rating is not None:
                    predictions[item] = predicted_rating
        
        # Sort by predicted rating and return top N
        sorted_predictions = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
        return sorted_predictions[:n_recommendations]
    
    def _predict_rating_user_based(self, user_id: str, item_id: str, 
                                  similar_users: List[Tuple[str, float]]) -> Optional[float]:
        """Predict rating using user-based collaborative filtering"""
        numerator = 0
        denominator = 0
        
        # Get target user's mean rating
        user_mean = self.user_item_matrix.loc[user_id].mean()
        
        for similar_user, similarity in similar_users:
            if similar_user in self.user_item_matrix.index:
                similar_user_rating = self.user_item_matrix.loc[similar_user, item_id]
                
                if not pd.isna(similar_user_rating):
                    similar_user_mean = self.user_item_matrix.loc[similar_user].mean()
                    
                    # Adjust for user bias
                    adjusted_rating = similar_user_rating - similar_user_mean
                    
                    numerator += similarity * adjusted_rating
                    denominator += abs(similarity)
        
        if denominator == 0:
            return None
        
        predicted_rating = user_mean + (numerator / denominator)
        return max(1, min(5, predicted_rating))  # Clamp to valid rating range
    
    def _predict_rating_item_based(self, item_id: str, 
                                  user_ratings: pd.Series) -> Optional[float]:
        """Predict rating using item-based collaborative filtering"""
        if item_id not in self.item_similarity_matrix.index:
            return None
        
        # Get similar items that the user has rated
        item_similarities = self.item_similarity_matrix.loc[item_id]
        
        numerator = 0
        denominator = 0
        
        for rated_item, rating in user_ratings.items():
            if rated_item in item_similarities.index:
                similarity = item_similarities[rated_item]
                
                if similarity > 0:  # Only consider positive similarities
                    numerator += similarity * rating
                    denominator += abs(similarity)
        
        if denominator == 0:
            return None
        
        predicted_rating = numerator / denominator
        return max(1, min(5, predicted_rating))  # Clamp to valid rating range
    
    def get_popular_items(self, n_items: int = 10) -> List[Tuple[str, float]]:
        """Get most popular items based on rating count and average rating"""
        # Calculate popularity score (avg_rating * log(num_reviews + 1))
        product_stats = self.ratings_df.groupby('product_id').agg({
            'rating': ['mean', 'count']
        }).round(2)
        
        product_stats.columns = ['avg_rating', 'num_ratings']
        product_stats['popularity_score'] = (
            product_stats['avg_rating'] * np.log1p(product_stats['num_ratings'])
        )
        
        popular_items = product_stats.nlargest(n_items, 'popularity_score')
        
        return [(item_id, row['avg_rating']) for item_id, row in popular_items.iterrows()]
    
    def get_recommendations_for_user(self, user_id: str, method: str = "item_based",
                                   n_recommendations: int = 10) -> List[Dict[str, Any]]:
        """
        Get recommendations for a user with detailed product information
        
        Args:
            user_id: Target user ID
            method: Recommendation method ('user_based', 'item_based', 'hybrid')
            n_recommendations: Number of recommendations
            
        Returns:
            List of recommendation dictionaries with product details
        """
        if method == "user_based":
            raw_recommendations = self.user_based_recommendations(user_id, n_recommendations)
        elif method == "item_based":
            raw_recommendations = self.item_based_recommendations(user_id, n_recommendations)
        elif method == "hybrid":
            # Combine both methods
            user_recs = self.user_based_recommendations(user_id, n_recommendations // 2)
            item_recs = self.item_based_recommendations(user_id, n_recommendations // 2)
            
            # Merge recommendations (simple combination for now)
            all_recs = dict(user_recs + item_recs)
            raw_recommendations = sorted(all_recs.items(), key=lambda x: x[1], reverse=True)[:n_recommendations]
        else:
            raw_recommendations = self.get_popular_items(n_recommendations)
        
        # Add product details
        recommendations = []
        for product_id, predicted_rating in raw_recommendations:
            if product_id in self.products_df['product_id'].values:
                product_info = self.products_df[
                    self.products_df['product_id'] == product_id
                ].iloc[0].to_dict()
                
                recommendation = {
                    'product_id': product_id,
                    'predicted_rating': predicted_rating,
                    'title': product_info.get('title', 'Unknown'),
                    'category': product_info.get('category', 'Unknown'),
                    'brand': product_info.get('brand', 'Unknown'),
                    'price': product_info.get('price', 0.0),
                    'avg_rating': product_info.get('avg_rating', 0.0),
                    'num_reviews': product_info.get('num_reviews', 0)
                }
                recommendations.append(recommendation)
        
        return recommendations
    
    def analyze_co_purchasing_patterns(self, user_id: str) -> Dict[str, Any]:
        """
        Analyze co-purchasing patterns for a user
        
        Args:
            user_id: Target user ID
            
        Returns:
            Dictionary with co-purchasing analysis
        """
        if user_id not in self.user_item_matrix.index:
            return {'error': f'User {user_id} not found'}
        
        # Get user's purchases
        user_purchases = self.user_item_matrix.loc[user_id].dropna().index.tolist()
        
        # Find other users who bought the same items
        co_purchasers = {}
        for item in user_purchases:
            item_buyers = self.user_item_matrix[item].dropna().index.tolist()
            for buyer in item_buyers:
                if buyer != user_id:
                    if buyer not in co_purchasers:
                        co_purchasers[buyer] = 0
                    co_purchasers[buyer] += 1
        
        # Find frequently co-purchased items
        co_purchased_items = defaultdict(int)
        for co_purchaser in co_purchasers.keys():
            co_purchaser_items = self.user_item_matrix.loc[co_purchaser].dropna().index.tolist()
            for item in co_purchaser_items:
                if item not in user_purchases:
                    co_purchased_items[item] += 1
        
        # Get product details for co-purchased items
        top_co_purchased = sorted(co_purchased_items.items(), key=lambda x: x[1], reverse=True)[:10]
        
        co_purchased_details = []
        for item_id, frequency in top_co_purchased:
            if item_id in self.products_df['product_id'].values:
                product_info = self.products_df[
                    self.products_df['product_id'] == item_id
                ].iloc[0]
                
                co_purchased_details.append({
                    'product_id': item_id,
                    'title': product_info['title'],
                    'category': product_info['category'],
                    'co_purchase_frequency': frequency,
                    'price': product_info['price'],
                    'avg_rating': product_info['avg_rating']
                })
        
        return {
            'user_id': user_id,
            'total_purchases': len(user_purchases),
            'co_purchasers_count': len(co_purchasers),
            'top_co_purchasers': dict(sorted(co_purchasers.items(), key=lambda x: x[1], reverse=True)[:5]),
            'co_purchased_items': co_purchased_details
        }
    
    def evaluate_recommendations(self, test_users: List[str] = None, 
                               n_recommendations: int = 10) -> Dict[str, float]:
        """
        Evaluate recommendation quality using basic metrics
        
        Args:
            test_users: List of users to test (if None, use random sample)
            n_recommendations: Number of recommendations per user
            
        Returns:
            Dictionary with evaluation metrics
        """
        if test_users is None:
            # Select random sample of users
            test_users = np.random.choice(
                self.user_item_matrix.index, 
                size=min(100, len(self.user_item_matrix.index)), 
                replace=False
            ).tolist()
        
        total_precision = 0
        total_recall = 0
        total_users = 0
        
        for user_id in test_users:
            # Get user's actual high ratings (4+ stars)
            user_ratings = self.user_item_matrix.loc[user_id]
            liked_items = user_ratings[user_ratings >= 4].dropna().index.tolist()
            
            if not liked_items:
                continue
            
            # Get recommendations
            recommendations = self.item_based_recommendations(user_id, n_recommendations)
            recommended_items = [item_id for item_id, _ in recommendations]
            
            # Calculate precision and recall
            relevant_recommended = set(liked_items) & set(recommended_items)
            
            precision = len(relevant_recommended) / len(recommended_items) if recommended_items else 0
            recall = len(relevant_recommended) / len(liked_items) if liked_items else 0
            
            total_precision += precision
            total_recall += recall
            total_users += 1
        
        avg_precision = total_precision / total_users if total_users > 0 else 0
        avg_recall = total_recall / total_users if total_users > 0 else 0
        f1_score = 2 * (avg_precision * avg_recall) / (avg_precision + avg_recall) if (avg_precision + avg_recall) > 0 else 0
        
        return {
            'precision': avg_precision,
            'recall': avg_recall,
            'f1_score': f1_score,
            'test_users_count': total_users
        }


def demo_recommender_system():
    """Demonstrate recommender system capabilities"""
    recommender = CollaborativeFilteringRecommender()
    
    print("=== COLLABORATIVE FILTERING RECOMMENDER DEMO ===\n")
    
    # Get a sample user
    sample_users = recommender.user_item_matrix.index[:5].tolist()
    
    for i, user_id in enumerate(sample_users[:2]):  # Test 2 users
        print(f"{i+1}. Recommendations for User {user_id}:")
        
        # Item-based recommendations
        item_recs = recommender.get_recommendations_for_user(user_id, method="item_based", n_recommendations=5)
        print("Item-based recommendations:")
        for rec in item_recs:
            print(f"  - {rec['title'][:50]}... | {rec['category']} | ${rec['price']:.2f} | ⭐{rec['predicted_rating']:.2f}")
        
        # Co-purchasing analysis
        co_purchase_analysis = recommender.analyze_co_purchasing_patterns(user_id)
        print(f"\nCo-purchasing analysis:")
        print(f"  - Total purchases: {co_purchase_analysis['total_purchases']}")
        print(f"  - Co-purchasers: {co_purchase_analysis['co_purchasers_count']}")
        if co_purchase_analysis['co_purchased_items']:
            print("  - Top co-purchased items:")
            for item in co_purchase_analysis['co_purchased_items'][:3]:
                print(f"    * {item['title'][:40]}... | Frequency: {item['co_purchase_frequency']}")
        print()
    
    # Popular items
    print("3. Most Popular Items:")
    popular_items = recommender.get_popular_items(n_items=5)
    for item_id, rating in popular_items:
        product_info = recommender.products_df[
            recommender.products_df['product_id'] == item_id
        ].iloc[0]
        print(f"  - {product_info['title'][:50]}... | {product_info['category']} | ⭐{rating:.2f}")
    print()
    
    # Evaluation
    print("4. Recommendation Evaluation:")
    metrics = recommender.evaluate_recommendations()
    print(f"  - Precision: {metrics['precision']:.3f}")
    print(f"  - Recall: {metrics['recall']:.3f}")
    print(f"  - F1-Score: {metrics['f1_score']:.3f}")
    print(f"  - Test users: {metrics['test_users_count']}")


if __name__ == "__main__":
    demo_recommender_system()