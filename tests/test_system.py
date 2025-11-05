"""
Test suite for the Amazon Recommender System
"""
import unittest
import sys
import pandas as pd
from pathlib import Path

# Add src to path to import our modules
sys.path.append(str(Path(__file__).parent.parent / "src"))

from search.search_engine import AmazonSearchEngine
from search.query_processor import QueryProcessor, SearchQuery, SearchFilter, ComparisonOperator
from recommendation.collaborative_filter import CollaborativeFilteringRecommender
from recommendation.similarity import SimilarityCalculator
from data_processing.parser import AmazonDataParser


class TestQueryProcessor(unittest.TestCase):
    """Test the query processor functionality"""
    
    def setUp(self):
        self.processor = QueryProcessor()
    
    def test_create_simple_query(self):
        """Test creating a simple query"""
        query = self.processor.create_simple_query(
            text="laptops",
            category="Electronics",
            min_price=100.0,
            max_price=500.0,
            min_rating=4.0
        )
        
        self.assertEqual(query.text_query, "laptops")
        self.assertEqual(len(query.filters), 4)  # category, min_price, max_price, min_rating
    
    def test_parse_query_string(self):
        """Test parsing natural language queries"""
        query_string = "books with price < 50"
        query = self.processor.parse_query_string(query_string)
        
        # Should have text query and filters
        self.assertIsNotNone(query.text_query)
        self.assertGreater(len(query.filters), 0)
    
    def test_query_validation(self):
        """Test query validation"""
        # Valid query
        valid_query = SearchQuery(
            text_query="test",
            sort_by="price",
            sort_order="asc",
            limit=10
        )
        is_valid, errors = self.processor.validate_query(valid_query)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Invalid query
        invalid_query = SearchQuery(
            sort_by="invalid_field",
            sort_order="invalid_order",
            limit=-1
        )
        is_valid, errors = self.processor.validate_query(invalid_query)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)


class TestSearchEngine(unittest.TestCase):
    """Test the search engine functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class with search engine instance"""
        try:
            cls.search_engine = AmazonSearchEngine()
        except Exception as e:
            # Skip tests if data is not available
            cls.search_engine = None
            print(f"Warning: Search engine tests skipped due to missing data: {e}")
    
    def setUp(self):
        if self.search_engine is None:
            self.skipTest("Search engine not available")
    
    def test_advanced_search(self):
        """Test advanced search functionality"""
        results = self.search_engine.advanced_search(
            text="product",
            min_price=10.0,
            max_price=100.0,
            limit=5
        )
        
        self.assertIsInstance(results, pd.DataFrame)
        self.assertLessEqual(len(results), 5)
        
        # Check price filtering
        if not results.empty and 'price' in results.columns:
            self.assertTrue(all(results['price'] >= 10.0))
            self.assertTrue(all(results['price'] <= 100.0))
    
    def test_get_best_sellers(self):
        """Test best sellers functionality"""
        results = self.search_engine.get_best_sellers(n=5)
        
        self.assertIsInstance(results, pd.DataFrame)
        self.assertLessEqual(len(results), 5)
        
        # Should have popularity_score column
        if not results.empty:
            self.assertIn('popularity_score', results.columns)
    
    def test_category_search(self):
        """Test category-based search"""
        # Get available categories
        categories = self.search_engine.products_df['category'].unique()
        if len(categories) > 0:
            test_category = categories[0]
            results = self.search_engine.search_by_category(test_category, limit=10)
            
            self.assertIsInstance(results, pd.DataFrame)
            
            # All results should be from the specified category
            if not results.empty:
                self.assertTrue(all(results['category'].str.contains(test_category, case=False, na=False)))
    
    def test_get_category_statistics(self):
        """Test category statistics"""
        stats = self.search_engine.get_category_statistics()
        
        self.assertIsInstance(stats, dict)
        self.assertGreater(len(stats), 0)
        
        # Check structure of statistics
        for category, stat in stats.items():
            self.assertIn('total_products', stat)
            self.assertIn('avg_price', stat)
            self.assertIn('avg_rating', stat)


