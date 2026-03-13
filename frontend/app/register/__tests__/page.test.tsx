import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import RegisterPage from "@/app/register/page";
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
      registerAndLogin: vi.fn(),
    },
  };
});

const registerAndLoginMock = vi.mocked(authService.registerAndLogin);

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
    registerAndLoginMock.mockReset();
  });

  it("disables submit while registering and re-enables after success", async () => {
    const pendingRegistration = deferred<void>();
    registerAndLoginMock.mockReturnValueOnce(pendingRegistration.promise);

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

    pendingRegistration.resolve();

    await waitFor(() => {
      expect(registerAndLoginMock).toHaveBeenCalledWith({
        username: "alice",
        email: "alice@example.com",
        password: "strong-password",
      });
      expect(pushMock).toHaveBeenCalledWith("/dashboard");
      expect(screen.getByRole("button", { name: "Register" })).toBeEnabled();
    });
  });

  it("renders API errors and re-enables submit", async () => {
    registerAndLoginMock.mockRejectedValueOnce(new Error("Username already exists"));

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

  it("keeps centered layout and width-capped auth card classes", () => {
    const { container } = render(<RegisterPage />);

    const main = container.querySelector("main");
    expect(main).not.toBeNull();
    expect(main!).toHaveClass("items-center");

    const registerButton = screen.getByRole("button", { name: "Register" });
    const form = registerButton.closest("form");
    expect(form).not.toBeNull();
    const card = form!.parentElement;
    expect(card).not.toBeNull();
    expect(card!).toHaveClass("max-w-md", "mx-auto", "lg:max-w-none", "lg:mx-0");
  });
});
