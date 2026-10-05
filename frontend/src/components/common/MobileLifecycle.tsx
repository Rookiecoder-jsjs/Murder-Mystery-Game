import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { App } from '@capacitor/app';
import { isAndroid } from '../../api/native';
import { mobileBackTarget } from '../../utils/mobileLibrary';

export function MobileLifecycle() {
  const navigate = useNavigate();
  const { pathname, state } = useLocation();
  useEffect(() => {
    if (!isAndroid) return;
    const viewport = window.visualViewport;
    let fullHeight = viewport?.height ?? window.innerHeight;
    let fullWidth = viewport?.width ?? window.innerWidth;
    let keyboardVisible = false;
    const updateKeyboard = () => {
      const height = viewport?.height ?? window.innerHeight;
      const width = viewport?.width ?? window.innerWidth;
      if (Math.abs(width - fullWidth) > 80) {
        fullWidth = width;
        fullHeight = height;
      }
      fullHeight = Math.max(fullHeight, height);
      const editing = document.activeElement instanceof HTMLElement &&
        document.activeElement.matches('input,textarea');
      // adjustResize shrinks the WebView; focus alone also occurs after the IME closes.
      keyboardVisible = editing && fullHeight - height > 120;
      document.documentElement.classList.toggle('native-keyboard-open', keyboardVisible);
    };
    window.addEventListener('resize', updateKeyboard);
    viewport?.addEventListener('resize', updateKeyboard);
    document.addEventListener('focusin', updateKeyboard);
    document.addEventListener('focusout', updateKeyboard);
    updateKeyboard();
    const resume = App.addListener('appStateChange', ({ isActive }) => {
      if (isActive) {
        updateKeyboard();
        window.dispatchEvent(new Event('mystery:resume'));
      }
    });
    const back = App.addListener('backButton', () => {
      const overlay = document.querySelector('.modal-overlay');
      if (overlay) { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })); return; }
      const event = new Event('mystery:back', { cancelable: true });
      if (!window.dispatchEvent(event)) return;
      updateKeyboard();
      const hideKeyboard = keyboardVisible;
      if (document.activeElement instanceof HTMLElement && document.activeElement.matches('input,textarea')) {
        document.activeElement.blur();
      }
      if (hideKeyboard) return;
      if (pathname !== '/') navigate(mobileBackTarget(pathname, state), { replace: true });
      else void App.exitApp();
    });
    return () => {
      void resume.then(handle => handle.remove());
      void back.then(handle => handle.remove());
      window.removeEventListener('resize', updateKeyboard);
      viewport?.removeEventListener('resize', updateKeyboard);
      document.removeEventListener('focusin', updateKeyboard);
      document.removeEventListener('focusout', updateKeyboard);
      document.documentElement.classList.remove('native-keyboard-open');
    };
  }, [navigate, pathname, state]);
  return null;
}
