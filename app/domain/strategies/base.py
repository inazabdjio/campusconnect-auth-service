from abc import ABC, abstractmethod


class AuthStrategy(ABC):
    @abstractmethod
    def authenticate(self, **kwargs):
        ...