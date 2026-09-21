---
name: Bangalore Bites
colors:
  surface: '#131316'
  surface-dim: '#131316'
  surface-bright: '#39393c'
  surface-container-lowest: '#0e0e11'
  surface-container-low: '#1b1b1e'
  surface-container: '#1f1f22'
  surface-container-high: '#2a2a2d'
  surface-container-highest: '#353438'
  on-surface: '#e4e1e6'
  on-surface-variant: '#dfc0b5'
  inverse-surface: '#e4e1e6'
  inverse-on-surface: '#303033'
  outline: '#a78b81'
  outline-variant: '#58423a'
  surface-tint: '#ffb59a'
  primary: '#ffb59a'
  on-primary: '#5b1b00'
  primary-container: '#ff7a45'
  on-primary-container: '#672000'
  inverse-primary: '#a73a05'
  secondary: '#ffb95f'
  on-secondary: '#472a00'
  secondary-container: '#ee9800'
  on-secondary-container: '#5b3800'
  tertiary: '#4fd8e9'
  on-tertiary: '#00363c'
  tertiary-container: '#00b2c2'
  on-tertiary-container: '#003f45'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdbcf'
  primary-fixed-dim: '#ffb59a'
  on-primary-fixed: '#380d00'
  on-primary-fixed-variant: '#802900'
  secondary-fixed: '#ffddb8'
  secondary-fixed-dim: '#ffb95f'
  on-secondary-fixed: '#2a1700'
  on-secondary-fixed-variant: '#653e00'
  tertiary-fixed: '#8ff1ff'
  tertiary-fixed-dim: '#4fd8e9'
  on-tertiary-fixed: '#001f23'
  on-tertiary-fixed-variant: '#004f56'
  background: '#131316'
  on-background: '#e4e1e6'
  surface-variant: '#353438'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '800'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 30px
    fontWeight: '800'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.25rem
  gutter-mobile: 0.75rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

The design system establishes an atmospheric, late-night food-tech aesthetic engineered for Bangalore’s vibrant, tech-forward dining culture. It captures the energy of late-night exploratory food crawls—from high-energy Indiranagar craft breweries and Koramangala hole-in-the-wall bakeries to calm Whitefield bistros—while retaining the precision of an AI-driven culinary concierge.

The visual style blends **Contemporary Dark Mode** with **Refined Glassmorphic Glows**. It relies on deep charcoal substrates layered with warm culinary ambers, crisp typographical hierarchies, and subtle glowing borders. Interfaces feel responsive, tactile, and cinematic rather than clinical, creating an immersive night-mode experience that makes imagery pop and decision-making intuitive.

## Colors

The palette is tuned specifically for deep-contrast, low-strain night viewing:

- **Primary Accent (`#FF7A45` / `#FF8A50`)**: Energetic Ember. Used for primary CTAs, active recommendation tags, AI sparkle accents, and high-impact states. Emits an ambient low-opacity glow on hover.
- **Secondary Accent (`#F59E0B`)**: Warm Saffron Gold. Reserved for curated badges, Michelin/Must-Try flags, aggregate ratings, and price tiers.
- **Neutral Substrates**:
  - `Canvas Dark`: `#121212` to `#18181B` base canvas.
  - `Surface Tier 1`: `#1F1F23` (structural panels, bottom navigation sheets).
  - `Surface Tier 2`: `#27272A` (restaurant interactive cards, modal windows).
  - `Surface Tier 3`: `#323238` (hover states, nested chips, inactive toggles).
- **Border & Stroke**:
  - `Border Subtle`: `#333338` (structural card bounding).
  - `Border Glow`: `rgba(255, 122, 69, 0.35)` (AI highlighted recommendation cards).
- **Text & Content Hierarchy**:
  - `High Contrast`: `#FFFFFF` and `#F4F4F5` (restaurant titles, prominent headlines, numbers).
  - `Medium Contrast`: `#A1A1AA` (neighborhood descriptions, AI rationale, culinary tags).
  - `Low Contrast`: `#71717A` (metadata, distance meters, operating hours, structural hints).

## Typography

The design system standardizes on **Plus Jakarta Sans** across all typographic touchpoints to deliver modern geometric discipline alongside welcoming, sculpted curves.

- **Headlines (`headline-xl`, `headline-lg`, `headline-md`)**: High-contrast, negative tracking (-0.02em) to maintain punchy visual weight against deep charcoal backgrounds. Used for restaurant names, curated AI summaries, and localized neighborhood titles.
- **Body (`body-lg`, `body-md`, `body-sm`)**: Formatted with deliberate line-height expansions (1.5x - 1.6x) to preserve effortless scanability in low-light environments, specifically for AI-generated tasting notes and ingredient breakdowns.
- **Labels & Overlays (`label-md`, `label-sm`)**: High-weight, slightly tracked tokens tailored for rating pills, culinary style tags, veg/non-veg flags, and neighborhood location indicators.

