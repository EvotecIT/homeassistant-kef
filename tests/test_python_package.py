"""Regression checks for the standalone KEF Python package."""

from kef_client import ModernKefClient, async_create_client
from kef_client.client import ModernKefClient as ClientFromModule
from kef_client.client import async_create_client as FactoryFromModule


def test_public_package_exports_client() -> None:
    assert ModernKefClient is ClientFromModule


def test_public_package_exports_factory() -> None:
    assert async_create_client is FactoryFromModule
