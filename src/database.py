from tortoise import Tortoise
from dotenv import load_dotenv
from fastapi import HTTPException
import os
from src.models import User

load_dotenv()

async def init_db():
    try:
        await Tortoise.init(
            db_url=f"postgres://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@"
                   f"{os.getenv('DATABASE_HOST')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_NAME')}",
            modules={"models": ["src.models"]}
        )
        await Tortoise.generate_schemas()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database initialization failed: {str(e)}")
    
async def get_or_create_user(firebase_uid: str, email: str, display_name: str | None):
    try:
        user, created = await User.get_or_create(
            firebase_Uid = firebase_uid,
            defaults={"email": email, "display_name": display_name}
        )
        return user.userID
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error while creating the user:{str(e)}")
    
async def close_db():
    await Tortoise.close_connections()