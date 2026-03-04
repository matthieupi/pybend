from typing import Annotated, List, Union

from n3tx.core.utils.typer import Ref


class _ListRefMarker:
    """Metadata tag to identify ListRef fields during schema generation."""
    def __init__(self, model_type):
        self.model_type = model_type


class ListRef:
    """
    Type alias factory for collection reference fields.

    Usage:
        comments: Optional[ListRef[Comment]] = []

    Produces Annotated[List[Union[T, str]], _ListRefMarker(T)] so Pydantic
    accepts a list of model instances or string hrefs.
    """
    def __class_getitem__(cls, model_type):
        return Annotated[List[Union[model_type, str]], _ListRefMarker(model_type)]
