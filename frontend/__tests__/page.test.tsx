import { render, screen } from "@testing-library/react";

import HomePage from "../app/page";

describe("HomePage", () => {
  it("renders the project placeholder copy", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { name: /ai reality check/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/mvp scaffold for the accountability platform/i),
    ).toBeInTheDocument();
  });
});
