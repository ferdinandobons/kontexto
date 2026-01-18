"""Product business logic service."""

from typing import Optional
from decimal import Decimal
from src.models.product import Product, ProductCreate
from src.utils.database import DatabaseConnection


class ProductService:
    """Handles product business logic."""

    def __init__(self, db: DatabaseConnection):
        """Initialize with database connection."""
        self.db = db

    def find_by_id(self, product_id: int) -> Optional[Product]:
        """Find a product by ID."""
        row = self.db.query_one(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        )
        return Product.from_row(row) if row else None

    def find_by_category(self, category: str) -> list[Product]:
        """Find all products in a category."""
        rows = self.db.query_all(
            "SELECT * FROM products WHERE category = ? AND active = 1",
            (category,)
        )
        return [Product.from_row(row) for row in rows]

    def search(
        self,
        query: str,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        category: Optional[str] = None,
        limit: int = 50
    ) -> list[Product]:
        """Search products with filters."""
        sql = "SELECT * FROM products WHERE active = 1 AND name LIKE ?"
        params: list = [f"%{query}%"]

        if min_price is not None:
            sql += " AND price >= ?"
            params.append(float(min_price))
        if max_price is not None:
            sql += " AND price <= ?"
            params.append(float(max_price))
        if category:
            sql += " AND category = ?"
            params.append(category)

        sql += " ORDER BY name LIMIT ?"
        params.append(limit)

        rows = self.db.query_all(sql, tuple(params))
        return [Product.from_row(row) for row in rows]

    def create(self, data: ProductCreate) -> Product:
        """Create a new product."""
        product_id = self.db.execute(
            """
            INSERT INTO products (name, description, price, category, stock, active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (data.name, data.description, float(data.price), data.category, data.stock)
        )
        return self.find_by_id(product_id)

    def update_stock(self, product_id: int, quantity: int) -> bool:
        """Update product stock.

        Args:
            product_id: Product ID.
            quantity: New stock quantity.

        Returns:
            True if updated.
        """
        affected = self.db.execute(
            "UPDATE products SET stock = ? WHERE id = ?",
            (quantity, product_id)
        )
        return affected > 0

    def decrease_stock(self, product_id: int, amount: int) -> bool:
        """Decrease stock by amount (for orders).

        Args:
            product_id: Product ID.
            amount: Amount to decrease.

        Returns:
            True if successful.

        Raises:
            ValueError: If insufficient stock.
        """
        product = self.find_by_id(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")
        if product.stock < amount:
            raise ValueError(f"Insufficient stock for product {product_id}")

        return self.update_stock(product_id, product.stock - amount)


def format_price(price: Decimal, currency: str = "EUR") -> str:
    """Format price for display.

    Args:
        price: The price value.
        currency: Currency code.

    Returns:
        Formatted price string.
    """
    symbols = {"EUR": "€", "USD": "$", "GBP": "£"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{price:.2f}"
