# Harbor Design System

Harbor is the extracted visual system behind this portfolio app: warm canvas backgrounds, glassy panels, geometric display type, soft pills, and crisp data surfaces that still feel inviting.

## Install

```bash
npm install harbor-design-system
```

## Quick start in another React project

1. Import the CSS once near your app entry point.
2. Wrap the relevant screen or app shell in `<DsTheme>`.
3. Use the primitives or the raw `ds-*` classes directly.
4. Pull in `harborTokens` or `harbor-design-system/tokens.json` if you want the token manifest outside React.

```tsx
import "harbor-design-system/harbor.css";
import { DsButton, DsPanel, DsStage, DsTheme } from "harbor-design-system";

export function Example() {
  return (
    <DsTheme>
      <DsStage>
        <DsPanel kicker="Overview" title="Harbor in a new app">
          <p className="ds-copy">Warm, precise, dashboard-friendly UI without a framework dependency.</p>
          <DsButton variant="primary">Primary action</DsButton>
        </DsPanel>
      </DsStage>
    </DsTheme>
  );
}
```

## Package contents

- `harbor-design-system`: React primitives and `harborTokens`
- `harbor-design-system/harbor.css`: design-system CSS
- `harbor-design-system/tokens.json`: JSON token manifest for non-React tooling

## Local build

```bash
npm install
npm run build
npm run pack:check
```

## Export a tarball or zip

From the repo root:

```bash
./scripts/package-design-system.sh
```

That generates:

- `design-system/artifacts/harbor-design-system-0.1.0.tgz`
- `design-system/artifacts/harbor-design-system-0.1.0.zip`

For publish steps and release notes, see `design-system/PUBLISHING.md`.

## Core principles

- Keep the background warm and the content surfaces cool. That contrast gives the UI its personality.
- Use `Space Grotesk` only for major headings and key numbers. Everything else stays in `IBM Plex Sans`.
- Preserve rounded geometry. Pills, inputs, and panels should feel soft, not sharp.
- Limit strong colors to a few jobs: blue for action, green for positive states, coral for warmth, red for destruction.
- Let data stay dense, but surround it with breathing room and muted labels.

## Live reference

Open the in-app showroom at `/design-system` to inspect the full token set and sample components.
