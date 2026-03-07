import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import Home from "@/app/page";
import { isLoggedIn, loginAsDemo } from "@/lib/api";

const pushMock = vi.fn();
const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: replaceMock,
  }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    isLoggedIn: vi.fn(),
    loginAsDemo: vi.fn(),
  };
});

const isLoggedInMock = vi.mocked(isLoggedIn);
const loginAsDemoMock = vi.mocked(loginAsDemo);

describe("Home page Try Demo behavior", () => {
  beforeEach(() => {
    pushMock.mockReset();
    replaceMock.mockReset();
    isLoggedInMock.mockReset();
    loginAsDemoMock.mockReset();
    isLoggedInMock.mockReturnValue(false);
  });

  it("redirects authenticated users to dashboard", async () => {
    isLoggedInMock.mockReturnValueOnce(true);

    render(<Home />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("logs in demo user and routes directly to dashboard", async () => {
    loginAsDemoMock.mockResolvedValueOnce();

    render(<Home />);

    fireEvent.click(screen.getByRole("button", { name: "Try Demo" }));

    await waitFor(() => {
      expect(loginAsDemoMock).toHaveBeenCalledTimes(1);
      expect(pushMock).toHaveBeenCalledWith("/dashboard");
    });
  });
});
