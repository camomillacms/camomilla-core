# 🍜 Use Menu 

Camomilla comes with a menu system that allows you to create and render menus in your templates.

To render a menu you need only to load menu tags and use the `render_menu` tag.

```html
{% load menus %}
...
<header>
    {% render_menu "main_menu" %}
</header>
...
```
The `render_menu` tag will create or fetch from the database a menu with the name specified in the first argument and render it using the default template.

If you want to use a custom template you can specify the path to the template in the second argument.

```html
{% load menus %}
...
<header>
    {% render_menu "main_menu" "website/parts/menu.html" %}
</header>
...
```

### The Default Template
If no template_path is specified, the default template will be used.

The default template is very simple and looks like this: 


```html
<!-- Take inspiration from this template to create your own! -->

{% load menus %}
{% if menu.nodes|length %}
<ul>
  {% for item in menu.nodes %}
  <li>
    {% if item.link.url %}
      <a href="{{ item|node_url:request }}">{{ item.title }}</a>
    {% else %}
      <span>{{item.title}}</span>
    {% endif %}
    {% include 'defaults/parts/menu.html' with menu=item %} 
  </li>
  {% endfor %}
</ul>
{% endif %}
```

### Menu node links

Each menu node carries a `link` of type [`camomilla.types.Permalink`](../Use%20StructuredJSONField/README.md#permalink-field-typed-links) — the same polymorphic link primitive you can use in any typed `template_data`. A node link is either:

- **relational** — a foreign key to a camomilla page (`UrlNode`). It survives renames and resolves to the active-language URL.
- **static** — a free-form URL string for external links, `mailto:`, `tel:`, anchors.

In templates, resolve a node to its URL with the `node_url` filter rather than reading `link.url` directly — it handles both link kinds and, when you pass the request, returns an **absolute** URL:

```html
{% load menus %}

{{ item|node_url }}          {# root-relative, e.g. /it/about/ #}
{{ item|node_url:request }}  {# absolute, e.g. https://host/it/about/ #}
```

`request` is available in the menu template via the standard request context processor (the menu renderer always binds it, falling back to `None`), so `{{ item|node_url:request }}` is always safe to write — static links ignore the request and pass through verbatim.




