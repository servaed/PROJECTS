---
name: frontend-design
description: Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, or applications. Generates creative, polished code that avoids generic AI aesthetics.
license: Complete terms in LICENSE.txt
---

This skill guides creation of distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics. Implement real working code with exceptional attention to aesthetic details and creative choices.

The user provides frontend requirements: a component, page, application, or interface to build. They may include context about the purpose, audience, or technical constraints.

## Design Thinking

Before coding, understand the context and commit to a BOLD aesthetic direction:
- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick an extreme: brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, industrial/utilitarian, etc. There are so many flavors to choose from. Use these for inspiration but design one that is true to the aesthetic direction.
- **Constraints**: Technical requirements (framework, performance, accessibility).
- **Differentiation**: What makes this UNFORGETTABLE? What's the one thing someone will remember?

**CRITICAL**: Choose a clear conceptual direction and execute it with precision. Bold maximalism and refined minimalism both work - the key is intentionality, not intensity.

Then implement working code (HTML/CSS/JS, React, Vue, etc.) that is:
- Production-grade and functional
- Visually striking and memorable
- Cohesive with a clear aesthetic point-of-view
- Meticulously refined in every detail

## Frontend Aesthetics Guidelines

Focus on:
- **Typography**: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics; unexpected, characterful font choices. Pair a distinctive display font with a refined body font.
- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes.
- **Motion**: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions. Use scroll-triggering and hover states that surprise.
- **Spatial Composition**: Unexpected layouts. Asymmetry. Overlap. Diagonal flow. Grid-breaking elements. Generous negative space OR controlled density.
- **Backgrounds & Visual Details**: Create atmosphere and depth rather than defaulting to solid colors. Add contextual effects and textures that match the overall aesthetic. Apply creative forms like gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows, decorative borders, custom cursors, and grain overlays.

NEVER use generic AI-generated aesthetics like overused font families (Inter, Roboto, Arial, system fonts), cliched color schemes (particularly purple gradients on white backgrounds), predictable layouts and component patterns, and cookie-cutter design that lacks context-specific character.

Interpret creatively and make unexpected choices that feel genuinely designed for the context. No design should be the same. Vary between light and dark themes, different fonts, different aesthetics. NEVER converge on common choices (Space Grotesk, for example) across generations.

**IMPORTANT**: Match implementation complexity to the aesthetic vision. Maximalist designs need elaborate code with extensive animations and effects. Minimalist or refined designs need restraint, precision, and careful attention to spacing, typography, and subtle details. Elegance comes from executing the vision well.

Remember: Claude is capable of extraordinary creative work. Don't hold back, show what can truly be created when thinking outside the box and committing fully to a distinctive vision.

---

## Project Design System — cloudera-ai-id-rag-demo

When working on pages within this project, follow the established design system:

### Color Palette
```css
--orange:  #F96702;   /* Cloudera brand — primary accent */
--teal:    #00A591;   /* secondary accent (dark) / #00796B (light mode) */
--indigo:  #818CF8;   /* tertiary accent (dark) / #5C6BC0 (light mode) */
--green:   #34D399;   /* success / positive */
--bg:      #F8F9FA;   /* light mode background */
--surface: #FFFFFF;   /* light mode card */
/* Dark mode (presentation + dark UI variant): #0a0e1a bg, #111827 surface */
```

### Typography
- **Body**: `Google Sans` (from Google Fonts) — `system-ui` fallback for offline
- **Display headings**: `Google Sans Display` (700/800/900)
- **Monospace**: `JetBrains Mono` (code blocks, SQL, paths, monospace labels)
- Anti-aliasing: always `-webkit-font-smoothing: antialiased`

### Icon Vocabulary
**Rule: zero emoji in UI chrome.** All icons are stroke SVG, Feather icon style, `fill:none`, `stroke:currentColor`, `stroke-width:1.5`, `stroke-linecap:round`, `stroke-linejoin:round`, 24×24 viewBox.

Domain symbols (sidebar tabs, welcome screen): `◈` Banking · `⬡` Telco · `⬢` Government · `◉` All

Common icons:
- Chat: `<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>`
- Database: `<ellipse cx="12" cy="5" rx="9" ry="3"/>` + path arcs
- Bar chart: `<line x1="18" y1="20" x2="18" y2="10"/>` + similar lines + baseline
- Settings/gear: circle + gear path (full Feather settings icon)
- File: `<path d="M14 2H6a2 2 0 0 0-2 2v16..."/>` + polyline for fold
- Folder: `<path d="M22 19a2 2 0 0 1-2 2H4..."/>` with tab

### Cloudera Logo Usage
- **Light mode chat**: orange filter — `brightness(0) saturate(100%) invert(43%) sepia(97%) saturate(739%) hue-rotate(346deg) brightness(103%) contrast(103%)`
- **Dark mode chat**: white filter — `brightness(0) invert(1)`
- **Presentation (dark bg)**: orange filter via `--logo-filter` CSS variable

### Component Patterns
- Cards: `border-radius:14px`, `border:1px solid var(--border)`, 3px top accent bar via `::before`
- Pills/badges: `border-radius:20px`, uppercase, 700 weight, dimmed background + colored border
- Buttons (primary): orange bg, white text, `box-shadow:0 4px 20px rgba(249,103,2,0.4)`
- Topbar: `height:64px`, white/surface bg, 1px bottom border, flex align-center
- Nav links (topbar): `height:32px`, `border-radius:8px`, border, `var(--s2)` bg — plain text labels