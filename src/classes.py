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


class Thread:
    def __init__(self,
                 thread_id:   int,
                 category_id: int,
                 user_id:     int,
                 username:    str,
                 created:     datetime,
                 title:       str,
                 content:     str) -> None:
        """Create new Thread object."""
        self.thread_id = thread_id
        self.category_id = category_id
        self.user_id = user_id
        self.username = username
        self.created = created
        self.title = title
        self.content = content
        self.replies : list[Reply] = []

    def __repr__(self) -> str:
        return f"  {self.title} (Thread by {self.username}, created on {self.created})\n    {self.content}"


class Reply:
    def __init__(self,
                 reply_id     : int,
                 thread_id    : int,
                 user_id      : int,
                 username     : str,
                 reply_tstamp : datetime,
                 content      : int
                 ) -> None:
        """Creat new Reply object."""
        self.reply_id = reply_id
        self.thread_id = thread_id
        self.user_id = user_id
        self.username = username
        self.reply_tstamp = reply_tstamp
        self.content = content

    def __repr__(self) -> str:
        return (f"      {self.username}  ({self.reply_tstamp})\n"
                f"        {self.content}")
