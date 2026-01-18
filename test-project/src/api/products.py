"""Product API endpoints."""

from typing import Optional
from decimal import Decimal
from src.models.product import Product, ProductCreate
from src.services.product_service import ProductService
from src.middleware.auth import require_auth


class ProductController:
    """Handles product-related API endpoints."""

    def __init__(self, product_service: ProductService):
        """Initialize with product service."""
        self.product_service = product_service

    def get_product(self, product_id: int) -> Optional[Product]:
        """Get a product by ID."""
        return self.product_service.find_by_id(product_id)

    def search_products(
        self,
        query: str,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        category: Optional[str] = None,
        limit: int = 50
    ) -> list[Product]:
        """Search products with filters.

        Args:
            query: Search query string.
            min_price: Minimum price filter.
            max_price: Maximum price filter.
            category: Category filter.
            limit: Max results.

        Returns:
            List of matching products.
        """
        return self.product_service.search(
            query=query,
            min_price=min_price,
            max_price=max_price,
            category=category,
            limit=limit
        )

    def get_products_by_category(self, category: str) -> list[Product]:
        """Get all products in a category."""
        return self.product_service.find_by_category(category)

    @require_auth
    def create_product(self, data: ProductCreate) -> Product:
        """Create a new product."""
        self._validate_price(data.price)
        return self.product_service.create(data)

    @require_auth
    def update_stock(self, product_id: int, quantity: int) -> bool:
        """Update product stock quantity."""
        return self.product_service.update_stock(product_id, quantity)

    def _validate_price(self, price: Decimal) -> None:
        """Ensure price is positive."""
        if price <= 0:
            raise ValueError("Price must be positive")


def calculate_discount(original_price: Decimal, discount_percent: int) -> Decimal:
    """Calculate discounted price.

    Args:
        original_price: The original price.
        discount_percent: Discount percentage (0-100).

    Returns:
        The discounted price.
    """
    if not 0 <= discount_percent <= 100:
        raise ValueError("Discount must be between 0 and 100")
    return original_price * (100 - discount_percent) / 100
