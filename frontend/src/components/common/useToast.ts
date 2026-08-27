import { useContext } from 'react';
import { ToastContext, type ToastContextValue, type ToastKind } from './ToastContext';

export function useToast(): ToastContextValue {
  return useContext(ToastContext);
}

export type { ToastKind };
