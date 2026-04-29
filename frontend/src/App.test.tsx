import { render, screen } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  it("renders the AI Reality Check placeholder page", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "AI Reality Check" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("MVP scaffold for the accountability platform."),
    ).toBeInTheDocument();
  });
});
