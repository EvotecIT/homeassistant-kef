"""Regression checks for the standalone KEF Python package."""

from kef_client import KefCommandRejectedError, ModernKefClient, async_create_client
from kef_client.client import ModernKefClient as ClientFromModule
from kef_client.client import async_create_client as FactoryFromModule
from kef_client.exceptions import KefCommandRejectedError as ModuleRejection
from kef_client.exceptions import KefResponseError


def test_public_package_exports_client() -> None:
    assert ModernKefClient is ClientFromModule


def test_public_package_exports_factory() -> None:
    assert async_create_client is FactoryFromModule


def test_public_package_exports_compatible_command_rejection() -> None:
    assert KefCommandRejectedError is ModuleRejection
    assert isinstance(KefCommandRejectedError("rejected"), KefResponseError)
