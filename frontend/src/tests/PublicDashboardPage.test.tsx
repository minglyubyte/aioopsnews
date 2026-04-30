import { render, screen } from "@testing-library/react";

import { RouteEntry } from "../main";

describe("RouteEntry", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
  });

  it("renders the public dashboard on the root route without admin controls", () => {
    render(<RouteEntry />);

    expect(
      screen.getByRole("heading", { name: "Public dashboard" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Unlock admin" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Admin token")).not.toBeInTheDocument();
  });
});
