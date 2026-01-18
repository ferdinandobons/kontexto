"""Input validation utilities."""

import re
from typing import Any, Optional
from decimal import Decimal, InvalidOperation


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, field: str, message: str):
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


class Validator:
    """Collection of validation methods."""

    EMAIL_PATTERN = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )

    @classmethod
    def email(cls, value: str, field: str = "email") -> str:
        """Validate email format.

        Args:
            value: Email to validate.
            field: Field name for error messages.

        Returns:
            Validated email (lowercase).

        Raises:
            ValidationError: If invalid.
        """
        if not value:
            raise ValidationError(field, "Email is required")

        value = value.strip().lower()
        if not cls.EMAIL_PATTERN.match(value):
            raise ValidationError(field, "Invalid email format")

        return value

    @staticmethod
    def required(value: Any, field: str) -> Any:
        """Validate that value is not empty.

        Args:
            value: Value to check.
            field: Field name.

        Returns:
            The value if valid.

        Raises:
            ValidationError: If empty.
        """
        if value is None or value == "":
            raise ValidationError(field, "This field is required")
        return value

    @staticmethod
    def min_length(value: str, min_len: int, field: str) -> str:
        """Validate minimum string length.

        Args:
            value: String to validate.
            min_len: Minimum length.
            field: Field name.

        Returns:
            The value if valid.

        Raises:
            ValidationError: If too short.
        """
        if len(value) < min_len:
            raise ValidationError(
                field,
                f"Must be at least {min_len} characters"
            )
        return value

    @staticmethod
    def max_length(value: str, max_len: int, field: str) -> str:
        """Validate maximum string length."""
        if len(value) > max_len:
            raise ValidationError(
                field,
                f"Must be at most {max_len} characters"
            )
        return value

    @staticmethod
    def positive_int(value: Any, field: str) -> int:
        """Validate positive integer.

        Args:
            value: Value to validate.
            field: Field name.

        Returns:
            Validated integer.

        Raises:
            ValidationError: If not positive integer.
        """
        try:
            int_val = int(value)
            if int_val <= 0:
                raise ValidationError(field, "Must be a positive integer")
            return int_val
        except (ValueError, TypeError):
            raise ValidationError(field, "Must be an integer")

    @staticmethod
    def positive_decimal(value: Any, field: str) -> Decimal:
        """Validate positive decimal.

        Args:
            value: Value to validate.
            field: Field name.

        Returns:
            Validated Decimal.

        Raises:
            ValidationError: If not positive decimal.
        """
        try:
            dec_val = Decimal(str(value))
            if dec_val <= 0:
                raise ValidationError(field, "Must be a positive number")
            return dec_val
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError(field, "Must be a valid number")

    @staticmethod
    def in_list(value: Any, allowed: list, field: str) -> Any:
        """Validate value is in allowed list.

        Args:
            value: Value to check.
            allowed: List of allowed values.
            field: Field name.

        Returns:
            The value if valid.

        Raises:
            ValidationError: If not in list.
        """
        if value not in allowed:
            raise ValidationError(
                field,
                f"Must be one of: {', '.join(str(a) for a in allowed)}"
            )
        return value


def validate_dict(data: dict, rules: dict) -> dict:
    """Validate a dictionary against rules.

    Args:
        data: Dictionary to validate.
        rules: Dict of field -> validation function pairs.

    Returns:
        Validated dictionary.

    Raises:
        ValidationError: On first validation failure.

    Example:
        rules = {
            "email": lambda v: Validator.email(v),
            "name": lambda v: Validator.min_length(v, 2, "name"),
        }
        validated = validate_dict(data, rules)
    """
    validated = {}
    for field, validator in rules.items():
        value = data.get(field)
        validated[field] = validator(value)
    return validated


def validate_all(data: dict, rules: dict) -> tuple[dict, list[ValidationError]]:
    """Validate dict and collect all errors.

    Unlike validate_dict, this collects all errors instead of
    stopping at the first one.

    Args:
        data: Dictionary to validate.
        rules: Validation rules.

    Returns:
        Tuple of (validated_dict, list_of_errors).
    """
    validated = {}
    errors = []

    for field, validator in rules.items():
        value = data.get(field)
        try:
            validated[field] = validator(value)
        except ValidationError as e:
            errors.append(e)

    return validated, errors
