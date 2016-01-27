from vkapi import ApiError, AuthStandalone, Client, ClientError
import logging

logging.basicConfig(level=logging.DEBUG)
c = Client()
AuthStandalone(c, scope='wall,nohttps').exec_() or exit(1)
c.api.wall.post(message="Test standalone authentication passed")
