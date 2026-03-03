import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import RegisterPage from "@/app/register/page";
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
      register: vi.fn(),
      login: vi.fn(),
    },
  };
});

const registerMock = vi.mocked(api.register);
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

describe("RegisterPage form behavior", () => {
  beforeEach(() => {
    pushMock.mockReset();
    registerMock.mockReset();
    loginMock.mockReset();
    saveTokensMock.mockReset();
  });

  it("disables submit while registering and re-enables after success", async () => {
    const pendingRegistration = deferred<{
      id: number;
      username: string;
      email: string;
      created_at: string;
    }>();
    registerMock.mockReturnValueOnce(pendingRegistration.promise);
    loginMock.mockResolvedValueOnce({
      csrf_token: "csrf-token",
      token_type: "bearer",
    });

    render(<RegisterPage />);

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "alice" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "alice@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "strong-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Register" }));

    expect(
      screen.getByRole("button", { name: "Creating account..." })
    ).toBeDisabled();

    pendingRegistration.resolve({
      id: 1,
      username: "alice",
      email: "alice@example.com",
      created_at: "2026-03-02T10:00:00Z",
    });

    await waitFor(() => {
      expect(registerMock).toHaveBeenCalledWith({
        username: "alice",
        email: "alice@example.com",
        password: "strong-password",
      });
      expect(loginMock).toHaveBeenCalledWith({
        username: "alice",
        password: "strong-password",
      });
      expect(saveTokensMock).toHaveBeenCalledWith({
        csrf_token: "csrf-token",
        token_type: "bearer",
      });
      expect(pushMock).toHaveBeenCalledWith("/dashboard");
      expect(screen.getByRole("button", { name: "Register" })).toBeEnabled();
    });
  });

  it("renders API errors and re-enables submit", async () => {
    registerMock.mockRejectedValueOnce(new Error("Username already exists"));

    render(<RegisterPage />);

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "alice" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "alice@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "strong-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Register" }));

    expect(await screen.findByText("Username already exists")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register" })).toBeEnabled();
  });
});
