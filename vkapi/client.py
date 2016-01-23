from .structures import AttrDict
import hashlib
import logging
import re
import requests
import sys
import time
import urllib.parse

__author__ = "Sergei Snegirev (yamldeveloper@proton.me)"
__copyright__ = "Copyright (C) 2013-2016 Sergei Snegirev"
__license__ = "MIT"
__version__ = "3.0"
__url__ = "https://github.com/s3rgeym/vkapi/"

__all__ = ['ApiError', 'AuthError', 'Client', 'ClientError', 'DirectClient',
           'OAuthError', 'StandaloneClient']

API_DELAY = 0.34
API_HOST = "api.vk.com"
API_PATH = "/method/"
API_VERSION = 5.44

API_METHOD_REGEXP = re.compile("[a-z]+([A-Z][a-z]+)*$")
USER_AGENT = "Mozilla/5.0 ({}/{} Python/{})".format(
    __name__,
    __version__,
    sys.version.split(" ")[0]
)


class Client:
    """Клиент для работы с Api Вконтакте.

    Способы вызова методов Api:
        Client.api.<method_name>(**kwargs)
        Client.api.<method_name>(params_dict, **kwargs)
        Client.api_request('<method_name>', params_dict)

    Usage::
        >> from vkapi import Client
        >> vk = Client()
        >> users = vk.api.users.get(user_id=100)
        >> print(users[0].first_name)

    Если имя именованно параметра совпадает с ключевым словом, добавляем
    к нему подчеркивание (global_, from_).
    """
    def __init__(self,
                 access_token=None,
                 user_id=None,
                 secret_token=None,
                 token_expiry=None,
                 api_params={},
                 api_delay=API_DELAY,
                 api_version=API_VERSION,
                 session=None):
        """Конструктор.

        :param access_token: Токен доступа
        :type access_token: str
        :param user_id: Id пользователя
        :type user_id: int
        :param secret_token: Секретный токен
        :type secret_token: str
        :param token_expiry: Timestamp
        :type token_expiry: int
        :param api_delay: Задержка между вызовами методов Api
        :type api_delay: int
        :param api_version: Версия Api
        :type api_version: float
        :param api_params: Дополнительные параметры, которые будут
            передаваться при каждом запросе (помимо токена и версии Api).
            Например: {'https': 1, 'lang': 'en'}
        :type api_params: dict
        :param session: Сессия requests
        :type session: requests.Session instance
        """
        self.access_token = access_token
        self.user_id = user_id
        self.token_expiry = token_expiry
        self.secret_token = secret_token
        self.api_params = api_params
        self.api_delay = api_delay
        self.api_version = api_version
        if not session:
            session = requests.session()
            session.headers['User-Agent'] = USER_AGENT
        self.session = session
        logger_name = '.'.join([__name__, self.__class__.__name__])
        self.logger = logging.getLogger(logger_name)
        self.last_api_request = 0
        # Сахар над вызовом api_request
        self.api = Api(self)

    def request(self, url, data=None, files=None):
        start_time = time.time()
        if data or files:
            response = self.session.post(url, data, files=files)
        else:
            response = self.session.get(url)
        request_time = (time.time() - start_time) * 1000
        self.logger.debug("Total Request Time: %dms", request_time)
        # try:
        #     return response.json(object_hook=AttrDict)
        # else:
        #     return response.text
        return response.json(object_hook=AttrDict)

    def api_request(self, method, params={}):
        """Делает запрос к Api.

        Список методов Api: <https://vk.com/dev/methods>
        Подробнее про запросы к Api: <https://vk.com/dev/api_requests>

        :param method: Метод Api
        :type method: str
        :param params: Передаваемые параметры
        :type params: dict
        :return: Возвращает содержимое поля `response`. Заметьте, что к
            элементам словаря можно обращаться как к аттрибутам через точечную
            нотацию. Вместо обычного словаря используется
            :class:``vkapi.structures.AttrDict``.
        """
        defaults = dict(self.api_params)
        defaults.update(params)
        params = defaults
        params['v'] = self.api_version
        if self.access_token:
            params['access_token'] = self.access_token
        # >>> re.sub('^(/|)|(/|)$', '/', 'foo')
        # /foo/
        path = re.sub('^(/|)|(/|)$', '/', API_PATH)
        path = urllib.parse.urljoin(path, method)
        # <https://vk.com/dev/api_nohttps>
        if self.secret_token:
            # Исправлен баг с неверной подписью. Дело в том, что словари в
            # python неупорядоченные. Новый элемент может быть добавлен как в
            # конец так и любое другое место, да и еще элементы могут
            # поменяться местами. И в итоге имеем, что:
            # md5('foo=bar&baz=qux') != md5('baz=qux&foo=bar')
            # Чтобы закрепить порядок элементов, добавим sig
            params['sig'] = ''
            # Сформировали Query String из словаря
            query = urllib.parse.urlencode(params)
            # А теперь вырежем параметр sig
            query = re.sub('^sig=&|&sig=', '', query)
            uri = '{}?{}{}'.format(path, query, self.secret_token)
            sig = hashlib.md5(uri.encode('ascii')).hexdigest()
            params["sig"] = sig
            scheme = 'http'
        else:
            scheme = 'https'
        # !!! params не должен изменяться после добавления sig
        api_endpoint = "{}://{}{}".format(scheme, API_HOST, path)
        delay = self.api_delay + self.last_api_request - time.time()
        if delay > 0:
            self.logger.debug("Wait %dms", delay * 1000)
            time.sleep(delay)
        self.logger.debug(
            "Calling Api method %r with parameters: %s", method, params)
        response = self.request(api_endpoint, params)
        self.last_api_request = time.time()
        error = response.get('error')
        if error:
            if 'captcha_img' in error:
                params['captcha_sid'] = error.captcha_sid
                return self.handle_captcha(
                    error.captcha_img,
                    method,
                    params
                )
            if 'redirect_uri' in error:
                return self.handle_validation(
                    error.redirect_uri,
                    method,
                    params
                )
            # Кастомные ошибки
            error = ApiError(error)
            return self.handle_error(error, method, params)
        return response.response

    #
    # Обработчики ошибок
    #

    def handle_validation(self, redirect_uri, method, params):
        # Для переопределения в классах потомках.
        # Мы открываем URL в браузере (либо эмулирует его открытие), а затем
        # вводим номер телефона без префикса и двух последних цифр (ранее
        # нужно было кликнуть по кнопке). После этого нас перенаправляют на:
        # {REDIRECT_URI}#access_token=NEW_ACCESS_TOKEN...
        # либо на:
        # {REDIRECT_URI}#error=...&error_description=...
        # ... do smth
        # if ok:
        #     return self.api_request(method, params)
        raise ClientError("Validation Required")

    def handle_captcha(self, captcha_img, method, params):
        # Для переопределения в классах потомках.
        # ... get captcha_key
        # captcha_sid уже добавлен
        # params['captcha_key'] = captcha_key
        # return self.api_request(method, params)
        raise ClientError("Captcha Required")

    def handle_error(self, error, method, params):
        """Обработчик всех ошибок кроме капчи и валидации"""
        # Для переопределения в классах потомках.
        # if error.code is vkapi.errors.TOO_MANY_REQUESTS_PER_SECOND:
        #     time.sleep(5)
        #     return self.api_request(method, params)
        raise error

    def upload(self, upload_url, files):
        response = self.request(upload_url, None, files)
        if 'error' in response:
            raise ClientError(response.error)
        return response

    @property
    def valid_token(self):
        """Проверяет access_token."""
        # Можно короче:
        # return self.api.users.get() == []
        # Но этот способ не будет работать с серверными приложениями
        if not self.token_expired:
            try:
                return self.api.execute(code="return true;")
            except ApiError:
                pass
        return False

    @property
    def token_expired(self):
        if self.access_token:
            # Токен может выдаваться на неопределенный срок и тогда
            # token_expiry равно None либо 0
            if self.token_expiry:
                return time.time() > self.token_expiry
        return False


