from pydantic import BaseModel, ConfigDict


class EUMFABaseModel(BaseModel):

    model_config = ConfigDict(extra="forbid", protected_namespaces=(), arbitrary_types_allowed=True)
