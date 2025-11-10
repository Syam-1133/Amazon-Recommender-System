"""
Query processor for parsing and validating search queries
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ComparisonOperator(Enum):
    """Enumeration of supported comparison operators"""
    EQUALS = "="
    GREATER_THAN = ">"
    GREATER_EQUAL = ">="
    LESS_THAN = "<"
    LESS_EQUAL = "<="
    NOT_EQUAL = "!="
    LIKE = "LIKE"
    IN = "IN"


@dataclass
class SearchFilter:
    """Represents a single search filter"""
    field: str
    operator: ComparisonOperator
    value: Any
    
    def __str__(self):
        return f"{self.field} {self.operator.value} {self.value}"


@dataclass
class SearchQuery:
    """Represents a complete search query"""
    text_query: Optional[str] = None
    filters: List[SearchFilter] = None
    sort_by: Optional[str] = None
    sort_order: str = "asc"  # asc or desc
    limit: Optional[int] = None
    offset: int = 0
    
    def __post_init__(self):
        if self.filters is None:
            self.filters = []


class QueryProcessor:
    """Processes and parses search queries"""
    
    # Mapping of field names to their data types
    FIELD_TYPES = {
        'price': 'float',
        'rating': 'float',  # Allow 'rating' as alias for 'avg_rating'
        'avg_rating': 'float',
        'num_reviews': 'int',
        'total_reviews': 'int',  # Allow 'total_reviews' as alias for 'num_reviews'
        'sales_rank': 'int',
        'salesrank': 'int',  # Allow 'salesrank' as alias
        'category': 'string',
        'brand': 'string',
        'title': 'string',
        'description': 'string',
        'price_range': 'string',
        'group': 'string'  # Allow 'group' as alias for 'category'
    }
    
    # Valid sortable fields
    SORTABLE_FIELDS = ['price', 'avg_rating', 'num_reviews', 'sales_rank', 'title']
    
    def __init__(self):
        self.operators_pattern = r'(>=|<=|!=|>|<|=|LIKE|IN)'
    
    def parse_query_string(self, query_string: str) -> SearchQuery:
        """
        Parse a natural language query string into SearchQuery object
        
        Example queries:
        - "laptops with price > 500"
        - "books category = Books AND rating >= 4.0"
        - "electronics price between 100 and 500"
        """
        query = SearchQuery()
        
        # Split the query into parts
        parts = self._split_query_parts(query_string)
        
        for part in parts:
            part = part.strip()
            
            # Check if it's a filter with comparison operator
            if re.search(self.operators_pattern, part):
                filter_obj = self._parse_filter(part)
                if filter_obj:
                    query.filters.append(filter_obj)
            else:
                # Treat as text search
                if query.text_query:
                    query.text_query += f" {part}"
                else:
                    query.text_query = part
        
        return query
    
    def _split_query_parts(self, query_string: str) -> List[str]:
        """Split query string into logical parts"""
        # Simple splitting on AND/OR for now
        # More sophisticated parsing could be added later
        parts = re.split(r'\s+(AND|OR)\s+', query_string, flags=re.IGNORECASE)
        return [p for p in parts if p.upper() not in ['AND', 'OR']]
    
    def _parse_filter(self, filter_string: str) -> Optional[SearchFilter]:
        """Parse a single filter from string"""
        # Remove common words
        filter_string = re.sub(r'\b(with|having|where)\b', '', filter_string, flags=re.IGNORECASE)
        filter_string = filter_string.strip()
        
        # Find operator
        match = re.search(self.operators_pattern, filter_string)
        if not match:
            return None
        
        operator_str = match.group(1)
        operator = ComparisonOperator(operator_str)
        
        # Split by operator
        parts = filter_string.split(operator_str, 1)
        if len(parts) != 2:
            return None
        
        field = parts[0].strip().lower()
        value_str = parts[1].strip()
        
        # Validate field
        if field not in self.FIELD_TYPES:
            return None
        
        # Convert value to appropriate type
        value = self._convert_value(value_str, self.FIELD_TYPES[field])
        if value is None:
            return None
        
        return SearchFilter(field=field, operator=operator, value=value)
    
    def _convert_value(self, value_str: str, data_type: str) -> Any:
        """Convert string value to appropriate data type"""
        value_str = value_str.strip('\'"')
        
        try:
            if data_type == 'int':
                return int(value_str)
            elif data_type == 'float':
                return float(value_str)
            elif data_type == 'string':
                return value_str
            else:
                return value_str
        except ValueError:
            return None
    
    def create_simple_query(self, 
                          text: str = None,
                          category: str = None,
                          min_price: float = None,
                          max_price: float = None,
                          min_rating: float = None,
                          brand: str = None,
                          sort_by: str = None,
                          sort_order: str = "asc",
                          limit: int = None) -> SearchQuery:
        """Create a SearchQuery object using simple parameters"""
        
        query = SearchQuery(text_query=text, sort_by=sort_by, sort_order=sort_order, limit=limit)
        
        # Add filters based on parameters
        if category:
            query.filters.append(SearchFilter("category", ComparisonOperator.EQUALS, category))
        
        if brand:
            query.filters.append(SearchFilter("brand", ComparisonOperator.EQUALS, brand))
        
        if min_price is not None:
            query.filters.append(SearchFilter("price", ComparisonOperator.GREATER_EQUAL, min_price))
        
        if max_price is not None:
            query.filters.append(SearchFilter("price", ComparisonOperator.LESS_EQUAL, max_price))
        
        if min_rating is not None:
            query.filters.append(SearchFilter("avg_rating", ComparisonOperator.GREATER_EQUAL, min_rating))
        
        return query
    
    def validate_query(self, query: SearchQuery) -> Tuple[bool, List[str]]:
        """Validate a search query and return validation results"""
        errors = []
        
        # Validate sort field
        if query.sort_by and query.sort_by not in self.SORTABLE_FIELDS:
            errors.append(f"Invalid sort field: {query.sort_by}. Valid fields: {self.SORTABLE_FIELDS}")
        
        # Validate sort order
        if query.sort_order not in ['asc', 'desc']:
            errors.append(f"Invalid sort order: {query.sort_order}. Use 'asc' or 'desc'")
        
        # Validate filters
        for filter_obj in query.filters:
            if filter_obj.field not in self.FIELD_TYPES:
                errors.append(f"Invalid filter field: {filter_obj.field}")
        
        # Validate limit
        if query.limit is not None and query.limit <= 0:
            errors.append("Limit must be greater than 0")
        
        return len(errors) == 0, errors
    
    def get_example_queries(self) -> List[str]:
        """Return example queries for demonstration"""
        return [
            "laptops",
            "books with price < 50",
            "electronics with rating >= 4.0",
            "category = Books AND price <= 30",
            "brand = Apple AND price > 100",
            "rating >= 4.5 AND num_reviews > 100",
            "Sports equipment under $100"
        ]