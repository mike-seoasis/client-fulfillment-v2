"""API v1 router - minimal health-only setup for v2 rebuild."""

from fastapi import APIRouter

router = APIRouter(tags=["v1"])

# All endpoints have been removed for v2 rebuild.
# Health endpoints are defined directly in main.py.
