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
import getpass

from collections import defaultdict
from os          import getenv, getrandom

import argon2
import lorem
import random

from flask            import session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy       import text

from app         import app
from src.classes import Thread, Reply

app.config['SQLALCHEMY_DATABASE_URI'] = getenv('DATABASE_URL')
db = SQLAlchemy(app)


def create_tables():
    """Initialise the database by creating the tables."""
    sql = text("CREATE TABLE IF NOT EXISTS users ("
               "user_id SERIAL PRIMARY KEY, "
               "username TEXT, "
               "join_tstamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
               "is_admin BOOLEAN DEFAULT FALSE, "
               "password_hash TEXT)")
    db.session.execute(sql)
    db.session.commit()

    sql = text("CREATE TABLE IF NOT EXISTS categories ("
               "category_id SERIAL PRIMARY KEY, "
               "name TEXT)")
    db.session.execute(sql)
    db.session.commit()

    sql = text("CREATE TABLE IF NOT EXISTS threads ("
               "thread_id SERIAL PRIMARY KEY, "
               "category_id INTEGER NOT NULL, "
               "FOREIGN KEY (category_id) REFERENCES categories(category_id), "
               "user_id INTEGER NOT NULL, "
               "FOREIGN KEY (user_id) REFERENCES users(user_id), "
               "thread_tstamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
               "title TEXT,"
               "content TEXT)")
    db.session.execute(sql)
    db.session.commit()

    sql = text("CREATE TABLE IF NOT EXISTS replies ("
               "reply_id SERIAL PRIMARY KEY, "
               "thread_id INTEGER NOT NULL, "
               "FOREIGN KEY (thread_id) REFERENCES threads(thread_id), "
               "user_id INTEGER NOT NULL, "
               "FOREIGN KEY (user_id) REFERENCES users(user_id), "
               "reply_tstamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
               "content TEXT)")
    db.session.execute(sql)
    db.session.commit()

    sql = text("CREATE TABLE IF NOT EXISTS likes ("
               "like_id SERIAL PRIMARY KEY, "
               "reply_id INTEGER NOT NULL, "
               "FOREIGN KEY (reply_id) REFERENCES replies(reply_id), "
               "user_id INTEGER NOT NULL, "
               "FOREIGN KEY (user_id) REFERENCES users(user_id))")
    db.session.execute(sql)
    db.session.commit()


def mock_db_content():
    """Mock db content for testing."""

    # Sentinel for checking the databases are filled with mock data only once.
    sql = text("SELECT password_hash FROM users WHERE username=(:username)")
    result = db.session.execute(sql, {"username": "User1"}).first()
    if result is not None:
        return

    # Populate with test data:
    users = ["User1", "User2", "User3", "User4", "User5"]
    for user in users:
        password_hash = argon2.PasswordHasher().hash(password=user, salt=getrandom(32, flags=0))
        sql = text("INSERT INTO users (username, is_admin, password_hash) "
                   "VALUES (:username, :is_admin, :password_hash)"
                   "ON CONFLICT DO NOTHING")
        db.session.execute(sql, {"username": user,
                                 "is_admin": False,
                                 "password_hash": password_hash})
        db.session.commit()

    categories = ["Category 1", "Category 2", "Category 3", "Category 4"]
    for category in categories:
        sql = text("INSERT INTO categories (name) "
                   "VALUES (:category) "
                   "ON CONFLICT DO NOTHING")
        db.session.execute(sql, {"category": category})
        db.session.commit()

    sql = text("SELECT category_id FROM categories")
    category_ids = [t[0] for t in db.session.execute(sql).fetchall()]

    thread_titles = ["Title 1", "Title 2", "Title 3", "Title 4"]
    sql = text("SELECT user_id FROM users")
    user_ids = [t[0] for t in db.session.execute(sql).fetchall()]
    user_id = user_ids[0]

    for category_id in category_ids:
        for thread_title in thread_titles:
            sql = text("INSERT INTO threads (category_id, user_id, title, content) "
                       "VALUES (:category_id, :user_id, :title, :content) "
                       "ON CONFLICT DO NOTHING")
            db.session.execute(sql, {"category_id": category_id,
                                     "user_id": user_id,
                                     "title": thread_title,
                                     "content": lorem.sentence()})
            db.session.commit()

    sql = text("SELECT thread_id FROM threads")
    thread_ids = [t[0] for t in db.session.execute(sql).fetchall()]

    for thread_id in thread_ids:
        for user_id in user_ids:
            sql = text("INSERT INTO replies (thread_id, user_id, content)"
                       "VALUES (:thread_id, :user_id, :content)"
                       "ON CONFLICT DO NOTHING "
                       "RETURNING reply_id")

            reply_id = db.session.execute(sql, {"thread_id": thread_id,
                                     "user_id": user_id,
                                     "content": lorem.sentence()}).fetchone()[0]

            # 50% probability to like the reply of other posters
            for user_id_ in user_ids:
                if user_id_ == user_id and random.randint(0, 1):
                    continue
                sql = text("INSERT INTO likes (reply_id, user_id) VALUES (:reply_id, :user_id)")
                db.session.execute(sql, {"reply_id": reply_id, "user_id": user_id_})

            db.session.commit()


def create_admin_account():
    """Create the administrator account."""
    sql = text("SELECT password_hash FROM users WHERE username=(:username)")
    result = db.session.execute(sql, {"username": "admin"}).first()
    if result is not None:
        return

    while True:
        password1 = getpass.getpass("Enter admin password: ")
        password2 = getpass.getpass("Repeat admin password: ")
        if password1 == password2:
            password_hash = argon2.PasswordHasher().hash(password=password1, salt=getrandom(32, flags=0))
            sql = text("INSERT INTO users (username, is_admin, password_hash) "
                       "VALUES (:username, :is_admin, :password_hash)"
                       "ON CONFLICT DO NOTHING")
            db.session.execute(sql, {"username": 'admin',
                                     "is_admin": True,
                                     "password_hash": password_hash})
            db.session.commit()
            print("Admin account successfully created.")
            break
        else:
            print("Passwords did not match.")


