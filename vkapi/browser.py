from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout
from PyQt5.QtWebKitWidgets import QWebView
import logging


class Browser(QDialog):
    def __init__(self, url):
        super().__init__(None, Qt.Window)
        self.logger = logging.getLogger('.'.join([
            self.__class__.__module__, self.__class__.__name__]))
        self.url = url
        self.webview = QWebView()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.webview)
        self.setLayout(layout)
        self.webview.titleChanged.connect(self.on_title_changed)
        self.webview.urlChanged.connect(self.on_url_changed)
        self.webview.setUrl(QUrl(self.url))

    def on_title_changed(self, title):
        self.logger.debug("Title changed: %s", title)
        self.setWindowTitle(title)

    def on_url_changed(self, url):
        self.logger.debug("URL changed: %s", url.toString())
