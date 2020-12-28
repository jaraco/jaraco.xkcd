import os
import random
import importlib
import contextlib
import datetime
import pathlib

import jaraco.text
from requests_toolbelt import sessions
import cachecontrol
from cachecontrol import heuristics
from cachecontrol.caches import file_cache
from jaraco.functools import except_
from jaraco.collections import dict_map


def make_cache(path=None):
    default = pathlib.Path('~/.cache/xkcd').expanduser()
    path = os.environ.get('XKCD_CACHE_DIR', path or default)
    return file_cache.FileCache(path)


session = cachecontrol.CacheControl(
    sessions.BaseUrlSession('https://xkcd.com/'),
    heuristic=heuristics.ExpiresAfter(days=365 * 20),
    cache=make_cache(),
)


class Comic:
    def __init__(self, number):
        resp = session.get(f'{number}/info.0.json')
        if number == 404:
            return
        resp.raise_for_status()
        vars(self).update(self._fix_numbers(resp.json()))

    @property
    def date(self):
        return datetime.date(self.year, self.month, self.day)

    @staticmethod
    def _fix_numbers(ob):
        """
        Given a dict-like object ob, ensure any integers are integers.
        """
        safe_int = except_(TypeError, ValueError, use='args[0]')(int)
        return dict_map(safe_int, ob)

    @classmethod
    def latest(cls):
        headers = {'Cache-Control': 'no-cache'}
        resp = session.get('info.0.json', headers=headers)
        resp.raise_for_status()
        return cls(resp.json()['num'])

    @classmethod
    def all(cls):
        latest = cls.latest()
        return map(cls, range(latest.number, 0, -1))

    @classmethod
    def older(cls):
        latest = cls.latest()
        return map(cls, range(latest.number - 100, 0, -1))

    @classmethod
    def random(cls):
        """
        Return a randomly-selected comic
        """
        latest = cls.latest()
        return cls(random.randint(1, latest.number))

    @classmethod
    def search(cls, text):
        """
        Find a comic with the matching text

        >>> print(Comic.search('password strength'))
        xkcd 936:Password Strength \
(https://imgs.xkcd.com/comics/password_strength.png)
        >>> Comic.search('Horse battery')
        Comic(2241)
        >>> Comic.search('ISO 8601')
        Comic(1179)
        >>> Comic.search('2013-02-27').title
        'ISO 8601'
        """
        matches = (comic for comic in cls.all() if text in comic.full_text)
        return next(matches, None)

    @property
    def number(self):
        return self.num

    @property
    def full_text(self):
        return jaraco.text.FoldedCase('|'.join(map(str, vars(self).values())))

    def __repr__(self):
        return f'{self.__class__.__name__}({self.number})'

    def __str__(self):
        return f'xkcd {self.number}:{self.title} ({self.img})'


with contextlib.suppress(ImportError):
    core = importlib.import_module('pmxbot.core')

    @core.command()  # type: ignore
    def xkcd(rest):
        return Comic.search(rest) if rest else Comic.random()
