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

from os import getenv, getrandom

import argon2
import lorem
import random

from flask            import session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy       import text

from app         import app
from src.classes import Thread, Reply, Category, Like
from src.statics import ADMIN

app.config['SQLALCHEMY_DATABASE_URI'] = getenv('DATABASE_URL')
db = SQLAlchemy(app)


###############################################################################
#                                     INIT                                    #
###############################################################################

def create_tables():
    """Initialise the database by creating the tables."""
    sql = text("CREATE TABLE IF NOT EXISTS users ("
               "  user_id SERIAL PRIMARY KEY, "
               "  username TEXT, "
               "  join_tstamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
               "  is_admin BOOLEAN DEFAULT FALSE, "
               "  password_hash TEXT)")
    db.session.execute(sql)
    db.session.commit()


    sql = text("CREATE TABLE IF NOT EXISTS categories ("
               "  category_id SERIAL PRIMARY KEY, "
               "  restricted BOOLEAN DEFAULT FALSE, "
               "  name TEXT)")
    db.session.execute(sql)
    db.session.commit()

    sql = text("CREATE TABLE IF NOT EXISTS permissions ("
               "  permission_id SERIAL PRIMARY KEY, "
               "  user_id INTEGER NOT NULL, "
               "FOREIGN KEY (user_id) REFERENCES users(user_id), "
               "  category_id INTEGER NOT NULL, "
               "FOREIGN KEY (category_id) REFERENCES categories(category_id))")
    db.session.execute(sql)
    db.session.commit()

    sql = text("CREATE TABLE IF NOT EXISTS threads ("
               "  thread_id SERIAL PRIMARY KEY, "
               "  category_id INTEGER NOT NULL, "
               "FOREIGN KEY (category_id) REFERENCES categories(category_id), "
               "  user_id INTEGER NOT NULL, "
               "FOREIGN KEY (user_id) REFERENCES users(user_id), "
               "  thread_tstamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
               "  title TEXT,"
               "  content TEXT)")
    db.session.execute(sql)
    db.session.commit()

    sql = text("CREATE TABLE IF NOT EXISTS replies ("
               "  reply_id SERIAL PRIMARY KEY, "
               "  thread_id INTEGER NOT NULL, "
               "FOREIGN KEY (thread_id) REFERENCES threads(thread_id), "
               "  user_id INTEGER NOT NULL, "
               "FOREIGN KEY (user_id) REFERENCES users(user_id), "
               "  reply_tstamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
               "  content TEXT)")
    db.session.execute(sql)
    db.session.commit()

    sql = text("CREATE TABLE IF NOT EXISTS likes ("
               "  like_id SERIAL PRIMARY KEY, "
               "  reply_id INTEGER NOT NULL, "
               "FOREIGN KEY (reply_id) REFERENCES replies(reply_id), "
               "  user_id INTEGER NOT NULL, "
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
        insert_new_user_into_db(user, password=user)

    categories = ["Category 1", "Category 2", "Category 3", "Category 4"]
    for category in categories:
        insert_category_to_db(category)

    user_ids = [get_user_id_by_username(user) for user in users]

    for category_id, _ in get_list_of_category_ids_and_names():
        for _ in range(5):
            insert_thread_into_db(category_id=category_id,
                                  user_id=random.choice(user_ids),
                                  title=lorem.sentence(),
                                  content=lorem.sentence())

        thread_ids = get_list_of_thread_ids_by_category_id(category_id)

        for thread_id in thread_ids:
            for user_id in user_ids:
                reply_id = insert_reply_into_db(thread_id=thread_id,
                                                user_id=user_id,
                                                content=lorem.paragraph())

                for user_id_ in user_ids:
                    # 50% probability to like the reply of other posters
                    if user_id_ == user_id and random.randint(0, 1):
                        continue
                    insert_like_to_db(user_id, reply_id)


###############################################################################
#                                    USERS                                    #
###############################################################################

def insert_admin_account_into_db():
    """Insert the admin account into the database."""
    # Sentinel that checks if admin account is already set
    sql = text("SELECT password_hash FROM users WHERE username=(:username)")
    result = db.session.execute(sql, {"username": "admin"}).first()
    if result is not None:
        return

    password_hash = argon2.PasswordHasher().hash(password=getenv('ADMIN_PASSWORD'),
                                                 salt=getrandom(32, flags=0))

    sql = text("INSERT INTO users (username, is_admin, password_hash) "
               "VALUES (:username, :is_admin, :password_hash)"
               "ON CONFLICT DO NOTHING")
    db.session.execute(sql, {"username": 'admin',
                             "is_admin": True,
                             "password_hash": password_hash})
    db.session.commit()


def insert_new_user_into_db(username: str, password: str) -> int:
    """Insert a new user into the database.

    Some repeated code here, but for misuse resistance, we want
    the admin account to be creatable only by a separate function.
    """
    password_hash = argon2.PasswordHasher().hash(password=password,
                                                 salt=getrandom(32, flags=0))

    sql = text("INSERT INTO users (username, password_hash) "
               "VALUES (:username, :password_hash)"
               "ON CONFLICT DO NOTHING "
               "RETURNING user_id")
    user_id = db.session.execute(sql, {"username": username,
                                       "is_admin": False,
                                       "password_hash": password_hash})
    db.session.commit()
    return user_id


def get_user_id_for_session() -> int:
    """Get user's user_id by username."""
    sql = text("SELECT users.user_id FROM users WHERE username=(:username)")
    user_id = db.session.execute(sql, {"username": session["username"]}).fetchone()[0]
    return user_id


def get_user_id_by_username(username: str) -> int:
    """Get user's user_id by username."""
    sql = text("SELECT users.user_id FROM users WHERE username=(:username)")
    user_id = db.session.execute(sql, {"username": username}).fetchone()[0]
    return user_id


def get_user_ids_and_names(include_admin: bool = False) -> tuple[int, str]:
    """Get users' user_ids and names."""
    sql = text("SELECT user_id, username FROM users")
    results = db.session.execute(sql).fetchall()

    if not include_admin:
        results = [t for t in results if t[1] != ADMIN]

    return results


def get_username_by_reply_id(reply_id: int) -> str:
    """Get username by reply_id."""
    sql = text("SELECT users.username "
               "FROM users, replies "
               "WHERE "
               "  users.user_id = replies.user_id "
               "  AND "
               "  replies.reply_id = :reply_id")
    username = db.session.execute(sql, {"reply_id": reply_id}).fetchone()[0]
    return username


def get_username_by_thread_id(thread_id: int) -> str:
    """Get username by thread_id."""
    sql = text("SELECT users.username "
               "FROM users, threads "
               "WHERE "
               "  users.user_id = threads.user_id "
               "  AND "
               "  threads.thread_id = :thread_id")
    username = db.session.execute(sql, {"thread_id": thread_id}).fetchone()[0]
    return username


###############################################################################
#                                  CATEGORIES                                 #
###############################################################################

def insert_category_to_db(category_name: str, restricted: bool = False) -> int:
    """Add a new category to the database. Return category_id"""
    sql = text("INSERT INTO categories (name, restricted) "
               "VALUES (:category_name, :restricted) "
               "ON CONFLICT DO NOTHING "
               "RETURNING category_id")
    category_id = db.session.execute(sql, {"category_name": category_name,
                                           "restricted": restricted}).fetchone()[0]

    db.session.commit()
    return category_id


def delete_category_from_db(category_id: int) -> None:
    """Delete category from database."""
    sql = text("DELETE FROM categories WHERE category_id = :category_id")
    db.session.execute(sql, {"category_id": category_id})
    db.session.commit()


def category_exists_in_db(category_name: str) -> bool:
    """Return true if the category exists in the database."""
    sql = text("SELECT category_id "
               "FROM categories "
               "WHERE name=:category")
    result = db.session.execute(sql, {"category": category_name}).fetchall()
    return len(result) > 0


def get_list_of_category_ids_and_names() -> list[tuple[int, str]]:
    """Get list of categories (id and string)."""
    sql = text("SELECT category_id, name "
               "FROM categories")
    ids_and_categories = db.session.execute(sql).fetchall()
    return ids_and_categories

def get_category_data() -> list[tuple[int, str]]:
    """Get category data."""
    sql = text("SELECT category_id, restricted, name "
               "FROM categories")
    ids_and_categories = db.session.execute(sql).fetchall()
    return ids_and_categories


def get_list_of_thread_ids_by_category_id(category_id: int) -> list[int]:
    """Get list of thread ids from database that match category id."""
    sql = text("SELECT threads.thread_id "
               "FROM threads "
               "WHERE threads.category_id = :category_id")
    thread_ids = [t[0] for t in db.session.execute(sql, {"category_id": category_id}).fetchall()]
    return thread_ids


###############################################################################
#                                 PERMISSIONS                                 #
###############################################################################

def insert_permission_into_db(category_id: int, user_id: int) -> int:
    """Insert permission into database.

    The permission controls whether a user is allowed to access a category.
    """
    sql = text("INSERT INTO permissions (user_id, category_id)"
               "VALUES (:user_id, :category_id)"
               "ON CONFLICT DO NOTHING "
               "RETURNING permission_id")
    permission_id = db.session.execute(sql, {"user_id": user_id,
                                             "category_id": category_id}).fetchone()[0]
    db.session.commit()
    return permission_id


def delete_permissions_for_category_from_db(category_id: int) -> None:
    """Delete permissions for category from database."""
    sql = text("DELETE FROM permissions WHERE category_id = :category_id")
    db.session.execute(sql, {"category_id": category_id})
    db.session.commit()


def user_has_permission_to_category(category_id: int, user_id: int) -> bool:
    """Return True if user has permission to access the category."""
    sql = text("SELECT username FROM users WHERE user_id = :user_id ")
    user = db.session.execute(sql, {"user_id": user_id}).fetchone()[0]
    if user == ADMIN:
        return True

    sql = text("SELECT restricted FROM categories WHERE category_id = :category_id ")
    is_restricted = db.session.execute(sql, {"category_id": category_id}).fetchone()[0]

    sql = text("SELECT user_id FROM permissions WHERE category_id = :category_id ")
    permission_ids = [t[0] for t in db.session.execute(sql, {"category_id": category_id}).fetchall()]
    has_permission = user_id in permission_ids

    if not is_restricted or (is_restricted and has_permission):
        return True
    return False


###############################################################################
#                                   THREADS                                   #
###############################################################################

def insert_thread_into_db(category_id: int, user_id: int, title: str, content: str) -> int:
    """Insert new thread into the database."""
    sql = text("INSERT INTO threads (category_id, user_id, title, content) "
               "VALUES (:category_id, :user_id, :title, :content) "
               "ON CONFLICT DO NOTHING "
               "RETURNING thread_id")
    thread_id = db.session.execute(sql, {"category_id": category_id,
                                         "user_id": user_id,
                                         "title": title,
                                         "content": content}).fetchone()[0]

    db.session.commit()
    return thread_id


def update_thread_in_db(thread_id: int, title: str, message: str) -> None:
    """Update thread in database."""
    sql = text("UPDATE threads "
               "SET "
               "  title = :title, "
               "  content = :content "
               "WHERE threads.thread_id = :thread_id ")
    db.session.execute(sql, {"thread_id": thread_id, "title": title, "content": message})
    db.session.commit()


def delete_thread_from_db(thread_id: int) -> None:
    """Delete thread from database."""
    sql = text("DELETE FROM threads WHERE threads.thread_id = :thread_id")
    db.session.execute(sql, {"thread_id": thread_id})
    db.session.commit()


def get_thread_by_thread_id(thread_id: int) -> Thread:
    """Get Thread object generated from database with thread_id."""
    sql = text("SELECT "
               "  threads.thread_id, "
               "  threads.category_id, "
               "  threads.user_id, "
               "  users.username, "
               "  threads.thread_tstamp, "
               "  threads.title, "
               "  threads.content "
               "FROM threads, users "
               "WHERE "
               "  threads.user_id = users.user_id "
               "  AND"
               "  threads.thread_id = :thread_id "
               "ORDER BY thread_tstamp")

    thread_data = db.session.execute(sql, {"thread_id": thread_id}).fetchone()
    thread = Thread(*thread_data)

    for reply in get_list_of_replies_by_thread_id(thread_id):
        thread.replies[reply.reply_id] = reply

    return thread


###############################################################################
#                                   REPLIES                                   #
###############################################################################

def insert_reply_into_db(thread_id: int, user_id: int, content: str) -> int:
    """Insert reply to replies table. Return reply_id."""
    sql = text("INSERT INTO replies (thread_id, user_id, content)"
               "VALUES (:thread_id, :user_id, :content)"
               "ON CONFLICT DO NOTHING "
               "RETURNING replies.reply_id ")
    reply_id = db.session.execute(sql, {"thread_id": thread_id,
                                        "user_id": user_id,
                                        "content": content}).fetchone()[0]
    db.session.commit()
    return reply_id


def update_reply_in_db(reply_id: int, message: str) -> None:
    """Update reply in database."""
    sql = text("UPDATE replies "
               "SET content = :content "
               "WHERE replies.reply_id = :reply_id ")
    db.session.execute(sql, {"reply_id": reply_id, "content": message})
    db.session.commit()


def delete_reply_from_db(reply_id: int) -> None:
    """Delete reply from database."""
    sql = text("DELETE FROM replies "
               "WHERE replies.reply_id = :reply_id")
    db.session.execute(sql, {"reply_id": reply_id})
    db.session.commit()


def get_reply_by_id(reply_id: int) -> Reply:
    """Get Reply object by reply_id."""
    sql = text("SELECT "
               "  replies.reply_id, "
               "  replies.thread_id, "
               "  replies.user_id, "
               "  users.username, "
               "  replies.reply_tstamp, "
               "  replies.content "
               "FROM replies, users "
               "WHERE "
               "  replies.user_id = users.user_id "
               "  AND "
               "  replies.reply_id = :reply_id "
               "ORDER BY replies.reply_tstamp")
    reply_data = db.session.execute(sql, {"reply_id": reply_id}).fetchone()
    return Reply(*reply_data)


def get_list_of_replies_by_thread_id(thread_id: int) -> list[Reply]:
    """Get list of Reply objects by thread_id."""
    sql = text("SELECT "
               "  replies.reply_id, "
               "  replies.thread_id, "
               "  replies.user_id, "
               "  users.username, "
               "  replies.reply_tstamp, "
               "  replies.content "
               "FROM replies, users "
               "WHERE "
               "  replies.user_id = users.user_id "
               "  AND "
               "  replies.thread_id = :thread_id "
               "ORDER BY replies.reply_tstamp")
    replies_data = db.session.execute(sql, {"thread_id": thread_id}).fetchall()
    list_of_replies = [Reply(*reply_data) for reply_data in replies_data]

    for reply in list_of_replies:
        reply.likes = get_likes_by_reply_id(reply.reply_id)

    return list_of_replies


###############################################################################
#                                    LIKES                                    #
###############################################################################

def insert_like_to_db(user_id: int, reply_id: int) -> None:
    """Insert like to the database."""
    sql = text("INSERT INTO likes (reply_id, user_id) VALUES (:reply_id, :user_id)")
    db.session.execute(sql, {"reply_id": reply_id, "user_id": user_id})
    db.session.commit()


def delete_like_from_db(user_id: int, reply_id: int) -> None:
    """Remove like from the database."""
    sql = text("DELETE FROM likes WHERE user_id=:user_id AND reply_id=:reply_id")
    db.session.execute(sql, {"user_id": user_id, "reply_id": reply_id})
    db.session.commit()


def user_has_liked_reply(user_id: int, reply_id: int) -> bool:
    """Check if user has liked a reply."""
    sql = text("SELECT COUNT(*) FROM likes WHERE user_id=:user_id AND reply_id=:reply_id")
    likes_data = db.session.execute(sql, {"user_id": user_id, "reply_id": reply_id}).fetchone()
    return bool(likes_data[0])


def get_likes_by_reply_id(reply_id: int) -> dict[int, Like]:
    """Return likes for reply as {like_id : Like} dictionary."""
    sql = text("SELECT like_id, user_id FROM likes WHERE reply_id = :reply_id")
    likes_data = db.session.execute(sql, {"reply_id": reply_id}).fetchall()
    return {like_id: Like(like_id, user_id, reply_id) for like_id, user_id in likes_data}


###############################################################################
#                                    OTHER                                    #
###############################################################################

def search_from_db(query: str) -> list[int]:
    """Get list of thread ids from database that match a search term."""

    # Search threads (title and content of OP's message)
    sql = text("SELECT threads.thread_id "
               "FROM threads, replies "
               "WHERE "
               "  threads.title LIKE :query "
               "  OR "
               "  threads.content LIKE :query")
    thread_ids = [t[0] for t in db.session.execute(sql, {"query": f'%{query}%'}).fetchall()]

    # Search content of replies
    sql = text("SELECT threads.thread_id "
               "FROM threads, replies "
               "WHERE "
               "  replies.content LIKE :query "
               "  AND "
               "  replies.thread_id = threads.thread_id"
               )
    thread_ids += [t[0] for t in db.session.execute(sql, {"query": f'%{query}%'}).fetchall()]

    return list(set(thread_ids))


def get_forum_category_dict() -> dict[int, Category]:
    """Get forum categories as a {category_id: Category} dictionary."""
    forum_category_dict = {}
    for category_id, is_restricted, name in get_category_data():
        category = Category(category_id, is_restricted, name)

        for thread_id in get_list_of_thread_ids_by_category_id(category_id):
            thread = get_thread_by_thread_id(thread_id)
            category.threads[thread_id] = thread

        forum_category_dict[category_id] = category

    return forum_category_dict
