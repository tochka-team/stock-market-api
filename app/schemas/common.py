from typing import Literal

from pydantic import BaseModel


class OkResponse(BaseModel):
    success: Literal[True] = True
