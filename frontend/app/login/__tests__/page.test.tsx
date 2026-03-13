import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import LoginPage from "@/app/login/page";
import { authService } from "@/lib/services/authService";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/lib/services/authService", async () => {
  const actual = await vi.importActual<typeof import("@/lib/services/authService")>(
    "@/lib/services/authService"
  );
  return {
    ...actual,
    authService: {
      ...actual.authService,
      login: vi.fn(),
      loginDemo: vi.fn(),
    },
  };
});

const loginMock = vi.mocked(authService.login);
const loginDemoMock = vi.mocked(authService.loginDemo);

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
    loginDemoMock.mockReset();
  });

  it("disables submit while login is in flight and re-enables after success", async () => {
    const pending = deferred<void>();
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

    pending.resolve();

    await waitFor(() => {
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

  it("logs in with demo credentials from the Try Demo button", async () => {
    loginDemoMock.mockResolvedValueOnce();

    render(<LoginPage />);

    fireEvent.click(screen.getByRole("button", { name: "Try Demo" }));

    await waitFor(() => {
      expect(loginDemoMock).toHaveBeenCalledTimes(1);
      expect(pushMock).toHaveBeenCalledWith("/dashboard");
    });

    expect(screen.getByLabelText("Username")).toHaveValue("demo");
    expect(screen.getByLabelText("Password")).toHaveValue("demo");
  });

  it("keeps centered layout and width-capped auth card classes", () => {
    const { container } = render(<LoginPage />);

    const main = container.querySelector("main");
    expect(main).not.toBeNull();
    expect(main!).toHaveClass("items-center");

    const heroTitle = screen.getByRole("heading", { name: "Quaero" });
    const heroColumn = heroTitle.parentElement;
    expect(heroColumn).not.toBeNull();
    expect(heroColumn!).toHaveClass(
      "max-w-md",
      "mx-auto",
      "text-center",
      "lg:max-w-none",
      "lg:mx-0",
      "lg:text-left"
    );

    const signInButton = screen.getByRole("button", { name: "Sign In" });
    const form = signInButton.closest("form");
    expect(form).not.toBeNull();
    const card = form!.parentElement;
    expect(card).not.toBeNull();
    expect(card!).toHaveClass("max-w-md", "mx-auto", "lg:max-w-none", "lg:mx-0");
  });
});
