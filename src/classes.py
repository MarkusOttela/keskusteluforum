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


class Category:

    def __init__(self,
                 category_id   : int,
                 is_restricted : bool,
                 name          : str
                 ) -> None:
        """Create new category object."""
        self.category_id = category_id
        self.is_restricted = is_restricted
        self.name = name
        self.threads : dict[int, Thread] = dict()

    def __repr__(self) -> str:
        return f"  Category {self.name} (id {self.category_id}, {len(self.threads)} threads)"

    def total_threads(self) -> int:
        """Return the total number of threads."""
        return len(self.threads)

    def total_posts(self) -> int:
        """Return the total number of posts in all posts in the category."""
        return sum([thread.total_replies() for thread in self.threads.values()])

    def user_has_permission(self, user_id: int) -> bool:
        """Return True if the user has the permission to view the category."""
        from src.db import user_has_permission_to_category  # Avoid circular import
        return user_has_permission_to_category(self.category_id, user_id)

    def dt_most_recent_post_for_thread(self, thread_id: int) -> datetime:
        """Return the timestamp most recent post in a specified thread."""
        return self.threads[thread_id].dt_most_recent_post()


class Thread:

    def __init__(self,
                 thread_id   : int,
                 category_id : int,
                 user_id     : int,
                 username    : str,
                 created     : datetime,
                 title       : str,
                 content     : str
                 ) -> None:
        """Create new Thread object."""
        self.thread_id = thread_id
        self.category_id = category_id
        self.user_id = user_id
        self.username = username
        self.created = created
        self.title = title
        self.content = content
        self.replies : dict[int, Reply] = dict()

    def total_replies(self) -> int:
        """Return the total number of replies.

        +1 accounts for OP's post in the thread.
        """
        return len(self.replies) + 1

    def __repr__(self) -> str:
        return f"  {self.title} (Thread by {self.username}, created on {self.created})\n    {self.content}"

    def dt_most_recent_post(self) -> datetime:
        """Return the timestamp most recent post in the thread."""
        if not self.replies:
            return self.created
        return list(self.replies.values())[-1].reply_tstamp


class Reply:

    def __init__(self,
                 reply_id     : int,
                 thread_id    : int,
                 user_id      : int,
                 username     : str,
                 reply_tstamp : datetime,
                 content      : int,
                 ) -> None:
        """Creat new Reply object."""
        self.reply_id = reply_id
        self.thread_id = thread_id
        self.user_id = user_id
        self.username = username
        self.reply_tstamp = reply_tstamp
        self.content = content
        self.likes : dict[int, Like] = dict()

    def __repr__(self) -> str:
        return (f"      {self.username}  ({self.reply_tstamp})\n"
                f"        {self.content}")

    def has_been_liked_by(self, user_id: int) -> bool:
        """Check if a user has liked this reply."""
        from src.db import user_has_liked_reply
        return user_has_liked_reply(user_id, self.reply_id)


class Like:

    def __init__(self,
                 like_id  : int,
                 user_id  : int,
                 reply_id : int
                 ) -> None:
        """Create new Like object."""
        self.like_id = like_id
        self.user_id = user_id
        self.reply_id = reply_id
