import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import LoginPage from "@/app/login/page";
import { api, saveTokens } from "@/lib/api";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    saveTokens: vi.fn(),
    api: {
      ...actual.api,
      login: vi.fn(),
    },
  };
});

const loginMock = vi.mocked(api.login);
const saveTokensMock = vi.mocked(saveTokens);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("LoginPage form behavior", () => {
  beforeEach(() => {
    pushMock.mockReset();
    loginMock.mockReset();
    saveTokensMock.mockReset();
  });

  it("disables submit while login is in flight and re-enables after success", async () => {
    const pending = deferred<{ csrf_token: string; token_type: string }>();
    loginMock.mockReturnValueOnce(pending.promise);

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "alice" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    expect(screen.getByRole("button", { name: "Accessing..." })).toBeDisabled();

    pending.resolve({ csrf_token: "csrf-token", token_type: "bearer" });

    await waitFor(() => {
      expect(saveTokensMock).toHaveBeenCalledWith({
        csrf_token: "csrf-token",
        token_type: "bearer",
      });
      expect(pushMock).toHaveBeenCalledWith("/dashboard");
      expect(screen.getByRole("button", { name: "Sign In" })).toBeEnabled();
    });
  });

  it("renders API errors and re-enables submit", async () => {
    loginMock.mockRejectedValueOnce(new Error("Invalid credentials"));

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "alice" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "wrong-pass" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    expect(await screen.findByText("Invalid credentials")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign In" })).toBeEnabled();
  });
});