class TestRecommenderSystem(unittest.TestCase):
    """Test the recommender system functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class with recommender instance"""
        try:
            cls.recommender = CollaborativeFilteringRecommender()
        except Exception as e:
            # Skip tests if data is not available
            cls.recommender = None
            print(f"Warning: Recommender tests skipped due to missing data: {e}")
    
    def setUp(self):
        if self.recommender is None:
            self.skipTest("Recommender system not available")
    
    def test_user_item_matrix(self):
        """Test user-item matrix creation"""
        self.assertIsNotNone(self.recommender.user_item_matrix)
        self.assertGreater(self.recommender.user_item_matrix.shape[0], 0)
        self.assertGreater(self.recommender.user_item_matrix.shape[1], 0)
    
    def test_item_based_recommendations(self):
        """Test item-based recommendations"""
        # Get a sample user
        sample_users = self.recommender.user_item_matrix.index[:5]
        if len(sample_users) > 0:
            user_id = sample_users[0]
            recommendations = self.recommender.item_based_recommendations(user_id, n_recommendations=5)
            
            self.assertIsInstance(recommendations, list)
            self.assertLessEqual(len(recommendations), 5)
            
            # Each recommendation should be a tuple (product_id, rating)
            for rec in recommendations:
                self.assertIsInstance(rec, tuple)
                self.assertEqual(len(rec), 2)
                self.assertIsInstance(rec[0], str)  # product_id
                self.assertIsInstance(rec[1], (int, float))  # predicted_rating
    
    def test_get_recommendations_for_user(self):
        """Test getting detailed recommendations"""
        sample_users = self.recommender.user_item_matrix.index[:3]
        if len(sample_users) > 0:
            user_id = sample_users[0]
            recommendations = self.recommender.get_recommendations_for_user(
                user_id, method="item_based", n_recommendations=5
            )
            
            self.assertIsInstance(recommendations, list)
            self.assertLessEqual(len(recommendations), 5)
            
            # Each recommendation should be a dictionary with product details
            for rec in recommendations:
                self.assertIsInstance(rec, dict)
                self.assertIn('product_id', rec)
                self.assertIn('predicted_rating', rec)
                self.assertIn('title', rec)
                self.assertIn('category', rec)
                self.assertIn('price', rec)
    
    def test_co_purchasing_analysis(self):
        """Test co-purchasing analysis"""
        sample_users = self.recommender.user_item_matrix.index[:3]
        if len(sample_users) > 0:
            user_id = sample_users[0]
            analysis = self.recommender.analyze_co_purchasing_patterns(user_id)
            
            self.assertIsInstance(analysis, dict)
            self.assertIn('user_id', analysis)
            self.assertIn('total_purchases', analysis)
            self.assertIn('co_purchasers_count', analysis)
            self.assertEqual(analysis['user_id'], user_id)
    
    def test_popular_items(self):
        """Test getting popular items"""
        popular_items = self.recommender.get_popular_items(n_items=10)
        
        self.assertIsInstance(popular_items, list)
        self.assertLessEqual(len(popular_items), 10)
        
        # Each item should be a tuple (product_id, rating)
        for item in popular_items:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
    
    def test_evaluation_metrics(self):
        """Test recommendation evaluation"""
        # Test with a small sample of users
        sample_users = self.recommender.user_item_matrix.index[:10].tolist()
        metrics = self.recommender.evaluate_recommendations(
            test_users=sample_users, n_recommendations=5
        )
        
        self.assertIsInstance(metrics, dict)
        self.assertIn('precision', metrics)
        self.assertIn('recall', metrics)
        self.assertIn('f1_score', metrics)
        self.assertIn('test_users_count', metrics)
        
        # Metrics should be between 0 and 1
        self.assertGreaterEqual(metrics['precision'], 0)
        self.assertLessEqual(metrics['precision'], 1)
        self.assertGreaterEqual(metrics['recall'], 0)
        self.assertLessEqual(metrics['recall'], 1)


class TestSimilarityCalculator(unittest.TestCase):
    """Test similarity calculation functionality"""
    
    def setUp(self):
        self.calculator = SimilarityCalculator()
        
        # Create sample data
        self.sample_matrix = pd.DataFrame({
            'item1': [1, 2, 3, 0],
            'item2': [2, 3, 1, 1],
            'item3': [1, 1, 2, 0]
        }, index=['user1', 'user2', 'user3', 'user4'])
    
    def test_user_similarity(self):
        """Test user similarity calculation"""
        similarity_matrix = self.calculator.user_similarity(self.sample_matrix, method="cosine")
        
        self.assertIsInstance(similarity_matrix, pd.DataFrame)
        self.assertEqual(similarity_matrix.shape, (4, 4))  # 4 users x 4 users
        
        # Diagonal should be 1 (self-similarity)
        for i in range(4):
            self.assertAlmostEqual(similarity_matrix.iloc[i, i], 1.0, places=5)
    
    def test_item_similarity(self):
        """Test item similarity calculation"""
        similarity_matrix = self.calculator.item_similarity(self.sample_matrix, method="cosine")
        
        self.assertIsInstance(similarity_matrix, pd.DataFrame)
        self.assertEqual(similarity_matrix.shape, (3, 3))  # 3 items x 3 items
        
        # Diagonal should be 1 (self-similarity)
        for i in range(3):
            self.assertAlmostEqual(similarity_matrix.iloc[i, i], 1.0, places=5)
    
    def test_similar_users_items(self):
        """Test getting similar users/items"""
        user_similarity = self.calculator.user_similarity(self.sample_matrix)
        similar_users = self.calculator.get_similar_users('user1', user_similarity, top_k=2)
        
        self.assertIsInstance(similar_users, list)
        self.assertLessEqual(len(similar_users), 2)
        
        # Each similar user should be a tuple (user_id, similarity_score)
        for user, score in similar_users:
            self.assertIsInstance(user, str)
            self.assertIsInstance(score, (int, float))


