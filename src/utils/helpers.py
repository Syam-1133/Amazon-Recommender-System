"""
Utility functions for the Amazon Recommender System
"""
import logging
import time
import functools
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import requests
from tqdm import tqdm
import gzip
import shutil

from .config import LOG_CONFIG


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, LOG_CONFIG["level"]),
        format=LOG_CONFIG["format"],
        handlers=[
            logging.FileHandler(LOG_CONFIG["log_file"]),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def timing_decorator(func):
    """Decorator to measure function execution time"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(__name__)
        start_time = time.time()
        logger.info(f"Starting {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"Completed {func.__name__} in {execution_time:.2f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error in {func.__name__} after {execution_time:.2f} seconds: {str(e)}")
            raise
            
    return wrapper


def download_file(url: str, destination: Path, chunk_size: int = 8192) -> bool:
    """
    Download a file from URL with progress bar
    
    Args:
        url: URL to download from
        destination: Local path to save the file
        chunk_size: Size of chunks to download
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Create destination directory if it doesn't exist
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file already exists
        if destination.exists():
            logger.info(f"File {destination} already exists. Skipping download.")
            return True
            
        logger.info(f"Downloading {url} to {destination}")
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(destination, 'wb') as f, tqdm(
            desc=destination.name,
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
        
        logger.info(f"Successfully downloaded {destination}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to download {url}: {str(e)}")
        # Clean up partial download
        if destination.exists():
            destination.unlink()
        return False


def extract_gzip(source_file: Path, destination_file: Path) -> bool:
    """
    Extract gzip compressed file
    
    Args:
        source_file: Path to gzip file
        destination_file: Path to extract to
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Extracting {source_file} to {destination_file}")
        
        with gzip.open(source_file, 'rb') as f_in:
            with open(destination_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        logger.info(f"Successfully extracted to {destination_file}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to extract {source_file}: {str(e)}")
        return False


def calculate_similarity(vector1: np.ndarray, vector2: np.ndarray, 
                        metric: str = "cosine") -> float:
    """
    Calculate similarity between two vectors
    
    Args:
        vector1: First vector
        vector2: Second vector
        metric: Similarity metric (cosine, pearson, jaccard)
        
    Returns:
        float: Similarity score
    """
    if metric == "cosine":
        from sklearn.metrics.pairwise import cosine_similarity
        return cosine_similarity(vector1.reshape(1, -1), vector2.reshape(1, -1))[0][0]
    
    elif metric == "pearson":
        return np.corrcoef(vector1, vector2)[0][1]
    
    elif metric == "jaccard":
        intersection = np.sum(np.minimum(vector1, vector2))
        union = np.sum(np.maximum(vector1, vector2))
        return intersection / union if union > 0 else 0.0
    
    else:
        raise ValueError(f"Unknown similarity metric: {metric}")


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if division by zero"""
    return numerator / denominator if denominator != 0 else default


def validate_dataframe(df: pd.DataFrame, required_columns: List[str]) -> bool:
    """
    Validate that a DataFrame contains required columns
    
    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        
    Returns:
        bool: True if all required columns present
    """
    missing_columns = set(required_columns) - set(df.columns)
    if missing_columns:
        logger = logging.getLogger(__name__)
        logger.error(f"Missing required columns: {missing_columns}")
        return False
    return True


def create_price_ranges(prices: pd.Series, n_bins: int = 5) -> pd.Series:
    """
    Create price range categories
    
    Args:
        prices: Series of prices
        n_bins: Number of price bins
        
    Returns:
        pd.Series: Price range categories
    """
    return pd.cut(prices, bins=n_bins, labels=[f"Range_{i+1}" for i in range(n_bins)])


def clean_text(text: str) -> str:
    """
    Clean and normalize text data
    
    Args:
        text: Input text
        
    Returns:
        str: Cleaned text
    """
    if pd.isna(text) or text is None:
        return ""
    
    # Convert to string and lowercase
    text = str(text).lower()
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    return text


def format_number(number: float, decimal_places: int = 2) -> str:
    """Format number with appropriate decimal places and thousand separators"""
    if pd.isna(number):
        return "N/A"
    return f"{number:,.{decimal_places}f}"


def get_memory_usage(df: pd.DataFrame) -> Dict[str, str]:
    """Get memory usage information for a DataFrame"""
    memory_usage = df.memory_usage(deep=True)
    return {
        "total": format_number(memory_usage.sum() / 1024**2, 2) + " MB",
        "per_column": {col: format_number(usage / 1024**2, 2) + " MB" 
                      for col, usage in memory_usage.items()}
    }