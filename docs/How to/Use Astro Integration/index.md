# 🚀 Use Astro Integration

Camomilla ships with a first-class frontend integration for [Astro](https://astro.build/): **[@camomillacms/astro-integration](https://github.com/camomillacms/astro-camomilla-integration)**. It turns Camomilla into a fully headless CMS backend for an Astro site with zero boilerplate — auto-routing, SSR *or* prerendered static output, SEO meta, template registration, caching, and ready-made components all handled by the integration.

> [!IMPORTANT]
> **Version compatibility** — Camomilla **6.5** requires **`@camomillacms/astro-integration` ≥ 0.7**. The 6.5 release moves page-visibility gating server-side and adds the authenticated preview router and the public menus resolver; integration 0.7 is the first version that speaks this API. On camomilla 6.5, an older (0.6.x) integration would render non-public pages publicly. Conversely, integration 0.7 targets 6.5+ — see [Use Page Lifecycle](../Use%20Page%20Lifecycle/) for the details. Camomilla **6.6** adds the `pages-router/changes` and `pages-router/publish-due` endpoints; **integration 0.9** is the first version that speaks them (0.10.0 at the time of writing), so [static mode](#static-build) requires camomilla **6.6+** — an older backend 404s `changes` and rejects `publish-due` with `405`.

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

> [!NOTE]
> The integration supports two modes. **SSR** (`mode: "server"`, the default) — set `output: "server"` and use the `@astrojs/node` adapter, as above. **Static / incremental build** (`mode: "static"`, integration ≥ 0.9 with camomilla ≥ 6.6) — build-time prerendering, no adapter and no Node runtime; see [Static build](#static-build) below.

## Key Features

- **Auto Routing** — routes are created on the fly from the Camomilla page API.
- **SEO** — `<title>`, Open Graph, Twitter Card, schema.org JSON-LD are populated from the page response.
- **Templates** — map Camomilla `template` identifiers to `.astro` files via a single index module.
- **Error templates** — register a generic `error` template plus per-status templates (`404`, `500`, …).
- **Draft pages** — non-public pages return `404` by default; append `?preview=true` to preview.
- **Forwarded headers** — configurable request-header forwarding so Camomilla knows the real host/proto.
- **Cache** — optional response cache with `memory`, `redis`, `valkey`, or `memcache` backends and `varyOnHeaders` support.
- **Transitions** — works with Astro's view-transitions engine.
- **Static mode** — `mode: "static"` prerenders the auto-routing catch-all for CDN hosting, rebuilt page-by-page by the `incremental-build` CLI (see [Static build](#static-build)).
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

## Static build

With `mode: "static"` the auto-routing catch-all is prerendered, so the build output is plain HTML that any CDN or static web server can serve. There is no runtime, so the SSR middleware, the response cache and its `/api/cache-flush` endpoint, `/api/templates`, the djsuperadmin proxy routes and the `/static/` proxy are not registered — keep inline editing and previews on a separate `mode: "server"` instance pointed at the same Camomilla server.

Switch the mode **and drop `output: "server"` and the adapter** from the [Install](#install) config: left in place they make Astro emit its server layout (`dist/client/**` + `dist/server/**`), which the build CLI copies wholesale into the publish tree — every page ends up under `client/` and the deploy is broken with no error.

```javascript
camomilla({
  server: "http://localhost:8000",
  mode: "static",
})
```

Builds are driven by the `incremental-build` CLI shipped with the package:

```bash
CAMOMILLA_SERVER=http://localhost:8000 \
  node node_modules/@camomillacms/astro-integration/bin/incremental-build.mjs
```

Pass `--full` to force a rebuild of every page; everything else is configured by environment variables (`CAMOMILLA_DIST_DIR`, `CAMOMILLA_PUBLISH_DIR`, `CAMOMILLA_DEPLOY_TARGET`, `CAMOMILLA_BUILD_TOKEN`, …).

The CLI consumes two Camomilla endpoints:

| Endpoint | Auth | Role |
|---|---|---|
| `POST /api/camomilla/pages-router/publish-due` | Admin token, from `CAMOMILLA_BUILD_TOKEN` | Step 0 — materialises the scheduled publishes that are due, so the build renders them. Skipped when no token is set. See [Use Page Lifecycle](../Use%20Page%20Lifecycle/). |
| `GET /api/camomilla/pages-router/changes` | Public | The content-hash manifest (`urls`, `redirects`, `epoch`), diffed against the previous build state to select the pages to re-render. See [Use Pages](../Use%20Pages/). |

The rebuild authority is the per-URL content hash, never a page timestamp — an inline edit that bumps no page timestamp still changes the hash — while a changed frontend fingerprint (git HEAD plus the lockfile) or a changed `epoch` (menus, global content) forces a full rebuild instead.

## More

Full documentation, source code, and issue tracker: **[github.com/camomillacms/astro-camomilla-integration](https://github.com/camomillacms/astro-camomilla-integration)**.