class Api:
    def __init__(self, client, method=None):
        self._client = client
        self._method = method

    def __getattr__(self, name):
        if API_METHOD_REGEXP.match(name):
            method = name if not self._method \
                             else '.'.join([self._method, name])
            return Api(self._client, method)
        raise AttributeError(name)

    def __call__(self, *args, **kwargs):
        # Если имя именованного параметра совпадает с ключевым словом, то
        # добавляем подчеркивание (from_, global_)
        params = {k[:-1] if len(k) > 1 and k.endswith('_')
                  else k: v for k, v in kwargs.items()}
        if len(args):
            # Первым аргументом является словарь
            d = dict(args[0])
            # Если переданы именованные параметры, то обновляем словарь
            d.update(params)
            params = d
        return self._client.api_request(self._method, params)


class ClientError(Exception):
    pass


class ApiError(ClientError):
    def __init__(self, data):
        self.code = data.error_code
        self.msg = data.error_msg

    def __str__(self):
        return "{}: {}".format(self.code, self.msg)


# Существует 4 способа авторизации, но нам
# интересны только два: прямая авторизация и авторизация standalone приложений.
# Данные (client id и client secret) от официальных приложений нагуглить
# несложно (например, от Android client id: 2274003, client secret:
# hHbZxrka2uZ6jB1inYsH), свое же standalone приложение можно создать по ссылке
# <https://vk.com/editapp?act=create>


