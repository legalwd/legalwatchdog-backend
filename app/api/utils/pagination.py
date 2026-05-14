def calculate_pagination(total: int, page: int, limit: int) -> dict:
    """
    Calculate pagination metadata.

    Args:
        total: Total number of items
        page: Current page number
        limit: Items per page

    Returns:
        Dictionary with pagination metadata
    """
    total_pages = (total + limit - 1) // limit if total > 0 else 0

    return {"total": total, "page": page, "limit": limit, "total_pages": total_pages}
