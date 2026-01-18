"""Order business logic service."""

from typing import Optional
from datetime import datetime
from decimal import Decimal
from src.models.order import Order, OrderCreate, OrderItem, OrderStatus
from src.services.product_service import ProductService
from src.utils.database import DatabaseConnection


class OrderService:
    """Handles order business logic."""

    def __init__(self, db: DatabaseConnection, product_service: ProductService):
        """Initialize with dependencies."""
        self.db = db
        self.product_service = product_service

    def find_by_id(self, order_id: int) -> Optional[Order]:
        """Find an order by ID."""
        row = self.db.query_one(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,)
        )
        if not row:
            return None

        order = Order.from_row(row)
        order.items = self._get_order_items(order_id)
        return order

    def find_by_user(
        self,
        user_id: int,
        status: Optional[OrderStatus] = None,
        limit: int = 50
    ) -> list[Order]:
        """Find orders for a user."""
        sql = "SELECT * FROM orders WHERE user_id = ?"
        params: list = [user_id]

        if status:
            sql += " AND status = ?"
            params.append(status.value)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.db.query_all(sql, tuple(params))
        orders = []
        for row in rows:
            order = Order.from_row(row)
            order.items = self._get_order_items(order.id)
            orders.append(order)
        return orders

    def find_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list[Order]:
        """Find orders within a date range."""
        rows = self.db.query_all(
            """
            SELECT * FROM orders
            WHERE created_at BETWEEN ? AND ?
            ORDER BY created_at DESC
            """,
            (start_date.isoformat(), end_date.isoformat())
        )
        return [Order.from_row(row) for row in rows]

    def create(self, user_id: int, data: OrderCreate) -> Order:
        """Create a new order.

        This method:
        1. Validates all items are available
        2. Calculates total
        3. Decreases stock
        4. Creates order record
        """
        # Calculate total and validate stock
        total = Decimal("0")
        for item in data.items:
            product = self.product_service.find_by_id(item.product_id)
            if not product:
                raise ValueError(f"Product {item.product_id} not found")
            if product.stock < item.quantity:
                raise ValueError(f"Insufficient stock for {product.name}")
            total += product.price * item.quantity

        # Create order
        order_id = self.db.execute(
            """
            INSERT INTO orders (user_id, status, total, created_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (user_id, OrderStatus.PENDING.value, float(total))
        )

        # Add items and decrease stock
        for item in data.items:
            self._add_order_item(order_id, item)
            self.product_service.decrease_stock(item.product_id, item.quantity)

        return self.find_by_id(order_id)

    def update_status(self, order_id: int, status: OrderStatus) -> Optional[Order]:
        """Update order status."""
        affected = self.db.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (status.value, order_id)
        )
        if affected:
            return self.find_by_id(order_id)
        return None

    def cancel(self, order_id: int) -> bool:
        """Cancel an order and restore stock."""
        order = self.find_by_id(order_id)
        if not order:
            return False

        # Restore stock
        for item in order.items:
            product = self.product_service.find_by_id(item.product_id)
            if product:
                self.product_service.update_stock(
                    item.product_id,
                    product.stock + item.quantity
                )

        # Update status
        self.db.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (OrderStatus.CANCELLED.value, order_id)
        )
        return True

    def _get_order_items(self, order_id: int) -> list[OrderItem]:
        """Get items for an order."""
        rows = self.db.query_all(
            "SELECT * FROM order_items WHERE order_id = ?",
            (order_id,)
        )
        return [OrderItem.from_row(row) for row in rows]

    def _add_order_item(self, order_id: int, item: OrderItem) -> None:
        """Add an item to an order."""
        product = self.product_service.find_by_id(item.product_id)
        self.db.execute(
            """
            INSERT INTO order_items (order_id, product_id, quantity, price)
            VALUES (?, ?, ?, ?)
            """,
            (order_id, item.product_id, item.quantity, float(product.price))
        )


def calculate_order_total(items: list[OrderItem]) -> Decimal:
    """Calculate total for order items.

    Args:
        items: List of order items.

    Returns:
        Total price.
    """
    return sum(item.price * item.quantity for item in items)
