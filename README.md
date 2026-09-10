# Music Atlas self-hosted mirror

Self-hosted capture of `musicatlas.radio`, including the original Squarespace page DOM, functional runtime, component bundles, responsive image variants, lazy loading, progressive resources, animation hooks, and navigation UX.

Serve this directory from the web root with any static HTTP server. For example:

```sh
python3 -m http.server 4175 --bind 127.0.0.1
```

## Runtime and privacy behavior

- Squarespace's functional common runtime, polyfills, site bundle, and page component bundles are mirrored under `_mirror/`.
- Images, CSS, fonts, image effects, and responsive `srcset` variants are local.
- SoundCloud players load by default from `w.soundcloud.com`; they are the intentional remote dependency.
- Visitor error reporting, performance telemetry, user-account code, the Typekit network loader, and cookie-banner capability are removed.
- The parent page has `connect-src 'none'`, blocking analytics, telemetry, and runtime API calls.
- A small local fallback preserves fade reveals, progressive-image completion, header offsets, smooth anchor navigation, mobile-menu behavior, keyboard escape, and reduced-motion support.

`mirror-manifest.json` records every mirrored URL and any failed downloads. Run `tools/mirror_site.py` to refresh the capture from the public page.

The `reference/` directory contains the desktop and mobile captures used for visual matching; the previous hand-built local assets remain available under `assets/`.
