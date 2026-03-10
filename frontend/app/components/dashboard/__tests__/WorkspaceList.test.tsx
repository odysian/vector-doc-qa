import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceList } from "@/app/components/dashboard/WorkspaceList";
import type { Workspace } from "@/lib/api";

function makeWorkspace(overrides: Partial<Workspace> = {}): Workspace {
  return {
    id: 1,
    name: "Workspace A",
    user_id: 10,
    document_count: 2,
    created_at: "2026-03-10T00:00:00Z",
    updated_at: "2026-03-10T00:00:00Z",
    ...overrides,
  };
}

describe("WorkspaceList", () => {
  it("renders empty state when there are no workspaces", () => {
    render(
      <WorkspaceList
        workspaces={[]}
        onWorkspaceClick={vi.fn()}
        onCreate={vi.fn().mockResolvedValue(undefined)}
      />
    );

    expect(
      screen.getByText("No workspaces yet. Create one to group documents.")
    ).toBeInTheDocument();
  });

  it("renders workspace rows with document counts and handles workspace click", () => {
    const onWorkspaceClick = vi.fn();
    const firstWorkspace = makeWorkspace({ id: 5, name: "Alpha", document_count: 1 });
    const secondWorkspace = makeWorkspace({ id: 6, name: "Beta", document_count: 3 });

    render(
      <WorkspaceList
        workspaces={[firstWorkspace, secondWorkspace]}
        onWorkspaceClick={onWorkspaceClick}
        onCreate={vi.fn().mockResolvedValue(undefined)}
      />
    );

    expect(screen.getByText("1 document")).toBeInTheDocument();
    expect(screen.getByText("3 documents")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Beta 3 documents" }));
    expect(onWorkspaceClick).toHaveBeenCalledWith(secondWorkspace);
  });

  it("runs create flow callback with trimmed name and closes the form", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);

    render(
      <WorkspaceList
        workspaces={[]}
        onWorkspaceClick={vi.fn()}
        onCreate={onCreate}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    fireEvent.change(screen.getByPlaceholderText("Workspace name"), {
      target: { value: "   New Team Workspace   " },
    });
    const createForm = screen.getByPlaceholderText("Workspace name").closest("div");
    expect(createForm).toBeTruthy();
    fireEvent.click(within(createForm as HTMLElement).getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith("New Team Workspace");
    });
    expect(screen.queryByPlaceholderText("Workspace name")).not.toBeInTheDocument();
  });
});
