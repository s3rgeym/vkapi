from test_session import vk
from vkapi.browser import Browser

image_url = 'https://vintage.ponychan.net/chan/arch/src/130629801105.jpg'
image_data = vk.http.get(image_url).content
server_url = vk.api.photos.getWallUploadServer().upload_url
result = vk.upload(server_url, {'photo': ('photo.jpg', image_data)})
photos = vk.api.photos.saveWallPhoto(result)
attachment = "photo{photo.owner_id}_{photo.id}".format(photo=photos[0])
post = vk.api.wall.post(
    message="Test wall photo uload passed", attachment=attachment)
Browser("https://vk.com/wall{}_{}".format(vk.user_id, post.post_id)).exec_()
