import { defineConfig } from 'vitepress'
import llmstxt from 'vitepress-plugin-llms'

// Camomilla documentation — VitePress.
// Published to GitHub Pages under /camomilla-core/. The vitepress-plugin-llms
// build step emits llms.txt + llms-full.txt (and per-page .md) into the dist
// so AI agents / IDEs can ingest the docs and an MCP bridge (mcpdoc) can serve
// them. See README "AI-readable docs (llms.txt / MCP)".
export default defineConfig({
  lang: 'en-US',
  title: 'Camomilla',
  description: 'Django-powered headless CMS — REST APIs, media, multilingual pages, drafts & preview.',
  base: '/camomilla-core/',
  cleanUrls: false, // keep VuePress-style directory URLs (/How to/Use API/) so existing links don't break
  ignoreDeadLinks: true, // TODO: tighten once the legacy relative links are normalized
  markdown: {
    // Django/Jinja template fences (```django) have no Shiki grammar — render
    // them as HTML so they still get sensible highlighting instead of plain text.
    languageAlias: { django: 'html' },
  },
  head: [
    ['link', { rel: 'icon', href: 'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📑</text></svg>' }],
  ],
  vite: {
    plugins: [llmstxt()],
  },
  themeConfig: {
    logo: '/images/camomilla-short-logo.svg',
    nav: [
      { text: 'Home', link: '/' },
      { text: 'QuickStart', link: '/QuickStart/' },
      { text: 'How to', link: '/How to/' },
      { text: 'Demo', link: 'https://camomilla.lotrek.io/' },
    ],
    sidebar: [
      { text: 'QuickStart', link: '/QuickStart/' },
      {
        text: 'How to',
        link: '/How to/',
        collapsed: false,
        items: [
          { text: 'Use Pages', link: '/How to/Use Pages/' },
          { text: 'Use Page Lifecycle', link: '/How to/Use Page Lifecycle/' },
          { text: 'Use Pages Context', link: '/How to/Use Pages Context/' },
          { text: 'Use StructuredJSONField', link: '/How to/Use StructuredJSONField/' },
          { text: 'Use Meta Models', link: '/How to/Use Meta Models/' },
          { text: 'Use Media', link: '/How to/Use Media/' },
          { text: 'Use Menu', link: '/How to/Use Menu/' },
          { text: 'Use Modeltranslation', link: '/How to/Use Modeltranslation/' },
          { text: 'Use API', link: '/How to/Use API/' },
          { text: 'Use Astro Integration', link: '/How to/Use Astro Integration/' },
          { text: 'Use Settings', link: '/How to/Use Settings/' },
        ],
      },
      { text: 'Contribute', link: '/Contribute/' },
      { text: 'Changelog', link: '/Changelog/' },
      { text: 'License', link: '/License/' },
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/camomillacms/camomilla-core' },
    ],
    search: { provider: 'local' },
    editLink: {
      pattern: 'https://github.com/camomillacms/camomilla-core/edit/master/docs/:path',
      text: 'Edit this page on GitHub',
    },
  },
})
