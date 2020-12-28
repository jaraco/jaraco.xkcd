import os
import random
import importlib
import contextlib
import datetime
import pathlib
import itertools

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
        self._404(number) or self._load(number)

    def _404(self, number):
        """
        The 404 comic is not found.
        >>> Comic(404)
        Comic(404)
        >>> print(Comic(404))
        xkcd 404:Not Found (None)
        >>> print(Comic(404).date)
        2008-04-01
        """
        if number != 404:
            return

        vars(self).update(
            num=404,
            title="Not Found",
            img=None,
            year=2008,
            month=4,
            day=1,
        )
        return self

    def _load(self, number):
        resp = session.get(f'{number}/info.0.json')
        resp.raise_for_status()
        vars(self).update(self._fix_numbers(resp.json()))

    @property
    def date(self):
        """
        >>> print(Comic(1).date)
        2006-01-01
        """
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
    def random(cls):
        """
        Return a randomly-selected comic.

        >>> Comic.random()
        Comic(...)
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
        >>> Comic.search('2020-12-25').title
        'Wrapping Paper'
        """
        matches = (comic for comic in cls.all() if text in comic.full_text)
        return next(matches, None)

    @property
    def number(self):
        return self.num

    @property
    def full_text(self):
        """
        >>> comic = Comic.random()
        >>> str(comic.date) in comic.full_text
        True
        """
        values = itertools.chain(vars(self).values(), [self.date])
        return jaraco.text.FoldedCase('|'.join(map(str, values)))

    def __repr__(self):
        return f'{self.__class__.__name__}({self.number})'

    def __str__(self):
        return f'xkcd {self.number}:{self.title} ({self.img})'


with contextlib.suppress(ImportError):
    core = importlib.import_module('pmxbot.core')

    @core.command()  # type: ignore  # pragma: no cover
    def xkcd(rest):
        return Comic.search(rest) if rest else Comic.random()  # pragma: no cover
