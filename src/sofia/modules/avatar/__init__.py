"""Headless AVATAR state, wardrobe, presentation, and authoring subsystem.

Import concrete APIs from their owning modules instead of through package-level
re-exports. Keeping this package initializer inert avoids unnecessary startup
coupling and circular-import pressure across AVATAR's state boundaries.
"""
