from vkapi import AuthDirect, Client
import logging

logging.basicConfig(level=logging.DEBUG)

vk = Client(session_filename="D:\\.vksession")
if not vk.access_token:
    if not AuthDirect(vk).exec_():
        exit(-1)
    vk.save_session()

user = vk.api.users.get()[0]
print("Hello, {u.first_name} {u.last_name}!".format(u=user))
