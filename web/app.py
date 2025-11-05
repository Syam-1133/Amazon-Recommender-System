"""
Flask Web Application for Amazon Recommender System
"""
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sys
import os
import logging
from pathlib import Path
import pandas as pd

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path to import our modules
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.append(str(project_root / "src"))

from search.search_engine import AmazonSearchEngine
from recommendation.collaborative_filter import CollaborativeFilteringRecommender
from utils.config import WEB_CONFIG

app = Flask(__name__)
CORS(app)

# Production configuration
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# Initialize search engine and recommender
search_engine = None
recommender = None

def init_systems():
    """Initialize search and recommendation systems"""
    global search_engine, recommender
    try:
        search_engine = AmazonSearchEngine()
        recommender = CollaborativeFilteringRecommender()
        print("✅ Search engine and recommender system initialized successfully")
    except Exception as e:
        print(f"❌ Error initializing systems: {str(e)}")
        search_engine = None
        recommender = None

@app.route('/')
def home():
    """Home page"""
    return render_template('index.html')

@app.route('/search')
def search_page():
    """Search page"""
    return render_template('search.html')

@app.route('/recommendations')
def recommendations_page():
    """Recommendations page"""
    return render_template('recommendations.html')

@app.route('/analytics')
def analytics_page():
    """Analytics page"""
    return render_template('analytics.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    """API endpoint for product search"""
    if not search_engine:
        return jsonify({'error': 'Search engine not available'}), 503
    
    try:
        data = request.json
        query_text = data.get('query', '')
        category = data.get('category', '')
        min_price = data.get('min_price')
        max_price = data.get('max_price')
        min_rating = data.get('min_rating')
        brand = data.get('brand', '')
        sort_by = data.get('sort_by', '')
        limit = data.get('limit', 20)
        
        # Convert string numbers to float/None
        try:
            min_price = float(min_price) if min_price else None
            max_price = float(max_price) if max_price else None
            min_rating = float(min_rating) if min_rating else None
        except (ValueError, TypeError):
            min_price = max_price = min_rating = None
        
        # Perform search
        results = search_engine.advanced_search(
            text=query_text if query_text else None,
            category=category if category else None,
            min_price=min_price,
            max_price=max_price,
            min_rating=min_rating,
            brand=brand if brand else None,
            sort_by=sort_by if sort_by else None,
            limit=limit
        )
        
        # Convert to JSON-serializable format
        results_list = []
        for _, row in results.iterrows():
            results_list.append({
                'product_id': row['product_id'],
                'title': row['title'],
                'category': row['category'],
                'brand': row['brand'],
                'price': float(row['price']),
                'avg_rating': float(row['avg_rating']),
                'num_reviews': int(row['num_reviews']),
                'description': row.get('description', ''),
                'price_range': row.get('price_range', '')
            })
        
        return jsonify({
            'results': results_list,
            'total_count': len(results_list)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/best_sellers/<category>')
def api_best_sellers(category):
    """API endpoint for best sellers by category"""
    if not search_engine:
        return jsonify({'error': 'Search engine not available'}), 503
    
    try:
        n = request.args.get('n', 10, type=int)
        results = search_engine.get_best_sellers(category=category, n=n)
        
        results_list = []
        for _, row in results.iterrows():
            results_list.append({
                'product_id': row['product_id'],
                'title': row['title'],
                'category': row['category'],
                'brand': row['brand'],
                'price': float(row['price']),
                'avg_rating': float(row['avg_rating']),
                'num_reviews': int(row['num_reviews']),
                'popularity_score': float(row.get('popularity_score', 0))
            })
        
        return jsonify({'results': results_list})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recommendations/<user_id>')
def api_recommendations(user_id):
    """API endpoint for user recommendations"""
    if not recommender:
        return jsonify({'error': 'Recommender system not available'}), 503
    
    try:
        method = request.args.get('method', 'item_based')
        n = request.args.get('n', 10, type=int)
        
        recommendations = recommender.get_recommendations_for_user(
            user_id=user_id,
            method=method,
            n_recommendations=n
        )
        
        return jsonify({'recommendations': recommendations})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/co_purchasing/<user_id>')
def api_co_purchasing(user_id):
    """API endpoint for co-purchasing analysis"""
    if not recommender:
        return jsonify({'error': 'Recommender system not available'}), 503
    
    try:
        analysis = recommender.analyze_co_purchasing_patterns(user_id)
        return jsonify(analysis)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/categories')
def api_categories():
    """API endpoint for available categories"""
    if not search_engine:
        return jsonify({'error': 'Search engine not available'}), 503
    
    try:
        categories = search_engine.products_df['category'].unique().tolist()
        return jsonify({'categories': sorted(categories)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users')
def api_users():
    """API endpoint for all user IDs"""
    if not recommender:
        return jsonify({'error': 'Recommender system not available'}), 503
    
    try:
        # Get all users who have ratings data
        users = recommender.user_item_matrix.index.tolist()
        return jsonify({'users': users})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def api_stats():
    """API endpoint for system statistics"""
    if not search_engine or not recommender:
        return jsonify({'error': 'Systems not available'}), 503
    
    try:
        stats = {
            'total_products': len(search_engine.products_df),
            'total_ratings': len(search_engine.ratings_df),
            'total_users': len(recommender.user_item_matrix.index),
            'categories': search_engine.products_df['category'].nunique(),
            'avg_rating': float(search_engine.ratings_df['rating'].mean()),
            'price_range': {
                'min': float(search_engine.products_df['price'].min()),
                'max': float(search_engine.products_df['price'].max()),
                'avg': float(search_engine.products_df['price'].mean())
            }
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error in /api/stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Error handlers for production
@app.errorhandler(404)
def not_found_error(error):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("🚀 Starting Amazon Recommender System Web Application...")
    init_systems()
    
    # Use environment variables for production
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    host = os.environ.get('FLASK_HOST', WEB_CONFIG.get('host', '127.0.0.1'))
    port = int(os.environ.get('FLASK_PORT', WEB_CONFIG.get('port', 5000)))
    
    app.run(
        host=host,
        port=port,
        debug=debug_mode
    )