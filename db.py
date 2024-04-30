#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Keskusteluforum

Copyright (C) 2024  Markus Ottela

This file is part of Keskusteluforum.

Keskusteluforum is free software: you can redistribute it and/or modify it under the terms
of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

Keskusteluforum is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Keskusteluforum. If not, see <https://www.gnu.org/licenses/>.
"""

import datetime

from collections import defaultdict
from os          import getenv

from flask            import session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy       import text

from app         import app
from src.classes import Thread, Reply

app.config['SQLALCHEMY_DATABASE_URI'] = getenv('DATABASE_URL')
db = SQLAlchemy(app)

def get_list_of_ids_and_categories() -> list[tuple[int, str]]:
    """Get list of categories (id and string)."""
    sql = text("SELECT category_id, name FROM categories")
    ids_and_categories = db.session.execute(sql).fetchall()
    return ids_and_categories


def get_thread(thread_id: int) -> Thread:
    """Get Thread object generated from database with thread_id."""
    sql = text("SELECT "
               "  threads.thread_id, "
               "  threads.category_id, "
               "  threads.user_id, "
               "  users.username, "
               "  threads.thread_tstamp, "
               "  threads.title, "
               "  threads.content "
               "FROM "
               "  threads, users "
               "WHERE "
               "  threads.user_id = users.user_id "
               "  AND"
               "  threads.thread_id = :thread_id "
               "ORDER BY thread_tstamp")

    thread_data = db.session.execute(sql, {"thread_id": thread_id}).fetchone()
    thread = Thread(*thread_data)

    sql = text("SELECT "
               "  replies.reply_id, "
               "  replies.thread_id, "
               "  replies.user_id, "
               "  users.username, "
               "  replies.reply_tstamp, "
               "  replies.content "
               "FROM "
               "  replies, users "
               "WHERE "
               "  replies.user_id = users.user_id "
               "  AND "
               "  replies.thread_id = :thread_id "
               "ORDER BY replies.reply_tstamp")
    replies_data = db.session.execute(sql, {"thread_id": thread_id}).fetchall()
    if replies_data:
        thread.replies = [Reply(*data) for data in replies_data]

    return thread


def get_user_id_by_name() -> int:
    """Get user's user_id by username."""
    sql = text("SELECT users.user_id FROM users WHERE username=(:username)")
    user_id = db.session.execute(sql, {"username": session["username"]}).fetchone()[0]
    return user_id

def insert_thread_into_db(category_id: int , user_id: int, title: str, message: str) -> int:
    """Insert new thread into the database."""
    sql = text("INSERT INTO threads (category_id, user_id, title, content) "
               "VALUES (:category_id, :user_id, :title, :content) "
               "ON CONFLICT DO NOTHING "
               "RETURNING thread_id")
    thread_id = db.session.execute(sql, {"category_id": category_id,
                                         "user_id": user_id,
                                         "title": title,
                                         "content": message}).fetchone()[0]

    db.session.commit()

    return thread_id


def insert_reply_into_db(thread_id, user_id, message) -> None:
    """Insert reply to replies table."""
    sql = text("INSERT INTO replies (thread_id, user_id, content)"
               "VALUES (:thread_id, :user_id, :content)"
               "ON CONFLICT DO NOTHING")
    db.session.execute(sql, {"thread_id": thread_id,
                             "user_id": user_id,
                             "content": message})
    db.session.commit()

def get_most_recent_post_tstamp_dict() -> dict[int, datetime.datetime]:
    """Get most recent reply from thread."""
    thread_id_dict = dict()
    forum_thread_dict = get_forum_thread_dict()
    for category, list_of_threads in forum_thread_dict.items():
        thread_id_dict[category] = [thread.thread_id for thread in list_of_threads]

    timestamp_dict = dict()
    for category, thread_id_list in thread_id_dict.items():
        for thread_id in thread_id_list:
            thread = get_thread(thread_id)
            timestamp_dict[thread_id] = thread.replies[-1].reply_tstamp

    return timestamp_dict


def get_total_post_dict() -> dict[str, int]:
    """Get dict containing {category: total_posts_in_category}."""

    thread_id_dict = dict()
    forum_thread_dict = get_forum_thread_dict()
    for category, list_of_threads in forum_thread_dict.items():
        thread_id_dict[category] = [thread.thread_id for thread in list_of_threads]

    counter_dict = dict()
    for category, thread_id_list in thread_id_dict.items():
        counter_dict[category] = 0
        for thread_id in thread_id_list:
            counter_dict[category] += len(get_thread(thread_id).replies) + 1

    return counter_dict


def get_forum_thread_dict() -> defaultdict:
    """Get forum threads as a {category : [thread1, thread2, ...]} dictionary."""
    sql = text("SELECT category_id, name FROM categories")
    ids_and_categories = db.session.execute(sql).fetchall()

    sql = text("SELECT "
               "  threads.thread_id, "
               "  threads.category_id, "
               "  threads.user_id, "
               "  users.username, "
               "  threads.thread_tstamp, "
               "  threads.title, "
               "  threads.content "
               "FROM "
               "  threads, users "
               "WHERE"
               "  threads.user_id = users.user_id "
               "ORDER BY thread_tstamp")

    db_data = db.session.execute(sql).fetchall()
    threads = [Thread(*thread_data) for thread_data in db_data]
    forum_threads = defaultdict(list)

    for category_id, category in ids_and_categories:
        for thread in threads:
            if thread.category_id == category_id:
                forum_threads[category].append(thread)
    return forum_threads