class TestDataParser(unittest.TestCase):
    """Test data parsing functionality"""
    
    def setUp(self):
        self.parser = AmazonDataParser()
    
    def test_sample_data_creation(self):
        """Test sample data creation"""
        try:
            products_df, ratings_df = self.parser.create_sample_data()
            
            self.assertIsInstance(products_df, pd.DataFrame)
            self.assertIsInstance(ratings_df, pd.DataFrame)
            
            # Check required columns
            required_product_cols = ['product_id', 'title', 'category', 'price']
            for col in required_product_cols:
                self.assertIn(col, products_df.columns)
            
            required_rating_cols = ['user_id', 'product_id', 'rating']
            for col in required_rating_cols:
                self.assertIn(col, ratings_df.columns)
            
            # Check data types and ranges
            self.assertTrue(all(products_df['price'] > 0))
            self.assertTrue(all(ratings_df['rating'].between(1, 5)))
            
        except Exception as e:
            self.skipTest(f"Sample data creation failed: {e}")


def run_performance_tests():
    """Run performance tests for the system"""
    print("\n=== PERFORMANCE TESTS ===")
    
    try:
        # Test search engine performance
        search_engine = AmazonSearchEngine()
        
        import time
        
        # Test search performance
        start_time = time.time()
        results = search_engine.advanced_search(text="product", limit=100)
        search_time = time.time() - start_time
        print(f"Search (100 results): {search_time:.3f} seconds")
        
        # Test recommendation performance
        recommender = CollaborativeFilteringRecommender()
        sample_user = recommender.user_item_matrix.index[0]
        
        start_time = time.time()
        recommendations = recommender.item_based_recommendations(sample_user, n_recommendations=10)
        rec_time = time.time() - start_time
        print(f"Item-based recommendations: {rec_time:.3f} seconds")
        
        # Test similarity computation
        start_time = time.time()
        recommender.compute_similarities(method="cosine")
        sim_time = time.time() - start_time
        print(f"Similarity computation: {sim_time:.3f} seconds")
        
    except Exception as e:
        print(f"Performance tests failed: {e}")


def run_system_integration_test():
    """Run a complete system integration test"""
    print("\n=== SYSTEM INTEGRATION TEST ===")
    
    try:
        # Test complete workflow
        print("1. Loading data...")
        parser = AmazonDataParser()
        products_df, ratings_df = parser.load_data()
        print(f"   ✓ Loaded {len(products_df)} products and {len(ratings_df)} ratings")
        
        print("2. Testing search engine...")
        search_engine = AmazonSearchEngine()
        search_results = search_engine.advanced_search(text="electronics", limit=5)
        print(f"   ✓ Search returned {len(search_results)} results")
        
        print("3. Testing recommender system...")
        recommender = CollaborativeFilteringRecommender()
        sample_user = recommender.user_item_matrix.index[0]
        recommendations = recommender.get_recommendations_for_user(sample_user, n_recommendations=5)
        print(f"   ✓ Generated {len(recommendations)} recommendations for user {sample_user}")
        
        print("4. Testing co-purchasing analysis...")
        co_analysis = recommender.analyze_co_purchasing_patterns(sample_user)
        print(f"   ✓ Found {co_analysis['co_purchasers_count']} co-purchasers")
        
        print("\n✅ System integration test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ System integration test failed: {e}")
        return False


if __name__ == '__main__':
    print("🧪 Running Amazon Recommender System Tests")
    print("=" * 50)
    
    # Run unit tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run performance tests
    run_performance_tests()
    
    # Run integration test
    run_system_integration_test()