def category_exists_in_db(category_name: str) -> bool:
    """Return true if the category exists in the database."""
    sql = text("SELECT category_id FROM categories where name=:category")
    result = db.session.execute(sql, {"category": category_name}).fetchall()
    if result:
        return True
    return False


def add_category_to_db(category_name: str) -> None:
    """Add category to database."""
    sql = text("INSERT INTO categories (name)"
               "VALUES (:category_name)"
               "ON CONFLICT DO NOTHING ")
    db.session.execute(sql, {"category_name": category_name})
    db.session.commit()


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

    for reply_data in replies_data:
        reply = Reply(*reply_data)
        reply.likes = get_reply_likes(reply.reply_id)
        thread.replies.append(reply)

    return thread


def get_reply_likes(reply_id: int) -> list[int]:
    """Get list of user ids that have liked the reply matching the reply_id."""
    sql = text("SELECT user_id FROM likes WHERE reply_id = :reply_id")
    likes_data = db.session.execute(sql, {"reply_id": reply_id}).fetchall()
    likes = [tup[0] for tup in likes_data]
    return likes


def get_reply_by_id(reply_id: int) -> Reply:
    """Get Reply object generated from database with reply_id."""
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
               "  replies.reply_id = :reply_id "
               "ORDER BY replies.reply_tstamp")
    reply_data = db.session.execute(sql, {"reply_id": reply_id}).fetchone()
    return Reply(*reply_data)


def get_users_id() -> int:
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


def insert_like_to_db(user_id: int, reply_id: int) -> None:
    """Insert like to the database."""
    sql = text("INSERT INTO likes (reply_id, user_id) VALUES (:reply_id, :user_id)")
    db.session.execute(sql, {"reply_id": reply_id, "user_id": user_id})
    db.session.commit()


def remove_like_from_db(user_id: int, reply_id: int) -> None:
    """Remove like from the database."""
    sql = text("DELETE FROM likes WHERE user_id=:user_id AND reply_id=:reply_id")
    db.session.execute(sql, {"user_id": user_id, "reply_id": reply_id})
    db.session.commit()


def user_has_liked_reply(user_id: int, reply_id: int) -> bool:
    """Check if user has liked a reply."""
    sql = text("SELECT COUNT(*) FROM likes WHERE user_id=:user_id AND reply_id=:reply_id")
    likes_data = db.session.execute(sql, {"user_id": user_id, "reply_id": reply_id}).fetchone()
    return bool(likes_data[0])


def get_username_by_reply_id(reply_id: int) -> str:
    """Get username by reply_id."""
    sql = text("SELECT users.username "
               "FROM users, replies "
               "WHERE users.user_id = replies.user_id "
               "      AND "
               "      replies.reply_id = :reply_id")
    username = db.session.execute(sql, {"reply_id": reply_id}).fetchone()[0]
    return username


def get_username_by_thread_id(thread_id: int) -> str:
    """Get username by thread_id."""
    sql = text("SELECT users.username "
               "FROM users, threads "
               "WHERE users.user_id = threads.user_id "
               "      AND "
               "      threads.thread_id = :thread_id")
    username = db.session.execute(sql, {"thread_id": thread_id}).fetchone()[0]
    return username


def update_thread_in_db(thread_id: int, title: str, message: str) -> None:
    """Update thread in database."""
    sql = text("UPDATE threads SET title = :title, content = :content WHERE threads.thread_id = :thread_id ")
    db.session.execute(sql, {"thread_id": thread_id, "title": title, "content": message})
    db.session.commit()


def update_reply_in_db(reply_id: int, message: str) -> None:
    """Update reply in database."""
    sql = text("UPDATE replies SET content = :content WHERE replies.reply_id = :reply_id ")
    db.session.execute(sql, {"reply_id": reply_id, "content": message})
    db.session.commit()


def delete_reply_from_db(reply_id: int) -> None:
    """Delete reply from database."""
    sql = text("DELETE FROM replies WHERE replies.reply_id = :reply_id")
    db.session.execute(sql, {"reply_id": reply_id})
    db.session.commit()


def delete_thread_from_db(thread_id: int) -> None:
    """Delete thread from database."""
    sql = text("DELETE FROM threads WHERE threads.thread_id = :thread_id")
    db.session.execute(sql, {"thread_id": thread_id})
    db.session.commit()


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
            try:
                timestamp_dict[thread_id] = thread.replies[-1].reply_tstamp
            except IndexError:
                timestamp_dict[thread_id] = thread.created

    return timestamp_dict


def search_from_db(query: str) -> list[int]:
    """Get list of thread ids from database that match a search term."""
    sql = text("SELECT "
               "    threads.thread_id "
               "FROM "
               "    threads, replies "
               "WHERE "
               "    threads.title LIKE :query "
               "    OR "
               "    threads.content LIKE :query")
    thread_ids = [t[0] for t in db.session.execute(sql, {"query": f'%{query}%'}).fetchall()]

    sql = text("SELECT "
               "    threads.thread_id "
               "FROM "
               "    threads, replies "
               "WHERE "
               "    replies.content LIKE :query "
               "    AND "
               "    replies.thread_id = threads.thread_id"
               )
    thread_ids += [t[0] for t in db.session.execute(sql, {"query": f'%{query}%'}).fetchall()]

    return thread_ids

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

        # Ensures categories with no threads are visible in index.
        if category not in forum_threads.keys():
            forum_threads[category] = []

    return forum_threads

