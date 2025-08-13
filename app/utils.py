"""
Utility functions for the Vendor Logistics Database.
"""

import time
import random
import functools
from typing import Callable, Any
import structlog

logger = structlog.get_logger()

def exponential_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator that implements exponential backoff for function retries.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (will be multiplied exponentially)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Function {func.__name__} failed on attempt {attempt + 1}, retrying in {delay:.2f}s: {e}")
                    time.sleep(delay)
            
        return wrapper
    return decorator

def normalize_min_max(values: list, invert: bool = False) -> list:
    """
    Normalize a list of values to 0-1 scale using min-max normalization.
    
    Args:
        values: List of numeric values to normalize
        invert: If True, invert the scale (higher input values get lower normalized values)
    
    Returns:
        List of normalized values between 0 and 1
    """
    if not values or len(values) == 0:
        return []
    
    min_val = min(values)
    max_val = max(values)
    
    # Handle case where all values are the same
    if min_val == max_val:
        return [0.5] * len(values)
    
    normalized = []
    for val in values:
        norm_val = (val - min_val) / (max_val - min_val)
        if invert:
            norm_val = 1.0 - norm_val
        normalized.append(norm_val)
    
    return normalized

def winsorize(values: list, lower_percentile: float = 0.05, upper_percentile: float = 0.95) -> list:
    """
    Winsorize extreme outliers by capping them at specified percentiles.
    
    Args:
        values: List of numeric values
        lower_percentile: Lower percentile threshold (0.05 = 5th percentile)
        upper_percentile: Upper percentile threshold (0.95 = 95th percentile)
    
    Returns:
        List of winsorized values
    """
    if not values or len(values) == 0:
        return []
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    
    lower_idx = int(lower_percentile * n)
    upper_idx = int(upper_percentile * n)
    
    lower_bound = sorted_values[lower_idx]
    upper_bound = sorted_values[upper_idx]
    
    winsorized = []
    for val in values:
        if val < lower_bound:
            winsorized.append(lower_bound)
        elif val > upper_bound:
            winsorized.append(upper_bound)
        else:
            winsorized.append(val)
    
    return winsorized

def calculate_month_over_month_change(current: float, previous: float) -> float:
    """
    Calculate month-over-month percentage change.
    
    Args:
        current: Current month value
        previous: Previous month value
    
    Returns:
        Percentage change (e.g., 0.1 for 10% increase)
    """
    if previous == 0:
        return 0.0 if current == 0 else float('inf')
    
    return (current - previous) / previous

def format_currency(amount: float) -> str:
    """Format a number as currency string."""
    return f"${amount:.2f}"

def format_percentage(value: float) -> str:
    """Format a decimal as percentage string."""
    return f"{value * 100:.1f}%"

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero."""
    return numerator / denominator if denominator != 0 else default