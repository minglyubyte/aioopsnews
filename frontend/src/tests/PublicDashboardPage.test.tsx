import { render, screen } from "@testing-library/react";

import { RouteEntry } from "../main";

describe("RouteEntry", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
  });

  it("renders the public route reader contract without internal review UI", () => {
    render(<RouteEntry />);

    expect(
      screen.getByRole("heading", { name: "AI Reality Check" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "A calm feed of reviewed AI failures, grounded in credible reporting.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Editor queue" }),
    ).not.toBeInTheDocument();
  });
});
