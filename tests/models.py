import datetime
import uuid

from sqlmodel import UUID, Field, Relationship, SQLModel

from .utils import utcnow


class Headquarter(SQLModel, table=True):  # type: ignore
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)

    teams: list["Team"] = Relationship(back_populates="headquarter")


class Team(SQLModel, table=True):  # type: ignore
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)

    headquarter_id: int | None = Field(default=None, foreign_key="headquarter.id")
    headquarter: Headquarter | None = Relationship(back_populates="teams")

    heroes: list["Hero"] = Relationship(back_populates="team")


class Hero(SQLModel, table=True):  # type: ignore
    id: int | None = Field(default=None, primary_key=True)
    name: str
    secret_name: str
    age: int | None = None
    created_at: datetime.datetime = Field(default_factory=utcnow)

    team_id: int | None = Field(default=None, foreign_key="team.id")
    team: Team | None = Relationship(back_populates="heroes")


class Extra(SQLModel, table=True):  # type: ignore
    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4, sa_type=UUID)
    is_admin: bool = Field(...)


class Tag(SQLModel, table=True):
    __tablename__ = "tags"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(...)

    posts: list["Post"] = Relationship(back_populates="tags", sa_relationship_kwargs={"secondary": "taggings"})


class Post(SQLModel, table=True):
    __tablename__ = "posts"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)

    tags: list["Tag"] = Relationship(back_populates="posts", sa_relationship_kwargs={"secondary": "taggings"})


class Tagging(SQLModel, table=True):
    __tablename__ = "taggings"  # type: ignore

    tag_id: str = Field(foreign_key="tags.id", primary_key=True)
    post_id: str = Field(foreign_key="posts.id", primary_key=True)
