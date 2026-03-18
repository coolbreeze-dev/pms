import {
  DsButton,
  DsChip,
  DsCodeBlock,
  DsField,
  DsHero,
  DsInput,
  DsPanel,
  DsSelect,
  DsStage,
  DsTheme,
  DsStatCard,
  DsTextarea,
  harborTokens,
} from "harbor-design-system";
import "harbor-design-system/harbor.css";

const swatches = [
  { name: "Canvas", value: "#f8f5ef", usage: "App backgrounds", color: "#f8f5ef" },
  { name: "Ink", value: "#102336", usage: "Headings and primary text", color: "#102336" },
  { name: "Accent", value: "#0b7fab", usage: "Primary actions and highlights", color: "#0b7fab" },
  { name: "Growth", value: "#1f9f6f", usage: "Positive deltas and success states", color: "#1f9f6f" },
  { name: "Signal", value: "#ff7f50", usage: "Charts and warm emphasis", color: "#ff7f50" },
  { name: "Glow", value: "#ffcb77", usage: "Warm overlays and hero lighting", color: "#ffcb77" },
  { name: "Danger", value: "#b23b3b", usage: "Destructive actions and warnings", color: "#b23b3b" },
  { name: "Line", value: "rgba(16,35,54,.12)", usage: "Borders and dividers", color: "rgba(16,35,54,.12)" },
];

const typeScale = [
  { token: "Display", value: "Space Grotesk 700", usage: "Page titles and key figures" },
  { token: "Body", value: "IBM Plex Sans 400-600", usage: "Everything else" },
  { token: "Eyebrow", value: "0.75rem / 0.12em tracking", usage: "Section kickers" },
  { token: "Value", value: "1.85rem", usage: "Dashboard stat numbers" },
];

const spacingScale = [
  { token: "--ds-space-2", value: "8px" },
  { token: "--ds-space-3", value: "12px" },
  { token: "--ds-space-4", value: "16px" },
  { token: "--ds-space-5", value: "20px" },
  { token: "--ds-space-6", value: "24px" },
  { token: "--ds-space-8", value: "32px" },
];

const installSnippet = `import "harbor-design-system/harbor.css";
import { DsButton, DsPanel, DsStage, DsTheme } from "harbor-design-system";

export function ExampleScreen() {
  return (
    <DsTheme>
      <DsStage>
        <DsPanel kicker="Overview" title="Bring the system into any product">
          <p className="ds-copy">Use the tokens, panels, buttons, chips, forms, and tables as-is.</p>
          <DsButton variant="primary">Primary action</DsButton>
        </DsPanel>
      </DsStage>
    </DsTheme>
  );
}`;

