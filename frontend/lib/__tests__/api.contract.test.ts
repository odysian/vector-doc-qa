import { describe, expect, it } from "vitest";
import * as apiModule from "@/lib/api";

describe("public api module contract", () => {
  it("exposes stable helpers and error types", () => {
    expect(typeof apiModule.isLoggedIn).toBe("function");
    expect(typeof apiModule.saveTokens).toBe("function");
    expect(typeof apiModule.loginAsDemo).toBe("function");
    expect(apiModule.ApiError).toBeDefined();
    expect(apiModule.SessionExpiredError).toBeDefined();
  });

  it("exposes stable api method surface", () => {
    expect(Object.keys(apiModule.api).sort()).toEqual([
      "deleteDocument",
      "getCurrentUser",
      "getDocumentFile",
      "getDocumentStatus",
      "getDocuments",
      "getMessages",
      "login",
      "logout",
      "processDocument",
      "queryDocument",
      "queryDocumentStream",
      "register",
      "uploadDocument",
    ]);
  });
});
