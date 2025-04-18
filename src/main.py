from fastapi import FastAPI, WebSocketDisconnect, WebSocket, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.database import init_db, get_or_create_user, close_db
from src.models import User, Group, GroupMember, Message, UserCreatePydantic, GroupCreatePydantic, GroupMemberPydantic, MessageCreatePydantic, MediaType
from src.auth import verify_firebase_token_websocket, verify_firebase_token
import os
import aiofiles
from contextlib import asynccontextmanager
import uuid
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
security = HTTPBearer()

# websocket connections for group chats
group_connections = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs(os.getenv(""), exist_ok=True)
    # anything above is equivalent to on_event("startup")
    yield
    # anything below is equivalent to on_event("shutdown")
    await close_db()

app.lifespan = lifespan

@app.post("/users")
async def create_users(user: UserCreatePydantic):
    try:
        exisiting_user = await User.filter(
            firebase_Uid = user.firebase_Uid
        ).first() or await User.filter(
            email = user.email
        ).first()
        if exisiting_user:
            raise HTTPException(status_code=400, detail="User already exists")
        await User.create(**user.dict())
        return {"message": "User Created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"User creation failed: {str(e)}")
    
@app.post("groups")
async def create_groups(
    group: GroupCreatePydantic,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    decoded_token = await verify_firebase_token(credentials.credentials)
    creator_id = await get_or_create_user(
        decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
    )
    try:
        creator = await User.get(userID = creator_id)
        new_group = await Group.create(group_name = group.group_name, group_creator = creator)
        await GroupMember.create(group_user=creator, group=new_group)
        return {"group_id": new_group.group_id, "message": "Group created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Group creation failed: {str(e)}")
    
@app.post("/groups/{group_id}/member")
async def add_group_members(
    group_id: int,
    member: GroupMemberPydantic,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    decoded_token = await verify_firebase_token(credentials.credentials)
    requester_id = await get_or_create_user(
        decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
    )
    try:
        group = await Group.get(group_id = group_id)
        requester = await User.get(userID = requester_id)
        if group.group_creator != requester:
            raise HTTPException(status_code=403, detail="Only group creator can add members")
        new_member = await User.get(userID = member.userID)
        existing_member = await GroupMember.filter(group=group, group_user = member).first()
        if existing_member:
            raise HTTPException(status_code=400, detail="User already in group")
        await GroupMember.create(group=group, group_user = member)
        return {"message": f"User {new_member.user_id} added to group {group_id}"}
    except User.DoesNotExist:
        raise HTTPException(status_code=404, detail="User or group not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to add member: {str(e)}")
    
@app.post("/media")
async def upload_media(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    decoded_token = await verify_firebase_token(credentials.credentials)
    await get_or_create_user(
        decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
    )
    try:
        file_extension = file.filename.rsplit(".",1)[-1].lower()
        media_type = MediaType.IMAGE if file_extension in ["jpg", "jpeg", "png"] else MediaType.VIDEO
        file_name = f"{uuid.uuid4()}.{file_extension}"
        file_path = Path(os.getenv("UPLOAD_DIR")) / file_name
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(await file.read())
        media_url = f"/uploads/{file_name}"
        return {"media_url": media_url, "media_type": media_type}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Media upload failed: {str(e)}")