"""Chatango bot."""

import asyncio
import re
from typing import Optional, Tuple

import chatango
from chatango import Room, RoomMessage
from emoji import emojize
from logger import LOGGER

from broiestbot.commands import (  # get_crypto_chart,
    all_leagues_golden_boot,
    bach_gang_counter,
    basic_message,
    blaze_time_remaining,
    change_or_stay_vote,
    covid_cases_usa,
    create_wiki_preview,
    epl_golden_boot,
    fetch_aafk_fixture_data,
    fetch_fox_fixtures,
    fetch_latest_image_from_gcs_bucket,
    fetch_random_image_from_gcs_bucket,
    fetch_redgifs_gif,
    fetch_sleeper_matchups,
    find_movie,
    footy_all_upcoming_fixtures,
    footy_live_fixtures,
    footy_live_odds,
    footy_stats_for_live_fixtures,
    footy_team_lineups,
    footy_today_fixtures_odds,
    footy_upcoming_fixtures,
    gcs_count_images_in_bucket,
    generate_llm_response,
    generate_twitter_preview,
    generate_youtube_video_preview,
    search_youtube_video,
    get_all_live_twitch_streams,
    get_crypto_price,
    get_current_show,
    get_current_weather,
    get_english_definition,
    get_english_translation,
    get_live_nfl_game_summaries,
    get_live_poll_results,
    get_odds,
    get_psn_game_trophies,
    get_psn_online_friends,
    get_song_lyrics,
    get_stock,
    get_summer_olympic_medals,
    get_titles_with_stats,
    get_today_nfl_games,
    get_top_crypto,
    get_urban_definition,
    get_winter_olympic_medals,
    klipy_image_search,
    league_table_standings,
    live_nba_games,
    mls_standings,
    nba_standings,
    nontent_time_remaining,
    random_image,
    search_youtube_video,
    send_text_message,
    spam_random_images_from_gcs_bucket,
    streaming_service_show,
    time_until_wayne,
    today_sumo_matches,
    today_upcoming_fixtures,
    tovala_counter,
    tuner,
    upcoming_nba_games,
    upcoming_sumo_matches,
    wiki_summary,
)
from config import (
    BUND_LEAGUE_ID,
    CHATANGO_IGNORED_IPS,
    CHATANGO_IGNORED_USERS,
    ELITESERIEN_LEAGUE_ID,
    ENGLISH_CHAMPIONSHIP_LEAGUE_ID,
    ENGLISH_LEAGUE_ONE_ID,
    ENGLISH_LEAGUE_TWO_ID,
    ENGLISH_NATIONAL_LEAGUE_ID,
    EPL_LEAGUE_ID,
    LIGA_LEAGUE_ID,
    LIGUE_ONE_ID,
    PRIMEIRA_LIGA_ID,
)
from database import async_session
from database.models import Command, Phrase

from .data import persist_chat_logs, persist_user_data
from .moderation import ban_daddy_anons, ban_word, check_blacklisted_users
from .moderation.users import ignored_user


async def _db_fetch_command(cmd: str) -> Optional[Command]:
    """Fetch a bot command from the database in its own async session."""
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(Command).where(Command.command == cmd))
        return result.scalars().first()


async def _db_fetch_phrase(chat_message: str) -> Optional[Phrase]:
    """Fetch a trigger phrase from the database in its own async session."""
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(Phrase).where(Phrase.phrase == chat_message))
        return result.scalars().one_or_none()


