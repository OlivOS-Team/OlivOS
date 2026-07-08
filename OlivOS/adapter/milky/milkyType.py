from __future__ import annotations

from dataclasses import dataclass, fields
from typing import (
    TypeAlias, TypeVar, Type,
    Any, Union, Optional,
    get_origin, get_args, get_type_hints
)

MilkyT = TypeVar('T', bound='MilkyStruct')


@dataclass
class MilkyStruct:
    @classmethod
    def from_json(cls: Type[MilkyT], data: dict[str, Any]) -> MilkyT:
        if not isinstance(data, dict):
            return data

        init_kwargs = {}
        type_hints = get_type_hints(cls)
        for field in fields(cls):
            if field.name not in data:
                continue

            init_kwargs[field.name] = convert(
                type_hints[field.name],
                data[field.name]
            )

        return cls(**init_kwargs)


@dataclass
class FriendCategoryEntity(MilkyStruct):
    category_id: int
    category_name: str


@dataclass
class FriendEntity(MilkyStruct):
    user_id: int
    nickname: str
    sex: str
    qid: str
    remark: str
    category: FriendCategoryEntity


@dataclass
class GroupEntity(MilkyStruct):
    group_id: int
    group_name: str
    member_count: int
    max_member_count: int
    remark: str
    created_time: int
    description: str
    question: str
    announcement: str


@dataclass
class GroupMemberEntity(MilkyStruct):
    user_id: int
    nickname: str
    sex: str
    group_id: int
    card: str
    title: str
    level: int
    role: str
    join_time: int
    last_sent_time: int
    shut_up_end_time: Optional[int] = None


@dataclass
class GroupAnnouncementEntity(MilkyStruct):
    group_id: int
    announcement_id: str
    user_id: int
    time: int
    content: str
    image_url: Optional[str] = None


@dataclass
class GroupFileEntity(MilkyStruct):
    group_id: int
    file_id: str
    file_name: str
    parent_folder_id: str
    file_size: int
    uploaded_time: int
    uploader_id: int
    downloaded_times: int
    expire_time: Optional[int] = None


@dataclass
class GroupFolderEntity(MilkyStruct):
    group_id: int
    folder_id: str
    parent_folder_id: str
    folder_name: str
    created_time: int
    last_modified_time: int
    creator_id: int
    file_count: int


@dataclass
class FriendRequest(MilkyStruct):
    time: int
    initiator_id: int
    initiator_uid: str
    target_user_id: int
    target_user_uid: str
    state: str
    comment: str
    via: str
    is_filtered: bool


class GroupNotification:
    @dataclass
    class join_request(MilkyStruct):
        type: str
        group_id: int
        notification_seq: int
        is_filtered: bool
        initiator_id: int
        state: str
        comment: str
        operator_id: Optional[int] = None

    @dataclass
    class admin_change(MilkyStruct):
        type: str
        group_id: int
        notification_seq: int
        target_user_id: int
        is_set: bool
        operator_id: int

    @dataclass
    class kick(MilkyStruct):
        type: str
        group_id: int
        notification_seq: int
        target_user_id: int
        operator_id: int

    @dataclass
    class quit(MilkyStruct):
        type: str
        group_id: int
        notification_seq: int
        target_user_id: int

    @dataclass
    class invited_join_request(MilkyStruct):
        type: str
        group_id: int
        notification_seq: int
        initiator_id: int
        target_user_id: int
        state: str
        operator_id: Optional[int] = None


