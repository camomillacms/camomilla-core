# 🖼️ Use Media 

Camomilla has full media management.
Everything is stored in the Media model. 

To attach medias to a custom model just assign a ForeignKey or a ManyToMany relation.

```python
class MyModel(models.Model):
    image = models.ForeignKey(
        "camomilla.Media",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    gallery = models.ManyToManyField("camomilla.Media", blank=True)
```

Every media can be associated to a MediaFolder.
The MediaFolder is a tree structure of folders (like a fs).

The media takes care of optimizing images. The optimization consists in a resize to a max width-height and to a DPI scaling. You can disable optimization or change sizes and dpi from settings:

```python
CAMOMILLA = {
    "MEDIA": {
        "OPTIMIZE": {"MAX_WIDTH": 1980, "MAX_HEIGHT": 1400, "DPI": 30, "ENABLE": True},
    },
}
```

Camomilla creates also image thumbnails. You can change, thumbnails size from settings:
```python
CAMOMILLA = {
    "MEDIA": {
        "THUMBNAIL": {"FOLDER": "", "WIDTH": 50, "HEIGHT": 50}
    },
}
```


## 🗂️ Media API

The media model has its own api methods to upload file.

::: warning Beware!
Remember to add camomilla api url to your `urlpatterns`. You can find more info [here](../Use%20API/).
:::

### Upload new media

__URL:__ `/api/camomilla/media` __METHOD:__ `POST` __MODE:__ `MultipartFormData`


__PAYLOAD:__
```
alt_text: Text
title: Text
description: Text
file: Multipart File
folder: Folder id
```

### Update existing media

__URL:__ `/api/camomilla/media/<media_id>` __METHOD:__ `PUT | PATCH` __MODE:__ `MultipartFormData`


__PAYLOAD:__
```
alt_text: Text
title: Text
description: Text
file: Multipart File
folder: Folder id
```
### Get media detail

__URL:__ `/api/camomilla/media/<media_id>` __METHOD:__ `GET` 

__Response:__
```json
{
    "id": 6,
    "links": [],
    "is_image": true,
    "alt_text": null,
    "title": null,
    "description": null,
    "file": "http://mydomain.it/media/sample-image.jpg",
    "thumbnail": "http://mydomain.it/media/thumbnails/sample-image_thumb.jpg",
    "created": "2023-07-24T13:47:26.986873Z",
    "size": 680313,
    "mime_type": "image/jpeg",
    "image_props": {
        "mode": "RGB",
        "width": 1980,
        "format": "JPEG",
        "height": 1319
    },
    "folder": null
}
```

### Navigate media folders

To navigate media you need to navigate folder structure.
In the main url you will get all media and all folders without a parent folder (root elements).

__URL:__ `/api/camomilla/media-folder` __METHOD:__ `GET`

__Response:__
```json
{
    "folders": [
        {
            "id": 1,
            "title": "Folder 1",
            "slug": "folder-1",
            "creation_date": "2023-07-31T15:17:37.612115Z",
            "last_modified": "2023-07-31T15:17:37.612173Z",
            "path": "/folder-1",
            "updir": null
        }
    ],
    "media": {
        "items": [
            {
                "id": 6,
                "is_image": true,
                "alt_text": null,
                "title": null,
                "description": null,
                "file": "http://mydomain.com/media/sample-image.jpg",
                "thumbnail": "http://mydomain.com/media/thumbnails/sample-image_thumb.jpg",
                "created": "2023-07-24T13:47:26.986873Z",
                "size": 680313,
                "mime_type": "image/jpeg",
                "image_props": {
                    "mode": "RGB",
                    "width": 1980,
                    "format": "JPEG",
                    "height": 1319
                },
                "folder": null,
            }
        ],
        "paginator": {
            "count": 1,
            "page": 1,
            "has_next": false,
            "has_previous": false,
            "pages": 1,
            "page_size": 18
        }
    },
    "parent_folder": {
        "title": "",
        "path": "",
        "updir": null
    }
}
```

To navigate a subfolder just add its id to the url path:

__URL:__ `/api/camomilla/media-folder/<folder_id>` __METHOD:__ `GET`

The media endpoint response is always paginated. The pagination is made only for media elements. For subfolder you will get always all subfolder in a folder.







