from vkapi import ApiError, AuthDirect, Client, ClientError
import logging

logging.basicConfig(level=logging.DEBUG)
c = Client()
AuthDirect(c, scope='nohttps', test_redirect_uri=1).exec_() or exit(1)
c.api.wall.post(message="Test direct authentication passed")
