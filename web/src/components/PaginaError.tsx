import { AlertTriangle, RotateCcw } from "lucide-react";
import { useRouteError } from "react-router";

/** Se muestra si una página falla al dibujarse, en lugar de la pantalla técnica de React Router. */
export default function PaginaError() {
  const error = useRouteError();
  const detalle = error instanceof Error ? error.message : String(error);
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-6">
      <div className="max-w-md rounded-md border border-line bg-surface p-8 text-center">
        <span className="mx-auto flex size-12 items-center justify-center rounded-md bg-bad-soft text-bad">
          <AlertTriangle className="size-6" />
        </span>
        <h1 className="mt-4 text-lg font-semibold text-ink">Algo salió mal en esta página</h1>
        <p className="mt-2 text-sm text-ink-2">Tus datos no se perdieron. Vuelve al inicio o recarga la página.</p>
        <p className="mt-3 rounded bg-surface-2 px-3 py-2 font-mono text-xs text-ink-3">{detalle}</p>
        <div className="mt-5 flex justify-center gap-2">
          <a href="/" className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover">Ir al inicio</a>
          <button onClick={() => location.reload()} className="inline-flex items-center gap-1.5 rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-surface-2">
            <RotateCcw className="size-4" /> Recargar
          </button>
        </div>
      </div>
    </div>
  );
}
