import os.path
import setuptools


with open(os.path.join(os.path.dirname(__file__), 'README.md')) as fp:
	readme = fp.read()


setuptools.setup(
	name = 'octotraher',
	version = '0.1.0',
	description = 'A social networking service scraper',
	long_description = readme,
	long_description_content_type = 'text/markdown',
	author = 'JustAnotherArchivist',
	url = 'https://github.com/JustAnotherArchivist/octotraher',
	classifiers = [
		'Development Status :: 4 - Beta',
		'Programming Language :: Python :: 3.8',
		'Programming Language :: Python :: 3.9',
		'Programming Language :: Python :: 3.10',
		'Programming Language :: Python :: 3.11',
		'Programming Language :: Python :: 3.12',
	],
	packages = ['octotraher', 'octotraher.modules'],
	install_requires = [
		'requests[socks]',
		'lxml',
		'beautifulsoup4',
		'pytz; python_version < "3.9.0"',
		'filelock',
	],
	python_requires = '>=3.8',
	extras_require = {
		'test': ['coverage'],
	},
	entry_points = {
		'console_scripts': [
			'octotraher = octotraher._cli:main',
		],
	},
)
