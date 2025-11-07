"""
Configuration settings for the Amazon Recommender System
"""
import os
from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
MODELS_DIR = PROJECT_ROOT / "models"

# Create directories if they don't exist
for dir_path in [RAW_DATA_DIR, PROCESSED_DATA_DIR, MODELS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Dataset configuration
# Stanford SNAP Amazon product co-purchasing network metadata
AMAZON_META_URL = "http://snap.stanford.edu/data/bigdata/amazon/amazon-meta.txt.gz"

# Local file paths
AMAZON_META_FILE = RAW_DATA_DIR / "amazon-meta.txt.gz"
AMAZON_META_EXTRACTED = RAW_DATA_DIR / "amazon-meta.txt"
PROCESSED_PRODUCTS_FILE = PROCESSED_DATA_DIR / "amazon_products.csv"
PROCESSED_REVIEWS_FILE = PROCESSED_DATA_DIR / "amazon_reviews.csv"


# Spark configuration
SPARK_CONFIG = {
    "spark.app.name": "AmazonRecommenderSystem",
    "spark.master": "local[*]",  # Use all available cores
    "spark.sql.adaptive.enabled": "true",
    "spark.sql.adaptive.coalescePartitions.enabled": "true",
    "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
    "spark.driver.memory": "4g",
    "spark.executor.memory": "4g",
    "spark.driver.maxResultSize": "2g"
}

# Search engine configuration
SEARCH_CONFIG = {
    "max_results": 100,
    "default_page_size": 20,
    "enable_fuzzy_search": True,
    "similarity_threshold": 0.7
}

# Recommender system configuration
RECOMMENDER_CONFIG = {
    "min_interactions": 5,  # Minimum interactions for user/item to be considered
    "n_recommendations": 10,
    "similarity_metric": "cosine",  # cosine, pearson, jaccard
    "algorithms": {
        "collaborative_filtering": {
            "n_factors": 50,
            "n_epochs": 20,
            "learning_rate": 0.005,
            "regularization": 0.02
        },
        "content_based": {
            "feature_weights": {
                "category": 0.3,
                "brand": 0.2,
                "price_range": 0.2,
                "rating": 0.3
            }
        }
    }
}

# Web application configuration
WEB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5000,
    "debug": True,
    "secret_key": os.environ.get("SECRET_KEY", "dev-secret-key")
}

# Logging configuration
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": PROJECT_ROOT / "logs" / "app.log"
}

# Create logs directory
LOG_CONFIG["log_file"].parent.mkdir(parents=True, exist_ok=True)
