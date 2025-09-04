from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.api.roles.models import RolePermissions, Permissions
from app.database.db import get_db
from typing import List
# from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta, timezone

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import time

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from passlib.context import CryptContext    

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

bearer_scheme = HTTPBearer()

SECRET_KEY = "dG9rZW4tdXJsc2FmZTItc3VwZXItc2VjdXJlLWtleS0xMjM0NTY3ODkwYWJjZGVmZ2hpamtsbW5vcA"
ALGORITHM = "HS256"


def get_password_hash(password: str):
    """
    Function to encrypt password.
    Args:
        password: This will accept the plain password from the user.
 
    Return:
        This will return encrypted password.
    """
    return pwd_context.hash(password)
 
def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)
 
def generate_tokens(email: str, user_id: str, role_id: int) -> dict:
    """
    Generate JWT access and refresh tokens for a user.
 
    Args:
        email (str): User's email address
        user_id (str): User's unique ID
 
    Returns:
        dict: Contains access_token, refresh_token, and access_token_expires_at
    """
    # Access token payload
    access_payload = {
        "email": email,
        "user_id": user_id,
        "role_id": role_id,  # Include role_id in the access token payload
        "exp": datetime.now(timezone.utc)
        + timedelta(days=4),     # minutes=30
        "iat": datetime.now(timezone.utc),
    }
 
    # Refresh token payload
    refresh_payload = {
        "email": email,
        "user_id": user_id,
        "role_id": role_id,  # Include role_id in the refresh token payload
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "iat": datetime.now(timezone.utc),
    }
 
    # Encode tokens
    access_token = jwt.encode(access_payload, SECRET_KEY, algorithm=ALGORITHM)
 
    refresh_token = jwt.encode(refresh_payload, SECRET_KEY, algorithm=ALGORITHM)
 
    # Calculate expiration timestamp (Unix epoch)
    access_token_expires_at = int(time.time() + 30 * 60)
 
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_token_expires_at": access_token_expires_at,
    }
 
 
def check_authorization(
    authorization: HTTPAuthorizationCredentials = Security(bearer_scheme),
):
    """
    Function to check user is authenticated or not.
    Args:
        authorization: This function will accept token to verify the user.
    Return:
        return user payload.
    """
    try:
        token: str = authorization.credentials
        # token_data = jwt.decode(token, "SECRET_KEY", algorithms=["HS256"])
        # print("token_data",token_data)
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
 
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
 
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# def create_access_token(data: dict, expires_delta: timedelta):
#     to_encode = data.copy()
#     to_encode["sub"] = str(to_encode.get("sub", "")) 
#     print("type-=-=-", type(to_encode["sub"])) # Debugging line to check the type of "sub"
#     expire = datetime.utcnow() + expires_delta
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: HTTPAuthorizationCredentials  = Depends(bearer_scheme)):  # your OAuth2 token logic here
    # try:
    # breakpoint()
    token_ext =token.credentials
    payload = jwt.decode(token_ext, SECRET_KEY, algorithms=[ALGORITHM])
    role_id = payload.get("role_id")
    return payload  # include "role_id" in token payload
    # except JWTError as e:
    #     print("JWT decoding error:", str(e))  # 👈 this is important
    #     raise HTTPException(status_code=401, detail="Invalid token!!!")

def get_user_permissions(role_id: int, db: Session) -> List[str]:
    role_perm = db.query(RolePermissions).filter(RolePermissions.role_id == role_id).first()
    if not role_perm:
        return []

    permission_objs = db.query(Permissions).filter(Permissions.id.in_(role_perm.permissions)).all()
    return [p.permission_code() for p in permission_objs]

def check_permission(required: str):
    def dependency(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # def dependency(user: dict = user_dict, db: Session = Depends(get_db)):
        role_id = user.get("role_id")
        user_perms = get_user_permissions(role_id, db)

        if required not in user_perms:
            raise HTTPException(status_code=403, detail="Access denied")
    return dependency


