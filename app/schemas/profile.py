from app.schemas.user import UserRead, UserUpdate


class ProfileResponse(UserRead):
    pass


class ProfileUpdate(UserUpdate):
    pass
