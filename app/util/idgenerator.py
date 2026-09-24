import ulid
import secrets
import string
from typing import Type

BASE62 = string.ascii_letters + string.digits


def generate_public_id(
    model: Type,
    prefix: str,
    db_session,
    length: int = 6,
    max_retries: int = 5
) -> str:

    for _ in range(max_retries):

        u = ulid.new().str.lower()

        rand = ''.join(
            secrets.choice(BASE62)
            for _ in range(length)
        )

        public_id = f"{prefix}_{u}_{rand}"

        with db_session.no_autoflush:

            exists = (
                db_session.query(model.id)
                .filter_by(public_id=public_id)
                .first()
            )

        if not exists:
            return public_id

    raise RuntimeError(
        f"Failed to generate unique public_id for {model.__name__}"
    )