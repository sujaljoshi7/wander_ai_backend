from typing import Dict

def get_pagination_metadata(total: int, skip: int, limit: int) -> Dict:
    """
    Calculate and return pagination metadata.

    Args:
        total (int): Total number of records.
        skip (int): Number of records to skip.
        limit (int): Maximum number of records to return.

    Returns:
        dict: Pagination metadata.
    """
    current_page = (skip // limit) + 1
    total_pages = (total + limit - 1) // limit  # ceiling division
    has_next = current_page < total_pages
    has_prev = current_page > 1

    return {
        "total": total,
        "page": current_page,
        "limit": limit,
        "pages": total_pages,
        "has_next": has_next,
        "has_prev": has_prev
    }