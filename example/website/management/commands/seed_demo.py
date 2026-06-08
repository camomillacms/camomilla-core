"""Seed a rich demo dataset for manual / visual testing of the CMS.

Run via:

    uv run python manage.py seed_demo            # idempotent, adds-or-updates
    uv run python manage.py seed_demo --reset    # wipe demo rows first

Covers every preview-relevant lifecycle state plus enough surrounding
content (articles, tags, menus, redirects, media folders, translations)
that the admin and the public API have something to render. Designed to
be re-runnable without leaving duplicates behind — each row is keyed by
a stable identifier (permalink for pages, slug for tags, etc.).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from rest_framework.authtoken.models import Token

from camomilla.models import (
    Article,
    MediaFolder,
    Menu,
    Page,
    Tag,
    UrlNode,
    UrlRedirect,
)
from camomilla.models.draft import Draft
from camomilla.types import LinkTypes, Permalink
from camomilla.utils import get_nofallbacks, set_nofallbacks
from example.website.models import HomePage


User = get_user_model()
LANGS = ("en", "it")


# ---------------------------------------------------------------------------
# Demo content tables — each entry is a tuple of (key, payload). The command
# diffs by ``key`` so a re-run updates in place instead of duplicating.
# ---------------------------------------------------------------------------

# Page fixture rows. Each dict drives one Page row: lifecycle stamp,
# permalink, both translations of every text field, the template to
# render, and a ``template_data`` payload per language (the field is
# translatable in ``AbstractPageTranslationOptions``). Templates
# referenced here live under ``example/website/templates/website/pages/``.
#
# ``lifecycle`` ∈ {"public", "scheduled", "draft", "trashed"}.
# ``with_draft=True`` stages a pending Draft on the EN row so the preview
# router has something obvious to overlay.
PAGE_FIXTURES = [
    {
        "permalink": "/",
        # Concrete model class. Defaults to ``Page`` when omitted. Set this on a
        # row that uses a typed ``template_data`` schema — see ``HomePage`` for
        # the supported pattern (typed pydantic model + ``camomilla.types.Permalink``
        # for URL-bearing fields).
        "model": HomePage,
        # Row-level marker resolved by ``_wire_homepage_cta`` after every page
        # exists: rewrites the hero CTA into a ``Permalink(link_type=relational,
        # url_node=…)`` pointing at the ``/about`` page's ``UrlNode``. Kept
        # outside ``template_data`` so pydantic validation never sees this
        # seed-only hint.
        "cta_target": "/about",
        "title_en": "Welcome to Camomilla",
        "title_it": "Benvenuti in Camomilla",
        "lifecycle": "public",
        "with_draft": True,
        "parent": None,
        "template": "website/pages/home.html",
        "description_en": "A flexible, headless-friendly Django CMS.",
        "description_it": "Un CMS Django flessibile e headless-friendly.",
        "template_data_en": {
            "hero": {
                "headline": "Build content-rich Django sites",
                "subheadline": "Pages, articles, menus, drafts and previews — all in one place.",
                "cta_label": "Explore the docs",
            },
            "features": [
                {"icon": "📄", "title": "Page builder", "description": "Compose pages from typed JSON blocks the editor can shape."},
                {"icon": "🌍", "title": "Multilingual", "description": "Translate every field per language with modeltranslation."},
                {"icon": "✏️", "title": "Drafts & previews", "description": "Edit and preview without touching the live site."},
                {"icon": "🔁", "title": "Scheduled publishes", "description": "Plan content swaps for a future moment."},
            ],
            "testimonial": {
                "quote": "Camomilla turned our content workflow around in two weeks.",
                "author": "Jane Smith",
                "role": "Head of Editorial, Acme Co.",
            },
        },
        "template_data_it": {
            "hero": {
                "headline": "Costruisci siti Django ricchi di contenuti",
                "subheadline": "Pagine, articoli, menu, bozze e anteprime — tutto in un posto solo.",
                "cta_label": "Esplora la documentazione",
            },
            "features": [
                {"icon": "📄", "title": "Page builder", "description": "Componi pagine con blocchi JSON tipizzati e modellabili in admin."},
                {"icon": "🌍", "title": "Multilingua", "description": "Traduci ogni campo per lingua con modeltranslation."},
                {"icon": "✏️", "title": "Bozze & anteprime", "description": "Modifica e visualizza l'anteprima senza toccare la versione live."},
                {"icon": "🔁", "title": "Pubblicazioni programmate", "description": "Pianifica il cambio di contenuto per un momento futuro."},
            ],
            "testimonial": {
                "quote": "Camomilla ha rivoluzionato il nostro workflow editoriale in due settimane.",
                "author": "Jane Smith",
                "role": "Head of Editorial, Acme Co.",
            },
        },
    },
    {
        "permalink": "/about",
        "title_en": "About us",
        "title_it": "Chi siamo",
        "lifecycle": "public",
        "with_draft": False,
        "parent": None,
        "template": "website/pages/default.html",
        "description_en": "Who we are and what we build.",
        "description_it": "Chi siamo e cosa costruiamo.",
        "template_data_en": {
            "body": (
                "<p>Camomilla powers content-driven Django projects with a REST-first API, "
                "per-language translations, a rich admin and a first-class draft / preview "
                "workflow.</p>"
                "<p>This demo is a living example of every moving part: pages with structured "
                "<code>template_data</code>, menus rendered from the admin, articles tagged "
                "and listed, and previews that overlay pending edits.</p>"
            ),
            "values": [
                {"title": "Pragmatic", "description": "We pick the boring tool when it gets the job done."},
                {"title": "Open", "description": "MIT-licensed and built in public on GitHub."},
                {"title": "Editor-first", "description": "Every decision is measured against editor ergonomics."},
            ],
            "team": [
                {"name": "Ada Lovelace", "role": "Engineering", "bio": "Picks pragmatic primitives."},
                {"name": "Grace Hopper", "role": "Editorial", "bio": "Shepherds the writers."},
                {"name": "Linus Torvalds", "role": "Infrastructure", "bio": "Keeps the lights on."},
            ],
        },
        "template_data_it": {
            "body": (
                "<p>Camomilla alimenta progetti Django incentrati sul contenuto con un'API "
                "REST-first, traduzioni per lingua, un admin ricco e un workflow di bozze e "
                "anteprime di prima classe.</p>"
                "<p>Questa demo è un esempio vivo di ogni componente: pagine con "
                "<code>template_data</code> strutturato, menu gestiti dall'admin, articoli "
                "taggati e in elenco, anteprime che sovrappongono le modifiche pendenti.</p>"
            ),
            "values": [
                {"title": "Pragmatici", "description": "Scegliamo lo strumento noioso quando fa il suo lavoro."},
                {"title": "Aperti", "description": "Licenza MIT, sviluppato pubblicamente su GitHub."},
                {"title": "Editor-first", "description": "Ogni scelta si misura sull'ergonomia dell'editor."},
            ],
            "team": [
                {"name": "Ada Lovelace", "role": "Engineering", "bio": "Sceglie primitive pragmatiche."},
                {"name": "Grace Hopper", "role": "Editoria", "bio": "Coordina gli autori."},
                {"name": "Linus Torvalds", "role": "Infrastruttura", "bio": "Tiene accese le luci."},
            ],
        },
    },
    {
        "permalink": "/services",
        "title_en": "Services",
        "title_it": "Servizi",
        "lifecycle": "public",
        "with_draft": False,
        "parent": None,
        "template": "website/pages/services.html",
        "description_en": "Pick the service that fits your team.",
        "description_it": "Scegli il servizio adatto al tuo team.",
        "template_data_en": {
            "intro": "We work alongside Django teams adopting Camomilla, from small editorial sites to multilingual portals.",
        },
        "template_data_it": {
            "intro": "Lavoriamo con team Django che adottano Camomilla, da piccoli siti editoriali a portali multilingua.",
        },
    },
    {
        "permalink": "/services/consulting",
        "title_en": "Consulting",
        "title_it": "Consulenza",
        "lifecycle": "public",
        "with_draft": False,
        "parent": "/services",
        "template": "website/pages/default.html",
        "description_en": "Hands-on help, from architecture to migration.",
        "description_it": "Supporto pratico, dall'architettura alla migrazione.",
        "template_data_en": {
            "body": "<p>Pair with our team on the hard parts — content modeling, performance, migrations.</p>",
            "features": [
                {"icon": "🏗️", "title": "Architecture review", "description": "We audit your content model and recommend a path forward."},
                {"icon": "🚚", "title": "Migration", "description": "Move from legacy CMS or hand-rolled Django models without losing history."},
                {"icon": "🛠️", "title": "Custom builds", "description": "Bespoke serializers, viewsets, admin tweaks — by the day."},
            ],
        },
        "template_data_it": {
            "body": "<p>Lavora fianco a fianco con il nostro team sui punti più tecnici — modellazione, performance, migrazioni.</p>",
            "features": [
                {"icon": "🏗️", "title": "Audit architetturale", "description": "Analizziamo il tuo content model e indichiamo la rotta."},
                {"icon": "🚚", "title": "Migrazione", "description": "Sposta da CMS legacy o modelli Django artigianali senza perdere lo storico."},
                {"icon": "🛠️", "title": "Sviluppi custom", "description": "Serializer, viewset, admin tweaks su misura — a giornata."},
            ],
        },
    },
    {
        "permalink": "/services/training",
        "title_en": "Training",
        "title_it": "Formazione",
        "lifecycle": "public",
        "with_draft": True,
        "parent": "/services",
        "template": "website/pages/default.html",
        "description_en": "Workshops for Django teams adopting Camomilla.",
        "description_it": "Workshop per team Django che adottano Camomilla.",
        "template_data_en": {
            "body": "<p>From half-day intros to multi-day deep dives, tailored to your stack.</p>",
            "features": [
                {"icon": "🎓", "title": "Intro workshop", "description": "Half day. Pages, articles, menus and translations — end-to-end."},
                {"icon": "🔬", "title": "Deep dive", "description": "Two days. Serializers, viewsets, custom mixins, performance."},
                {"icon": "🎯", "title": "Editor onboarding", "description": "Train your content team to use the admin like pros."},
            ],
        },
        "template_data_it": {
            "body": "<p>Da intro di mezza giornata a deep dive di più giorni, calibrati sul tuo stack.</p>",
            "features": [
                {"icon": "🎓", "title": "Workshop intro", "description": "Mezza giornata. Pagine, articoli, menu e traduzioni — end-to-end."},
                {"icon": "🔬", "title": "Deep dive", "description": "Due giorni. Serializer, viewset, mixin custom, performance."},
                {"icon": "🎯", "title": "Onboarding editor", "description": "Forma il team editoriale a usare l'admin da professionisti."},
            ],
        },
    },
    {
        "permalink": "/contact",
        "title_en": "Contact",
        "title_it": "Contatti",
        "lifecycle": "public",
        "with_draft": False,
        "parent": None,
        "template": "website/pages/default.html",
        "description_en": "Reach out — we read everything.",
        "description_it": "Contattaci — leggiamo tutto.",
        "template_data_en": {
            "body": "<p>Pick the channel that works for you. We answer in business hours, Mon–Fri.</p>",
            "methods": [
                {"label": "Email", "value": "hello@example.com", "href": "mailto:hello@example.com"},
                {"label": "GitHub", "value": "camomillacms/camomilla-core", "href": "https://github.com/camomillacms/camomilla-core"},
                {"label": "Office", "value": "Via Esempio 1, Milano, Italia", "href": ""},
            ],
        },
        "template_data_it": {
            "body": "<p>Scegli il canale che preferisci. Rispondiamo in orario d'ufficio, lun–ven.</p>",
            "methods": [
                {"label": "Email", "value": "hello@example.com", "href": "mailto:hello@example.com"},
                {"label": "GitHub", "value": "camomillacms/camomilla-core", "href": "https://github.com/camomillacms/camomilla-core"},
                {"label": "Sede", "value": "Via Esempio 1, Milano, Italia", "href": ""},
            ],
        },
    },
    {
        "permalink": "/blog",
        "title_en": "Blog",
        "title_it": "Blog",
        "lifecycle": "public",
        "with_draft": False,
        "parent": None,
        "template": "website/pages/blog_list.html",
        "description_en": "Articles, notes and updates from the team.",
        "description_it": "Articoli, note e aggiornamenti dal team.",
        "template_data_en": {"intro": "Recent posts, latest first."},
        "template_data_it": {"intro": "Post recenti, dal più nuovo."},
    },
    {
        "permalink": "/news/draft-article",
        "title_en": "Draft article (preview only)",
        "title_it": "Articolo bozza (anteprima)",
        "lifecycle": "draft",
        "with_draft": False,
        "parent": None,
        "template": "website/pages/default.html",
        "description_en": "This page is unpublished — only the preview router serves it.",
        "description_it": "Questa pagina non è pubblicata — solo il preview router la mostra.",
        "template_data_en": {
            "body": "<p>This row has <code>published_at IS NULL</code>; the public router 404s it.</p>",
        },
        "template_data_it": {
            "body": "<p>Questa riga ha <code>published_at IS NULL</code>; il router pubblico la 404a.</p>",
        },
    },
    {
        "permalink": "/news/scheduled-launch",
        "title_en": "Scheduled launch",
        "title_it": "Lancio programmato",
        "lifecycle": "scheduled",
        "with_draft": False,
        "parent": None,
        "template": "website/pages/default.html",
        "description_en": "Goes live in the future. Preview-only until then.",
        "description_it": "Pubblicazione futura. Solo anteprima fino ad allora.",
        "template_data_en": {
            "body": "<p>This row has <code>published_at &gt; now()</code>; the public router 404s it until the timestamp passes.</p>",
        },
        "template_data_it": {
            "body": "<p>Questa riga ha <code>published_at &gt; now()</code>; il router pubblico la 404a finché il timestamp non scade.</p>",
        },
    },
    {
        "permalink": "/archive/old-page",
        "title_en": "Archived page",
        "title_it": "Pagina archiviata",
        "lifecycle": "trashed",
        "with_draft": False,
        "parent": None,
        "template": "website/pages/default.html",
        "description_en": "Soft-deleted — preview-only.",
        "description_it": "Cestinata — solo anteprima.",
        "template_data_en": {
            "body": "<p>This row has <code>deleted_at IS NOT NULL</code>; the public router 404s it everywhere.</p>",
        },
        "template_data_it": {
            "body": "<p>Questa riga ha <code>deleted_at IS NOT NULL</code>; il router pubblico la 404a ovunque.</p>",
        },
    },
]

# (key, name_en, name_it) — ``key`` is the EN name used for lookup;
# ``Tag`` doesn't have a slug field so we identify by the EN name.
TAG_FIXTURES = [
    ("technology", "Technology", "Tecnologia"),
    ("design",     "Design",     "Design"),
    ("business",   "Business",   "Business"),
]

# (permalink, title_en, title_it, content_en, content_it, tag_slugs)
ARTICLE_FIXTURES = [
    (
        "/blog/hello-world",
        "Hello, world",
        "Ciao, mondo",
        "Our first post. Camomilla is up and running.",
        "Il nostro primo post. Camomilla è online.",
        ["technology"],
    ),
    (
        "/blog/on-design",
        "On Design",
        "Sul design",
        "A few thoughts about content modeling.",
        "Qualche riflessione sul modeling dei contenuti.",
        ["design", "business"],
    ),
]

# (title, parent_title_or_None)
MEDIA_FOLDER_FIXTURES = [
    ("Demo images",   None),
    ("Hero banners",  "Demo images"),
    ("Documents",     None),
]

# (from_url, to_url, permanent)
REDIRECT_FIXTURES = [
    ("/old-about", "/about", True),
]


class Command(BaseCommand):
    help = "Seed a rich demo dataset for manual / visual CMS testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete demo rows before seeding (keyed by permalink / slug).",
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()

        admin, token = self._seed_admin()
        pages = self._seed_pages()
        self._wire_homepage_cta(pages=pages)
        tags = self._seed_tags()
        self._seed_articles(tags=tags, author=admin)
        self._seed_media_folders()
        self._seed_menus(pages=pages)
        self._seed_redirects()

        self._print_summary(admin=admin, token=token)

    # ------------------------------------------------------------------
    # Reset — narrow, predictable wipe
    # ------------------------------------------------------------------

    def _reset(self):
        page_permalinks = [row["permalink"] for row in PAGE_FIXTURES]
        article_permalinks = [row[0] for row in ARTICLE_FIXTURES]
        # Delete pages and articles directly. The ``auto_delete_url_node``
        # post-delete signal (camomilla/models/page.py) cleans up the related
        # UrlNode for us. Deleting UrlNodes here would cascade-delete the
        # page (FK ``on_delete=CASCADE``) and the signal would then try to
        # look up an already-gone UrlNode and raise ``DoesNotExist``.
        Page.objects.filter(url_node__permalink_en__in=page_permalinks).delete()
        HomePage.objects.filter(url_node__permalink_en__in=page_permalinks).delete()
        Article.objects.filter(url_node__permalink_en__in=article_permalinks).delete()
        # Sweep any orphan UrlNodes from half-failed previous runs (no page /
        # article points at them anymore).
        UrlNode.objects.filter(
            permalink_en__in=page_permalinks + article_permalinks
        ).delete()
        Tag.objects.filter(name_en__in=[row[1] for row in TAG_FIXTURES]).delete()
        Menu.objects.filter(key__in=["main", "footer"]).delete()
        MediaFolder.objects.filter(title__in=[row[0] for row in MEDIA_FOLDER_FIXTURES]).delete()
        UrlRedirect.objects.filter(
            from_url__in=[row[0].rstrip("/") for row in REDIRECT_FIXTURES]
        ).delete()
        self.stdout.write(self.style.WARNING("Demo rows cleared."))

    # ------------------------------------------------------------------
    # Admin user
    # ------------------------------------------------------------------

    def _seed_admin(self):
        admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@example.com"},
        )
        admin.is_staff = True
        admin.is_superuser = True
        admin.is_active = True
        admin.set_password("admin")
        admin.save()
        token, _ = Token.objects.get_or_create(user=admin)
        return admin, token

    # ------------------------------------------------------------------
    # Pages — preview / public / trash matrix + a small tree
    # ------------------------------------------------------------------

    def _seed_pages(self):
        now = timezone.now()
        past = now - timedelta(days=1)
        future = now + timedelta(days=2)
        pages_by_permalink = {}

        # Two-pass: parents first so children can attach. The fixture list is
        # already ordered that way, but we resolve explicitly to stay robust
        # against reordering.
        deferred = []
        for row in PAGE_FIXTURES:
            if row["parent"] is None:
                pages_by_permalink[row["permalink"]] = self._make_or_update_page(
                    row, now=now, past=past, future=future, parent=None
                )
                if row["with_draft"]:
                    self._stage_draft(pages_by_permalink[row["permalink"]], row["title_en"])
            else:
                deferred.append(row)

        for row in deferred:
            pages_by_permalink[row["permalink"]] = self._make_or_update_page(
                row,
                now=now,
                past=past,
                future=future,
                parent=pages_by_permalink.get(row["parent"]),
            )
            if row["with_draft"]:
                self._stage_draft(pages_by_permalink[row["permalink"]], row["title_en"])

        return pages_by_permalink

    def _make_or_update_page(self, row, *, now, past, future, parent):
        permalink = row["permalink"]
        model = row.get("model") or Page
        node = UrlNode.objects.filter(permalink_en=permalink).first()
        page = node.page if node else None
        if page is None or not isinstance(page, model):
            page = model()

        page.parent_page = parent
        page.template = row.get("template") or ""
        page.deleted_at = now if row["lifecycle"] == "trashed" else None
        # All translatable fields go through ``set_nofallbacks`` so we
        # don't trip Pyright on modeltranslation's dynamic ``<field>_<lang>``
        # attrs (they exist at runtime but aren't visible to the type checker).
        shared_template_data = row.get("template_data") or {}
        for lang in LANGS:
            set_nofallbacks(page, "autopermalink", False, language=lang)
            set_nofallbacks(page, "permalink", permalink, language=lang)
            set_nofallbacks(page, "title", row[f"title_{lang}"], language=lang)
            if row.get(f"description_{lang}"):
                set_nofallbacks(page, "description", row[f"description_{lang}"], language=lang)
            # ``template_data`` is translatable (per the AbstractPageTranslationOptions
            # listing). Prefer a per-language payload (``template_data_en`` /
            # ``template_data_it``) so editorial text differs per locale; fall
            # back to a single ``template_data`` if the row didn't bother.
            data = row.get(f"template_data_{lang}", shared_template_data)
            set_nofallbacks(page, "template_data", data, language=lang)
            if row["lifecycle"] in ("public", "trashed"):
                set_nofallbacks(page, "published_at", past, language=lang)
            elif row["lifecycle"] == "scheduled":
                set_nofallbacks(page, "published_at", future, language=lang)
            else:  # "draft"
                set_nofallbacks(page, "published_at", None, language=lang)

        page.save()
        return page

    def _wire_homepage_cta(self, *, pages):
        """Resolve ``cta_target`` markers into a typed ``Permalink`` once
        every page (and thus every ``UrlNode``) exists.

        Why a second pass: the home row references ``/about`` as a CTA,
        but :class:`HomePage` types that field as :class:`Permalink` —
        a polymorphic struct that stores the *target's UrlNode PK*, not
        a string. We can't construct it during the first pass because
        the target page may not have been created yet. Once every page
        has a row + a ``UrlNode``, this method finishes the wiring.

        Per-language pass: ``template_data`` is translatable
        (``AbstractPageTranslationOptions``), so each language's
        ``template_data_<lang>`` carries its own hero object that
        needs its own ``cta``. The ``url_node`` reference is the same
        across languages — ``UrlNode.routerlink`` resolves it through
        Django's ``i18n_patterns`` per-request, so the same FK emits
        ``/about/`` for EN and ``/it/about/`` for IT at read time.
        """
        for row in PAGE_FIXTURES:
            target_permalink = row.get("cta_target")
            if not target_permalink:
                continue
            page = pages.get(row["permalink"])
            if not isinstance(page, HomePage):
                continue
            target_node = UrlNode.objects.filter(
                permalink_en=target_permalink
            ).first()
            if not target_node:
                continue
            cta = Permalink(
                link_type=LinkTypes.relational,
                url_node=target_node,
            )
            for lang in LANGS:
                data = get_nofallbacks(page, "template_data", language=lang)
                if data is None or not getattr(data, "hero", None):
                    continue
                data.hero.cta = cta
                set_nofallbacks(page, "template_data", data, language=lang)
            page.save()

    def _stage_draft(self, page: Page, live_title_en: str):
        # Wipe and re-stage so the demo always carries an obvious overlay
        # (different title from the live row, so preview ≠ public).
        Draft.objects.filter(
            content_type__model="page", object_id=page.pk, language="en"
        ).delete()
        page.save_draft(
            {"translations": {"en": {"title": f"{live_title_en} — pending edits"}}},
            merge=True,
        )

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def _seed_tags(self):
        out = {}
        for key, name_en, name_it in TAG_FIXTURES:
            # ``Tag.name`` is translatable with ``unique=True`` on the base
            # column. Look up by ``name_en`` so re-runs find the same row.
            tag = Tag.objects.filter(name_en=name_en).first() or Tag()
            set_nofallbacks(tag, "name", name_en, language="en")
            set_nofallbacks(tag, "name", name_it, language="it")
            tag.save()
            out[key] = tag
        return out

    # ------------------------------------------------------------------
    # Articles
    # ------------------------------------------------------------------

    def _seed_articles(self, *, tags, author):
        now = timezone.now()
        past = now - timedelta(hours=12)
        for permalink, title_en, title_it, content_en, content_it, tag_slugs in ARTICLE_FIXTURES:
            node = UrlNode.objects.filter(permalink_en=permalink).first()
            article = node.page if node else None
            if article is None or not isinstance(article, Article):
                article = Article()
            article.author = author
            # Render through the demo article template — overrides the
            # camomilla default. Same template for every article in the demo;
            # production sites typically pick by article kind / category.
            article.template = "website/articles/detail.html"
            for lang, title, content in (
                ("en", title_en, content_en),
                ("it", title_it, content_it),
            ):
                set_nofallbacks(article, "autopermalink", False, language=lang)
                set_nofallbacks(article, "permalink", permalink, language=lang)
                set_nofallbacks(article, "title", title, language=lang)
                set_nofallbacks(article, "content", content, language=lang)
                set_nofallbacks(article, "published_at", past, language=lang)
            article.save()
            article.tags.set([tags[s] for s in tag_slugs])

    # ------------------------------------------------------------------
    # Media folders (folders only — actual files are uploaded via admin)
    # ------------------------------------------------------------------

    def _seed_media_folders(self):
        folders_by_title = {}
        for title, parent_title in MEDIA_FOLDER_FIXTURES:
            parent = folders_by_title.get(parent_title) if parent_title else None
            folder, _ = MediaFolder.objects.get_or_create(
                title=title, defaults={"updir": parent}
            )
            folder.updir = parent
            folder.save()
            folders_by_title[title] = folder

    # ------------------------------------------------------------------
    # Menus — main + footer, pointing at the public pages we just seeded
    # ------------------------------------------------------------------

    def _seed_menus(self, *, pages):
        def link_node(title: str, permalink: str) -> dict:
            page = pages.get(permalink)
            url_node_id = page.url_node_id if page else None
            return {
                "title": title,
                "link": {
                    "link_type": "RE",
                    "url_node": url_node_id,
                },
                "nodes": [],
                "meta": {},
            }

        def static_node(title: str, href: str) -> dict:
            return {
                "title": title,
                "link": {"link_type": "ST", "static": href},
                "nodes": [],
                "meta": {},
            }

        # ``Menu.nodes`` is translatable (see ``MenuTranslationOptions``),
        # so the node tree must be seeded in EVERY language. The link
        # ``url_node`` references are the same across languages — Django
        # resolves the per-language URL at serialization time via
        # ``i18n_patterns`` + the active language; titles differ.
        def build_main(t):
            return [
                link_node(t("About", "Chi siamo"), "/about"),
                {
                    **link_node(t("Services", "Servizi"), "/services"),
                    "nodes": [
                        link_node(t("Consulting", "Consulenza"), "/services/consulting"),
                        link_node(t("Training", "Formazione"), "/services/training"),
                    ],
                },
                link_node(t("Blog", "Blog"), "/blog"),
                link_node(t("Contact", "Contatti"), "/contact"),
            ]

        def build_footer(t):
            return [
                static_node("GitHub", "https://github.com/camomillacms/camomilla-core"),
                link_node(t("About", "Chi siamo"), "/about"),
                link_node(t("Blog", "Blog"), "/blog"),
            ]

        def pick(en: str, it: str, lang: str) -> str:
            return en if lang == "en" else it

        main, _ = Menu.objects.get_or_create(key="main")
        main.enabled = True
        for lang in LANGS:
            t = lambda en, it, lang=lang: pick(en, it, lang)
            set_nofallbacks(main, "nodes", build_main(t), language=lang)
        main.save()

        footer, _ = Menu.objects.get_or_create(key="footer")
        footer.enabled = True
        for lang in LANGS:
            t = lambda en, it, lang=lang: pick(en, it, lang)
            set_nofallbacks(footer, "nodes", build_footer(t), language=lang)
        footer.save()

    # ------------------------------------------------------------------
    # Redirects
    # ------------------------------------------------------------------

    def _seed_redirects(self):
        for from_url, to_url, permanent in REDIRECT_FIXTURES:
            # UrlRedirect rows are scoped to a UrlNode (the *destination*). Look
            # up by ``permalink_en`` so the redirect attaches to the real
            # target page even if its ``permalink_it`` differs.
            target = UrlNode.objects.filter(permalink_en=to_url).first()
            if not target:
                continue
            UrlRedirect.objects.update_or_create(
                from_url=from_url.rstrip("/"),
                language_code="en",
                defaults={
                    "to_url": to_url,
                    "url_node": target,
                    "permanent": permanent,
                },
            )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _print_summary(self, *, admin, token):
        write = self.stdout.write
        write("")
        write("=" * 72)
        write(self.style.SUCCESS("Demo seed complete."))
        write("")
        write("Admin: http://localhost:8000/admin/")
        write(f"  username: {admin.username}")
        write(f"  password: admin")
        write(f"  token:    {token.key}")
        write("")
        write("Pages (public router gates on is_public):")
        for row in PAGE_FIXTURES:
            tag = "+draft" if row["with_draft"] else ""
            write(
                f"  {row['permalink']:<28} [{row['lifecycle']:<9}]  "
                f"{row['title_en']} {tag}"
            )
        write("")
        write("Articles:")
        for permalink, title_en, _, _, _, _ in ARTICLE_FIXTURES:
            write(f"  {permalink:<28} {title_en}")
        write("")
        write("Try:")
        write("  curl -s http://localhost:8000/api/camomilla/pages-router/about | jq .title")
        write(
            f'  curl -s -H "Authorization: Token {token.key}" \\\n'
            f"       http://localhost:8000/api/camomilla/pages-router-preview/ | jq .title"
        )
        write("=" * 72)
