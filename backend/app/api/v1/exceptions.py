from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.verification import ExceptionSummary
from app.services.verification import get_exception_summary

router = APIRouter()

@router.get("/summary", response_model=ExceptionSummary, status_code=status.HTTP_200_OK)
def get_exceptions_summary_api(db: Session = Depends(get_db)):
    """
    Returns an aggregated summary of all invoice exceptions.
    """
    return get_exception_summary(db)
