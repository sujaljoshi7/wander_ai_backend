from fastapi import APIRouter, Depends, HTTPException, status

def validate_user_id(value: int) -> int:
    if value <= 0:
        raise ValueError("user_id must be a positive, non-zero integer")
        # return CommonResponse.response_handler(
        #         is_success=False,
        #         message="user_id must be a positive, non-zero integer",
        #         status_code=status.HTTP_400_BAD_REQUEST
        #     )
    return value

def validate_phone(value: str) -> str:
    if not value.isdigit():
        raise ValueError("Phone number must contain only digits")
    if len(value) != 10:
        raise ValueError("Phone number must be exactly 10 digits")
    return value

