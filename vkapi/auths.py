from . import defaults
from .browser import Browser
from .ui_auth import Ui_Auth
from .utils import parse_hash
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QDialog, QMessageBox
import logging
import urllib.parse


class AuthDirect(QDialog):
    def __init__(self,
                 client,
                 client_id=2274003,
                 client_secret='hHbZxrka2uZ6jB1inYsH',
                 username='',
                 password='',
                 scope='',
                 test_redirect_uri=0):
        super().__init__()
        self.logger = logging.getLogger('.'.join([
            self.__class__.__module__, self.__class__.__name__]))
        self.client = client
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.scope = scope
        self.test_redirect_uri = test_redirect_uri
        self.captcha_img = None
        self.captcha_sid = None
        self.ui = Ui_Auth()
        self.ui.setupUi(self)
        self.hide_error()
        self.hide_captcha()
        # Значение полей по-умолчанию
        self.ui.username_line.setText(self.username)
        self.ui.password_line.setText(self.password)
        self.connect_slots()

    def connect_slots(self):
        # Убираем пробелы у значений полей
        """self.ui.username_line.editingFinished.connect(
            lambda: self.ui.username_line.setText(
                self.ui.username_line.text().strip()))
        self.ui.password_line.editingFinished.connect(
            lambda: self.ui.password_line.setText(
                self.ui.password_line.text().strip()))
        self.ui.captcha_line.editingFinished.connect(
            lambda: self.ui.captcha_line.setText(
                self.ui.captcha_line.text().strip()))"""
        self.ui.refresh_captcha_button.clicked.connect(self.load_captcha)
        self.ui.login_button.clicked.connect(self.login)

    def login(self):
        # Запоминает username & password на случай если они понадобятся
        self.username = self.ui.username_line.text()
        self.password = self.ui.password_line.text()
        if not self.username:
            self.ui.username_line.setFocus()
            self.show_error('Username required')
            return
        if not self.password:
            self.ui.password_line.setFocus()
            self.show_error('Password required')
            return
        params = self.get_params()
        response = self.client.get(defaults.AUTH_BASE + '/token', params)
        self.logger.warning("Response: %s", response)
        if 'captcha_sid' in response:
            self.captcha_img = response.captcha_img
            self.captcha_sid = response.captcha_sid
            self.show_error('Captcha required')
            self.show_captcha()
            return
        if 'redirect_uri' in response:
            if Validation(response.redirect_uri).exec_():
                # {REDIRECT_URI}?success=1
                # Еще раз пробуем войти
                self.login()
                return
            self.show_error("Validation failed")
            return
        if 'error' in response:
            self.ui.password_line.clear()
            self.ui.username_line.setFocus()
            self.ui.username_line.selectAll()
            self.show_error(response.error_description)
            self.hide_captcha()
            return
        self.client.from_dict(response)
        self.accept()
        self.logger.info('Authentication successful')

    def get_params(self):
        params = {
            'v': self.client.api_version,
            'grant_type': 'password',
            'username': self.username,
            'password': self.password,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        if self.scope:
            params['scope'] = self.scope
        if self.test_redirect_uri:
            params['test_redirect_uri'] = self.test_redirect_uri
        if self.ui.captcha_frame.isVisible():
            params['captcha_sid'] = self.captcha_sid
            params['captcha_key'] = self.ui.captcha_line.text()
        return params

    def hide_error(self):
        self.ui.error_label.hide()

    def show_error(self, message):
        self.ui.error_label.setText(self.tr(message))
        self.ui.error_label.show()

    def hide_captcha(self):
        self.ui.captcha_frame.hide()

    def show_captcha(self):
        self.load_captcha()
        self.ui.captcha_frame.show()

    def load_captcha(self):
        data = self.client.http.get(self.captcha_img).content
        pix = QPixmap.fromImage(QImage.fromData(data))
        self.ui.captcha_image.setPixmap(pix)
        self.ui.captcha_line.clear()
        self.ui.captcha_line.setFocus()


class Validation(Browser):
    def on_url_changed(self, url):
        self.logger.debug("URL changed: %s", str(url))
        if url.hasQuery():
            if 'fail=1' in url.query():
                self.reject()
                return
            if 'success=1' in url.query():
                self.accept()


class AuthStandalone(Browser):
    def __init__(self,
                 client,
                 client_id=5234000,
                 scope='',
                 display='page',
                 redirect_uri=defaults.REDIRECT_URI):
        self.client = client
        self.client_id = client_id
        self.scope = scope
        self.display = display
        self.redirect_uri = redirect_uri
        url = "{}?{}".format(
            defaults.AUTH_BASE + '/authorize', urllib.parse.urlencode(
                self.get_params()))
        super().__init__(url)

    def get_params(self):
        params = {
            'v': self.client.api_version,
            'response_type': 'token',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
        }
        if self.scope:
            params['scope'] = self.scope
        if self.display:
            params['display'] = self.display
        return params

    def on_url_changed(self, url):
        self.logger.debug("URL changed: %s", str(url))
        if not url.hasFragment():
            return
        result = parse_hash(url.fragment())
        if 'error' in result:
            self.reject()
            QMessageBox.warning(
                None,
                self.tr("Authentication Error"),
                self.tr(result['error_description'])
            )
            return
        self.client.from_dict(result)
        self.accept()
        self.logger.info('Authentication successful')
