import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import Home from "@/app/page";
import { authService } from "@/lib/services/authService";

const pushMock = vi.fn();
const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: replaceMock,
  }),
}));

vi.mock("@/lib/services/authService", () => {
  return {
    authService: {
      hasActiveSession: vi.fn(),
      loginDemo: vi.fn(),
    },
  };
});

const hasActiveSessionMock = vi.mocked(authService.hasActiveSession);
const loginDemoMock = vi.mocked(authService.loginDemo);

describe("Home page Try Demo behavior", () => {
  beforeEach(() => {
    pushMock.mockReset();
    replaceMock.mockReset();
    hasActiveSessionMock.mockReset();
    loginDemoMock.mockReset();
    hasActiveSessionMock.mockReturnValue(false);
  });

  it("redirects authenticated users to dashboard", async () => {
    hasActiveSessionMock.mockReturnValueOnce(true);

    render(<Home />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("logs in demo user and routes directly to dashboard", async () => {
    loginDemoMock.mockResolvedValueOnce();

    render(<Home />);

    fireEvent.click(screen.getByRole("button", { name: "Try Demo" }));

    await waitFor(() => {
      expect(loginDemoMock).toHaveBeenCalledTimes(1);
      expect(pushMock).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("keeps centered hero/layout presentation classes", () => {
    const { container } = render(<Home />);

    const main = container.querySelector("main");
    const section = container.querySelector("main section");

    expect(main).not.toBeNull();
    expect(main!).toHaveClass("items-center");
    expect(section).not.toBeNull();
    expect(section!).toHaveClass("items-center");

    const heroTitle = screen.getByRole("heading", { name: "Quaero" });
    const heroColumn = heroTitle.parentElement;
    expect(heroColumn).not.toBeNull();
    expect(heroColumn!).toHaveClass("max-w-xl", "text-center", "lg:text-left");

    const howItWorksLabel = screen.getByText("How It Works");
    const howItWorksCard = howItWorksLabel.closest("div");
    expect(howItWorksCard).not.toBeNull();
    expect(howItWorksCard!).toHaveClass("max-w-md", "mx-auto", "lg:max-w-none", "lg:mx-0");
  });
});
