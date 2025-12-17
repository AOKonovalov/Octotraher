__all__ = ['LinkPreview', 'TelegramPost', 'Channel', 'TelegramChannelScraper']


import bs4
import dataclasses
import datetime
import logging
import re
import octotraher.base
import typing
import urllib.parse

_logger = logging.getLogger(__name__)
_SINGLE_MEDIA_LINK_PATTERN = re.compile(r'^https://t\.me/[^/]+/\d+\?single$')
_STYLE_MEDIA_URL_PATTERN = re.compile(r'url\(\'(.*?)\'\)')

@dataclasses.dataclass
class LinkPreview:
	href: str
	siteName: typing.Optional[str] = None
	title: typing.Optional[str] = None
	description: typing.Optional[str] = None
	image: typing.Optional[str] = None


@dataclasses.dataclass
class Channel(octotraher.base.Entity):
	username: str
	title: typing.Optional[str] = None
	verified: typing.Optional[bool] = None
	photo: typing.Optional[str] = None
	description: typing.Optional[str] = None
	members: typing.Optional[int] = None
	photos: typing.Optional[octotraher.base.IntWithGranularity] = None
	videos: typing.Optional[octotraher.base.IntWithGranularity] = None
	links: typing.Optional[octotraher.base.IntWithGranularity] = None
	files: typing.Optional[octotraher.base.IntWithGranularity] = None

	photosGranularity = octotraher.base._DeprecatedProperty('photosGranularity', lambda self: self.photos.granularity, 'photos.granularity')
	videosGranularity = octotraher.base._DeprecatedProperty('videosGranularity', lambda self: self.videos.granularity, 'videos.granularity')
	linksGranularity = octotraher.base._DeprecatedProperty('linksGranularity', lambda self: self.links.granularity, 'links.granularity')
	filesGranularity = octotraher.base._DeprecatedProperty('filesGranularity', lambda self: self.files.granularity, 'files.granularity')

	def __str__(self):
		return f'https://t.me/s/{self.username}'


@dataclasses.dataclass
class TelegramPost(octotraher.base.Item):
	url: str
	date: datetime.datetime
	content: str
	outlinks: typing.List[str] = None
	mentions: typing.List[str] = None
	hashtags: typing.List[str] = None
	forwarded: typing.Optional['Channel'] = None
	forwardedUrl: typing.Optional[str] = None
	media: typing.Optional[typing.List['Medium']] = None
	views: typing.Optional[octotraher.base.IntWithGranularity] = None
	reactions: typing.Optional[int] = None
	linkPreview: typing.Optional[LinkPreview] = None

	outlinksss = octotraher.base._DeprecatedProperty('outlinksss', lambda self: ' '.join(self.outlinks), 'outlinks')

	def __str__(self):
		return self.url


class Medium:
	pass


@dataclasses.dataclass
class Photo(Medium):
	url: str


@dataclasses.dataclass
class Video(Medium):
	thumbnailUrl: str
	duration: float
	url: typing.Optional[str] = None


@dataclasses.dataclass
class VoiceMessage(Medium):
	url: str
	duration: str
	bars:typing.List[float]


@dataclasses.dataclass
class Gif(Medium):
	thumbnailUrl: str
	url: typing.Optional[str] = None


