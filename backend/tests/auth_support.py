"""Trusted administrator actor for pre-auth business regression fixtures only.
Real JWT and role enforcement are covered independently in test_auth.py.
"""
from types import SimpleNamespace
from app.models.enums import UserRole

def business_admin():
    return SimpleNamespace(id=999999, name='Regression Administrator', role=UserRole.ADMIN, is_active=True)