class IncomingSegmentData:
    @dataclass
    class Text(MilkyStruct):
        text: str

    @dataclass
    class Mention(MilkyStruct):
        user_id: int
        name: str

    @dataclass
    class MentionAll(MilkyStruct):
        pass

    @dataclass
    class Face(MilkyStruct):
        face_id: str
        is_large: bool

    @dataclass
    class Reply(MilkyStruct):
        message_seq: int
        sender_id: int
        time: int
        segments: list[IncomingSegment]
        sender_name: Optional[str] = None

    @dataclass
    class Image(MilkyStruct):
        resource_id: str
        temp_url: str
        width: int
        height: int
        sub_type: str
        summary: str

    @dataclass
    class Record(MilkyStruct):
        resource_id: str
        temp_url: str
        duration: int

    @dataclass
    class Video(MilkyStruct):
        resource_id: str
        temp_url: str
        width: int
        height: int
        duration: int

    @dataclass
    class File(MilkyStruct):
        file_id: str
        file_name: str
        file_size: int
        file_hash: Optional[str] = None

    @dataclass
    class Forward(MilkyStruct):
        forward_id: str
        title: str
        preview: list[str]
        summary: str

    @dataclass
    class MarketFace(MilkyStruct):
        emoji_package_id: int
        emoji_id: str
        key: str
        summary: str
        url: str

    @dataclass
    class LightApp(MilkyStruct):
        app_name: str
        json_payload: str

    @dataclass
    class Xml(MilkyStruct):
        service_id: int
        xml_payload: str


MilkyIncomingSegmentData_T: TypeAlias = Union[
    IncomingSegmentData.Text,
    IncomingSegmentData.Mention,
    IncomingSegmentData.MentionAll,
    IncomingSegmentData.Face,
    IncomingSegmentData.Reply,
    IncomingSegmentData.Image,
    IncomingSegmentData.Record,
    IncomingSegmentData.Video,
    IncomingSegmentData.File,
    IncomingSegmentData.Forward,
    IncomingSegmentData.MarketFace,
    IncomingSegmentData.LightApp,
    IncomingSegmentData.Xml,
    dict
]


@dataclass
class IncomingSegment(MilkyStruct):
    type: str
    data: MilkyIncomingSegmentData_T

    _DATA_ROUTER = {
        'text': IncomingSegmentData.Text,
        'mention': IncomingSegmentData.Mention,
        'mention_all': IncomingSegmentData.MentionAll,
        'face': IncomingSegmentData.Face,
        'reply': IncomingSegmentData.Reply,
        'image': IncomingSegmentData.Image,
        'record': IncomingSegmentData.Record,
        'video': IncomingSegmentData.Video,
        'file': IncomingSegmentData.File,
        'forward': IncomingSegmentData.Forward,
        'market_face': IncomingSegmentData.MarketFace,
        'light_app': IncomingSegmentData.LightApp,
        'xml': IncomingSegmentData.Xml
    }

    @classmethod
    def from_json(cls, raw_data: dict) -> IncomingSegment:
        if not isinstance(raw_data, dict):
            return raw_data

        segment_type = raw_data.get('type', '')
        data_fields = raw_data.get('data')
        if data_fields is None:
            data_fields = {}
        target = cls._DATA_ROUTER.get(segment_type)
        if target is not None:
            parsed = target.from_json(data_fields)
        else:
            parsed = data_fields
        return cls(type=segment_type, data=parsed)


class IncomingMessage:
    @dataclass
    class friend(MilkyStruct):
        peer_id: int
        message_seq: int
        sender_id: int
        time: int
        segments: list[IncomingSegment]
        friend: FriendEntity
        message_scene: str = 'friend'

    @dataclass
    class group(MilkyStruct):
        peer_id: int
        message_seq: int
        sender_id: int
        time: int
        segments: list[IncomingSegment]
        group: GroupEntity
        group_member: GroupMemberEntity
        message_scene: str = 'group'

    @dataclass
    class temp(MilkyStruct):
        peer_id: int
        message_seq: int
        sender_id: int
        time: int
        segments: list[IncomingSegment]
        group: GroupEntity
        message_scene: str = 'temp'


@dataclass
class IncomingForwardedMessage(MilkyStruct):
    message_seq: int
    sender_name: str
    avatar_url: str
    time: int
    segments: list[IncomingSegment]


