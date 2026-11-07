from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.constants import DEFAULT_TENANT_ID
from app.services import Services
from app.types import AccessScope


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_session(services: Annotated[Services, Depends(get_services)]) -> Iterator[Session]:
    with services.session_factory() as session:
        yield session


def get_current_tenant() -> AccessScope:
    """Everyone is the default tenant until login arrives in Phase 3."""
    return AccessScope(tenant_id=DEFAULT_TENANT_ID, principals=("tenant",))


ServicesDep = Annotated[Services, Depends(get_services)]
SessionDep = Annotated[Session, Depends(get_session)]
ScopeDep = Annotated[AccessScope, Depends(get_current_tenant)]
