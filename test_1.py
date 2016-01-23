import vkapi
import webbrowser

client = vkapi.DirectClient(2274003, 'hHbZxrka2uZ6jB1inYsH', 'nohttps')
username = input("Логин: ")
password = input("Пароль: ")
client.authorize(username, password)
image_url = 'https://vintage.ponychan.net/chan/arch/src/130629801105.jpg'
image_data = client.session.get(image_url).content
server_url = client.api.photos.getWallUploadServer().upload_url
result = client.upload(server_url, {'photo': ('photo.jpg', image_data)})
photos = client.api.photos.saveWallPhoto(result)
attachment = "photo{photo.owner_id}_{photo.id}".format(photo=photos[0])
post = client.api.wall.post(message="Всем добра!", attachment=attachment)
webbrowser.open("https://vk.com/wall{}_{}".format(client.user_id,
                                                  post.post_id))
input('Нажмите любую клавишу для выхода')

