from datetime import datetime, timedelta, timezone
import random
from app.database.db import get_db
from fastapi import Security, status, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import time
from jose import jwt
from passlib.context import CryptContext
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Union, Type, TypeVar, Optional, Generic
from pydantic import BaseModel, ValidationError
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import re 
from urllib.parse import urlparse
import os
from functools import wraps

security = HTTPBearer()

T = TypeVar("T")
# class CommonResponse(GenericModel, Generic[T]):
#     result: Optional[T] = None
#     id: int = 0
#     role_id: int = 0
#     is_success: bool = True
#     message: str = "Success"
#     status_code: Optional[int] = None

#     @classmethod
#     def response_handler(cls, result: T = None, id: int = 0, role_id: int = 0,
#                          is_success: bool = True, message: str = "Success",
#                          status_code: int = None) -> "CommonResponse[T]":
#         return cls(
#             result=result,
#             id=id,
#             role_id=role_id,
#             is_success=is_success,
#             message=message,
#             status_code=status_code
#         )


class CommonResponse(BaseModel, Generic[T]):
    # result: Optional[T] = None
    # id: int = 0
    # role_id: int = 0
    result: Optional[T] = None
    id: Optional[int] = None
    role_id: Optional[int] = None
    is_success: bool = False
    error: Optional[str] = None
    # message: str = "Success"
    message: str
    # status_code: Optional[int] = None
    status_code: int
    pagination: Optional[dict] = None
    token: Optional[str] = None

    @classmethod
    def response_handler(
        cls,
        result: T = None,
        # id: int = 0,
        # role_id: int = 0,
        id = None,
        role_id = None,
        is_success = False,
        error = None,
        message: str = "Success",
        status_code = 200 ,
        pagination: dict = None,
        token : str = None,
    ) -> "CommonResponse[T]":
        return cls(
            result=result,
            id=id,
            role_id=role_id,
            is_success=is_success,
            error=error,
            # discount_value = discount_value,
            # is_percentage = is_percentage,
            # type_id = type_id,
            # type_name = type_name,
            message=message,
            status_code=status_code,
            pagination=pagination,
            token=token,
        )
    
    class Config:
        from_attributes = True 
