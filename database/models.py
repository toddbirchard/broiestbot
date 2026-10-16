"""Define data models for chat commands, phrases, user logs, etc."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Declarative base for all models."""


class Chat(Base):
    """Chat from a user to persist in logs."""

    __tablename__ = "chat"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    room: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"id={self.id}, username={self.username}, room={self.room}, chat={self.message}, time={self.created_at}"


class Command(Base):
    """Bot commands triggered by `!` prefix."""

    __tablename__ = "commands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    command: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    type: Mapped[str] = mapped_column(String(255), nullable=False)
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"command={self.command}, type={self.type}, response={self.response}"


class Phrase(Base):
    """Reserved phrases which trigger a response."""

    __tablename__ = "phrases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    phrase: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"command={self.phrase}, type={self.response}"


class ChatangoUser(Base):
    """Chatango user metadata."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    chatango_room: Mapped[Optional[str]] = mapped_column(String(255))
    ip: Mapped[Optional[str]] = mapped_column(String(255), index=True, unique=False)
    city: Mapped[Optional[str]] = mapped_column(String(255))
    region: Mapped[Optional[str]] = mapped_column(String(255))
    country_name: Mapped[Optional[str]] = mapped_column(String(255))
    company: Mapped[Optional[str]] = mapped_column(String(255))
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    postal: Mapped[Optional[str]] = mapped_column(String(255))
    emoji_flag: Mapped[Optional[str]] = mapped_column(Text)
    language: Mapped[Optional[str]] = mapped_column(String(255))
    currency_name: Mapped[Optional[str]] = mapped_column(String(255))
    currency_symbol: Mapped[Optional[str]] = mapped_column(String(255))
    time_zone_name: Mapped[Optional[str]] = mapped_column(String(255))
    time_zone_abbr: Mapped[Optional[str]] = mapped_column(String(255))
    time_zone_offset: Mapped[Optional[int]] = mapped_column(Integer)
    time_zone_is_dst: Mapped[Optional[int]] = mapped_column(Integer)
    time_zone_current_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    carrier_name: Mapped[Optional[str]] = mapped_column(String(255))
    carrier_mnc: Mapped[Optional[str]] = mapped_column(Text)
    carrier_mcc: Mapped[Optional[str]] = mapped_column(Text)
    asn_asn: Mapped[Optional[str]] = mapped_column(Text)
    asn_name: Mapped[Optional[str]] = mapped_column(String(255))
    asn_domain: Mapped[Optional[str]] = mapped_column(String(255))
    asn_route: Mapped[Optional[str]] = mapped_column(String(255))
    asn_type: Mapped[Optional[str]] = mapped_column(String(255))
    is_tor: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_proxy: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_known_attacker: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_threat: Mapped[Optional[bool]] = mapped_column(Boolean)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"id={self.id}, username={self.username}, chatango_room={self.chatango_room}, ip={self.ip}, city={self.city}"


class Weather(Base):
    """Mapping of weather emojis to weather conditions."""

    __tablename__ = "weather"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    code: Mapped[int] = mapped_column(Integer, nullable=False)
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(255), nullable=False)
    group: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self):
        return f"group={self.group}, icon={self.icon}, condition={self.condition}"


class PollResult(Base):
    """Result of a poll or counter."""

    __tablename__ = "poll"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    type: Mapped[str] = mapped_column(String(255), nullable=False, index=True, unique=True)
    count: Mapped[Optional[int]] = mapped_column(Integer)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"id={self.id}, type={self.type}, count={self.count}, updated_at={self.updated_at}"


class Sport(Base):
    """Professional Sport."""

    __tablename__ = "sport"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    abbr: Mapped[Optional[str]] = mapped_column(String(255))
    emoji: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"id={self.id}, name={self.name}, emoji={self.emoji}"


class League(Base):
    """Sports league."""

    __tablename__ = "league"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    display_name: Mapped[Optional[str]] = mapped_column(Text)
    abbr: Mapped[Optional[str]] = mapped_column(String(255))
    country: Mapped[Optional[str]] = mapped_column(String(255))
    sport_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sport.id"), index=True)
    season_year: Mapped[Optional[int]] = mapped_column(Integer)
    season_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, index=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"id={self.id}, name={self.name}, country={self.country}, is_active={self.is_active}"
