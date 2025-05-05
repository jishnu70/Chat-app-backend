from tortoise import Model, fields
from tortoise.contrib.pydantic import pydantic_model_creator
from enum import Enum

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"

class User(Model):
    id = fields.IntField(pk=True)
    uid = fields.CharField(max_length=255, unique=True)
    email = fields.CharField(max_length=255)
    username = fields.CharField(max_length=255, null=True)
    public_key = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"

class Group(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "groups"

class GroupMember(Model):
    id = fields.IntField(pk=True)
    group = fields.ForeignKeyField("models.Group", related_name="members", to_field="id")
    group_user = fields.ForeignKeyField("models.User", related_name="group_memberships", to_field="id")

    class Meta:
        table = "group_members"
        unique_together = (("group", "group_user"),)

class Message(Model):
    id = fields.IntField(pk=True)
    sender = fields.ForeignKeyField("models.User", related_name="sent_messages", to_field="id")
    receiver = fields.ForeignKeyField("models.User", related_name="received_messages", to_field="id", null=True)
    group = fields.ForeignKeyField("models.Group", related_name="messages", to_field="id", null=True)
    content = fields.TextField()
    timestamp = fields.DatetimeField(auto_now_add=True)
    media_type = fields.CharEnumField(MediaType, null=True)
    media_url = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "messages"

UserCreatePydantic = pydantic_model_creator(User, name="UserCreate", exclude_readonly=True)
GroupCreatePydantic = pydantic_model_creator(Group, name="GroupCreate", exclude=["group_id", "created_at"])
MessageCreatePydantic = pydantic_model_creator(
    Message, name="MessageCreate", exclude=["message_id", "timestamp", "sender", "receiver", "group"]
)
GroupMemberPydantic = pydantic_model_creator(GroupMember, name="GroupMember", exclude_readonly=True)