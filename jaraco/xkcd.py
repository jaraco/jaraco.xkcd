import urllib.parse
import random
import importlib
import contextlib
import datetime

import jaraco.text
import requests

session = requests.session()


class Comic:
	root = 'https://xkcd.com/'

	__cache = {}

	def __new__(cls, number):
		return cls.__cache.setdefault(number, super().__new__(cls))

	def __init__(self, number):
		if vars(self):
			return
		path = '{number}/info.0.json'.format(**locals())
		url = urllib.parse.urljoin(self.root, path)
		resp = session.get(url)
		resp.raise_for_status()
		vars(self).update(self._fix_numbers(resp.json()))
		self.date = datetime.date(self.year, self.month, self.day)

	@staticmethod
	def _fix_numbers(ob):
		"""
		Given a dict-like object ob, ensure any integers are integers.
		"""
		def make_int(val):
			try:
				return int(val)
			except Exception:
				return val

		return (
			(key, make_int(value))
			for key, value in ob.items()
		)

	@classmethod
	def latest(cls):
		url = urllib.parse.urljoin(cls.root, 'info.0.json')
		resp = session.get(url)
		resp.raise_for_status()
		return cls(resp.json()['num'])

	@classmethod
	def all(cls):
		latest = cls.latest()
		return map(cls, range(latest.number, 0, -1))

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
		Comic(936)
		>>> Comic.search('ISO 8601')
		Comic(1179)
		>>> Comic.search('2013-02-27').title
		'ISO 8601'
		"""
		matches = (
			comic
			for comic in cls.all()
			if text in comic.full_text
		)
		return next(matches, None)

	@property
	def number(self):
		return self.num

	@property
	def full_text(self):
		return jaraco.text.FoldedCase('|'.join(map(str, vars(self).values())))

	def __repr__(self):
		return '{self.__class__.__name__}({self.number})'.format(**locals())

	def __str__(self):
		return 'xkcd {self.number}:{self.title} ({self.img})'.format(**locals())


with contextlib.suppress(ImportError):
	core = importlib.import_module('pmxbot.core')

	@core.command()
	def xkcd(rest):
		return Comic.search(rest) if rest else Comic.random()
