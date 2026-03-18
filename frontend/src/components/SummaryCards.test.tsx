import { render, screen } from "@testing-library/react";

import { SummaryCards } from "./SummaryCards";

describe("SummaryCards", () => {
  it("renders formatted portfolio metrics", () => {
    render(
      <SummaryCards
        summary={{
          total_value: "125000.25",
          total_cost_basis: "101000.11",
          gain_loss: "24000.14",
          return_pct: "23.76",
          estimated_dividends: "1825.45",
        }}
      />,
    );

    expect(screen.getByText("Portfolio Value")).toBeInTheDocument();
    expect(screen.getByText("$125,000.25")).toBeInTheDocument();
    expect(screen.getByText("+23.76%")).toBeInTheDocument();
  });
});
