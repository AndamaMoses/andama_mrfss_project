"""Persona-driven QA harness.

This package is intentionally separate from the application: it creates
scratch databases, seeds synthetic data, and drives the real Flask routes
through the test client. It never opens the live pilot database.
"""
