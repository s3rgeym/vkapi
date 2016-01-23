import pickle
import os
import vkapi

SESSION_FILE = "D:\\.access_token"
while 1:
    if os.path.exists(SESSION_FILE):
        client = pickle.load(open(SESSION_FILE, 'rb'))
    else:
        client = vkapi.StandaloneClient(5234000, 'wall')
        username = input("Логин: ")
        password = input("Пароль: ")
        try:
            client.authorize(username, password)
        except vkapi.AuthError as e:
            print(e)
            continue
        with open(SESSION_FILE, 'wb') as fp:
            fp.write(pickle.dumps(client))
    break

while 1:
    ans = input("Что Вы сейчас делаете?\n>>> ")
    client.api.wall.post(message=ans)

    



