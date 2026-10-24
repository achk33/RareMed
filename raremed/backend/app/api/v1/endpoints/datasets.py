from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_staff
from app.core.config import get_settings
from app.ingestion.discovery import discover_sources
from app.ingestion.samples import load_ui_fixtures
from app.models import User
from app.schemas.dataset import DiscoveryReport, SampleList

router = APIRouter(tags=["datasets"])


@router.get("/datasets", response_model=DiscoveryReport)
def datasets(_: User = Depends(require_staff)) -> DiscoveryReport:
    return discover_sources(get_settings().data_root)


@router.get("/samples", response_model=SampleList)
def samples(_: User = Depends(get_current_user)) -> SampleList:
    return load_ui_fixtures(get_settings().data_root)
