from fastapi import FastAPI, WebSocketDisconnect, WebSocket, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
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

# ✅ Allow CORS from any origin
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket group storage
group_connections = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # ✅ FIX: Correct UPLOAD_DIR usage
    os.makedirs(os.getenv("UPLOAD_DIR", "./uploads"), exist_ok=True)
    # anything above is equivalent to on_event("startup")
    yield
    # anything below is equivalent to on_event("shutdown")
    await close_db()

app.lifespan = lifespan

@app.post("/users")
async def create_users(user: UserCreatePydantic):
    try:
        exisiting_user = await User.filter(
            firebase_Uid=user.firebase_Uid
        ).first() or await User.filter(
            email=user.email
        ).first()
        if exisiting_user:
            raise HTTPException(status_code=400, detail="User already exists")
        await User.create(**user.dict())
        return {"message": "User Created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"User creation failed: {str(e)}")

# ✅ FIX: missing forward slash in route
@app.post("/groups")
async def create_groups(
    group: GroupCreatePydantic,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    decoded_token = await verify_firebase_token(credentials.credentials)
    creator_id = await get_or_create_user(
        decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
    )
    try:
        creator = await User.get(userID=creator_id)
        new_group = await Group.create(group_name=group.group_name, group_creator=creator)
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
        group = await Group.get(group_id=group_id)
        requester = await User.get(userID=requester_id)
        if group.group_creator != requester:
            raise HTTPException(status_code=403, detail="Only group creator can add members")
        new_member = await User.get(userID=member.userID)
        existing_member = await GroupMember.filter(group=group, group_user=new_member).first()
        if existing_member:
            raise HTTPException(status_code=400, detail="User already in group")
        await GroupMember.create(group=group, group_user=new_member)
        return {"message": f"User {new_member.userID} added to group {group_id}"}
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
        file_extension = file.filename.rsplit(".", 1)[-1].lower()
        media_type = MediaType.IMAGE if file_extension in ["jpg", "jpeg", "png"] else MediaType.VIDEO
        file_name = f"{uuid.uuid4()}.{file_extension}"
        file_path = Path(os.getenv("UPLOAD_DIR", "./uploads")) / file_name
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(await file.read())
        media_url = f"/uploads/{file_name}"
        return {"media_url": media_url, "media_type": media_type}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Media upload failed: {str(e)}")

# ✅ FIX: Typo in route param + missing await on accept
@app.websocket("/chat/{receiver_id}")
async def individual_chat(websocket: WebSocket, receiver_id: int):
    token = websocket.headers.get("authorization")
    if not token or not token.startswith("Bearer "):
        await websocket.close(code=1000, reason="Authorization header missing or malformed")
        return
    token = token.removeprefix("Bearer ").strip()
    decoded_token = await verify_firebase_token_websocket(token)
    sender_id = await get_or_create_user(
        decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
    )
    sender = await User.filter(userID=sender_id).first()
    receiver = await User.filter(userID=receiver_id).first()
    if not sender or not receiver:
        await websocket.close(code=1008, reason="Sender or receiver not found")
        return
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            if not data.strip():
                await websocket.send_text("Message cannot be empty")
                continue
            message = MessageCreatePydantic(message_content=data)
            await Message.create(
                sender=sender,
                receiver=receiver,
                message_content=message.message_content
            )
            await websocket.send_text(f"You to {receiver_id}: {message.message_content}")
    except WebSocketDisconnect:
        print(f"User {sender_id} disconnected")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await websocket.close()

@app.websocket("/chat/group/{group_id}")
async def group_chat(websocket: WebSocket, group_id: int):
    token = websocket.headers.get("authorization")
    if not token or not token.startswith("Bearer "):
        await websocket.close(code=1008, reason="Authorization header missing or malformed")
        return
    token = token.removeprefix("Bearer ").strip()
    decoded_token = await verify_firebase_token_websocket(token)
    sender_id = await get_or_create_user(
        decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
    )
    sender = await User.filter(userID=sender_id).first()
    group = await Group.filter(group_id=group_id).first()
    membership = await GroupMember.filter(group=group, group_user=sender).first()
    if not sender or not group or not membership:
        await websocket.close(code=1008, reason="Group not found or user not a member")
        return
    if group_id not in group_connections:
        group_connections[group_id] = {}
    group_connections[group_id][sender_id] = websocket

    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            if not data.strip():
                await websocket.send_text("Message cannot be empty")
                continue
            message = MessageCreatePydantic(message_content=data)
            await Message.create(
                sender=sender,
                group=group,
                message_content=message.message_content
            )
            for member_id, member_ws in group_connections.get(group_id, {}).items():
                try:
                    await member_ws.send_text(
                        f"{sender_id} in group {group_id}: {message.message_content}"
                    )
                except Exception as e:
                    print(f"Failed to send to {member_id}: {e}")
    except WebSocketDisconnect:
        print(f"User {sender_id} disconnected from group {group_id}")
    except Exception as e:
        print(f"Error: {e}")
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        group_connections[group_id].pop(sender_id, None)
        if not group_connections[group_id]:
            del group_connections[group_id]
        await websocket.close()