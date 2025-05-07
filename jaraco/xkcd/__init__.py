from __future__ import annotations

import contextlib
import datetime
import importlib
import itertools
import os
import pathlib
import random
from collections.abc import Mapping
from typing import TYPE_CHECKING, TypeVar

import cachecontrol
from cachecontrol import heuristics
from cachecontrol.caches import file_cache
from requests_toolbelt import sessions

import jaraco.text
from jaraco.collections import dict_map
from jaraco.functools import except_

if TYPE_CHECKING:
    from _typeshed import ConvertibleToInt, StrPath
    from typing_extensions import Self

    _ConvertibleToIntT = TypeVar("_ConvertibleToIntT", bound=ConvertibleToInt)
else:
    _ConvertibleToIntT = TypeVar("_ConvertibleToIntT")

_T = TypeVar("_T")
_VT_co = TypeVar("_VT_co", covariant=True)


def make_cache(path: StrPath | None = None) -> file_cache.FileCache:
    default = pathlib.Path('~/.cache/xkcd').expanduser()
    path = os.environ.get('XKCD_CACHE_DIR', path or default)
    return file_cache.FileCache(path)  # type: ignore[arg-type] # FileCache is using too restrictive pathlib.Path


session = cachecontrol.CacheControl(
    sessions.BaseUrlSession('https://xkcd.com/'),
    heuristic=heuristics.ExpiresAfter(days=365 * 20),
    cache=make_cache(),
)


class Comic:
    def __init__(self, number: int) -> None:
        if not self._404(number):
            self._load(number)

    def _404(self, number: int) -> Self | None:
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
            return None

        self.num = 404
        self.title = "Not Found"
        self.img = None
        self.year = 2008
        self.month = 4
        self.day = 1
        return self

    def _load(self, number: int) -> None:
        resp = session.get(f'{number}/info.0.json')
        resp.raise_for_status()
        vars(self).update(self._fix_numbers(resp.json()))

    @property
    def date(self) -> datetime.date:
        """
        >>> print(Comic(1).date)
        2006-01-01
        """
        return datetime.date(self.year, self.month, self.day)

    @staticmethod
    def _fix_numbers(ob: Mapping[_T, _VT_co]) -> dict[_T, _VT_co | int]:
        """
        Given a dict-like object ob, ensure any integers are integers.
        """
        safe_int = except_(TypeError, ValueError, use='args[0]')(int)
        return dict_map(safe_int, ob)  # type: ignore[no-untyped-call, no-any-return] # jaraco/jaraco.collections#14

    @classmethod
    def latest(cls) -> Self:
        headers = {'Cache-Control': 'no-cache'}
        resp = session.get('info.0.json', headers=headers)
        resp.raise_for_status()
        return cls(resp.json()['num'])

    @classmethod
    def all(cls) -> map[Self]:
        latest = cls.latest()
        return map(cls, range(latest.number, 0, -1))

    @classmethod
    def random(cls) -> Self:
        """
        Return a randomly-selected comic.

        >>> Comic.random()
        Comic(...)
        """
        latest = cls.latest()
        return cls(random.randint(1, latest.number))

    @classmethod
    def search(cls, text: str) -> Self | None:
        """
        Find a comic with the matching text

        >>> print(Comic.search('password strength'))
        xkcd 936:Password Strength \
(https://imgs.xkcd.com/comics/password_strength.png)
        >>> Comic.search('Horse battery')
        Comic(2241)
        >>> Comic.search('ISO 8601')
        Comic(2562)
        >>> Comic.search('2013-02-27').title
        'ISO 8601'
        >>> Comic.search('2020-12-25').title
        'Wrapping Paper'
        """
        matches = (comic for comic in cls.all() if text in comic.full_text)
        return next(matches, None)

    @property
    def number(self) -> int:
        return self.num

    @property
    def full_text(self) -> jaraco.text.FoldedCase:
        """
        >>> comic = Comic.random()
        >>> str(comic.date) in comic.full_text
        True
        """
        values = itertools.chain(vars(self).values(), [self.date])
        return jaraco.text.FoldedCase('|'.join(map(str, values)))

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.number})'

    def __str__(self) -> str:
        return f'xkcd {self.number}:{self.title} ({self.img})'


with contextlib.suppress(ImportError):
    if TYPE_CHECKING:
        import pmxbot.core as core
    else:
        core = importlib.import_module('pmxbot.core')

    @core.command()  # type: ignore[misc] # pragma: no cover
    def xkcd(rest: str | None) -> Comic | None:
        return Comic.search(rest) if rest else Comic.random()  # pragma: no cover
