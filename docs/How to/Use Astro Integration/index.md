# 🚀 Use Astro Integration

Camomilla ships with a first-class frontend integration for [Astro](https://astro.build/): **[@camomillacms/astro-integration](https://github.com/camomillacms/astro-camomilla-integration)**. It turns Camomilla into a fully headless CMS backend for an Astro site with zero boilerplate — auto-routing, SSR, SEO meta, template registration, caching, and ready-made components all handled by the integration.

## Install

```bash
npm add @camomillacms/astro-integration
```

Register the integration in your `astro.config.mjs`:

```javascript
import camomilla from "@camomillacms/astro-integration";
import node from "@astrojs/node";

export default {
  integrations: [
    camomilla({
      server: "http://localhost:8000",          // your Camomilla server URL
      autoRouting: true,                        // auto-create routes from the Camomilla API
      templatesIndex: "./src/templates/index.js",
      stylesIndex: "/src/styles/main.scss",
      forwardedHeaders: ["X-Forwarded-Host", "X-Forwarded-Proto"],
      enableTransitions: false,
    }),
  ],
  output: "server",
  adapter: node({ mode: "standalone" }),
};
```

> [!WARNING]
> The integration runs in **SSR mode only** — set `output: "server"` and use the `@astrojs/node` adapter.

## Key Features

- **Auto Routing** — routes are created on the fly from the Camomilla page API.
- **SEO** — `<title>`, Open Graph, Twitter Card, schema.org JSON-LD are populated from the page response.
- **Templates** — map Camomilla `template` identifiers to `.astro` files via a single index module.
- **Error templates** — register a generic `error` template plus per-status templates (`404`, `500`, …).
- **Draft pages** — non-public pages return `404` by default; append `?preview=true` to preview.
- **Forwarded headers** — configurable request-header forwarding so Camomilla knows the real host/proto.
- **Cache** — optional response cache with `memory`, `redis`, `valkey`, or `memcache` backends and `varyOnHeaders` support.
- **Transitions** — works with Astro's view-transitions engine.
- **Components** — ready-made Astro components that consume Camomilla API shapes (see below).

## Components

### `<CamomillaPicture>`

Render a responsive `<picture>` from a Camomilla `Media` object. Uses the `renditions` / `srcset` fields produced by Camomilla's [responsive rendition system](../Use%20Media/#-responsive-renditions-srcset) (AVIF + WebP + original at `sm`/`md`/`lg` widths by default) and degrades gracefully to a plain `<img>` when no renditions exist.

```astro
---
import CamomillaPicture from '@camomillacms/astro-integration/components/CamomillaPicture.astro'
import type { CamomillaMedia } from '@camomillacms/astro-integration/types/camomillaMedia'

const media = Astro.locals.camomilla?.page?.template_data?.hero as CamomillaMedia
---

<CamomillaPicture
  media={media}
  sizes="(min-width: 1024px) 1600px, 100vw"
  loading="eager"
  fetchpriority="high"
  class="hero-img"
/>
```

**Output:**

```html
<picture>
  <source type="image/avif" srcset="…sm-avif.avif 400w, …md-avif.avif 800w, …lg-avif.avif 1600w" sizes="…">
  <source type="image/webp" srcset="…sm-webp.webp 400w, …md-webp.webp 800w, …lg-webp.webp 1600w" sizes="…">
  <img src="…lg-original.jpg" srcset="…" sizes="…" alt="…" loading="lazy" decoding="async" width="1980" height="1319">
</picture>
```

The browser picks the first `<source>` it understands; the inner `<img>` is the universal fallback. `width` / `height` are pre-filled from `media.image_props` to prevent layout shift.

**Props:**

| Prop | Default | Description |
|---|---|---|
| `media` | — | Required. The `Media` object from Camomilla's REST API. |
| `sizes` | — | Standard HTML `sizes` attribute, applied to every `<source>` and the `<img>`. |
| `alt` | `media.alt_text` | Image alt text. Falls back to the Media's alt_text. |
| `loading` | `'lazy'` | Use `'eager'` for above-the-fold images. |
| `decoding` | `'async'` | Native decoding hint. |
| `fetchpriority` | — | `'high'` / `'low'` / `'auto'`. |
| `formats` | `['avif', 'webp']` | `<source>` preference order. |
| `fallbackFormat` | `'original'` | Which rendition set feeds the fallback `<img>`. |
| `class` | — | Class applied to the `<img>`. Use this for Tailwind/CSS. |
| `pictureClass` | — | Class applied to the `<picture>`. |

All other props are forwarded to the `<img>` as HTML attributes.

### `<SeoHead>` and `<MainLayout>`

The integration also exposes a `SeoHead` component (auto-wired inside `MainLayout`) that populates the document head from Camomilla's page SEO fields, and a `MainLayout` that injects global styles and optional view-transitions. Both are consumed automatically by the template router — you rarely need to import them directly.

## Templates

Register your Astro templates in a single index module (`./src/templates/index.js`):

```javascript
import MyTemplate from './mytemplate.astro'
import ErrorTemplate from './error.astro'
import NotFoundTemplate from './404.astro'

export default {
  'my-template': MyTemplate,
  error: ErrorTemplate,
  '404': NotFoundTemplate,
}
```

The Camomilla-side `template` identifier on each page selects the component. Error statuses (`404`, `500`, …) match first, falling back to the generic `error` template.

## Accessing page data

Camomilla data is injected into `Astro.locals.camomilla` by the integration middleware:

```astro
---
const page = Astro.locals.camomilla?.page              // the current CamomillaPage
const user = Astro.locals.camomilla?.user              // current user (if authenticated)
const status = Astro.locals.camomilla?.response?.status
const error = Astro.locals.camomilla?.error
---
```

## Cache

Enable caching of the entire Astro response to keep pages fast under load:

```javascript
camomilla({
  cache: {
    backend: 'redis',                                  // 'memory' | 'redis' | 'valkey' | 'memcache'
    location: 'redis://user:pass@localhost:6379',
    ttl: 60 * 60 * 1000,                               // ms, or "1h" / "30m" / "45s"
    keyPrefix: 'astro-camomilla-integration',
    varyOnHeaders: ['Cookie', 'User-Agent'],           // cache separately per header value
  },
})
```

`varyOnHeaders` is the recommended knob for splitting the cache between authenticated and anonymous users (or per-locale via `Accept-Language`).

## More

Full documentation, source code, and issue tracker: **[github.com/camomillacms/astro-camomilla-integration](https://github.com/camomillacms/astro-camomilla-integration)**.