class Bot(chatango.Client):
    """Chatango bot."""

    def __init__(self, username: str = "", password: str = "", rooms: list = []):
        super().__init__(username=username, password=password, rooms=rooms)
        self.bot_username = username

    async def on_started(self):
        """Initialize bot font and color settings across all connected rooms."""
        for room in self.rooms.values():
            room.set_font(
                name_color="000000",
                font_color="000000",
                font_face=0,  # 0 = Arial
                font_size=11,
            )

    def create_message(
        self,
        cmd_type,
        content,
        command: Optional[str] = None,
        args: Optional[str] = None,
        room_name: Optional[str] = None,
        user_name: Optional[str] = None,
        bot_username: Optional[str] = None,
    ) -> Optional[str]:
        """
        Construct a message response based on command type and arguments.

        :param str cmd_type: `Type` of command triggered by a user.
        :param str content: Content to be used in response.
        :param Optional[str] command: Name of command triggered by user.
        :param Optional[str] args: Additional arguments passed with user command.
        :param Optional[str] room_name: Current Chatango room name.
        :param Optional[str] user_name: User who triggered command.
        :param Optional[str] bot_username: Bot's username in the room.

        :returns: Optional[str]
        """
        if cmd_type == "basic":
            return basic_message(content)
        elif cmd_type == "random":
            return random_image(content)
        elif cmd_type == "stock" and args:
            return get_stock(args)
        elif cmd_type == "randomimage":
            return fetch_random_image_from_gcs_bucket(content)
        elif cmd_type == "imagespam":
            return spam_random_images_from_gcs_bucket(content)
        elif cmd_type == "crypto" and command:
            return get_crypto_price(command.lower(), content)
        elif cmd_type == "giphy":
            return klipy_image_search(content)
        elif cmd_type == "weather" and args and room_name and user_name:
            return get_current_weather(args, room_name, user_name)
        elif cmd_type == "wiki" and args:
            return wiki_summary(args)
        elif cmd_type == "imdb" and args:
            return find_movie(args)
        elif cmd_type == "streamingshow" and args:
            return streaming_service_show(args)
        elif cmd_type == "urban" and args:
            return get_urban_definition(args)
        elif cmd_type == "420" and args is None:
            return blaze_time_remaining()
        elif cmd_type == "nontent" and user_name:
            return nontent_time_remaining(user_name)
        elif cmd_type == "sms" and args and user_name and content:
            return send_text_message(args, user_name, content)
        elif cmd_type == "epltable":
            return league_table_standings(EPL_LEAGUE_ID)
        elif cmd_type == "ligatable":
            return league_table_standings(LIGA_LEAGUE_ID)
        elif cmd_type == "bundtable":
            return league_table_standings(BUND_LEAGUE_ID)
        elif cmd_type == "efltable":
            return league_table_standings(ENGLISH_CHAMPIONSHIP_LEAGUE_ID)
        elif cmd_type == "eng1table":
            return league_table_standings(ENGLISH_LEAGUE_ONE_ID)
        elif cmd_type == "eng2table":
            return league_table_standings(ENGLISH_LEAGUE_TWO_ID)
        elif cmd_type == "engnationaltable":
            return league_table_standings(ENGLISH_NATIONAL_LEAGUE_ID)
        elif cmd_type == "liguetable":
            return league_table_standings(LIGUE_ONE_ID)
        elif cmd_type == "primeratable":
            return league_table_standings(PRIMEIRA_LIGA_ID)
        elif cmd_type == "estable":
            return league_table_standings(ELITESERIEN_LEAGUE_ID)
        elif cmd_type == "mlstable":
            return mls_standings()
        elif cmd_type == "fixtures" and room_name and user_name:
            return footy_upcoming_fixtures(room_name, user_name)
        elif cmd_type == "allfixtures" and room_name and user_name:
            return footy_all_upcoming_fixtures(room_name, user_name)
        elif cmd_type == "livefixtures" and user_name:
            return footy_live_fixtures(user_name, subs=True)
        elif cmd_type == "livefixtureswithsubs" and user_name:
            return footy_live_fixtures(user_name, subs=True)
        elif cmd_type == "livefixturestats" and room_name and user_name:
            return footy_stats_for_live_fixtures(room_name, user_name)
        elif cmd_type == "footystats" and room_name and user_name:
            return footy_stats_for_live_fixtures(room_name, user_name)
        elif cmd_type == "todayfixtures" and room_name and user_name:
            return today_upcoming_fixtures(room_name, user_name)
        elif cmd_type == "liveodds" and user_name:
            return footy_live_odds(user_name)
        elif cmd_type == "goldenboot":
            return epl_golden_boot()
        elif cmd_type == "goldenshoe":
            return all_leagues_golden_boot()
        elif cmd_type == "footypredicts" and room_name and user_name:
            return footy_today_fixtures_odds(room_name, user_name)
        elif cmd_type == "foxtures" and room_name and user_name:
            return fetch_fox_fixtures(room_name, user_name)
        elif cmd_type == "aafkxtures" and room_name and user_name:
            return fetch_aafk_fixture_data(room_name, user_name)
        elif cmd_type == "footyxi" and room_name and user_name:
            return footy_team_lineups(room_name, user_name)
        elif cmd_type == "covid":
            return covid_cases_usa()
        elif cmd_type == "lyrics" and args:
            return get_song_lyrics(args)
        elif cmd_type == "entranslation" and command and args:
            return get_english_translation(command, content, args)
        elif cmd_type == "olympics":
            return get_summer_olympic_medals()
        elif cmd_type in ("wolympics", "winterolympics"):
            return get_winter_olympic_medals()
        elif cmd_type == "footyodds" and room_name and user_name:
            return footy_today_fixtures_odds(room_name, user_name)
        elif cmd_type == "twitch":
            return get_all_live_twitch_streams()
        elif cmd_type == "todaynfl":
            return get_today_nfl_games()
        elif cmd_type == "livenfl" and user_name:
            return get_live_nfl_game_summaries(user_name)
        elif cmd_type == "topcrypto":
            return get_top_crypto()
        elif cmd_type == "define" and args and user_name:
            return get_english_definition(user_name, args)
        elif cmd_type == "tune" and args and user_name and bot_username:
            return tuner(args, user_name, bot_username)
        elif cmd_type == "wayne" and user_name:
            return time_until_wayne(user_name)
        elif cmd_type == "np" and bot_username:
            return get_current_show(True, bot_username)
        elif cmd_type == "reserved":
            return None
        elif cmd_type == "todaysumo":
            return today_sumo_matches()
        elif cmd_type == "sumo":
            return upcoming_sumo_matches()
        elif cmd_type == "nbastandings":
            return nba_standings()
        elif cmd_type == "nbagames":
            return upcoming_nba_games()
        elif cmd_type == "nbalive":
            return live_nba_games()
        elif cmd_type == "livenba":
            return live_nba_games()
        elif cmd_type == "tovala" and user_name:
            return tovala_counter(user_name)
        elif cmd_type == "imagecount":
            return gcs_count_images_in_bucket(content)
        elif cmd_type == "changeorstayvote" and room_name and user_name:
            return change_or_stay_vote(user_name, content)
        elif cmd_type == "changeorstay" and user_name:
            return get_live_poll_results(user_name)
        elif cmd_type == "odds":
            return get_odds(content)
        elif cmd_type == "bachcount" and args and user_name:
            return bach_gang_counter(user_name, args)
        elif cmd_type == "latestimage":
            return fetch_latest_image_from_gcs_bucket(content)
        elif cmd_type == "psntrophies":
            return get_psn_game_trophies()
        elif cmd_type == "bropsn":
            return get_titles_with_stats()
        elif cmd_type == "sleeper" and user_name:
            return fetch_sleeper_matchups(user_name)
        # elif cmd_type == "cryptochart" and args:
        #     return get_crypto_chart(args)
        elif cmd_type == "lesbians" and user_name:
            return fetch_redgifs_gif("lesbians", user_name)
        elif cmd_type == "nsfw" and args and user_name:
            return fetch_redgifs_gif(args, user_name, after_dark_only=True)
        elif cmd_type == "psn":
            return get_psn_online_friends()
        # elif cmd_type == "philliesgames":
        #    return today_phillies_games(
        # elif cmd_type == "youtube" and args:
        #     return search_youtube_for_video(args)
        LOGGER.warning(f"No response for command `{command}` {args}")
        return emojize(
            f":warning: idk wtf u did but bot is ded now, thanks @{user_name} :warning:",
            language="en",
        )

    async def on_message(self, room: Room, message: RoomMessage) -> None:
        """
        Triggers upon every chat message to parse commands, validate users, and save chat logs.

        :param Room room: Current Chatango room object.
        :param RoomMessage message: Raw chat message submitted by a user.

        :returns: None
        """
        user = message.user
        chat_message = message.body
        user_name = user.name
        room_name = room.name.lower()
        bot_username = self.username.lower()
        await check_blacklisted_users(room, user_name, message)
        await ban_daddy_anons(room, user, message)
        self._log_message(room, user_name, message)
        await persist_user_data(room_name, user, message, bot_username)
        await persist_chat_logs(user_name, room_name, chat_message, bot_username)
        if chat_message.startswith("?") and len(chat_message) > 3:
            search_query = chat_message[1:].strip()
            yt_video_result = await asyncio.to_thread(search_youtube_video, search_query)
            if yt_video_result:
                await room.send_message(yt_video_result, use_html=True)
        if chat_message.startswith("!"):
            await self._process_command(chat_message, room, user_name, message)
        if re.match(
            r"^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube(?:-nocookie)?\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|live\/|v\/)?)([\w\-]+)(\S+)?$",
            chat_message,
        ):
            preview = await asyncio.to_thread(generate_youtube_video_preview, chat_message)
            if preview and user_name != "acleebot":
                await room.send_message(preview, use_html=True)
        elif re.match(r"((https?):\/\/)?(www.)?x\.com(\/@?(\w){1,15})\/status\/[0-9]{19}", chat_message):
            preview = await asyncio.to_thread(generate_twitter_preview, chat_message)
            if preview:
                await room.send_message(preview, use_html=True)
        elif re.match(r".+(wikipedia.org)", chat_message):
            preview = await asyncio.to_thread(create_wiki_preview, chat_message)
            if preview:
                await room.send_message(preview, use_html=True)
        elif "https://i.imgur.com/wppfinC.png" in chat_message:
            await ban_word(room, message, user_name, silent=True)
        elif re.match(r"bl\/S+b", chat_message) and "south" not in chat_message:
            await ban_word(room, message, user_name, silent=False)
        elif chat_message == "image not found :(":
            await ban_word(room, message, user_name, silent=True)
        elif "http://broiestbro." in chat_message:
            await ban_word(room, message, user_name, silent=True)
        elif "https://i.imgur.com/bQJxsBV.png" in chat_message:
            await ban_word(room, message, user_name, silent=True)
        elif re.search(r"@bro(?![a-zA-Z0-9])", chat_message):
            await self._respond_llm_prompt(user_name, room)
        elif "idk wtf u did but bot is ded now, thanks" in chat_message:
            await ban_word(room, message, user_name, silent=True)
        else:
            await self._process_phrase(chat_message, room, user_name, message, bot_username)

    @staticmethod
    def _log_message(room: Room, user_name: str, message: RoomMessage):
        if bool(message.ip) is True and message.body is not None:
            LOGGER.info(f"[{room.name}] [{user_name}] [{message.ip}]: {message.body}")
        else:
            LOGGER.warning(f"[{room.name}] [{user_name}] [no IP address]: {message.body}")

    async def _process_command(self, chat_message: str, room: Room, user_name: str, message: RoomMessage):
        """
        Determines if message is a bot command.

        :param str chat_message: Raw message sent by user.
        :param Room room: Chatango room object.
        :param str user_name: User responsible for triggering command.
        :param RoomMessage message: Chatango message object to be parsed.

        :returns: None
        """
        if CHATANGO_IGNORED_USERS:
            if user_name in CHATANGO_IGNORED_USERS or message.ip in CHATANGO_IGNORED_IPS:
                return ignored_user(user_name, message.ip)
        if chat_message == "!!":
            return
        if re.match(r"^!!.+$", chat_message):
            return await self._gif_fallback(chat_message[2::], room)
        if re.match(r"^!ein+$", chat_message):
            return await self._respond_if_bot_command("!ein", room, user_name)
        if re.match(r"^!\S+", chat_message):
            return await self._respond_if_bot_command(chat_message, room, user_name)

    async def _process_phrase(
        self, chat_message: str, room: Room, user_name: str, message: RoomMessage, bot_username: str
    ) -> None:
        """
        Search database for non-command phrases which elicit a response.

        :param str chat_message: A non-command chat which may prompt a response.
        :param Room room: Current Chatango room object.
        :param str user_name: User responsible for triggering command.
        :param RoomMessage message: Chatango message object to be parsed.
        :param str bot_username: Username of the currently-running bot.

        :returns: None
        """
        if f"@{bot_username}" in chat_message and "*waves*" in chat_message:
            await self._wave_back(room, user_name, bot_username)
        elif chat_message.endswith("only on aclee"):
            await room.send_message("™")
        elif chat_message.lower() == "tm":
            await self._trademark(room, message)
        else:
            fetched_phrase = await _db_fetch_phrase(chat_message)
            if fetched_phrase is not None:
                await room.send_message(fetched_phrase.response, use_html=True)

    @staticmethod
    def _parse_command(user_msg: str) -> Tuple[str, Optional[str]]:
        """
        Parse user message into command & arguments.

        :param str user_msg: Raw chat message submitted by a user.

        :returns: Tuple[str, Optional[str]]
        """
        user_msg = user_msg.strip()
        if " " in user_msg:
            cmd = user_msg.split(" ", 1)[0].lower()
            args = user_msg.split(" ", 1)[1]
            return cmd, args
        return user_msg, None

    async def _respond_if_bot_command(self, chat_message: str, room: Room, user_name: str):
        """
        Fetch response from database to send to chat.

        :param str chat_message: Raw message sent by user.
        :param Room room: Current Chatango room object.
        :param str user_name: User responsible for triggering command.
        """
        cmd, args = self._parse_command(chat_message[1::].strip())
        command = await _db_fetch_command(cmd)
        if command is not None and command.type != "reserved":
            response = await asyncio.to_thread(
                self.create_message,
                command.type,
                command.response,
                command=cmd,
                args=args,
                room_name=room.name.lower(),
                user_name=user_name,
                bot_username=self.username.lower(),
            )
            if response:
                await room.send_message(response, use_html=True)
        else:
            await self._gif_fallback(chat_message, room)

    @staticmethod
    async def _wave_back(room: Room, user_name: str, bot_username: str) -> None:
        """
        Automatically reply to user who waved at the bot.

        :param Room room: Current Chatango room object.
        :param str user_name: Username of Chatango user who waved.
        :param str bot_username: Bot's username.

        :returns: None
        """
        if user_name == bot_username:
            await room.send_message(f"stop talking to urself and get some friends u loser jfc kys @{bot_username}")
        await room.send_message(f"@{user_name} *waves*")

    @staticmethod
    async def _gif_fallback(message: str, room: Room) -> None:
        """
        Default to Giphy for non-existent commands.

        :param str message: Command triggered by a user.
        :param Room room: Current Chatango room object.

        :returns: None
        """
        query = message.replace("!", "").lower().strip()
        if len(query) > 1:
            image = await asyncio.to_thread(klipy_image_search, query)
            if image:
                await room.send_message(image)

    @staticmethod
    async def _trademark(room: Room, message: RoomMessage) -> None:
        """
        Replace "TM" chats with a trademark symbol.

        :param Room room: Current Chatango room object.
        :param RoomMessage message: User submitted `tm` to be replaced.

        :returns: None
        """
        await room.delete_message(message)
        await room.send_message("™")

    @staticmethod
    async def _respond_llm_prompt(user_name: str, room: Room) -> None:
        """
        Respond to messages directed at the bot with LLM-generated responses.

        :param str user_name: Username of the Chatango user who triggered the LLM response.
        :param Room room: Current Chatango room object.

        :returns: None
        """
        LOGGER.info(f"Generating LLM response for message directed at bot in room {room.name}")
        response = await asyncio.to_thread(generate_llm_response, user_name, list(room.history))
        if response:
            await room.send_message(response, use_html=True)
