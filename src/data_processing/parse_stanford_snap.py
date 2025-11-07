"""
Parser for Stanford SNAP Amazon metadata dataset
Extracts and processes the real Amazon product data
"""
import pandas as pd
import numpy as np
import re
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, AMAZON_META_EXTRACTED
from utils.helpers import setup_logging, timing_decorator

logger = setup_logging()


class AmazonDataParser:
    """Parser for the Stanford SNAP Amazon metadata format"""
    
    def __init__(self):
        self.products = []
        self.reviews = []
        self.categories = []
        self.similar_products = []
        
    @timing_decorator
    def parse_amazon_file(self, file_path: Path) -> Dict:
        """
        Parse the Amazon metadata file and extract structured data
        
        Args:
            file_path: Path to the amazon-meta.txt file
            
        Returns:
            Dict with parsed data statistics
        """
        logger.info(f"Starting to parse Amazon metadata file: {file_path}")
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        current_product = {}
        product_count = 0
        review_count = 0
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Skip the "Total items" line
                if line.startswith('Total items:'):
                    continue
                
                # Start of a new product
                if line.startswith('Id:'):
                    # Save previous product if exists
                    if current_product:
                        self._save_product(current_product)
                        product_count += 1
                        
                        if product_count % 10000 == 0:
                            logger.info(f"Processed {product_count} products...")
                    
                    # Start new product
                    current_product = {'id': self._extract_value(line)}
                    current_product['reviews_list'] = []
                
                elif current_product:  # Only process if we have a current product
                    self._parse_product_line(line, current_product)
                    
                    # Track review lines
                    if self._is_review_line(line):
                        review_count += 1
        
        # Save the last product
        if current_product:
            self._save_product(current_product)
            product_count += 1
        
        logger.info(f"Parsing complete. Products: {product_count}, Reviews: {review_count}")
        
        return {
            'products': product_count,
            'reviews': review_count,
            'categories': len(self.categories),
            'similar_products': len(self.similar_products)
        }
    
    def _extract_value(self, line: str) -> str:
        """Extract value after colon"""
        return line.split(':', 1)[1].strip() if ':' in line else ''
    
    def _parse_product_line(self, line: str, product: Dict):
        """Parse a line within a product entry"""
        
        if line.startswith('ASIN:'):
            product['asin'] = self._extract_value(line)
            
        elif line.startswith('title:'):
            product['title'] = self._extract_value(line)
            
        elif line.startswith('group:'):
            product['group'] = self._extract_value(line)
            
        elif line.startswith('salesrank:'):
            try:
                product['salesrank'] = int(self._extract_value(line))
            except ValueError:
                product['salesrank'] = None
                
        elif line.startswith('similar:'):
            self._parse_similar_products(line, product)
            
        elif line.startswith('categories:'):
            try:
                product['categories_count'] = int(self._extract_value(line))
            except ValueError:
                product['categories_count'] = 0
                
        elif line.startswith('|'):
            self._parse_category_line(line, product)
            
        elif line.startswith('reviews:'):
            self._parse_review_summary(line, product)
            
        elif line.startswith('discontinued product'):
            product['discontinued'] = True
            
        elif self._is_review_line(line):
            self._parse_review_line(line, product)
    
    def _parse_similar_products(self, line: str, product: Dict):
        """Parse similar products line"""
        parts = line.split()
        if len(parts) >= 2:
            try:
                similar_count = int(parts[1])
                similar_asins = parts[2:2+similar_count] if len(parts) > 2 else []
                product['similar_products'] = similar_asins
                product['similar_count'] = similar_count
                
                # Store similar product relationships
                for similar_asin in similar_asins:
                    self.similar_products.append({
                        'product_id': product.get('id'),
                        'product_asin': product.get('asin'),
                        'similar_asin': similar_asin
                    })
            except ValueError:
                product['similar_products'] = []
                product['similar_count'] = 0
    
    def _parse_category_line(self, line: str, product: Dict):
        """Parse category hierarchy line"""
        # Remove leading |
        category_path = line[1:]
        
        # Extract category hierarchy
        categories = re.findall(r'([^[]+)\[(\d+)\]', category_path)
        
        if categories:
            category_info = {
                'product_id': product.get('id'),
                'product_asin': product.get('asin'),
                'category_path': ' > '.join([cat[0] for cat in categories]),
                'category_ids': [int(cat[1]) for cat in categories],
                'main_category': categories[0][0] if categories else None,
                'subcategory': categories[-1][0] if len(categories) > 1 else None
            }
            
            self.categories.append(category_info)
            
            # Add to product as well
            if 'categories' not in product:
                product['categories'] = []
            product['categories'].append(category_info)
    
    def _parse_review_summary(self, line: str, product: Dict):
        """Parse review summary line"""
        # Example: reviews: total: 8  downloaded: 8  avg rating: 4
        parts = line.split()
        
        for i, part in enumerate(parts):
            if part == 'total:' and i + 1 < len(parts):
                try:
                    product['total_reviews'] = int(parts[i + 1])
                except ValueError:
                    pass
            elif part == 'downloaded:' and i + 1 < len(parts):
                try:
                    product['downloaded_reviews'] = int(parts[i + 1])
                except ValueError:
                    pass
            elif part == 'rating:' and i + 1 < len(parts):
                try:
                    product['avg_rating'] = float(parts[i + 1])
                except ValueError:
                    pass
    
    def _is_review_line(self, line: str) -> bool:
        """Check if line is a review entry"""
        # Review lines have date format: YYYY-MM-DD
        return bool(re.match(r'^\d{4}-\d{1,2}-\d{1,2}', line))
    
    def _parse_review_line(self, line: str, product: Dict):
        """Parse individual review line"""
        # Example: 2000-7-28  cutomer: A2JW67OY8U6HHK  rating: 5  votes:  10  helpful:   9
        
        try:
            parts = line.split()
            if len(parts) >= 6:
                date_str = parts[0]
                
                review_data = {
                    'product_id': product.get('id'),
                    'product_asin': product.get('asin'),
                    'date': self._parse_date(date_str),
                    'date_str': date_str
                }
                
                # Parse other fields
                for i, part in enumerate(parts):
                    if part == 'cutomer:' and i + 1 < len(parts):
                        review_data['customer_id'] = parts[i + 1]
                    elif part == 'rating:' and i + 1 < len(parts):
                        try:
                            review_data['rating'] = int(parts[i + 1])
                        except ValueError:
                            pass
                    elif part == 'votes:' and i + 1 < len(parts):
                        try:
                            review_data['votes'] = int(parts[i + 1])
                        except ValueError:
                            pass
                    elif part == 'helpful:' and i + 1 < len(parts):
                        try:
                            review_data['helpful'] = int(parts[i + 1])
                        except ValueError:
                            pass
                
                self.reviews.append(review_data)
                product['reviews_list'].append(review_data)
                
        except Exception as e:
            logger.warning(f"Error parsing review line: {line} - {str(e)}")
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to standard format"""
        try:
            # Handle various date formats: YYYY-M-D or YYYY-MM-DD
            year, month, day = date_str.split('-')
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        except:
            return None
    
    def _save_product(self, product: Dict):
        """Save product to internal list"""
        # Clean up the product data
        cleaned_product = {
            'id': product.get('id'),
            'asin': product.get('asin'),
            'title': product.get('title', '').strip(),
            'group': product.get('group', '').strip(),
            'salesrank': product.get('salesrank'),
            'similar_count': product.get('similar_count', 0),
            'categories_count': product.get('categories_count', 0),
            'total_reviews': product.get('total_reviews', 0),
            'downloaded_reviews': product.get('downloaded_reviews', 0),
            'avg_rating': product.get('avg_rating'),
            'discontinued': product.get('discontinued', False)
        }
        
        # Only add products with essential data
        if cleaned_product['id'] and (cleaned_product['title'] or cleaned_product['asin']):
            self.products.append(cleaned_product)
    
    @timing_decorator
    def save_to_csv(self):
        """Save parsed data to CSV files"""
        logger.info("Saving parsed data to CSV files...")
        
        # Ensure output directory exists
        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Save products
        products_df = pd.DataFrame(self.products)
        products_file = PROCESSED_DATA_DIR / "amazon_products.csv"
        products_df.to_csv(products_file, index=False)
        logger.info(f"Saved {len(products_df)} products to {products_file}")
        
        # Save reviews
        if self.reviews:
            reviews_df = pd.DataFrame(self.reviews)
            reviews_file = PROCESSED_DATA_DIR / "amazon_reviews.csv"
            reviews_df.to_csv(reviews_file, index=False)
            logger.info(f"Saved {len(reviews_df)} reviews to {reviews_file}")
        
        # Save categories
        if self.categories:
            categories_df = pd.DataFrame(self.categories)
            categories_file = PROCESSED_DATA_DIR / "amazon_categories.csv"
            categories_df.to_csv(categories_file, index=False)
            logger.info(f"Saved {len(categories_df)} category entries to {categories_file}")
        
        # Save similar products
        if self.similar_products:
            similar_df = pd.DataFrame(self.similar_products)
            similar_file = PROCESSED_DATA_DIR / "amazon_similar_products.csv"
            similar_df.to_csv(similar_file, index=False)
            logger.info(f"Saved {len(similar_df)} similar product relationships to {similar_file}")
        
        return {
            'products_file': products_file,
            'reviews_file': reviews_file if self.reviews else None,
            'categories_file': categories_file if self.categories else None,
            'similar_products_file': similar_file if self.similar_products else None
        }


def main():
    """Main function to parse Amazon data"""
    logger.info("Starting Amazon data parsing process")
    
    # Check if raw data exists
    if not AMAZON_META_EXTRACTED.exists():
        logger.error(f"Raw data file not found: {AMAZON_META_EXTRACTED}")
        logger.info("Please run download_data.py first to download the dataset")
        return
    
    # Parse the data
    parser = AmazonDataParser()
    stats = parser.parse_amazon_file(AMAZON_META_EXTRACTED)
    
    # Save to CSV files
    files = parser.save_to_csv()
    
    # Print summary
    logger.info("=" * 50)
    logger.info("PARSING COMPLETE - SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Total products processed: {stats['products']:,}")
    logger.info(f"Total reviews processed: {stats['reviews']:,}")
    logger.info(f"Total category entries: {stats['categories']:,}")
    logger.info(f"Total similar product relationships: {stats['similar_products']:,}")
    logger.info("")
    logger.info("Generated files:")
    for file_type, file_path in files.items():
        if file_path:
            logger.info(f"  {file_type}: {file_path}")
    
    return stats, files


if __name__ == "__main__":
    main()