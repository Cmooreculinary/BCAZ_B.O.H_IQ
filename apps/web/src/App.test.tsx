import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import App, { formatMoney, titleCase } from "./App";


describe("BCAz B.O.H Global IQ shell", () => {
  beforeEach(() => window.localStorage.clear());

  it("renders the secure operator entry screen", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><App /></QueryClientProvider>);
    expect(screen.getByRole("heading", { name: /the back office/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /enter b\.o\.h iq/i })).toBeInTheDocument();
  });

  it("formats money and operating statuses consistently", () => {
    expect(formatMoney(2600)).toBe("$26.00");
    expect(titleCase("blocked_by_match_exception")).toBe("Blocked By Match Exception");
  });
});

