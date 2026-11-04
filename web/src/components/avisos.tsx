import { CheckCircle2, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { cx } from "./ui";

type Toast = { id: number; texto: string; error?: boolean };

const Contexto = createContext<(texto: string, error?: boolean) => void>(() => {});

/** Notificaciones breves abajo a la derecha ("Estado actualizado", errores de la API...). */
export function ProveedorAvisos({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const avisar = useCallback((texto: string, error = false) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, texto, error }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);
  return (
    <Contexto.Provider value={avisar}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex flex-col gap-2" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={cx(
            "aparecer pointer-events-auto flex max-w-sm items-start gap-2 rounded-md border border-line bg-surface px-4 py-3 text-sm",
            t.error ? "text-bad" : "text-ink",
          )}>
            {t.error ? <XCircle className="mt-0.5 size-4 shrink-0" /> : <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" />}
            {t.texto}
          </div>
        ))}
      </div>
    </Contexto.Provider>
  );
}

export const useAvisos = () => useContext(Contexto);
