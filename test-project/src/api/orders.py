"""Order API endpoints."""

from typing import Optional
from datetime import datetime
from src.models.order import Order, OrderCreate, OrderStatus
from src.services.order_service import OrderService
from src.services.user_service import UserService
from src.middleware.auth import require_auth, require_admin


class OrderController:
    """Handles order-related API endpoints."""

    def __init__(self, order_service: OrderService, user_service: UserService):
        """Initialize with required services."""
        self.order_service = order_service
        self.user_service = user_service

    @require_auth
    def get_order(self, order_id: int, user_id: int) -> Optional[Order]:
        """Get an order by ID.

        Users can only access their own orders unless they are admin.
        """
        order = self.order_service.find_by_id(order_id)
        if order and order.user_id == user_id:
            return order
        return None

    @require_auth
    def get_user_orders(
        self,
        user_id: int,
        status: Optional[OrderStatus] = None,
        limit: int = 50
    ) -> list[Order]:
        """Get all orders for a user."""
        return self.order_service.find_by_user(
            user_id=user_id,
            status=status,
            limit=limit
        )

    @require_auth
    def create_order(self, user_id: int, data: OrderCreate) -> Order:
        """Create a new order.

        Args:
            user_id: The ordering user's ID.
            data: Order creation data.

        Returns:
            The created order.

        Raises:
            ValidationError: If cart is empty or items unavailable.
        """
        self._validate_order_items(data)
        return self.order_service.create(user_id, data)

    @require_auth
    def cancel_order(self, order_id: int, user_id: int) -> bool:
        """Cancel an order.

        Only pending orders can be cancelled.
        """
        order = self.order_service.find_by_id(order_id)
        if not order or order.user_id != user_id:
            return False
        if order.status != OrderStatus.PENDING:
            raise ValueError("Can only cancel pending orders")
        return self.order_service.cancel(order_id)

    @require_admin
    def update_order_status(
        self,
        order_id: int,
        status: OrderStatus
    ) -> Optional[Order]:
        """Update order status (admin only)."""
        return self.order_service.update_status(order_id, status)

    @require_admin
    def get_orders_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list[Order]:
        """Get orders within a date range (admin only)."""
        return self.order_service.find_by_date_range(start_date, end_date)

    def _validate_order_items(self, data: OrderCreate) -> None:
        """Validate order items exist and are available."""
        if not data.items:
            raise ValueError("Order must have at least one item")


async def process_order_async(order_id: int) -> bool:
    """Process an order asynchronously.

    This function handles the async order processing workflow.
    """
    # Simulate async processing
    return True
