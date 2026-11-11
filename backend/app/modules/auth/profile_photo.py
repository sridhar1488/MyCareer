from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageOps
from sqlalchemy import select

from app.core.errors import AppError
from app.modules.users.models import User, UserProfilePhoto

MAX_UPLOAD = 2 * 1024 * 1024


def normalize_photo(data: bytes) -> bytes:
    try:
        with Image.open(BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as image:
            if image.width * image.height > 16_000_000:
                raise AppError(422, "PHOTO_DIMENSIONS", "Choose an image no larger than 16 megapixels.")
            portrait = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (192, 192))
            buffer = BytesIO()
            portrait.save(buffer, format="JPEG", quality=82)
            return buffer.getvalue()
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise AppError(422, "INVALID_PROFILE_PHOTO", "Choose a valid JPEG, PNG, or WebP image.") from error


def change_photo(db, user_id: str, image: bytes | None) -> None:
    user = db.scalar(select(User.id).where(User.id == user_id, User.active.is_(True)).with_for_update())
    if not user:
        raise AppError(401, "SESSION_EXPIRED", "Please sign in again.")
    photo = db.get(UserProfilePhoto, user_id, with_for_update=True, populate_existing=True)
    if image is None:
        if photo:
            db.delete(photo)
    elif photo:
        photo.image = image
        photo.revision = str(uuid4())
    else:
        db.add(UserProfilePhoto(user_id=user_id, revision=str(uuid4()), image=image))
    db.commit()
