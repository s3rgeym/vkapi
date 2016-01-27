from . import defaults
from .browser import Browser
from .structures import AttrDict
from .ui_captcha import Ui_Captcha
from .utils import parse_hash
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QDialog
import hashlib
import json
import logging
import os
import re
import requests
import sys
import time
import urllib.parse

__author__ = "Sergei Snegirev (yamldeveloper@proton.me)"
__copyright__ = "Copyright (C) 2013-2016 Sergei Snegirev"
__license__ = "MIT"
__version__ = "3.0"
__url__ = "github.com/s3rgeym/vkapi/"


API_METHOD_REGEXP = re.compile("[a-z]+([A-Z][a-z]+)*$")


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
    SAVED_ATTRS = ['access_token', 'user_id', 'secret_token', 'token_expiry']

    def __init__(self,
                 session_filename=None,
                 access_token=None,
                 user_id=None,
                 token_expiry=None,
                 secret_token=None,
                 api_params=None,
                 api_delay=None,
                 api_version=None,
                 http=None):
        """Конструктор.

        :param session_filename: Имя файла куда будут сохранены данные от
            токена
        :type session_filename: str
        :param access_token: Токен доступа
        :type access_token: str
        :param user_id: ID пользователя
        :type user_id: int
        :param token_expiry: Время истечения срока действия токена в формате
            timestamp
        :type token_expiry: int
        :param secret_token: Секретный токен
        :type secret_token: str
        :param api_delay: Задержка между вызовами методов Api
        :type api_delay: int
        :param api_version: Версия Api
        :type api_version: float
        :param api_params: Дополнительные параметры, которые будут
            передаваться при каждом запросе (помимо токена и версии Api).
            Например: {'https': 1, 'lang': 'en'}
        :type api_params: dict
        :param http: Сессия requests
        :type http: requests.Session instance
        """
        self.logger = logging.getLogger('.'.join([
            self.__class__.__module__, self.__class__.__name__]))
        self.session_filename = session_filename
        self.access_token = access_token
        self.user_id = user_id
        self.token_expiry = token_expiry
        self.secret_token = secret_token
        self.api_params = api_params or {}
        self.api_delay = api_delay or defaults.API_DELAY
        self.api_version = api_version or defaults.API_VERSION
        if not http:
            http = requests.session()
            # Mozilla/5.0 (compatible; vkapi.client/3.0; Python/3.4.3;
            # +github.com/s3rgeym/vkapi/)
            http.headers['User-Agent'] = defaults.USER_AGENT_FORMAT.format(
                __name__, __version__, sys.version.split(' ')[0], __url__)
        self.http = http
        self.last_api_request = 0
        # Сахар над вызовом api_request
        self.api = Api(self)
        self.load_session()
        self.qapp = QApplication.instance() or QApplication(sys.argv)

    def request(self, method, url, **kwargs):
        start_time = time.time()
        response = self.http.request(method, url, **kwargs)
        request_time = (time.time() - start_time) * 1000
        self.logger.debug("Total Request Time: %dms", request_time)
        return response.json(object_hook=AttrDict)
        # try:
        #     return response.json(object_hook=AttrDict)
        # else:
        #     return response.text

    def get(self, url, params=None, **kwargs):
        return self.request('GET', url, params=params, **kwargs)

    def post(self, url, data=None, **kwargs):
        return self.request('POST', url, data=data, **kwargs)

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
        q = dict(self.api_params)
        q.update(params)
        params = q
        params['v'] = self.api_version
        if self.access_token:
            params['access_token'] = self.access_token
        # >>> re.sub('^(/|)|(/|)$', '/', 'foo')
        # /foo/
        path = re.sub('^(/|)|(/|)$', '/', defaults.API_PATH)
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
        api_endpoint = "{}://{}{}".format(scheme, defaults.API_HOST, path)
        delay = self.api_delay + self.last_api_request - time.time()
        if delay > 0:
            self.logger.debug("Wait %dms", delay * 1000)
            time.sleep(delay)
        self.logger.debug(
            "Calling Api method %r with parameters: %s", method, params)
        response = self.post(api_endpoint, params)
        self.last_api_request = time.time()
        error = response.get('error')
        if error:
            if 'captcha_img' in error:
                return self.handle_captcha(
                    error.captcha_img,
                    error.captcha_sid,
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

    # Обработчики ошибок

    def handle_captcha(self, captcha_img, captcha_sid, method, params):
        c = Captcha(self, captcha_img)
        if c.exec_():
            params['captcha_sid'] = captcha_sid
            params['captcha_key'] = c.ui.captcha_line.text()
            return self.api_request(method, params)
        raise ClientError("Action canceled by user")

    def handle_validation(self, redirect_uri, method, params):
        if not Validation(self, redirect_uri).exec_():  # raises ClientError
            raise ClientError("Action canceled by user")
        self.save_session()
        return self.api_request(method, params)

    def handle_error(self, error, method, params):
        """Обработчик всех ошибок кроме капчи и валидации"""
        # Для переопределения в классах потомках.
        # if error.code == vkapi.errors.TOO_MANY_REQUESTS_PER_SECOND:
        #     time.sleep(5)
        #     return self.api_request(method, params)
        raise error

    # Загрузка файлов

    def upload(self, upload_url, files):
        response = self.post(upload_url, files=files)
        if 'error' in response:
            raise ClientError(response.error)
        return response

    # Работа с токеном

    @property
    def test_token(self):
        """Проверяет access_token."""
        # Можно короче:
        # return self.api.users.get() == []
        # Но этот способ не будет работать с серверными приложениями
        try:
            return self.api.execute(code="return true;")
        except ApiError:
            return False

    @property
    def token_expired(self):
        if self.access_token:
            # Токен может выдаваться на неопределенный срок и тогда
            # token_expiry равно None либо 0
            if self.token_expiry:
                return time.time() > self.token_expiry
        return False

    # Сессия

    def load_session(self):
        if self.session_filename and os.path.exists(self.session_filename):
            with open(self.session_filename, encoding='utf-8') as fp:
                dct = json.load(fp)
                for attr in self.SAVED_ATTRS:
                    setattr(self, attr, dct.get(attr))
            self.logger.debug(
                "Session loaded %s", os.path.realpath(self.session_filename))

    def save_session(self):
        with open(self.session_filename, 'w', encoding='utf-8') as fp:
            dct = {k: v for k, v in self.__dict__.items()
                   if k in self.SAVED_ATTRS and v is not None}
            json.dump(dct, fp, ensure_ascii=False, indent=4, sort_keys=True)
        self.logger.debug(
            "Session saved %s", os.path.realpath(self.session_filename))

    def delete_session(self):
        os.remove(self.session_filename)
        self.logger.debug(
            "Session deleted %s", os.path.realpath(self.session_filename))

    # Разное

    def from_dict(self, data):
        if 'access_token' not in data:
            raise TypeError("missing access_token")
        self.access_token = data['access_token']
        self.user_id = data.get('user_id')
        self.token_expiry = data.get('expires_in')
        if not isinstance(self.token_expiry, (type(None), int)):
            self.token_expiry = int(self.token_expiry)
        if self.token_expiry:
            self.token_expiry += time.time()
        if not isinstance(self.user_id, int):
            self.user_id = int(self.user_id)
        self.secret_token = data.get('secret')


class Captcha(QDialog):
    def __init__(self, client, captcha_img):
        self.client = client
        self.captcha_img = captcha_img
        super().__init__()
        self.ui = Ui_Captcha()
        self.ui.setupUi(self)
        self.ui.refresh_captcha_button.clicked.connect(self.load_captcha)

    def load_captcha(self):
        data = self.client.http.get(self.captcha_img).content
        pix = QPixmap.fromImage(QImage.fromData(data))
        self.ui.captcha_image.setPixmap(pix)
        self.ui.captcha_line.clear()
        self.ui.captcha_line.setFocus()


class Validation(Browser):
    def __init__(self, client, url):
        self.client = client
        super().__init__(url)

    def on_url_changed(self, url):
        self.logger.debug("URL changed: %s", str(url))
        if not url.hasFragment():
            return
        result = parse_hash(url.fragment())
        if 'error' in result:
            self.reject()
            raise ClientError(result['error_description'])
        self.client.from_dict(result)
        self.accept()
        self.logger.info('Validation successful')


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
