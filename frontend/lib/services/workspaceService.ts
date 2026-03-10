import { requestJsonWithAuth } from "@/lib/api/http";
import type {
  Workspace,
  WorkspaceDetail,
  WorkspaceListResponse,
} from "@/lib/api.types";

export const workspaceService = {
  createWorkspace: async (name: string): Promise<Workspace> => {
    return requestJsonWithAuth<Workspace>("/api/workspaces/", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  },

  getWorkspaces: async (): Promise<WorkspaceListResponse> => {
    return requestJsonWithAuth<WorkspaceListResponse>("/api/workspaces/");
  },

  getWorkspace: async (workspaceId: number): Promise<WorkspaceDetail> => {
    return requestJsonWithAuth<WorkspaceDetail>(`/api/workspaces/${workspaceId}`);
  },

  updateWorkspace: async (workspaceId: number, name: string): Promise<Workspace> => {
    return requestJsonWithAuth<Workspace>(`/api/workspaces/${workspaceId}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
  },

  deleteWorkspace: async (workspaceId: number): Promise<void> => {
    await requestJsonWithAuth<{ message: string }>(`/api/workspaces/${workspaceId}`, {
      method: "DELETE",
    });
  },

  addWorkspaceDocuments: async (
    workspaceId: number,
    documentIds: number[]
  ): Promise<WorkspaceDetail> => {
    return requestJsonWithAuth<WorkspaceDetail>(`/api/workspaces/${workspaceId}/documents`, {
      method: "POST",
      body: JSON.stringify({ document_ids: documentIds }),
    });
  },

  removeWorkspaceDocument: async (
    workspaceId: number,
    documentId: number
  ): Promise<WorkspaceDetail> => {
    return requestJsonWithAuth<WorkspaceDetail>(
      `/api/workspaces/${workspaceId}/documents/${documentId}`,
      {
        method: "DELETE",
      }
    );
  },
};