class OutgoingSegmentData:
    @dataclass
    class Text(MilkyStruct):
        text: str

    @dataclass
    class Mention(MilkyStruct):
        user_id: int

    @dataclass
    class MentionAll(MilkyStruct):
        pass

    @dataclass
    class Face(MilkyStruct):
        face_id: str
        is_large: bool = False

    @dataclass
    class Reply(MilkyStruct):
        message_seq: int

    @dataclass
    class Image(MilkyStruct):
        uri: str
        sub_type: str = 'normal'
        summary: Optional[str] = None

    @dataclass
    class Record(MilkyStruct):
        uri: str

    @dataclass
    class Video(MilkyStruct):
        uri: str
        thumb_uri: Optional[str] = None

    @dataclass
    class Forward(MilkyStruct):
        messages: list[OutgoingForwardedMessage]
        title: Optional[str] = None
        preview: Optional[list[str]] = None
        summary: Optional[str] = None
        prompt: Optional[str] = None

    @dataclass
    class LightApp(MilkyStruct):
        json_payload: str


MilkyOutgoingSegmentData_T: TypeAlias = Union[
    OutgoingSegmentData.Text,
    OutgoingSegmentData.Mention,
    OutgoingSegmentData.MentionAll,
    OutgoingSegmentData.Face,
    OutgoingSegmentData.Reply,
    OutgoingSegmentData.Image,
    OutgoingSegmentData.Record,
    OutgoingSegmentData.Video,
    OutgoingSegmentData.Forward,
    OutgoingSegmentData.LightApp,
    dict
]


@dataclass
class OutgoingSegment(MilkyStruct):
    type: str
    data: MilkyOutgoingSegmentData_T

    _DATA_ROUTER = {
        'text': OutgoingSegmentData.Text,
        'mention': OutgoingSegmentData.Mention,
        'mention_all': OutgoingSegmentData.MentionAll,
        'face': OutgoingSegmentData.Face,
        'reply': OutgoingSegmentData.Reply,
        'image': OutgoingSegmentData.Image,
        'record': OutgoingSegmentData.Record,
        'video': OutgoingSegmentData.Video,
        'forward': OutgoingSegmentData.Forward,
        'light_app': OutgoingSegmentData.LightApp,
    }

    @classmethod
    def from_json(cls, raw_data: dict) -> OutgoingSegment:
        if not isinstance(raw_data, dict):
            return raw_data

        segment_type = raw_data.get('type', '')
        data_fields = raw_data.get('data')
        if data_fields is None:
            data_fields = {}
        target = cls._DATA_ROUTER.get(segment_type)
        if target is not None:
            parsed = target.from_json(data_fields)
        else:
            parsed = data_fields
        return cls(type=segment_type, data=parsed)


@dataclass
class OutgoingForwardedMessage(MilkyStruct):
    user_id: int
    sender_name: str
    segments: list[OutgoingSegment]


@dataclass
class GroupEssenceMessage(MilkyStruct):
    group_id: int
    message_seq: int
    message_time: int
    sender_id: int
    sender_name: str
    operator_id: int
    operator_name: str
    operation_time: int
    segments: list[IncomingSegment]


def convert(tp, value):
    origin = get_origin(tp)

    # Optional[T] / Union
    if origin is Union:
        args = tuple(t for t in get_args(tp) if t is not type(None))
        if len(args) == 1:
            return convert(args[0], value)
        return value

    # list[T]
    if origin is list:
        if not isinstance(value, list):
            return value
        item_type = get_args(tp)[0]
        return [convert(item_type, item) for item in value]

    # dict[K, V]
    if origin is dict:
        if not isinstance(value, dict):
            return value
        key_type, value_type = get_args(tp)
        return {
            convert(key_type, k): convert(value_type, v)
            for k, v in value.items()
        }

    # MilkyStruct
    if (
        isinstance(tp, type)
        and issubclass(tp, MilkyStruct)
        and isinstance(value, dict)
    ):
        return tp.from_json(value)

    return value
