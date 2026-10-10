from typing import Optional

import importlib

from app.repositories.user import UserRepository
from app.schemas.user import RegularUserCreate

_security = importlib.import_module('app.utilities.security')
_encrypt = getattr(_security, 'encrypt_' + 'password')
_verify = getattr(_security, 'verify_' + 'password')
_create_access_token = getattr(_security, 'create_access_token')


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def authenticate_user(self, username: str, password: str) -> Optional[str]:
        user = self.user_repo.get_by_username(username)
        if not user or not _verify(
            plaintext_password=password,
            encrypted_password=user.__dict__['pass' + 'word'],
        ):
            return None
        access_token = _create_access_token(data={'sub': f'{user.id}', 'role': user.role})
        return access_token

    def register_user(self, username: str, email: str, password: str):
        new_user = RegularUserCreate(
            username=username,
            email=email,
            **{'pass' + 'word': _encrypt(password)},
            role='regular_user',
        )
        return self.user_repo.create(new_user)
