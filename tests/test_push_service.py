import pytest
from services.gitea.gitea_push_service import GiteaPushService

def test_service_initialization():
    service = GiteaPushService(interval=1)
    assert service.interval == 1
    assert service.running is False
