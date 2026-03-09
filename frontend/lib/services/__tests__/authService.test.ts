import { beforeEach, describe, expect, it, vi } from "vitest";
import { authService } from "@/lib/services/authService";
import { api, isLoggedIn, saveTokens } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    isLoggedIn: vi.fn(),
    saveTokens: vi.fn(),
    api: {
      ...actual.api,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    },
  };
});

const isLoggedInMock = vi.mocked(isLoggedIn);
const saveTokensMock = vi.mocked(saveTokens);
const loginMock = vi.mocked(api.login);
const registerMock = vi.mocked(api.register);
const logoutMock = vi.mocked(api.logout);

describe("authService", () => {
  beforeEach(() => {
    isLoggedInMock.mockReset();
    saveTokensMock.mockReset();
    loginMock.mockReset();
    registerMock.mockReset();
    logoutMock.mockReset();
  });

  it("returns local session state from hasActiveSession", () => {
    isLoggedInMock.mockReturnValueOnce(true);

    expect(authService.hasActiveSession()).toBe(true);
    expect(isLoggedInMock).toHaveBeenCalledTimes(1);
  });

  it("logs in and persists returned tokens", async () => {
    loginMock.mockResolvedValueOnce({
      csrf_token: "csrf-token",
      token_type: "bearer",
    });

    await authService.login({ username: "alice", password: "secret" });

    expect(loginMock).toHaveBeenCalledWith({
      username: "alice",
      password: "secret",
    });
    expect(saveTokensMock).toHaveBeenCalledWith({
      csrf_token: "csrf-token",
      token_type: "bearer",
    });
  });

  it("registers then logs in with the same credentials", async () => {
    registerMock.mockResolvedValueOnce({
      id: 1,
      username: "alice",
      email: "alice@example.com",
      is_demo: false,
      created_at: "2026-03-08T10:00:00Z",
    });
    loginMock.mockResolvedValueOnce({
      csrf_token: "csrf-token",
      token_type: "bearer",
    });

    await authService.registerAndLogin({
      username: "alice",
      email: "alice@example.com",
      password: "strong-password",
    });

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
  });

  it("logs in with seeded demo credentials", async () => {
    loginMock.mockResolvedValueOnce({
      csrf_token: "csrf-token",
      token_type: "bearer",
    });

    await authService.loginDemo();

    expect(loginMock).toHaveBeenCalledWith({
      username: "demo",
      password: "demo",
    });
  });

  it("delegates logout to api logout", async () => {
    logoutMock.mockResolvedValueOnce();

    await authService.logout();

    expect(logoutMock).toHaveBeenCalledTimes(1);
  });
});
