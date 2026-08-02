from __future__ import annotations

import hashlib

try:
    from meshtastic.protobuf import mqtt_pb2
except ImportError:
    mqtt_pb2 = None


def extract_root_and_suffix(
    topic: str,
    roots: list[str],
) -> tuple[str, str] | None:
    for root in sorted(
        roots,
        key=len,
        reverse=True,
    ):
        prefix = f"{root}/"

        if topic.startswith(prefix):
            return (
                root,
                topic[len(prefix):],
            )

    return None


def is_community_encrypted_topic(
    suffix: str,
    channel_name: str,
) -> bool:
    levels = suffix.split("/")

    if len(levels) < 4:
        return False

    return (
        levels[0] == "2"
        and levels[1] == "e"
        and levels[2].casefold()
        == channel_name.casefold()
    )


def decode_packet_identity(
    payload: bytes,
) -> tuple[
    str,
    int | None,
    int | None,
    str | None,
]:
    fallback = (
        "sha256:"
        f"{hashlib.sha256(payload).hexdigest()}"
    )

    if mqtt_pb2 is None:
        return (
            fallback,
            None,
            None,
            "mqtt_pb2 unavailable",
        )

    try:
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(payload)

        packet = envelope.packet

        packet_from = int(
            getattr(packet, "from", 0)
        )
        packet_id = int(packet.id)

        if packet_from and packet_id:
            return (
                f"mesh:{packet_from}:{packet_id}",
                packet_from,
                packet_id,
                None,
            )

        return (
            fallback,
            packet_from or None,
            packet_id or None,
            "Packet did not contain source and packet ID",
        )

    except Exception as exc:
        return (
            fallback,
            None,
            None,
            f"{type(exc).__name__}: {exc}",
        )
