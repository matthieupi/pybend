# app/models/storable_mixin.py

from typing import ClassVar, Any, List

from pydantic import BaseModel

from utils.decorators import expose_route
from storage.abstract_storage import AbstractStorage as StorageInterface


viewables = {} # Global registry for viewable models


class ViewableMixin(BaseModel):
    """
    Mixin that provides storage capabilities to models via dependency injection.
    """

    name: str
    desc: str
    src: str # Path to this resource's inbox for UI callbacks (COMM requests
    href: ClassVar[str] # Path to the HTML view component for this resource

    def __init_subclass__(cls, **kwargs):
        """
        Called when a subclass is created. Registers the class in the global registry.
        """
        cls.href = f"/{cls.__name__.lower()}"
        super().__init_subclass__(**kwargs)

    def __init__(self, **kwargs):
        """
        Initialize the ViewableMixin with the given keyword arguments.
        """
        super().__init__(**kwargs)
        self.name = kwargs.get('name', self.__class__.__name__)
        self.desc = kwargs.get('desc', '')
        self.src = kwargs.get('src', '')

    @classmethod
    @expose_route('/view', methods=['GET'])
    def view(cls) -> str:
        """
        Function returning the HTML view component URL for this resource.

        For now simply return the generic view URL. Eventually, we will check in the registry if a specific view URL is defined for this resource, and fallback to the generic one if not.
        """
        return f"{cls.href}/view"