## Layout & Spacing

A structured 8pt layout model governs spatial rhythm:

- **Grid Systems**:
  - **Desktop (1024px+)**: 12-column responsive grid with `margin: 2rem` and `gutter: 1.25rem`. Content max-width is pinned at 1280px to prevent visual dilution of food photography.
  - **Tablet (640px - 1023px)**: 6-column grid with `margin: 1.5rem` and dynamic card sizing.
  - **Mobile (<640px)**: 4-column flow with condensed `margin-mobile: 1rem` and `gutter-mobile: 0.75rem` for edge-to-edge culinary discovery carousels.
- **Spacing Roles**:
  - `space-xs` (4px): Micro-spacing between rating stars, icons, and inline text.
  - `space-sm` (8px): Pill chip padding, metadata stack vertical spacing.
  - `space-md` (16px): Internal padding for interactive cards, input field gutter.
  - `space-lg` (24px): Card interior spacing on desktop, module-level vertical margins.
  - `space-xl` (40px): Section-to-section breaks and feed cluster separators.

## Elevation & Depth

Visual depth is achieved through a combination of **tonal surface stacking**, **subtle border highlights**, and **warm ambient back-diffusion**:

- **Ground Plane (`z-0`)**: `#121212`—Deep canvas background.
- **Elevated Card (`z-1`)**: `#222226` background surface with a 1px continuous outline in `#333338`. Shadow is ultra-diffused: `0 8px 32px -4px rgba(0, 0, 0, 0.6)`.
- **Active / Featured Card (`z-2`)**: `#27272A` background surface with dynamic amber rim light: `0 0 0 1px rgba(255, 122, 69, 0.4), 0 12px 40px -6px rgba(255, 122, 69, 0.12)`.
- **Floating Overlays & AI Prompt Bars (`z-3`)**: Semi-transparent `#18181B` at 85% opacity paired with `backdrop-filter: blur(16px)` and a subtle interior border glow (`rgba(255, 255, 255, 0.08)`).

## Shapes

The interface embraces a generous, modern geometry with soft squircle principles:

- Standard structural components, action cards, and modals sit at a baseline of `12px` to `16px` (`rounded-lg` to `rounded-xl`).
- Micro-elements such as rating badges, category chips, and filter toggles use rounded contours (`8px` to `12px`) or full pills for instant tap target identification.
- Food photography frames adopt matched `12px` interior corner radiuses to integrate smoothly within card hulls.

## Components

### Buttons
- **Primary Action**: Gradient or solid background of `#FF7A45` transitioning to `#FF8A50` on hover. Contrast typography in `#FFFFFF`, font weight 600. Features a faint drop glow: `0 4px 16px rgba(255, 122, 69, 0.3)`. Border-radius is 12px.
- **Secondary Action**: `#27272A` surface with 1px border of `#333338`. Text in `#F4F4F5`. On hover, border shifts to `#FF7A45` with subtle background lift.
- **Ghost / Tertiary**: Transparent background, `#A1A1AA` text, turning `#FFFFFF` on interaction.

### Cards (Restaurant & AI Recommendation)
- Built on `#222226` or `#27272A` base with rounded corners (14px) and 1px `#333338` borders.
- Top section holds an edge-to-edge or padded 16:9 photo container with an embedded ambient gradient overlay at the bottom edge.
- Pinned to the top corner: Rating Pill using `#F59E0B` icon with bold label on translucent black backing.
- Bottom section contains dish tags, AI recommendation explanation in `#A1A1AA`, distance metadata in `#71717A`, and immediate booking/view CTAs.

### Chips & Filter Tags
- **Default State**: Surface `#1F1F23`, 1px outline `#333338`, text `#A1A1AA`, radius 9999px (full pill) or 10px.
- **Active State**: Rich `#FF7A45` background at 15% opacity, border 1px `#FF7A45`, text `#FF8A50`, accompanied by an active indicator dot.

### AI Search & Conversational Input
- Prominent persistent prompt bar using `#1F1F23` with 16px radius, inset box shadow, and `backdrop-filter: blur(12px)`.
- Left-aligned glowing amber AI sparkle glyph (`#FF7A45`).
- Input placeholder in `#71717A`, text entry in `#FFFFFF`.
- Right-aligned shortcut/submit button with an amber icon glow.

### Checkboxes, Radios, and Toggles
- Base track/border in `#333338`.
- Checked fill in `#FF7A45` with `#FFFFFF` inner mark.
- Toggles utilize smooth ease-in-out movement with an active track tint of `rgba(255, 122, 69, 0.25)` and solid `#FF7A45` thumb.