AUTH_BASE = "https://oauth.vk.com"
REDIRECT_URI = AUTH_BASE + "/blank.html"
DISPLAY = "mobile"


class AuthUrlMixin:
    @property
    def auth_url(self):
        return urllib.parse.urljoin(AUTH_BASE, self.auth_path)


class ParseHashMixin:
    def parse_hash(self, url):
        hash_ = url[url.find('#') + 1:]
        data = dict(urllib.parse.parse_qsl(hash_))
        if 'error' in data:
            raise OAuthError(data)
        self.access_token = data['access_token']
        self.user_id = int(data['user_id'])
        self.token_expiry = int(data['expires_in'])
        # У оффициальных приложений оно всегда 0
        if self.token_expiry:
            self.token_expiry += time.time()
        self.secret_token = data.get('secret')


class DirectClient(AuthUrlMixin, ParseHashMixin, Client):
    """Класс для прямой авторизации <https://vk.com/dev/auth_direct>
    """
    def __init__(self,
                 client_id,
                 client_secret,
                 scope=None,
                 test_redirect_uri=None,
                 **kwargs):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.test_redirect_uri = test_redirect_uri
        self.auth_path = 'token'
        Client.__init__(self, **kwargs)

    def authorize(self, username, password):
        if not username or not password:
            raise AuthError("Username and password are required")
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'password',
            'username': username,
            'password': password,
            'v': self.api_version
        }
        if self.scope:
            params['scope'] = self.scope
        if self.test_redirect_uri:
            params['test_redirect_uri'] = self.redirect_uri
        self.auth_request(params)

    def auth_request(self, params):
        self.logger.debug("Params: %s", params)
        response = self.request(self.auth_url, params)
        if 'captcha_img' in response:
            params['captcha_sid'] = response.captcha_sid
            self.handle_auth_captcha(response.captcha_img, params)
            return
        if 'redirect_uri' in response:
            self.handle_auth_validation(response.redirect_uri)
        # Прочие ошибки
        if 'error' in response:
            raise OAuthError(response)
        self.access_token = response.access_token
        self.user_id = response.user_id
        self.token_expiry = response.expires_in
        if self.token_expiry:
            self.token_expiry += time.time()
        self.secret_token = response.get('secret')
        self.logger.info("Successfully authorized")

    def handle_auth_captcha(self, captcha_img, params):
        # captcha_sid уже в params
        # params['captcha_key'] = captcha_key
        # можно еще обновить username и password, если допустим имеется
        # графический интерфейс и поля для ввода логина, пароля и капчи
        # одновременно
        # По новой пробуем авторизоваться
        # self.auth_request(params)
        raise AuthError("Captcha Required")

    def handle_auth_validation(self, redirect_uri):
        # Процедура валидации заключается в вводе цифр телефона (кроме префикса
        # и двух последних), после чего мы попадем на страницу:
        # {REDIRECT_URI}#access_token=ACCESS_TOKEN...
        # либо на:
        # {REDIRECT_URI}#error=...&error_description=...
        # Парсим эту строку с помощью self.parse_hash
        raise AuthError("Validation Required")


