"""Order data models."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class OrderStatus(Enum):
    """Order status values."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

    @classmethod
    def active_statuses(cls) -> list["OrderStatus"]:
        """Get statuses that represent active orders."""
        return [cls.PENDING, cls.CONFIRMED, cls.PROCESSING, cls.SHIPPED]

    @classmethod
    def final_statuses(cls) -> list["OrderStatus"]:
        """Get statuses that represent completed orders."""
        return [cls.DELIVERED, cls.CANCELLED, cls.REFUNDED]


@dataclass
class OrderItem:
    """Represents an item in an order."""

    product_id: int
    quantity: int
    price: Decimal = Decimal("0")

    @classmethod
    def from_row(cls, row: dict) -> "OrderItem":
        """Create from database row."""
        return cls(
            product_id=row["product_id"],
            quantity=row["quantity"],
            price=Decimal(str(row["price"])),
        )

    def subtotal(self) -> Decimal:
        """Calculate item subtotal."""
        return self.price * self.quantity


@dataclass
class Order:
    """Represents a customer order."""

    id: int
    user_id: int
    status: OrderStatus
    total: Decimal
    created_at: datetime
    items: list[OrderItem] = field(default_factory=list)
    shipping_address: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "Order":
        """Create Order from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            status=OrderStatus(row["status"]),
            total=Decimal(str(row["total"])),
            created_at=datetime.fromisoformat(row["created_at"]),
            shipping_address=row.get("shipping_address"),
            notes=row.get("notes"),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status.value,
            "total": str(self.total),
            "created_at": self.created_at.isoformat(),
            "items": [
                {"product_id": i.product_id, "quantity": i.quantity, "price": str(i.price)}
                for i in self.items
            ],
            "shipping_address": self.shipping_address,
            "notes": self.notes,
        }

    def can_cancel(self) -> bool:
        """Check if order can be cancelled."""
        return self.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED]

    def is_complete(self) -> bool:
        """Check if order is in a final state."""
        return self.status in OrderStatus.final_statuses()

    def recalculate_total(self) -> Decimal:
        """Recalculate total from items."""
        return sum(item.subtotal() for item in self.items)


@dataclass
class OrderCreate:
    """Data for creating a new order."""

    items: list[OrderItem]
    shipping_address: Optional[str] = None
    notes: Optional[str] = None

    def validate(self) -> list[str]:
        """Validate creation data."""
        errors = []
        if not self.items:
            errors.append("Order must have at least one item")
        for item in self.items:
            if item.quantity <= 0:
                errors.append(f"Invalid quantity for product {item.product_id}")
        return errors


class ShippingMethod:
    """Shipping method constants."""

    STANDARD = "standard"
    EXPRESS = "express"
    OVERNIGHT = "overnight"

    PRICES = {
        STANDARD: Decimal("5.99"),
        EXPRESS: Decimal("12.99"),
        OVERNIGHT: Decimal("24.99"),
    }

    @classmethod
    def get_price(cls, method: str) -> Decimal:
        """Get shipping price for method."""
        return cls.PRICES.get(method, cls.PRICES[cls.STANDARD])
