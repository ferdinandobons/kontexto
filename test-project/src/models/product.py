"""Product data models."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class Product:
    """Represents a product in the catalog."""

    id: int
    name: str
    description: str
    price: Decimal
    category: str
    stock: int
    active: bool = True
    image_url: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "Product":
        """Create Product from database row."""
        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            price=Decimal(str(row["price"])),
            category=row["category"],
            stock=row["stock"],
            active=row.get("active", True),
            image_url=row.get("image_url"),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": str(self.price),
            "category": self.category,
            "stock": self.stock,
            "active": self.active,
            "image_url": self.image_url,
        }

    def is_available(self) -> bool:
        """Check if product is available for purchase."""
        return self.active and self.stock > 0

    def can_fulfill(self, quantity: int) -> bool:
        """Check if requested quantity is available."""
        return self.is_available() and self.stock >= quantity


@dataclass
class ProductCreate:
    """Data for creating a new product."""

    name: str
    description: str
    price: Decimal
    category: str
    stock: int = 0

    def validate(self) -> list[str]:
        """Validate creation data."""
        errors = []
        if not self.name:
            errors.append("Name is required")
        if self.price <= 0:
            errors.append("Price must be positive")
        if self.stock < 0:
            errors.append("Stock cannot be negative")
        return errors


class ProductCategory:
    """Product category constants."""

    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    BOOKS = "books"
    HOME = "home"
    SPORTS = "sports"

    @classmethod
    def all_categories(cls) -> list[str]:
        """Get all categories."""
        return [
            cls.ELECTRONICS,
            cls.CLOTHING,
            cls.BOOKS,
            cls.HOME,
            cls.SPORTS,
        ]
