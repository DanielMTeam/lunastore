# Frontend, Retro Aesthetics, and Internet Explorer 6 Compatibility

**LunaStore** must work in modern browsers and in **Internet Explorer 6** on **Windows XP, Windows 2000, and Windows 98**.

---

## Design philosophy

1. **Windows XP Luna look:** Classic rounded tabs, panels, blue/green/silver schemes, early-2000s icons.
2. **Sound effects:** Click and system sounds live under `staticfiles/snd/`.
3. **Modals:** Time-tested `ThickBox` (`thickbox.js` + `thickbox.css`), adapted for legacy browsers.
4. **Themes:** Light (`main.css`) and dark (`darkthm.css`), toggled via cookies (`cookie.js`).

---

## JavaScript build via Babel (target: IE6)

### 1. File layout
- **Source:** [`staticfiles/js/`](../../../staticfiles/js/)
- **Compiled output:** `static/js/`
- **Config:** [`babel.config.json`](../../../babel.config.json)

```json
{
  "presets": [
    [
      "@babel/preset-env",
      {
        "targets": {
          "ie": "6"
        },
        "modules": false,
        "useBuiltIns": false
      }
    ]
  ],
  "ignore": [
    "**/*.min.js",
    "**/thickbox.js"
  ]
}
```

### 2. Build commands
```bash
# One-shot compile:
npm run babel:build

# Watch mode:
npm run babel:watch
```

> **Never edit files under `static/js/` directly.**
> Change `staticfiles/js/`, then run `npm run babel:build`.

---

## Strict IE6 development rules

### 1. JavaScript bans
- **No `const` / `let` in inline template scripts** — use `var`, or move logic into `staticfiles/js/` for Babel.
- **No arrow functions `() => {}`** in inline `<script>`.
- **No bare `fetch()` / `Promise`** without polyfills — use `jQuery.ajax()` or `XMLHttpRequest` / `ActiveXObject("Microsoft.XMLHTTP")`.
- **No `localStorage` / `sessionStorage`** on legacy pages — use cookies (`staticfiles/js/cookie.js`).
- **No trailing commas** in JS objects/arrays:
  ```javascript
  // Broken in IE6:
  var data = { a: 1, b: 2, };

  // Correct:
  var data = { a: 1, b: 2 };
  ```

### 2. PNG transparency (`DD_belatedPNG`)
IE6 does not support 8-bit PNG alpha (shows a gray/blue backdrop).
- Fix: [`staticfiles/js/dd_belatedpng.min.js`](../../../staticfiles/js/dd_belatedpng.min.js).
- Apply to transparent PNG elements:
  ```javascript
  DD_belatedPNG.fix('.png-fix, img, .icon');
  ```

### 3. Protocol-relative CDN URLs
Legacy OSes often fail modern TLS 1.3/SNI. To avoid mixed content and broken icons:
- Model properties `icon_url`, `screenshot_urls`, `avatar_url` emit **protocol-relative URLs** (e.g. `//spire.lunastore.app/storage/icons/abc.png`).
- The browser picks `http:` or `https:` from the current page protocol.

---

## CSS layout (`staticfiles/css/`)

| File | Purpose |
| :--- | :--- |
| `main.css` | Global styles: header, footer, buttons, sidebar |
| `darkthm.css` | Dark theme |
| `stpage.css` | App card, screenshots, reviews, rating |
| `collections.css` | 2×2 mosaic and collection layouts |
| `ie6/` | IE6-specific CSS hacks |
| `thickbox.css` | Screenshot gallery modals |
| `admin_custom.css` | Django Unfold Luna styling |
| `notify.css` | Push notification toasts |

---

## Client-side modules (`staticfiles/js/`)

- **`marketplace_cdn.js`**: Icon/screenshot upload and validation with LunaSpire tokens.
- **`distribution_cdn.js`**: Binary installer upload to CDN and hash retrieval.
- **`global_notifications.js`**: Poll unread notifications; bell indicator.
- **`rating.js`**: Interactive star rating widget.
- **`screenshots_manager.js`**: Add/remove/reorder screenshots.
- **`tabs.js` / `field_locale_tabs.js`**: Locale field tabs (**RU / EN / UK / BE / KK**).
