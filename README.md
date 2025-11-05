# Amazon Recommender System

A comprehensive data analytics engine for Amazon product data with search and recommendation capabilities.

## Project Overview

This project implements a recommender system using Amazon metadata from the SNAP Stanford dataset. It includes:

1. **Search Engine**: Complex query support with operators (>, >=, =, <, <=)
2. **Recommender System**: Collaborative filtering based on co-purchasing patterns
3. **Web Interface**: Interactive demonstration of functionalities
4. **Big Data Processing**: Built with Apache Spark for scalability

## Features

### Search Engine
- Best n sellers by category
- Product review statistics
- Complex queries with enriched operators
- Co-purchasing analysis for users

### Recommender System
- Collaborative filtering algorithm
- Co-purchasing pattern analysis
- Personalized product recommendations
- Similarity-based recommendations

## Project Structure

```
amazon-recommender-system/
├── src/
│   ├── data_processing/
│   │   ├── parser.py          # Data parsing and cleaning
│   │   └── preprocessor.py    # Data preprocessing utilities
│   ├── search/
│   │   ├── search_engine.py   # Search functionality
│   │   └── query_processor.py # Query parsing and processing
│   ├── recommendation/
│   │   ├── collaborative_filter.py  # Recommendation algorithms
│   │   └── similarity.py      # Similarity calculations
│   └── utils/
│       ├── config.py          # Configuration settings
│       └── helpers.py         # Utility functions
├── data/
│   ├── raw/                   # Raw Amazon metadata
│   └── processed/             # Cleaned and processed data
├── notebooks/
│   ├── data_exploration.ipynb # Data analysis and exploration
│   └── model_evaluation.ipynb # Model testing and evaluation
├── web/
│   ├── app.py                 # Flask/Streamlit web application
│   └── templates/             # Web templates
├── tests/
│   └── test_*.py             # Unit tests
├── docs/
│   ├── report.md             # Project report
│   └── presentation.pptx     # Project presentation
└── requirements.txt          # Python dependencies
```

## Dataset

**Source**: http://snap.stanford.edu/data/amazon-meta.html

The dataset contains metadata and review information for 548,552 Amazon products including:
- Books
- Music CDs
- DVDs
- VHS video tapes

## Getting Started

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Download the dataset to `data/raw/`
4. Run data preprocessing: `python src/data_processing/parser.py`
5. Start the web interface: `python web/app.py`

## Technologies Used

- **Apache Spark**: Big data processing
- **Python**: Core development language
- **Flask/Streamlit**: Web interface
- **Scikit-learn**: Machine learning algorithms
- **Pandas/NumPy**: Data manipulation
- **Matplotlib/Seaborn**: Data visualization

## Team

- Syam Gudipudi

## Timeline

- **Data Collection & Preprocessing**: Week 1-2
- **Search Engine Development**: Week 3
- **Recommender System Implementation**: Week 4-5
- **Web Interface & Testing**: Week 6
- **Documentation & Presentation**: Week 7

## Deliverables

1. **May 5th 1:30 PM**: Project Presentation
2. **May 5th EOD**: Source Code
3. **May 5th EOD**: Project Report