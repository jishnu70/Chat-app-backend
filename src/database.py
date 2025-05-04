from tortoise import Tortoise
from dotenv import load_dotenv
from fastapi import HTTPException
import os
import logging
from src.models import User

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()]
)
os.environ["PYTHONUNBUFFERED"] = "1"
logger = logging.getLogger()

async def init_db():
    try:
        logger.info("Attempting to connect to database")
        db_url = os.getenv("DATABASE_URL") or f"postgresql://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}@" \
                 f"{os.getenv('DATABASE_HOST')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_NAME')}"
        # Fix for Tortoise ORM: replace 'postgresql' with 'postgres'
        if db_url.startswith("postgresql://"):
            db_url = "postgres://" + db_url[len("postgresql://"):]
        # Remove sslmode from URL if present
        if "?sslmode=" in db_url:
            db_url = db_url.split("?sslmode=")[0]
        logger.info(f"Database URL (sanitized): {db_url.replace(os.getenv('DATABASE_PASSWORD', ''), '****')}")
        # Configure Tortoise with a config dictionary
        config = {
            "connections": {
                "default": {
                    "engine": "tortoise.backends.asyncpg",
                    "credentials": {
                        "database": db_url.split("/")[-1],
                        "host": db_url.split("@")[1].split(":")[0],
                        "port": db_url.split(":")[-1].split("/")[0],
                        "user": db_url.split("//")[1].split(":")[0],
                        "password": db_url.split(":")[2].split("@")[0],
                        "ssl": True
                    }
                }
            },
            "apps": {
                "models": {
                    "models": ["src.models"],
                    "default_connection": "default"
                }
            }
        }
        await Tortoise.init(config=config)
        logger.info("Database connected, generating schemas")
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