class TelegramChannelScraper(octotraher.base.Scraper):
	name = 'telegram-channel'

	def __init__(self, name, **kwargs):
		super().__init__(**kwargs)
		self._name = name
		self._headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'}
		self._initialPage = None
		self._initialPageSoup = None

	def _initial_page(self):
		if self._initialPage is None:
			r = self._get(f'https://t.me/s/{self._name}', headers = self._headers)
			if r.status_code != 200:
				raise octotraher.base.ScraperException(f'Got status code {r.status_code}')
			self._initialPage, self._initialPageSoup = r, bs4.BeautifulSoup(r.text, 'lxml')
		return self._initialPage, self._initialPageSoup

	def _soup_to_items(self, soup, pageUrl, onlyUsername = False):
		posts = soup.find_all('div', attrs = {'class': 'tgme_widget_message', 'data-post': True})
		for post in reversed(posts):
			if onlyUsername:
				yield post['data-post'].split('/')[0]
				return
			dateDiv = post.find('div', class_ = 'tgme_widget_message_footer').find('a', class_ = 'tgme_widget_message_date')
			rawUrl = dateDiv['href']
			if not rawUrl.startswith('https://t.me/') or sum(x == '/' for x in rawUrl) != 4 or rawUrl.rsplit('/', 1)[1].strip('0123456789') != '':
				_logger.warning(f'Possibly incorrect URL: {rawUrl!r}')
			url = rawUrl.replace('//t.me/', '//t.me/s/')
			date = datetime.datetime.strptime(dateDiv.find('time', datetime = True)['datetime'].replace('-', '', 2).replace(':', ''), '%Y%m%dT%H%M%S%z')
			media = []
			outlinks = []
			mentions = []
			hashtags = []
			forwarded = None
			forwardedUrl = None
			
			# Обработка группированных медиа (grouped media)
			groupedWrap = post.find('div', class_ = 'tgme_widget_message_grouped_wrap')
			if groupedWrap:
				# Фото в группированных медиа
				for photoWrap in groupedWrap.find_all('a', class_ = 'tgme_widget_message_photo_wrap'):
					style = photoWrap.attrs.get('style', '')
					if style:
						imageUrls = _STYLE_MEDIA_URL_PATTERN.findall(style)
						if imageUrls:
							media.append(Photo(url = imageUrls[0]))
				
				# Видео в группированных медиа
				for videoPlayer in groupedWrap.find_all('a', class_ = 'tgme_widget_message_video_player'):
					videoUrl = None
					videoThumbnailUrl = None
					
					iTag = videoPlayer.find('i', class_ = 'tgme_widget_message_video_thumb')
					if iTag is None:
						iTag = videoPlayer.find('i')
					
					if iTag and iTag.get('style'):
						style = iTag['style']
						thumbUrls = _STYLE_MEDIA_URL_PATTERN.findall(style)
						if thumbUrls:
							videoThumbnailUrl = thumbUrls[0]
					
					videoTag = videoPlayer.find('video')
					if videoTag and videoTag.get('src'):
						videoUrl = videoTag['src']
					
					if videoThumbnailUrl or videoUrl:
						mKwargs = {
							'thumbnailUrl': videoThumbnailUrl,
							'url': videoUrl,
						}
						timeTag = videoPlayer.find('time', class_ = 'message_video_duration')
						if timeTag is None:
							timeTag = videoPlayer.find('time')
						
					if timeTag is None:
						# Пропускаем Gif - не нужны (только Photo и Video)
						continue
					else:
						cls = Video
						durationStr = timeTag.text
						mKwargs['duration'] = _durationStrToSeconds(durationStr)
					media.append(cls(**mKwargs))

			if (forwardTag := post.find('a', class_ = 'tgme_widget_message_forwarded_from_name')):
				forwardedUrl = forwardTag['href']
				forwardedName = forwardedUrl.split('t.me/')[1].split('/')[0]
				forwarded = Channel(username = forwardedName)

			if (message := post.find('div', class_ = 'tgme_widget_message_text')):
				content = message.get_text(separator="\n")
			else:
				content = None

			# Обработка фото через tgme_widget_message_photo_wrap
			# Пропускаем, если медиа уже обработано в grouped media
			if not groupedWrap:
				for photoWrap in post.find_all('a', class_ = 'tgme_widget_message_photo_wrap'):
					style = photoWrap.attrs.get('style', '')
					if style:
						imageUrls = _STYLE_MEDIA_URL_PATTERN.findall(style)
						if imageUrls:
							media.append(Photo(url = imageUrls[0]))
			
			for link in post.find_all('a'):
				# Пропускаем ссылки внутри grouped media (уже обработаны)
				if groupedWrap:
					# Проверяем, является ли link потомком groupedWrap
					parent = link.find_parent('div', class_='tgme_widget_message_grouped_wrap')
					if parent == groupedWrap:
						continue
				if any(x in link.parent.attrs.get('class', []) for x in ('tgme_widget_message_user', 'tgme_widget_message_author')):
					# Author links at the top (avatar and name)
					continue
				if link['href'] == rawUrl or link['href'] == url:
					style = link.attrs.get('style', '')
					# Generic filter of links to the post itself, catches videos, photos, and the date link
					if style != '':
						imageUrls = _STYLE_MEDIA_URL_PATTERN.findall(style)
						if len(imageUrls) == 1:
							media.append(Photo(url = imageUrls[0]))
						continue
				if _SINGLE_MEDIA_LINK_PATTERN.match(link['href']):
					style = link.attrs.get('style', '')
					imageUrls = _STYLE_MEDIA_URL_PATTERN.findall(style)
					if len(imageUrls) == 1:
						media.append(Photo(url = imageUrls[0]))
						# resp = self._get(image[0])
						# encoded_string = base64.b64encode(resp.content)
					# Individual photo or video link
					continue
				if link.text.startswith('@'):
					mentions.append(link.text.strip('@'))
					continue
				if link.text.startswith('#'):
					hashtags.append(link.text.strip('#'))
					continue
				href = urllib.parse.urljoin(pageUrl, link['href'])
				if (href not in outlinks) and (href != rawUrl) and (href != forwardedUrl):
					outlinks.append(href)

			# Пропускаем VoiceMessage - не нужны (только Photo и Video)
			# for voicePlayer in post.find_all('a', {'class': 'tgme_widget_message_voice_player'}):
			# 	audioUrl = voicePlayer.find('audio')['src']
			# 	durationStr = voicePlayer.find('time').text
			# 	duration = _durationStrToSeconds(durationStr)
			# 	barHeights = [float(s['style'].split(':')[-1].strip(';%')) for s in voicePlayer.find('div', {'class': 'bar'}).find_all('s')]
			# 	media.append(VoiceMessage(url = audioUrl, duration = duration, bars = barHeights))

			for videoPlayer in post.find_all('a', {'class': 'tgme_widget_message_video_player'}):
				videoUrl = None
				videoThumbnailUrl = None
				
				# Ищем thumbnail в i.tgme_widget_message_video_thumb
				iTag = videoPlayer.find('i', class_ = 'tgme_widget_message_video_thumb')
				if iTag is None:
					# Пробуем найти любой i тег со style
					iTag = videoPlayer.find('i')
				
				if iTag and iTag.get('style'):
					style = iTag['style']
					thumbUrls = _STYLE_MEDIA_URL_PATTERN.findall(style)
					if thumbUrls:
						videoThumbnailUrl = thumbUrls[0]
				
				# Ищем video тег для получения URL
				videoTag = videoPlayer.find('video')
				if videoTag and videoTag.get('src'):
					videoUrl = videoTag['src']
				
				# Если нет video тега, но есть thumbnail, все равно создаем Video объект
				if videoThumbnailUrl or videoUrl:
					mKwargs = {
						'thumbnailUrl': videoThumbnailUrl,
						'url': videoUrl,
					}
					timeTag = videoPlayer.find('time', class_ = 'message_video_duration')
					if timeTag is None:
						# Пробуем найти любой time тег
						timeTag = videoPlayer.find('time')
					
					if timeTag is None:
						# Пропускаем Gif - не нужны (только Photo и Video)
						continue
					else:
						cls = Video
						durationStr = timeTag.text
						mKwargs['duration'] = _durationStrToSeconds(durationStr)
					media.append(cls(**mKwargs))

			linkPreview = None
			if (linkPreviewA := post.find('a', class_ = 'tgme_widget_message_link_preview')):
				kwargs = {}
				kwargs['href'] = urllib.parse.urljoin(pageUrl, linkPreviewA['href'])
				if (siteNameDiv := linkPreviewA.find('div', class_ = 'link_preview_site_name')):
					kwargs['siteName'] = siteNameDiv.text
				if (titleDiv := linkPreviewA.find('div', class_ = 'link_preview_title')):
					kwargs['title'] = titleDiv.text
				if (descriptionDiv := linkPreviewA.find('div', class_ = 'link_preview_description')):
					kwargs['description'] = descriptionDiv.text
				if (imageI := linkPreviewA.find('i', class_ = 'link_preview_image')):
					if imageI['style'].startswith("background-image:url('"):
						kwargs['image'] = imageI['style'][22 : imageI['style'].index("'", 22)]
					else:
						_logger.warning(f'Could not process link preview image on {url}')
				linkPreview = LinkPreview(**kwargs)
				if kwargs['href'] in outlinks:
					outlinks.remove(kwargs['href'])

			# Извлечение просмотров
			viewsSpan = post.find('span', class_ = 'tgme_widget_message_views')
			if viewsSpan is None:
				views = None
			else:
				viewsText = viewsSpan.text.strip()
				if viewsText:
					views = octotraher.base.IntWithGranularity(*_parse_num(viewsText))
				else:
					views = None
			
			# Извлечение реакций (сумма всех реакций)
			reactions = None
			reactionsDiv = post.find('div', class_ = 'tgme_widget_message_reactions')
			if reactionsDiv:
				total_reactions = 0
				for reactionSpan in reactionsDiv.find_all('span', class_ = 'tgme_reaction'):
					# Текст содержит эмодзи и число, например: "❤46" или "👍11"
					reaction_text = reactionSpan.get_text(strip=True)
					# Извлекаем число из конца строки
					numbers = re.findall(r'\d+', reaction_text)
					if numbers:
						total_reactions += int(numbers[-1])  # Берем последнее число
				if total_reactions > 0:
					reactions = total_reactions

			outlinks = outlinks if outlinks else None
			media = media if media else None
			mentions = mentions if mentions else None
			hashtags = hashtags if hashtags else None
			
			yield TelegramPost(url = url, date = date, content = content, outlinks = outlinks, mentions = mentions, hashtags = hashtags, linkPreview = linkPreview, media = media, forwarded = forwarded, forwardedUrl = forwardedUrl, views = views, reactions = reactions)

	def get_items(self):
		r, soup = self._initial_page()
		if '/s/' not in r.url:
			_logger.warning('No public post list for this user')
			return
		nextPageUrl = ''
		while True:
			yield from self._soup_to_items(soup, r.url)
			try:
				if soup.find('a', attrs = {'class': 'tgme_widget_message_date'}, href = True)['href'].split('/')[-1] == '1':
					# if message 1 is the first message in the page, terminate scraping
					break
			except:
				pass
			pageLink = soup.find('a', attrs = {'class': 'tme_messages_more', 'data-before': True})
			if not pageLink:
				# some pages are missing a "tme_messages_more" tag, causing early termination
				if '=' not in nextPageUrl:
					nextPageUrl =  soup.find('link', attrs = {'rel': 'canonical'}, href = True)['href']
				nextPostIndex = int(nextPageUrl.split('=')[-1]) - 20
				if nextPostIndex > 20:
					pageLink = {'href': nextPageUrl.split('=')[0] + f'={nextPostIndex}'}
				else:
					break
			nextPageUrl = urllib.parse.urljoin(r.url, pageLink['href'])
			r = self._get(nextPageUrl, headers = self._headers, responseOkCallback = _telegramResponseOkCallback)
			if r.status_code != 200:
				raise octotraher.base.ScraperException(f'Got status code {r.status_code}')
			soup = bs4.BeautifulSoup(r.text, 'lxml')

	def _get_entity(self):
		kwargs = {}
		# /channel has a more accurate member count and bigger profile picture
		r = self._get(f'https://t.me/{self._name}', headers = self._headers)
		if r.status_code != 200:
			raise octotraher.base.ScraperException(f'Got status code {r.status_code}')
		soup = bs4.BeautifulSoup(r.text, 'lxml')
		membersDiv = soup.find('div', class_ = 'tgme_page_extra')
		if membersDiv.text.split(',')[0].endswith((' members', ' subscribers')):
			membersStr = ''.join(membersDiv.text.split(',')[0].split(' ')[:-1])
			if membersStr == 'no':
				kwargs['members'] = 0
			else:
				kwargs['members'] = int(membersStr)
		photoImg = soup.find('img', class_ = 'tgme_page_photo_image')
		if photoImg is not None:
			kwargs['photo'] = photoImg.attrs['src']
		else:
			kwargs['photo'] = None

		r, soup = self._initial_page()
		if '/s/' not in r.url: # Redirect on channels without public posts
			return
		channelInfoDiv = soup.find('div', class_ = 'tgme_channel_info')
		assert channelInfoDiv, 'channel info div not found'
		titleDiv = channelInfoDiv.find('div', class_ = 'tgme_channel_info_header_title')
		kwargs['title'] = titleDiv.find('span').text
		kwargs['verified'] = bool(titleDiv.find('i', class_ = 'verified-icon'))
		# The username in the channel info is not canonicalised, nor is the one on the /channel page anywhere.
		# However, the post URLs are, so extract the first post and use that.
		try:
			kwargs['username'] = next(self._soup_to_items(soup, r.url, onlyUsername = True))
		except StopIteration:
			# If there are no posts, fall back to the channel info div, although that should never happen due to the 'Channel created' entry.
			_logger.warning('Could not find a post; extracting username from channel info div, which may not be capitalised correctly')
			kwargs['username'] = channelInfoDiv.find('div', class_ = 'tgme_channel_info_header_username').text[1:] # Remove @
		if (descriptionDiv := channelInfoDiv.find('div', class_ = 'tgme_channel_info_description')):
			kwargs['description'] = descriptionDiv.text

		for div in channelInfoDiv.find_all('div', class_ = 'tgme_channel_info_counter'):
			value, granularity = _parse_num(div.find('span', class_ = 'counter_value').text)
			type_ = div.find('span', class_ = 'counter_type').text
			if type_ == 'members':
				# Already extracted more accurately from /channel, skip
				continue
			elif type_ in ('photos', 'videos', 'links', 'files'):
				kwargs[type_] = octotraher.base.IntWithGranularity(value, granularity)

		return Channel(**kwargs)

	@classmethod
	def _cli_setup_parser(cls, subparser):
		subparser.add_argument('channel', type = octotraher.base.nonempty_string('channel'), help = 'A channel name')

	@classmethod
	def _cli_from_args(cls, args):
		return cls._cli_construct(args, args.channel)

def _parse_num(s):
	s = s.replace(' ', '')
	if s.endswith('M'):
		return int(float(s[:-1]) * 1e6), 10 ** (6 if '.' not in s else 6 - len(s[:-1].split('.')[1]))
	elif s.endswith('K'):
		return int(float(s[:-1]) * 1000), 10 ** (3 if '.' not in s else 3 - len(s[:-1].split('.')[1]))
	return int(s), 1

def _durationStrToSeconds(durationStr):
	durationList = durationStr.split(':')
	return sum([int(s) * int(g) for s, g in zip([1, 60, 3600], reversed(durationList))])

def _telegramResponseOkCallback(r):
	if r.status_code == 200:
		return (True, None)
	return (False, f'{r.status_code=}')
	