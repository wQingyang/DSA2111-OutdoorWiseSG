from pydantic import BaseModel,ConfigDict,Field
class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
class Coordinate(Contract):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
