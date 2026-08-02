from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers import (
    Cipher,
    algorithms,
    modes,
)
from meshtastic.protobuf import (
    mesh_pb2,
    mqtt_pb2,
    portnums_pb2,
)


BROADCAST_NODE = 0xFFFFFFFF


@dataclass(frozen=True, slots=True)
class DecodedMessage:
    source_node: int
    destination_node: int
    packet_id: int
    portnum: int
    payload: bytes
    text: str | None
    gateway_id: str | None


@dataclass(frozen=True, slots=True)
class OutboundEnvelope:
    topic_suffix: str
    payload: bytes
    packet_id: int
    source_node: int


def decode_base64_psk(value: str) -> bytes:
    cleaned = value.strip()

    if cleaned.startswith("base64:"):
        cleaned = cleaned.removeprefix("base64:")

    if not cleaned:
        raise ValueError("Channel PSK is empty")

    try:
        key = base64.b64decode(
            cleaned,
            validate=True,
        )
    except Exception as exc:
        raise ValueError(
            "Channel PSK is not valid Base64"
        ) from exc

    if len(key) not in {16, 32}:
        raise ValueError(
            "Channel PSK must decode to 16 or 32 bytes; "
            f"received {len(key)} bytes"
        )

    return key


def parse_node_id(value: str) -> int:
    cleaned = value.strip().lower()

    if cleaned.startswith("!"):
        cleaned = cleaned[1:]

    if len(cleaned) != 8:
        raise ValueError(
            "Bot node_id must contain exactly "
            "eight hexadecimal characters"
        )

    try:
        node_number = int(cleaned, 16)
    except ValueError as exc:
        raise ValueError(
            "Bot node_id is not valid hexadecimal"
        ) from exc

    if node_number in {0, BROADCAST_NODE}:
        raise ValueError(
            "Bot node_id cannot be zero or ffffffff"
        )

    return node_number


def format_node_id(node_number: int) -> str:
    return f"!{node_number:08x}"


def build_nonce(
    packet_id: int,
    source_node: int,
) -> bytes:
    return (
        int(packet_id).to_bytes(
            8,
            byteorder="little",
            signed=False,
        )
        + int(source_node).to_bytes(
            8,
            byteorder="little",
            signed=False,
        )
    )


def crypt_payload(
    payload: bytes,
    key: bytes,
    packet_id: int,
    source_node: int,
) -> bytes:
    cipher = Cipher(
        algorithms.AES(key),
        modes.CTR(
            build_nonce(
                packet_id=packet_id,
                source_node=source_node,
            )
        ),
    )

    cryptor = cipher.encryptor()

    return (
        cryptor.update(payload)
        + cryptor.finalize()
    )


def calculate_channel_hash(
    channel_name: str,
    key: bytes,
) -> int:
    result = 0

    for value in channel_name.encode("utf-8"):
        result ^= value

    for value in key:
        result ^= value

    return result


def decrypt_service_envelope(
    payload: bytes,
    key: bytes,
) -> DecodedMessage:
    envelope = mqtt_pb2.ServiceEnvelope()
    envelope.ParseFromString(payload)

    packet = envelope.packet

    source_node = int(
        getattr(packet, "from", 0)
    )
    destination_node = int(packet.to)
    packet_id = int(packet.id)
    encrypted = bytes(packet.encrypted)

    if not source_node:
        raise ValueError(
            "Packet has no source-node number"
        )

    if not packet_id:
        raise ValueError(
            "Packet has no packet ID"
        )

    if not encrypted:
        raise ValueError(
            "Packet has no encrypted payload"
        )

    plaintext = crypt_payload(
        payload=encrypted,
        key=key,
        packet_id=packet_id,
        source_node=source_node,
    )

    data = mesh_pb2.Data()
    data.ParseFromString(plaintext)

    raw_payload = bytes(data.payload)
    text: str | None = None

    if int(data.portnum) == int(
        portnums_pb2.TEXT_MESSAGE_APP
    ):
        try:
            text = raw_payload.decode("utf-8")
        except UnicodeDecodeError:
            text = None

    return DecodedMessage(
        source_node=source_node,
        destination_node=destination_node,
        packet_id=packet_id,
        portnum=int(data.portnum),
        payload=raw_payload,
        text=text,
        gateway_id=envelope.gateway_id or None,
    )


def create_text_service_envelope(
    text: str,
    key: bytes,
    channel_name: str,
    source_node: int,
    hop_limit: int = 3,
) -> OutboundEnvelope:
    encoded_text = text.encode("utf-8")

    if len(encoded_text) > 233:
        raise ValueError(
            "FATBOT response exceeds the "
            "Meshtastic payload limit"
        )

    packet_id = secrets.randbits(32)

    while packet_id == 0:
        packet_id = secrets.randbits(32)

    data = mesh_pb2.Data()
    data.portnum = portnums_pb2.TEXT_MESSAGE_APP
    data.payload = encoded_text

    plaintext = data.SerializeToString()

    ciphertext = crypt_payload(
        payload=plaintext,
        key=key,
        packet_id=packet_id,
        source_node=source_node,
    )

    packet = mesh_pb2.MeshPacket()

    setattr(packet, "from", source_node)

    packet.to = BROADCAST_NODE
    packet.channel = calculate_channel_hash(
        channel_name=channel_name,
        key=key,
    )
    packet.encrypted = ciphertext
    packet.id = packet_id
    packet.hop_limit = hop_limit
    packet.hop_start = hop_limit
    packet.want_ack = False
    packet.priority = mesh_pb2.MeshPacket.DEFAULT
    packet.via_mqtt = True

    gateway_id = format_node_id(source_node)

    envelope = mqtt_pb2.ServiceEnvelope()
    envelope.packet.CopyFrom(packet)
    envelope.channel_id = channel_name
    envelope.gateway_id = gateway_id

    return OutboundEnvelope(
        topic_suffix=(
            f"2/e/{channel_name}/{gateway_id}"
        ),
        payload=envelope.SerializeToString(),
        packet_id=packet_id,
        source_node=source_node,
    )