class StandaloneClient(AuthUrlMixin, ParseHashMixin, Client):
    """Осуществляет авторизацию Standalone приложения
    <https://vk.com/dev/auth_mobile>"""
    def __init__(self,
                 client_id,
                 scope=None,
                 display=DISPLAY,
                 redirect_uri=REDIRECT_URI,
                 **kwargs):
        self.client_id = client_id
        self.scope = scope
        self.redirect_uri = redirect_uri
        self.display = display
        self.auth_path = 'authorize'
        Client.__init__(self, **kwargs)

    def authorize(self, username, password):
        if not username or not password:
            raise AuthError("Username and password are required")
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'token',
            'v': self.api_version,
        }
        if self.scope:
            params['scope'] = self.scope
        if self.display:
            params['display'] = self.display
        r = self.session.post(self.auth_url, params)
        action = self.get_action(r.text)
        data = self.get_hiddens(r.text)
        data['email'] = username
        data['pass'] = password
        self.submit_login(action, data)

    def submit_login(self, action, data):
        """Эмилируем отправку формы."""
        r = self.session.post(action, data)
        self.logger.debug("Current URL: %s", r.url)
        # Если уже авторизованы сразу перебросит на {REDIRECT_URI}#{PARAMS}
        if '#' in r.url:
            self.parse_hash(r.url)
            return
        # Либо попадем на страницу подтверждения с кнопочкой Allow
        grant_access_match = re.search(
            'https://login\.vk\.com/\?act=grant_access([^"]+)', r.text)
        if grant_access_match:
            grant_access_url = grant_access_match.group(0)
            # Переходим по ссылке (эмулируем ее нажатие)
            r = self.session.get(grant_access_url)
            # Попадаем на {REDIRECT_URI}#{PARAMS}
            self.parse_hash(r.url)
            return
        # Ищем капчу
        captcha_match = re.search(
            '([^"]+/captcha\.php\?sid=[^"]+)', r.text)
        if captcha_match:
            captcha_img = captcha_match.group(1)
            action = self.get_action(r.text)
            data = self.get_hiddens(r.text)
            self.handle_captcha(captcha_img, action, data)
            return
        # Ищем ошибку
        # display=page,popup
        # <div class="oauth_error">Invalid login or password.</div>
        # display=mobile
        # <div class="service_msg service_msg_warning">Invalid login or
        # password.</div>
        error_match = re.search(
            '(?:warning|error)">([^<]+)', r.text)
        if error_match:
            raise AuthError(error_match.group(1))
        raise AuthError("WTF?")

    def handle_captcha(self, captcha_img, action, data):
        # Выводи форму с капчей либо используем антигейт, а потом снова
        # отправляем форму
        # data['captcha_key'] = captcha_key
        # self.submit_login(action, data)
        raise AuthError("Captcha Required")

    def get_action(self, content):
        match = re.search(' action="([^"]+)', content)
        return match.group(1)

    def get_hiddens(self, content):
        """Возвращает значения скрытых полей на странице в виде словаря."""
        matches = re.findall(
            ' name="(_origin|ip_h|lg_h|to|captcha_sid|expire)" value="([^"]+)',
            content
        )
        return dict(matches)


class AuthError(ClientError):
    pass


class OAuthError(AuthError):
    def __init__(self, data):
        self.error_type = data['error']
        self.description = data.get('error_description')

    def __str__(self):
        if self.description:
            return ": ".join([self.error_type, self.description])
        return self.error_type
