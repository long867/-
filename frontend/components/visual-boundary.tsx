"use client";

import { Component, type ReactNode } from "react";

/** Keep a visualization failure local so navigation and evidence remain usable. */
export class VisualBoundary extends Component<
  {
    children: ReactNode;
    fallback: (retry: () => void) => ReactNode;
    onRetry: () => void;
  },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: Error) {
    console.error("[MiningIntel visual]", error.message);
  }
  retry = () => {
    this.props.onRetry();
    this.setState({ failed: false });
  };
  render() {
    return this.state.failed
      ? this.props.fallback(this.retry)
      : this.props.children;
  }
}
