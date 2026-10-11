# USPBF WordPress theme — align with Pro Billiards & Alfa family

The marketing site runs in Docker; theme files live in the **`uspbf_wp_data`** volume, not in this repo. Use a **child theme** or **Appearance → Customize → Additional CSS** so upgrades do not wipe your styles.

## Design tokens (match maintenance page)

These mirror the Pro Billiards stack (slate + sky) with a **gold** accent for USPBF identity. Paste into **Additional CSS** or a child theme `style.css` after `:root` on `body` or `.wp-site-blocks`.

```css
:root {
  --uspbf-bg-deep: #0f172a;
  --uspbf-bg-mid: #1e293b;
  --uspbf-surface: rgba(30, 41, 59, 0.85);
  --uspbf-border: rgba(71, 85, 105, 0.5);
  --uspbf-accent-sky: #38bdf8;
  --uspbf-accent-sky-strong: #0ea5e9;
  --uspbf-accent-gold: #c9a227;
  --uspbf-text: #e2e8f0;
  --uspbf-muted: #94a3b8;
}

/* Example: dark page background */
body {
  background: linear-gradient(135deg, var(--uspbf-bg-deep) 0%, var(--uspbf-bg-mid) 100%);
  color: var(--uspbf-text);
}

/* Example: primary buttons / links */
a {
  color: var(--uspbf-accent-sky);
}
a:hover {
  color: var(--uspbf-accent-sky-strong);
}

/* Example: headings or badges */
.uspbf-accent-heading {
  color: var(--uspbf-accent-gold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 0.75rem;
}
```

Tune selectors to your block theme (Twenty Twenty-Five, Spectra One, etc.). Use the **Site Editor → Styles** for global colors where possible, and Additional CSS for gradients and fine tuning.

## Child theme (recommended)

1. **wp-content/themes/uspbf-spectra-child/style.css** (header):

   ```css
   /*
   Theme Name: USPBF Child
   Template: spectra-one
   */
   @import url("../spectra-one/style.css");
   ```

   Replace `spectra-one` with your parent theme folder name.

2. Add the `:root` and body rules above.

3. **Appearance → Themes** → activate the child theme.

## Block theme global styles

In **Appearance → Editor → Styles**:

- Set **background** to a dark slate (`#0f172a` or similar).
- Set **text** to `#e2e8f0`.
- Set **links** to `#38bdf8` (sky).

Use **gold** sparingly for federation labels or section labels so the site reads as USPBF while staying visually related to **probilliardssoftware.com** (Pro Billiards) and your Alfa properties.

## References

- Maintenance page (versioned): [nginx-config/maintenance/index.html](../nginx-config/maintenance/index.html)
- Page outline: [WORDPRESS_PAGES.md](WORDPRESS_PAGES.md)
