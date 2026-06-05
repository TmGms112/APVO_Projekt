from pydantic import BaseModel

class CreateSong(BaseModel):
    title: str
    artist: str
    duration: int

class Song(CreateSong):
    id: str

class UpdateSong(BaseModel):
    title: str | None = None
    artist: str | None = None
    duration: int | None = None
