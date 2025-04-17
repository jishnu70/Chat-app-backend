from tortoise import Tortoise
from dotenv import load_dotenv
from fastapi import HTTPException
import os

load_dotenv()

async def init_db():
    try:
        await Tortoise.init(
                db_url=
                    f"postgres://{os.getenv("DATABASE_USER")}:{os.getenv("DATABASE_PASSWORD")}@"
                    f"{os.getenv('DATABASE_HOST')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_NAME')}"
            )
        await Tortoise.generate_schemas()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database initialization failed: {str(e)}")