from fastapi import APIRouter
from sqlalchemy import text

from api.dependencies import DBSession

router = APIRouter()


@router.get("")
async def health(db=DBSession):
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
