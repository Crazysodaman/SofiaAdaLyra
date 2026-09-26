"""PKG-CLEAN read-only inspection, never authorization to delete."""
from .inventory import Disposition, InventoryRecord, inspect_candidates

__all__ = ["Disposition", "InventoryRecord", "inspect_candidates"]
