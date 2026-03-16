"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  variant?: "page" | "inline";
}

interface ErrorBoundaryState {
  hasError: boolean;
  errorMessage: string;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, errorMessage: "" };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, errorMessage: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Log for observability without exposing raw stack traces to users.
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children;
    }

    const isPage = this.props.variant !== "inline";

    return (
      <div
        className={
          isPage
            ? "flex flex-col items-center justify-center h-full gap-4 p-8 text-center"
            : "flex flex-col items-center justify-center gap-3 p-6 text-center"
        }
        role="alert"
      >
        <p className="text-zinc-300 font-medium">Something went wrong</p>
        <p className="text-zinc-500 text-sm max-w-sm">
          An unexpected error occurred. Reload the page to continue.
        </p>
        <button
          onClick={this.handleReload}
          className="ui-btn ui-btn-secondary text-sm mt-2"
        >
          Reload
        </button>
      </div>
    );
  }
}
