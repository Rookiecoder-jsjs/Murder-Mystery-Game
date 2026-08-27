import { createContext } from 'react';

export type ToastKind = 'info' | 'error' | 'success';

export interface ToastContextValue {
  notify: (message: string, kind?: ToastKind) => void;
}

export const ToastContext = createContext<ToastContextValue>({
  notify: () => {},
});
