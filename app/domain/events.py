from datetime import datetime, timezone
from uuid import UUID, uuid4


def build_user_registered_event(
    user_id: UUID,
    email: str,
    role: str,
    first_name: str,
    last_name: str,
) -> dict:
    return {
        "eventId": str(uuid4()),
        "occurredAt": datetime.now(timezone.utc).isoformat(),
        "userId": str(user_id),
        "email": email,
        "role": role,
        "firstName": first_name,
        "lastName": last_name,
    }


def build_user_deleted_event(user_id: UUID) -> dict:
    return {
        "eventId": str(uuid4()),
        "occurredAt": datetime.now(timezone.utc).isoformat(),
        "userId": str(user_id),
    }