export function DesignSystemPage() {
  return (
    <DsTheme>
      <DsStage>
        <DsHero
          kicker="Portable visual system"
          title="Harbor Design System"
          description="A warm, data-forward UI language extracted from this app so you can reuse the same polished tone in dashboards, ops tools, internal products, and consumer workflows."
          actions={
            <>
              <DsButton variant="primary">Use for dashboards</DsButton>
              <DsButton>Use for forms</DsButton>
              <DsButton variant="danger">Use for risky actions</DsButton>
            </>
          }
          meta={
            <p>
              Install `harbor-design-system`, import the CSS once, and use the exported token manifest
              for non-React stacks.
            </p>
          }
        />

        <section className="ds-stat-grid">
          <DsStatCard label="Mood" value="Warm + precise" meta="Soft glass surfaces, strong data density" />
          <DsStatCard label="Best for" value="Dashboards" meta="Portfolio, analytics, CRM, ops, admin" />
          <DsStatCard label="Core fonts" value="Plex + Grotesk" meta="Readable body copy, expressive display" />
          <DsStatCard label="Reuse path" value="npm install" meta="Package, CSS, token manifest" />
        </section>

        <section className="ds-showcase-grid">
          <DsPanel
            kicker="Foundation"
            title="Color, type, and spacing"
            description="The system works because the warm background, cool ink, and bright accent colors stay disciplined."
          >
            <div className="ds-swatch-grid">
              {swatches.map((swatch) => (
                <article key={swatch.name} className="ds-swatch">
                  <div className="ds-swatch__tile" style={{ background: swatch.color }} />
                  <div className="ds-swatch__meta">
                    <strong>{swatch.name}</strong>
                    <span>{swatch.value}</span>
                    <span>{swatch.usage}</span>
                  </div>
                </article>
              ))}
            </div>
          </DsPanel>

          <DsPanel kicker="Token map" title="Typography and rhythm" strong>
            <div className="ds-token-list">
              {typeScale.map((item) => (
                <div key={item.token} className="ds-token-row">
                  <div>
                    <strong>{item.token}</strong>
                    <p className="ds-caption">{item.usage}</p>
                  </div>
                  <span className="ds-badge">{item.value}</span>
                </div>
              ))}
              {spacingScale.map((item) => (
                <div key={item.token} className="ds-token-row">
                  <strong>{item.token}</strong>
                  <span className="ds-badge">{item.value}</span>
                </div>
              ))}
              <div className="ds-token-row">
                <strong>Token export</strong>
                <span className="ds-badge">{harborTokens.name}</span>
              </div>
            </div>
          </DsPanel>
        </section>

        <section className="ds-two-column">
          <DsPanel
            kicker="Components"
            title="Buttons, chips, and notices"
            description="Buttons stay pill-shaped and calm, while chips create compact filters without making the screen noisy."
          >
            <div className="ds-inline-actions">
              <DsButton variant="primary">Save changes</DsButton>
              <DsButton>Secondary action</DsButton>
              <DsButton variant="danger">Delete item</DsButton>
            </div>
            <div className="ds-chip-row">
              <DsChip active>Brokerage</DsChip>
              <DsChip>Retirement</DsChip>
              <DsChip>India</DsChip>
              <DsChip soft>Benchmark on</DsChip>
            </div>
            <div className="ds-notice">
              Use accent blue for the default action, green for good outcomes, coral for chart warmth, and red
              only when the user could lose work or data.
            </div>
          </DsPanel>

          <DsPanel
            kicker="Forms"
            title="Inputs stay soft and structured"
            description="The form language uses airy spacing, rounded fields, and muted labels so data-heavy screens still feel approachable."
            strong
          >
            <div className="ds-form-grid">
              <DsField label="Account name">
                <DsInput placeholder="Household taxable" />
              </DsField>
              <DsField label="Category">
                <DsSelect defaultValue="brokerage">
                  <option value="brokerage">Brokerage</option>
                  <option value="retirement">Retirement</option>
                  <option value="india">India</option>
                </DsSelect>
              </DsField>
              <DsField label="Notes" full>
                <DsTextarea defaultValue="Use the warm background and strong ink pairing to keep dense forms feeling human." />
              </DsField>
            </div>
          </DsPanel>
        </section>

        <section className="ds-two-column">
          <DsPanel
            kicker="Tables"
            title="High-density data, still calm"
            description="Tables inherit the same border, text, and spacing system so analytical screens don’t feel detached from the rest of the product."
          >
            <div className="ds-table-wrap">
              <table className="ds-table">
                <thead>
                  <tr>
                    <th>Account</th>
                    <th>Category</th>
                    <th>Value</th>
                    <th>Return</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Household Taxable</td>
                    <td>Brokerage</td>
                    <td>$184,240</td>
                    <td>12.4%</td>
                  </tr>
                  <tr>
                    <td>Roth IRA</td>
                    <td>Retirement</td>
                    <td>$92,118</td>
                    <td>9.8%</td>
                  </tr>
                  <tr>
                    <td>India MF</td>
                    <td>India</td>
                    <td>$34,882</td>
                    <td>14.1%</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </DsPanel>

          <DsPanel
            kicker="Copy elsewhere"
            title="Portable setup"
            description="This is intentionally lightweight. You can copy it into another app without needing a custom build pipeline or CSS framework."
            strong
          >
            <DsCodeBlock>{installSnippet}</DsCodeBlock>
            <hr className="ds-divider" />
            <p className="ds-copy ds-copy--tight">
              If the next project is not React, keep `harbor.css`, mirror the token names from
              `harbor-design-system/tokens.json`, and recreate just the pieces you need in your framework
              of choice.
            </p>
          </DsPanel>
        </section>
      </DsStage>
    </DsTheme>
  );
}
