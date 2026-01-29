"""Define data models for chat commands, phrases, user logs, etc."""

from sqlalchemy.orm import declarative_base, mapped_column
from sqlalchemy import Column, ForeignKey, DateTime, Float, Integer, String, Text, Boolean
from sqlalchemy.sql import func
from database import engine

Base = declarative_base()


class Chat(Base):
    """Chat from a user to persist in logs."""

    __tablename__ = "chat"

    id = Column(Integer, primary_key=True)
    username = Column(String(255), nullable=False, index=True)
    room = Column(String(255), nullable=False, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"id={self.id}, username={self.username}, room={self.room}, chat={self.message}, time={self.created_at}"


class Command(Base):
    """Bot commands triggered by `!` prefix."""

    __tablename__ = "commands"

    id = Column(Integer, primary_key=True, index=True)
    command = Column(String(255), nullable=False, unique=True, index=True)
    type = Column(String(255), nullable=False)
    response = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"command={self.command}, type={self.type}, response={self.response}"


class Phrase(Base):
    """Reserved phrases which trigger a response."""

    __tablename__ = "phrases"

    id = Column(Integer, primary_key=True, index=True)
    phrase = Column(String(255), nullable=False, unique=True, index=True)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"command={self.phrase}, type={self.response}"


class ChatangoUser(Base):
    """Chatango user metadata."""

    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), index=True, nullable=False)
    chatango_room = Column(String(255))
    ip = Column(String(255), index=True, unique=False)
    city = Column(String(255))
    region = Column(String(255))
    country_name = Column(String(255))
    company = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    postal = Column(String(255))
    emoji_flag = Column(Text)
    language = Column(String(255))
    currency_name = Column(String(255))
    currency_symbol = Column(String(255))
    time_zone_name = Column(String(255))
    time_zone_abbr = Column(String(255))
    time_zone_offset = Column(Integer)
    time_zone_is_dst = Column(Integer)
    time_zone_current_time = Column(DateTime)
    carrier_name = Column(String(255))
    carrier_mnc = Column(Text)
    carrier_mcc = Column(Text)
    asn_asn = Column(Text)
    asn_name = Column(String(255))
    asn_domain = Column(String(255))
    asn_route = Column(String(255))
    asn_type = Column(String(255))
    is_tor = Column(Boolean)
    is_proxy = Column(Boolean)
    is_known_attacker = Column(Boolean)
    is_threat = Column(Boolean)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"id={self.id}, username={self.username}, chatango_room={self.chatango_room}, ip={self.ip}, city={self.city}"


class Weather(Base):
    """Mapping of weather emojis to weather conditions."""

    __tablename__ = "weather"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(Integer, nullable=False)
    condition = Column(Text, nullable=False)
    icon = Column(String(255), nullable=False)
    group = Column(String(255), nullable=False)

    def __repr__(self):
        return f"group={self.group}, icon={self.icon}, condition={self.condition}"


class PollResult(Base):
    """Result of a poll or counter."""

    __tablename__ = "poll"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(255), nullable=False, index=True, unique=True)
    count = Column(Integer)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"id={self.id}, type={self.type}, count={self.count}, updated_at={self.updated_at}"


class Sport(Base):
    """Professional Sport."""

    __tablename__ = "sport"

    id = mapped_column(Integer, primary_key=True)
    name = Column(String(255))
    abbr = Column(String(255))
    emoji = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"id={self.id}, name={self.name}, emoji={self.emoji}"


class League(Base):
    """Sports league."""

    __tablename__ = "league"

    id = mapped_column(Integer, primary_key=True)
    name = Column(String(255))
    display_name = Column(Text)
    abbr = Column(String(255))
    country = Column(String(255))
    sport_id = Column(Integer, ForeignKey("sport.id"), index=True)
    season_year = Column(Integer)
    season_start_date = Column(DateTime)
    is_active = Column(Boolean, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"id={self.id}, name={self.name}, country={self.country}, is_active={self.is_active}"


Base.metadata.create_all(engine)
