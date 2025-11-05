"""
Similarity calculation utilities for recommendation system
"""
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances
from sklearn.feature_extraction.text import TfidfVectorizer
from typing import Dict, List, Tuple, Any
import sys
from pathlib import Path

# Add src to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from utils.helpers import setup_logging

logger = setup_logging()


class SimilarityCalculator:
    """Calculate various types of similarity between users and items"""
    
    def __init__(self):
        self.logger = setup_logging()
    
    def cosine_similarity_matrix(self, matrix: np.ndarray) -> np.ndarray:
        """Calculate cosine similarity matrix"""
        return cosine_similarity(matrix)
    
    def pearson_correlation(self, matrix: np.ndarray) -> np.ndarray:
        """Calculate Pearson correlation matrix"""
        return np.corrcoef(matrix)
    
    def jaccard_similarity(self, matrix: np.ndarray) -> np.ndarray:
        """Calculate Jaccard similarity for binary data"""
        # Convert to binary (1 if > 0, 0 otherwise)
        binary_matrix = (matrix > 0).astype(int)
        
        # Calculate Jaccard similarity
        intersection = np.dot(binary_matrix, binary_matrix.T)
        union = np.sum(binary_matrix, axis=1)[:, None] + np.sum(binary_matrix, axis=1) - intersection
        
        # Avoid division by zero
        union[union == 0] = 1
        return intersection / union
    
    def user_similarity(self, ratings_matrix: pd.DataFrame, method: str = "cosine") -> pd.DataFrame:
        """
        Calculate user-user similarity matrix
        
        Args:
            ratings_matrix: User-item ratings matrix (users as rows, items as columns)
            method: Similarity method ('cosine', 'pearson', 'jaccard')
            
        Returns:
            DataFrame with user similarity scores
        """
        # Fill NaN values with 0 for similarity calculation
        matrix = ratings_matrix.fillna(0).values
        
        if method == "cosine":
            similarity = self.cosine_similarity_matrix(matrix)
        elif method == "pearson":
            similarity = self.pearson_correlation(matrix)
        elif method == "jaccard":
            similarity = self.jaccard_similarity(matrix)
        else:
            raise ValueError(f"Unknown similarity method: {method}")
        
        # Convert back to DataFrame
        return pd.DataFrame(
            similarity, 
            index=ratings_matrix.index, 
            columns=ratings_matrix.index
        )
    
    def item_similarity(self, ratings_matrix: pd.DataFrame, method: str = "cosine") -> pd.DataFrame:
        """
        Calculate item-item similarity matrix
        
        Args:
            ratings_matrix: User-item ratings matrix (users as rows, items as columns)
            method: Similarity method ('cosine', 'pearson', 'jaccard')
            
        Returns:
            DataFrame with item similarity scores
        """
        # Transpose matrix to have items as rows
        item_matrix = ratings_matrix.T.fillna(0).values
        
        if method == "cosine":
            similarity = self.cosine_similarity_matrix(item_matrix)
        elif method == "pearson":
            similarity = self.pearson_correlation(item_matrix)
        elif method == "jaccard":
            similarity = self.jaccard_similarity(item_matrix)
        else:
            raise ValueError(f"Unknown similarity method: {method}")
        
        # Convert back to DataFrame
        return pd.DataFrame(
            similarity,
            index=ratings_matrix.columns,
            columns=ratings_matrix.columns
        )
    
    def content_similarity(self, products_df: pd.DataFrame, features: List[str] = None) -> pd.DataFrame:
        """
        Calculate content-based similarity between items
        
        Args:
            products_df: Products DataFrame
            features: List of feature columns to use for similarity
            
        Returns:
            DataFrame with content similarity scores
        """
        if features is None:
            features = ['category', 'brand', 'description']
        
        # Combine text features
        text_features = []
        for _, row in products_df.iterrows():
            combined_text = ' '.join([str(row[col]) for col in features if col in products_df.columns])
            text_features.append(combined_text)
        
        # Calculate TF-IDF vectors
        vectorizer = TfidfVectorizer(max_features=1000, stop_words='english', lowercase=True)
        tfidf_matrix = vectorizer.fit_transform(text_features)
        
        # Calculate cosine similarity
        similarity_matrix = cosine_similarity(tfidf_matrix)
        
        return pd.DataFrame(
            similarity_matrix,
            index=products_df['product_id'],
            columns=products_df['product_id']
        )
    
    def get_similar_users(self, user_id: str, similarity_matrix: pd.DataFrame, 
                         top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Get most similar users to a given user
        
        Args:
            user_id: Target user ID
            similarity_matrix: User similarity matrix
            top_k: Number of similar users to return
            
        Returns:
            List of (user_id, similarity_score) tuples
        """
        if user_id not in similarity_matrix.index:
            return []
        
        # Get similarity scores for the user
        user_similarities = similarity_matrix.loc[user_id]
        
        # Remove self-similarity and sort
        user_similarities = user_similarities.drop(user_id)
        similar_users = user_similarities.nlargest(top_k)
        
        return [(user, score) for user, score in similar_users.items()]
    
    def get_similar_items(self, item_id: str, similarity_matrix: pd.DataFrame,
                         top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Get most similar items to a given item
        
        Args:
            item_id: Target item ID
            similarity_matrix: Item similarity matrix
            top_k: Number of similar items to return
            
        Returns:
            List of (item_id, similarity_score) tuples
        """
        if item_id not in similarity_matrix.index:
            return []
        
        # Get similarity scores for the item
        item_similarities = similarity_matrix.loc[item_id]
        
        # Remove self-similarity and sort
        item_similarities = item_similarities.drop(item_id)
        similar_items = item_similarities.nlargest(top_k)
        
        return [(item, score) for item, score in similar_items.items()]
    
    def calculate_adjusted_cosine_similarity(self, ratings_matrix: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate adjusted cosine similarity (item-based collaborative filtering)
        This adjusts for user bias by subtracting user mean ratings
        """
        # Calculate user means
        user_means = ratings_matrix.mean(axis=1)
        
        # Adjust ratings by subtracting user means
        adjusted_ratings = ratings_matrix.subtract(user_means, axis=0).fillna(0)
        
        # Calculate item similarity using adjusted ratings
        return self.item_similarity(adjusted_ratings, method="cosine")
    
    def demographic_similarity(self, user_profiles: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate demographic similarity between users (if demographic data available)
        
        Args:
            user_profiles: DataFrame with user demographic information
            
        Returns:
            DataFrame with demographic similarity scores
        """
        # This is a placeholder - in a real system you would have demographic data
        # For now, we'll create a simple similarity based on purchase patterns
        
        # For demonstration, assume all users are similar (this would be replaced with actual demographic data)
        n_users = len(user_profiles)
        similarity_matrix = np.ones((n_users, n_users)) * 0.5
        np.fill_diagonal(similarity_matrix, 1.0)
        
        return pd.DataFrame(
            similarity_matrix,
            index=user_profiles.index,
            columns=user_profiles.index
        )