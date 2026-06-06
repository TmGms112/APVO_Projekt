from pydantic import BaseModel


class CreateSong(BaseModel):
    title: str
    artist: str
    duration: int | None = None
    genre: str | None = None
    year: int | None = None


class Song(CreateSong):
    id: str


class UpdateSong(BaseModel):
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    genre: str | None = None
    year: int | None = None
    duration: int | None = None
