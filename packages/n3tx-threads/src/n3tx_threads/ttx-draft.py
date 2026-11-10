""" Typed TX

Our new transaction/threads system

This is our draft file, we put all related class here, but we have to move them to their proper file once implementation is complete.

ID           SRC      NAME        TGT
ttx/067:    user/1 --ANALYZE--> email/42
    # Programmatic dispatch
    ttx/068:    ttx.067 --AGENTIC--> Persons 
        ttx/071:    ttx/68 --MESSAGE--> ttx/68
        ttx/072:    ttx/68 --TOOL--> ttx/68
        ttx/073:    ttx/68 --THINKING--> ttx/68
        ttx/074:    ttx/68 --MESSAGE--> ttx/68
        ttx/075:    ttx/68 --RETURN--> {ttx/68 | Person | ttx/67}
        # Not sure what is the more intuitive, easier to work 
        # with return pattern is.We need to explore those options
    # Programmatic parallel dispatch
    ttx/069:    ttx/67 --AGENTIC--> Organizations
        ttx/076:    ttx/68 --MESSAGE--> ttx/69
        ttx/077:    ttx/68 --TOOL--> ttx/69
        ttx/078:    ttx/68 --SEARCH--> ttx/69
        ttx/079:    ttx/68 --TOOL--> ttx/69
    ttx/070:    ttx/67 --MESSAGE--> ttx/67
        ...
    ttx/080:    ttx/067 --UPDATE--> email/42

They are all noted as ttx/id, but in practice they could be any TTX child (ttx/68 = AgentSession/68)
"""


from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import fields as dataclass_fields, replace
from math import isfinite
from typing import ClassVar, Optional

from pydantic import Field, JsonValue

from n3tx_actors.actor import Actor
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import NEVER
from n3tx_core.models.ref import Ref, is_ref_url, public_id_url


# TTX
class TTX(ActorModel):

    __tablename__: ClassVar[str] = "ttx"
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {"*": NEVER}

    uuid: str
    name: str
    source: str
    target: str
    data: dict = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)
    timestamp: float = Field(allow_inf_nan=False)
    user_owner: Optional[int] = Field(default=None, ge=1, strict=True)

    def __init__(self, tx: TX | None = None, **fields):
        # TODO
        pass

    @property
    def value(self) -> JsonValue | ActorModel:
    """ Loads TTX -> Note (takes desc in data, and create a Note from it.) """
        pass

    def send(...) -> TTX:
        """ Used to send a TX from this TTX. i.e for ttx/67 -> Person, we use ttx67.send("AGENTIC", target=Person, ...). We might actually even be able to use Actor.send() directly, to explore."""
        pass

class Note(TTX):
    """We need a new system for this. When additionnal fields are added to a TTX child (in __init__subclass) Those are saved normally. But when sent, they are serialized, with all additionnal fields being put in tx.data. This way, we do not need a TX enveloppe when sending, Note IS the enveloppe -. i.e Note.tx() -> {src:..., dest:..., ..., data:{desc:str}, ...}. This way we can have arbitrairely complex TTX all fitting inside a normal TX.

    # Note
        modules/notes/
          mixin.py
          model.py
          static/
            note.js # clg-note

    """ 
    name: str # optionnal
    desc: str 


class NoteMixin(ThreadMixin):

    @expose...(...)
    def note(note:str, user):
        # If coming from the frontend, src=user. If called from within another TTX context (i.e) ttx/67 --NOTE--> email/42, src=ttx/67.
        Note(src=user, target=self | cls, name: ..., data:{desc: "My note here""}}
        Note(tx).save()
        return

    @expose...(...)
    def notes(tx, user) -> list[Note]:
        return Note.list("where target = self.addr and user=user")

# Threads
class Thread(TTX):

    # Class meant to be inherited.
    def append()
        cls = self.__class__
        cls(src=user, target=self, data={**kwargs}).save()

    def children(...) -> list[T]:
        """ Get children of this thread (TTX with self.addr as target)

        We might need to handle different child types (i.e a Thread(TTX), Note(TTX), Message(TTX) might all have records pointing to the thread TTX.)
        - Should we add a list of referenced tables for recovery models: list[Ref]? children could have an optionnal parameter to select a specific, list of specific tables to  read from (children([note_ref, Person_ref], ...))
        """
        return T.list("where target = self.addr and user=user")




# # TODO
# ## Questions to resolve
# - Can TX routing support additionnal fields along for the ride?
# - Can/should we organize our routing tree to be: email/42/ttx/67 (ttx are put under their owning ref)
# - We might even be able to generalize eventually, ie Email(Thread[Note], Thread[Comment])
# 
# 
