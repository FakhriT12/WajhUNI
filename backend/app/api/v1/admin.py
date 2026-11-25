from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.models.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ping")
async def ping(
    current_user: User = Depends(require_admin),
) -> dict[str, str]:
    return {"status": "ok"}
