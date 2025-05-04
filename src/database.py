from tortoise import Tortoise
from dotenv import load_dotenv
from fastapi import HTTPException
import os
import logging
from src.models import User

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def init_db():
    try:
        logger.info("Attempting to connect to database...")
        db_url = os.getenv("DATABASE_URL")
        await Tortoise.init(
            db_url= db_url,
            modules={"models": ["src.models"]}
        )
        logger.info("Database connected, generating schemas...")
        await Tortoise.generate_schemas()
        logger.info("Database initialization complete")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}", exc_info=True)
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