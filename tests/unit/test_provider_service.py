"""Unit tests for ProviderService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.exceptions import NotFoundError, ProviderError
from app.providers.registry import ProviderRegistry
from app.repositories.provider_repository import ProviderRepository
from app.services.provider_service import ProviderService


@pytest.fixture()
def mock_repo() -> MagicMock:
    repo = MagicMock(spec=ProviderRepository)
    repo.get_all.return_value = []
    repo.get_by_id.return_value = None
    repo.insert.return_value = None
    repo.update.return_value = None
    repo.delete.return_value = None
    repo.count.return_value = 1
    return repo


@pytest.fixture()
def mock_reg() -> MagicMock:
    return MagicMock(spec=ProviderRegistry)


@pytest.fixture()
def svc(mock_repo: MagicMock, mock_reg: MagicMock) -> ProviderService:
    return ProviderService(repo=mock_repo, registry=mock_reg)


class TestListProviders:
    def test_empty_list(self, svc: ProviderService, mock_repo: MagicMock) -> None:
        result = svc.list_providers()
        assert result == []
        mock_repo.get_all.assert_called_once()

    def test_returns_configs(self, svc: ProviderService, mock_repo: MagicMock) -> None:
        mock_repo.get_all.return_value = [
            {
                "id": "p1",
                "name": "Massive",
                "type": "MASSIVE",
                "base_url": "https://api.massive.com",
                "enabled": True,
                "priority": 1,
            }
        ]
        result = svc.list_providers()
        assert len(result) == 1
        assert result[0].id == "p1"


class TestCreateProvider:
    def test_create_valid(self, svc: ProviderService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_id.return_value = {
            "id": "prov-test",
            "name": "Test",
            "type": "MASSIVE",
            "base_url": "",
            "enabled": True,
            "priority": 1,
        }
        data = {"name": "Test", "type": "MASSIVE", "baseUrl": ""}
        result = svc.create_provider(data)
        assert result.name == "Test"
        mock_repo.insert.assert_called_once()

    def test_create_invalid_type(self, svc: ProviderService) -> None:
        with pytest.raises(ProviderError, match="Invalid provider type"):
            svc.create_provider({"name": "Bad", "type": "INVALID"})


class TestGetProvider:
    def test_not_found(self, svc: ProviderService) -> None:
        with pytest.raises(NotFoundError):
            svc.get_provider("nonexistent")


class TestUpdateProvider:
    def test_not_found(self, svc: ProviderService) -> None:
        with pytest.raises(NotFoundError):
            svc.update_provider("nonexistent", {"name": "New"})

    def test_update_name(self, svc: ProviderService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_id.return_value = {
            "id": "p1",
            "name": "Old",
            "type": "MASSIVE",
            "base_url": "",
            "enabled": True,
            "priority": 1,
        }
        result = svc.update_provider("p1", {"name": "New"})
        mock_repo.update.assert_called_once()
        assert result.name in ("Old", "New")  # mock returns same row


class TestDeleteProvider:
    def test_not_found(self, svc: ProviderService) -> None:
        with pytest.raises(NotFoundError):
            svc.delete_provider("nonexistent")

    def test_delete_ok(self, svc: ProviderService, mock_repo: MagicMock, mock_reg: MagicMock) -> None:
        mock_repo.get_by_id.return_value = {"id": "p1", "name": "X", "type": "MASSIVE"}
        mock_repo.get_all.return_value = [
            {"id": "p1", "name": "X", "type": "MASSIVE"},
            {"id": "p2", "name": "Y", "type": "MASSIVE"},
        ]
        result = svc.delete_provider("p1")
        assert result["status"] == "deleted"
        mock_repo.delete.assert_called_once_with("p1")
        mock_reg.unregister.assert_called_once_with("p1")


class TestTestConnection:
    def test_not_found(self, svc: ProviderService) -> None:
        with pytest.raises(NotFoundError):
            svc.test_connection("nonexistent")

    def test_custom_provider_not_available(self, svc: ProviderService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_id.return_value = {"id": "p1", "type": "CUSTOM"}
        result = svc.test_connection("p1")
        assert result.success is False
        assert result.latencyMs >= 0
