from sqlalchemy.orm import Query
from typing import Optional


def apply_sorting(query: Query, model, sort_by: Optional[str], sort_order: Optional[str]) -> Query:
    """
    Applies sorting to the SQLAlchemy query.

    Args:
        query (Query): SQLAlchemy query.
        model: SQLAlchemy model class.
        sort_by (str): Field name to sort by.
        sort_order (str): 'asc' or 'desc'.

    Returns:
        Query: Sorted query.
    """
    default_sort_by = "created_at"
    sort_by = sort_by or default_sort_by
    if sort_by and hasattr(model, sort_by):
        column = getattr(model, sort_by)
        if sort_order == "desc":
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column.asc())
    return query
