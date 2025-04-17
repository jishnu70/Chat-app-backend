from tortoise import Model, fields
from tortoise.contrib.pydantic import pydantic_model_creator

class User(Model):
    userID = fields.IntField(primary_key=True)
    firebase_Uid = fields.CharField(max_length = 128, unique=True)
    email = fields.CharField(max_length=255, unique=True)
    display_name = fields.CharField(max_length=100, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class meta:
        table="users"

class Group(Model):
    group_id = fields.IntField(primary_key=True)
    group_name = fields.CharField(max_length=100)
    group_creator = fields.ForeignKeyField("models.User", related_name="group_creator")
    created_at = fields.DatetimeField(auto_now_add=True)

    class meta:
        table="groups"

class GroupMember(Model):
    group_user = fields.ForeignKeyField("models.User", related_name="group_membership")
    group = fields.ForeignKeyField("models.Group", related_name="members")

    class meta:
        table="group_members"
        unique_together = (("group_user", "group"),)

class Message(Model):
    message_id = fields.IntField(pk=True)
    sender = fields.ForeignKeyField("models.User", related_name="sent_messages")
    receiver = fields.ForeignKeyField("models.User", related_name="received_messages", null=True)
    group = fields.ForeignKeyField("models.Group", related_name="group_messages", null=True)
    message_content = fields.TextField()
    media_url = fields.CharField(max_length=255, null=True)
    media_type = fields.CharField(max_length=20, null=True)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "message"
        indexes = [("sender_id", "receiver_id"), ("group_id",)]

UserCreatePydantic = pydantic_model_creator(User, name="UserCreate", exclude_readonly=True)
GroupCreatePydantic = pydantic_model_creator(Group, name="GroupCreate", exclude=["group_id", "created_at"])
MessageCreatePydantic = pydantic_model_creator(
    Message, name="MessageCreate", exclude=["message_id", "timestamp", "sender", "receiver", "group"]
)
GroupMemberPydantic = pydantic_model_creator(GroupMember, name="GroupMember", exclude_readonly=True)