"""
Data downloader and initial examiner for Amazon metadata
"""
import sys
import os
from pathlib import Path

# Add src to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))

from utils.helpers import download_file, extract_gzip, setup_logging
from utils.config import AMAZON_META_URL, RAW_DATA_DIR, AMAZON_META_FILE

logger = setup_logging()


def download_amazon_data():
    """Download Amazon metadata from SNAP Stanford"""
    logger.info("Starting Amazon data download...")
    
    # Download the compressed file
    success = download_file(AMAZON_META_URL, AMAZON_META_FILE)
    
    if success:
        logger.info("Download completed successfully")
        
        # Extract the file
        extracted_file = RAW_DATA_DIR / "amazon-meta.txt"
        extract_success = extract_gzip(AMAZON_META_FILE, extracted_file)
        
        if extract_success:
            logger.info(f"File extracted to {extracted_file}")
            return extracted_file
        else:
            logger.error("Failed to extract the downloaded file")
            return None
    else:
        logger.error("Failed to download Amazon data")
        return None


def examine_data_structure(file_path: Path, num_lines: int = 100):
    """
    Examine the structure of the Amazon metadata file
    
    Args:
        file_path: Path to the data file
        num_lines: Number of lines to examine
    """
    logger.info(f"Examining data structure of {file_path}")
    
    if not file_path.exists():
        logger.error(f"File {file_path} does not exist")
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= num_lines:
                    break
                lines.append(line.strip())
        
        logger.info(f"First {len(lines)} lines of the file:")
        for i, line in enumerate(lines[:20]):  # Show first 20 lines
            print(f"{i+1:3d}: {line}")
        
        # Analyze the structure
        analyze_amazon_format(lines)
        
    except Exception as e:
        logger.error(f"Error reading file: {str(e)}")


def analyze_amazon_format(lines):
    """Analyze the Amazon metadata format"""
    logger.info("Analyzing Amazon data format...")
    
    # The Amazon dataset has a specific format
    # Each product starts with "Id: " and contains various fields
    
    fields = {}
    current_product = {}
    product_count = 0
    
    for line in lines:
        if line.startswith("Id:"):
            if current_product:
                # Process previous product
                for field in current_product:
                    if field not in fields:
                        fields[field] = 0
                    fields[field] += 1
                product_count += 1
            current_product = {}
            current_product["Id"] = line.split(":", 1)[1].strip()
        
        elif ":" in line and not line.startswith(" "):
            # Extract field name
            field_name = line.split(":", 1)[0].strip()
            current_product[field_name] = line.split(":", 1)[1].strip()
    
    # Process last product
    if current_product:
        for field in current_product:
            if field not in fields:
                fields[field] = 0
            fields[field] += 1
        product_count += 1
    
    logger.info(f"Found {product_count} products in sample")
    logger.info("Field frequency:")
    for field, count in sorted(fields.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / product_count) * 100 if product_count > 0 else 0
        print(f"  {field}: {count}/{product_count} ({percentage:.1f}%)")


def main():
    """Main function to download and examine Amazon data"""
    logger.info("Starting Amazon data download and examination")
    
    # Check if raw data already exists
    extracted_file = RAW_DATA_DIR / "amazon-meta.txt"
    
    if not extracted_file.exists():
        logger.info("Raw data not found. Downloading...")
        extracted_file = download_amazon_data()
        
        if not extracted_file:
            logger.error("Failed to download data. Exiting.")
            return
    else:
        logger.info("Raw data already exists. Skipping download.")
    
    # Examine the data structure
    examine_data_structure(extracted_file, num_lines=1000)
    
    logger.info("Data examination completed")


if __name__ == "__main__":
    main()