import { Check, Octagon, Pause, RotateCcw, X } from "lucide-react";
import { AGENTE, type EstadoPaso, type Paso } from "../agentes";
import { cx } from "./ui";

const ETIQUETA: Record<EstadoPaso, string> = {
  trabajando: "Trabajando",
  ok: "Listo",
  detenido: "Se detuvo",
  pausa: "Esperándote",
  rechazo: "Rechazó",
  error: "Error",
};

const TONO: Record<EstadoPaso, string> = {
  trabajando: "bg-primary-soft text-primary",
  ok: "bg-ok-soft text-ok",
  detenido: "bg-surface-2 text-ink-2",
  pausa: "bg-warn-soft text-warn",
  rechazo: "bg-warn-soft text-warn",
  error: "bg-bad-soft text-bad",
};

function IconoEstado({ estado }: { estado: EstadoPaso }) {
  const clase = "size-3";
  if (estado === "ok") return <Check className={clase} />;
  if (estado === "pausa") return <Pause className={clase} />;
  if (estado === "rechazo") return <RotateCcw className={clase} />;
  if (estado === "error") return <X className={clase} />;
  if (estado === "detenido") return <Octagon className={clase} />;
  return <span className="size-1.5 animate-pulse rounded-full bg-current" />;
}

/**
 * Los agentes trabajando en vivo: cada fila aparece cuando el agente
 * empieza y se completa cuando termina (eventos reales de LangGraph).
 * `esperados` muestra en gris a los que aún no les toca.
 */
export default function LineaAgentes({ titulo, pasos, esperados = [] }: {
  titulo: string; pasos: Paso[]; esperados?: string[];
}) {
  const yaAparecieron = new Set(pasos.map((p) => p.agente));
  const pendientes = esperados.filter((a) => !yaAparecieron.has(a));
  const trabajando = pasos.some((p) => p.estado === "trabajando");

  return (
    <div className="rounded-md border border-line bg-surface p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-ink">{titulo}</p>
        {trabajando && (
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
            <span className="size-1.5 animate-pulse rounded-full bg-primary" />
            En vivo
          </span>
        )}
      </div>
      <ol className="relative">
        {pasos.map((p, i) => <Fila key={p.id} paso={p} ultimo={i === pasos.length - 1 && !pendientes.length} />)}
        {pendientes.map((a, i) => (
          <Fila key={`pend-${a}`} paso={{ id: -1, nodo: a, agente: a, estado: "trabajando", texto: "En espera" }}
                ultimo={i === pendientes.length - 1} enEspera />
        ))}
      </ol>
    </div>
  );
}

function Fila({ paso, ultimo, enEspera }: { paso: Paso; ultimo: boolean; enEspera?: boolean }) {
  const info = AGENTE[paso.agente] ?? { nombre: paso.agente, rol: "", icono: Check, color: "#888" };
  const Icono = info.icono;
  const activo = paso.estado === "trabajando" && !enEspera;
  return (
    <li className={cx("aparecer relative flex gap-3.5 pb-4 last:pb-0", enEspera && "opacity-45")}>
      {!ultimo && <span className="absolute top-9 bottom-0 left-[17px] w-px bg-line" aria-hidden />}
      <span className="relative shrink-0">
        <span
          className={cx("relative flex size-9 items-center justify-center rounded-md border bg-surface",
            activo ? "border-primary" : "border-line")}
          style={{ color: enEspera ? "var(--text-3)" : info.color }}
        >
          <Icono className="size-[18px]" />
        </span>
      </span>
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold text-ink">{info.nombre}</span>
          <span className="text-xs text-ink-3">{info.rol}</span>
          {!enEspera && (
            <span className={cx("inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-[11px] font-medium", TONO[paso.estado])}>
              <IconoEstado estado={paso.estado} /> {ETIQUETA[paso.estado]}
            </span>
          )}
          {paso.ms != null && <span className="font-mono text-[11px] text-ink-3 tabular-nums">{(paso.ms / 1000).toFixed(1)} s</span>}
        </div>
        <p className={cx("mt-0.5 text-sm", activo ? "text-ink-2" : "text-ink")}>
          {paso.texto}{activo && <span className="animate-pulse">…</span>}
        </p>
      </div>
    </li>
  );
}
