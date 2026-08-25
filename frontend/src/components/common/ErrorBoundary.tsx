// ErrorBoundary — 渲染异常兜底：可读错误 + 重试，取代 React 默认白屏
import React from 'react';
import './ErrorBoundary.css';

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error('[ErrorBoundary] 页面渲染异常：', error);
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div className="error-boundary" role="alert">
          <h1 className="font-display error-boundary-title">页面出错了</h1>
          <p className="error-boundary-message">{this.state.error.message}</p>
          <button type="button" className="btn btn-primary" onClick={this.handleReset}>
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}