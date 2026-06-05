from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from database import db
from auth_utilis import hash_password, verify_password, create_access_token
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginModel(BaseModel):
    identifier: str
    password: str


@router.post("/register")
async def register(data: RegisterRequest):
    users = db.users

    if await users.find_one({"username": data.username}):
        raise HTTPException(status_code=400, detail="Username already exists")

    if await users.find_one({"email": data.email}):
        raise HTTPException(status_code=400, detail="Email already exists")

    hashed_password = hash_password(data.password)

    user_doc = {
        "username": data.username,
        "email": data.email,
        "password": hashed_password,
        "created_at": datetime.utcnow()
    }

    result = await users.insert_one(user_doc)

    return {
        "message": "User created",
        "id": str(result.inserted_id)
    }


@router.post("/login")
async def login(data: LoginModel):
    users = db.users
    
    if "@" in data.identifier:
        user = await users.find_one({"email": data.identifier})
    else:
        user = await users.find_one({"username": data.identifier})

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({
        "sub": str(user["_id"])
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }
