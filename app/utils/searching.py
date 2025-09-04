from sqlalchemy.orm import Query
from sqlalchemy import or_
from typing import List, Optional


def apply_searching(query: Query, model, search_fields: List[str], keyword: Optional[str]) -> Query:
    """
    Apply searching on specified fields.

    Args:
        query (Query): SQLAlchemy query.
        model: SQLAlchemy model class.
        search_fields (list): List of field names to search in.
        keyword (str): Keyword to search for.

    Returns:
        Query: Filtered query.
    """
    if keyword:
        search_filters = []
        for field in search_fields:
            if hasattr(model, field):
                search_filters.append(getattr(model, field).ilike(f"%{keyword}%"))
        if search_filters:
            query = query.filter(or_(*search_filters))
    return query
