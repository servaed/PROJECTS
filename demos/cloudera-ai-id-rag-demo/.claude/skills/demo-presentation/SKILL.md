---
name: demo-presentation
description: Managing the dual-audience presales slide deck at /presentation — structure, audience toggle, slide content, icon vocabulary, and extending slides.
---

# Skill: Demo Presentation

## File Location

- **Primary**: `app/static/presentation.html`
- **Sync copy**: `docs/presentation.html` — always keep in sync with `cp`

## Audience Mode

The deck has two modes controlled by the top-right toggle:

| Mode | Slides | Use when |
|------|--------|----------|
| Business (default) | s1–s9 (9 slides) | C-suite, business stakeholders, sales calls |
| Technical | s1–s14 (14 slides) | Architects, IT leads, technical evaluators |

Technical slides carry `data-tech="1"` attribute. The `buildSlideList()` JS function filters them out in Business mode.

## Slide Structure

### Business Slides (s1–s9)
| ID | Topic | Background |
|----|-------|-----------|
| s1 | Cover — "Your Data Already Has All the Answers" | `bg-cover` (orange radial glow) |
| s2 | The Problem — 4 pain-point cards | `bg-dark` |
| s3 | The Solution — 3 industry scenarios (ID + EN) | `bg-teal` |
| s4 | Capabilities — 3 question types + feature row | `bg-dark` |
| s5 | Business Value — checklist + impact stats | `bg-indigo` |
| s6 | Why Cloudera — 6 platform cards | `bg-orange` |
| s7 | Industry Applications — 3-column vertical checklist | `bg-dark` |
| s8 | Getting Started — 3-step flow | `bg-teal` |
| s9 | CTA — "Let's Run It Live" + live demo link | `bg-cover` |

### Technical Slides (s10–s14, `data-tech="1"`)
| ID | Topic | Key content |
|----|-------|------------|
| s10 | Pipeline Architecture | Router → 3 mode branches → LLM synthesis → cited answer (arch-box diagram) |
| s11 | Retrieval Quality Stack | FAISS → BM25/RRF → cross-encoder; SQL engine stats (layer-stack + card grid) |
| s12 | Deployment Architecture | Dev (DuckDB/local) vs. Production CDP (CDW/Trino + Ozone) side-by-side |
| s13 | LLM Flexibility & APIs | 4 provider cards + API endpoint code block |
| s14 | Security & Observability | SQL AST guardrails, SHA-256, DOMPurify, MLflow, Iceberg time travel |

## How the Audience Toggle Works

```js
var allSlides = Array.from(document.querySelectorAll('.slide'));
var aud = 'biz'; // or 'tech'

function buildSlideList() {
  slides = allSlides.filter(s => aud === 'tech' || !s.dataset.tech);
  total = slides.length;
  // Updates slide-num and progress-fill on all visible slides
}

function setAud(a) {
  aud = a;
  // Update button styles, hide all slides, rebuild list, show slide[0]
}
```

When toggling audience, all slides are hidden and navigation resets to slide 1.

## Adding New Slides

### Business slide
1. Add `<section class="slide bg-{variant}" id="sN">` before `</div><!-- /#deck -->`
2. Include the standard `.slide-footer` with `.slide-num` and `.progress-fill` (dynamic values updated by JS)
3. No `data-tech` attribute — it will show in both modes

### Technical slide
1. Add `<section class="slide bg-{variant}" id="sN" data-tech="1">`
2. Include the `.tech-badge` div at the top (shows "Technical Deep Dive" label)
3. Add `.slide-tag` with the section name

## Icon Vocabulary (Presentation)

Always use inline stroke SVG — no emoji. Key icons:

- **Banking** (column chart / bank building): `<line x1="3" y1="22" x2="21" y2="22"/>` + columns + `<polygon points="12 2 20 7 4 7"/>`
- **Telco** (wifi): `<path d="M5 12.55a11 11 0 0 1 14.08 0"/>` + two more arcs + dot
- **Government** (landmark): `<polyline points="22 8 12 2 2 8"/>` + columns + base line
- **Info/tip** (replaces 💡): `<circle cx="12" cy="12" r="10"/>` + `<line x1="12" y1="8" x2="12" y2="12"/>` + dot
- **Globe** (replaces 🌐): `<circle cx="12" cy="12" r="10"/>` + horizontal line + latitude path

## CSS Classes Reference

| Class | Purpose |
|-------|---------|
| `bg-cover` | Orange radial + dark gradient (cover/CTA slides) |
| `bg-dark` | Plain dark gradient |
| `bg-teal` | Teal radial + dark gradient |
| `bg-indigo` | Indigo radial + dark gradient |
| `bg-orange` | Orange radial + warm dark gradient |
| `card-grid-2/3/4` | CSS grid layouts |
| `card-teal/indigo/green/yellow/orange` | Card top-accent color via `--card-accent` |
| `pill-orange/teal/indigo/green` | Pill badge variants |
| `arch-box / arch-box.hl-*` | Architecture diagram boxes |
| `layer-stack / layer` | Vertical stack diagram rows |
| `check-list / check-item` | Checklist with green check circles |
| `stat / stat-n / stat-l` | Big number + label pairs |
| `code-block` | Monospace code block with syntax highlight classes |
| `tech-badge` | Indigo "Technical Deep Dive" label for tech slides |
| `anim / anim-1 … anim-6` | Staggered fadeInUp animations (cover slide only) |

## Syncing docs/presentation.html

After every edit to `app/static/presentation.html`:
```bash
cp app/static/presentation.html docs/presentation.html
```
