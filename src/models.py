from tortoise import Model, fields
from tortoise.contrib.pydantic import pydantic_model_creator
from enum import Enum

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"

class User(Model):
    id = fields.IntField(pk=True)
    uid = fields.CharField(max_length=128, unique=True, null=False)
    email = fields.CharField(max_length=255, null=False)
    username = fields.CharField(max_length=100, null=True)
    public_key = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"

class Group(Model):
    group_id = fields.IntField(pk=True)
    group_name = fields.CharField(max_length=255)
    group_creator = fields.ForeignKeyField("models.User", related_name="created_groups")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "groups"

class GroupMember(Model):
    id = fields.IntField(pk=True)
    group = fields.ForeignKeyField("models.Group", related_name="members")
    group_user = fields.ForeignKeyField("models.User", related_name="group_memberships")
    added_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "group_members"
        unique_together = (("group", "group_user"),)

class Message(Model):
    id = fields.IntField(pk=True)
    sender = fields.ForeignKeyField("models.User", related_name="sent_messages")
    receiver = fields.ForeignKeyField("models.User", related_name="received_messages", null=True)
    group = fields.ForeignKeyField("models.Group", related_name="group_messages", null=True)
    message_content = fields.TextField()
    timestamp = fields.DatetimeField(auto_now_add=True)
    media_url = fields.CharField(max_length=255, null=True)
    media_type = fields.CharEnumField(MediaType, null=True)

    class Meta:
        table = "message"

UserCreatePydantic = pydantic_model_creator(User, name="UserCreate", exclude_readonly=True)
GroupCreatePydantic = pydantic_model_creator(Group, name="GroupCreate", exclude=["group_id", "created_at"])
MessageCreatePydantic = pydantic_model_creator(
    Message, name="MessageCreate", exclude=["message_id", "timestamp", "sender", "receiver", "group"]
)
GroupMemberPydantic = pydantic_model_creator(GroupMember, name="GroupMember", exclude_readonly=True)