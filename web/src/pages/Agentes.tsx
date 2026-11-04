import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bot, Cpu, RotateCcw, Sparkles } from "lucide-react";
import { AGENTE } from "../agentes";
import { obtenerAgentes, type Actividad } from "../api";
import { Cargando, Encabezado, Insignia, Seccion, Tarjeta, Vacio, cx } from "../components/ui";

// Los tres flujos que coordina Batuta, en el orden real del grafo.
const FLUJOS: { titulo: string; descripcion: string; pasos: (string | { bucle: [string, string] })[] }[] = [
  {
    titulo: "Analizar una oferta",
    descripcion: "Cuando pegas una oferta, la envías con el marcador o la trae Sabueso.",
    pasos: ["batuta", "lupa", "archivero", "balanza"],
  },
  {
    titulo: "Adaptar tu CV",
    descripcion: "Preguntón pausa el flujo hasta que respondes; el Validador puede devolverle el texto a Pluma.",
    pasos: ["batuta", "balanza", "pregunton", { bucle: ["pluma", "validador"] }, "imprenta"],
  },
  {
    titulo: "Rutina diaria (8:00)",
    descripcion: "Corre sola con el Programador de tareas de Windows. Los lunes también actúa Brújula.",
    pasos: ["sabueso", "lupa", "balanza", "centinela", "brujula"],
  },
];

function hace(fecha: string) {
  const s = (Date.now() - new Date(fecha).getTime()) / 1000;
  if (s < 60) return "hace un momento";
  if (s < 3600) return `hace ${Math.round(s / 60)} min`;
  if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
  const d = Math.round(s / 86400);
  return d === 1 ? "ayer" : `hace ${d} días`;
}

function Avatar({ id, tamano = "size-10", activo }: { id: string; tamano?: string; activo?: boolean }) {
  const info = AGENTE[id];
  if (!info) return null;
  const Icono = info.icono;
  return (
    <span className="relative inline-flex shrink-0">
      <span className={cx("relative flex items-center justify-center rounded-md border bg-surface", activo ? "border-primary" : "border-line", tamano)}
            style={{ color: info.color }}>
        <Icono className="size-1/2" />
      </span>
    </span>
  );
}

function Chip({ id }: { id: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-md border border-line bg-surface px-2.5 py-1.5">
      <Avatar id={id} tamano="size-7" />
      <span className="text-sm font-semibold text-ink">{AGENTE[id]?.nombre}</span>
    </span>
  );
}

export default function Agentes() {
  // Se actualiza solo: si corre un flujo, la actividad aparece sin recargar.
  const { data, isLoading } = useQuery({ queryKey: ["agentes"], queryFn: obtenerAgentes, refetchInterval: 8000, staleTime: 0 });
  if (isLoading || !data) return <Cargando />;

  const ultima: Record<string, Actividad> = {};
  for (const a of data.actividad) if (!ultima[a.agente]) ultima[a.agente] = a;
  const recienteMs = 2 * 60 * 1000;
  const activo = (id: string) => !!ultima[id] && Date.now() - new Date(ultima[id].fecha).getTime() < recienteMs;

  return (
    <div className="aparecer">
      <Encabezado
        seccion="Sistema"
        titulo="Agentes"
        descripcion="Job-Intelligence funciona con un equipo de agentes, cada uno con una sola tarea. Batuta los coordina con LangGraph. Solo tres usan IA (Gemini); el resto es código que calcula, valida o guarda."
      />

      {/* Flujos */}
      <div className="grid gap-4 lg:grid-cols-3">
        {FLUJOS.map((f) => (
          <Tarjeta key={f.titulo} className="flex flex-col gap-3">
            <p className="font-semibold text-ink">{f.titulo}</p>
            <p className="text-sm text-ink-2">{f.descripcion}</p>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              {f.pasos.map((p, i) => (
                <span key={i} className="inline-flex items-center gap-1.5">
                  {i > 0 && <ArrowRight className="size-3.5 text-ink-3" />}
                  {typeof p === "string" ? <Chip id={p} /> : (
                    <span className="inline-flex items-center gap-1 rounded-md border border-dashed border-warn/60 p-1">
                      <Chip id={p.bucle[0]} />
                      <RotateCcw className="size-3.5 text-warn" aria-label="puede repetirse" />
                      <Chip id={p.bucle[1]} />
                    </span>
                  )}
                </span>
              ))}
            </div>
          </Tarjeta>
        ))}
      </div>

      {/* Equipo */}
      <Seccion titulo="El equipo">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.agentes.map((a) => {
            const ult = ultima[a.id];
            return (
              <Tarjeta key={a.id} className="flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <Avatar id={a.id} activo={activo(a.id)} />
                  <div className="min-w-0">
                    <p className="text-base font-semibold text-ink">{a.nombre}</p>
                    <p className="text-xs text-ink-3">{a.rol}</p>
                  </div>
                  {activo(a.id) && <Insignia tono="info">Activo</Insignia>}
                </div>
                <p className="text-sm leading-relaxed text-ink-2">{a.tarea}</p>
                <div className="flex flex-wrap gap-1.5">
                  {a.gemini
                    ? <Insignia tono="info" icono={Sparkles}>Gemini · {a.modelos[0]}</Insignia>
                    : <Insignia icono={Cpu}>Sin IA · Python</Insignia>}
                  {a.gemini && a.modelos.length > 1 && <Insignia>respaldo: {a.modelos.slice(1).join(", ")}</Insignia>}
                </div>
                <div className="mt-auto border-t border-line pt-3 text-xs">
                  {ult ? (
                    <p className="text-ink-2"><span className="font-semibold text-ink">{hace(ult.fecha)}:</span> {ult.resumen}</p>
                  ) : <p className="text-ink-3">Sin actividad registrada todavía.</p>}
                </div>
              </Tarjeta>
            );
          })}
        </div>
      </Seccion>

      {/* Actividad */}
      <Seccion titulo="Actividad reciente">
        {!data.actividad.length ? (
          <Vacio icono={Bot} titulo="Todavía no hay actividad">Analiza una oferta o adapta tu CV y verás aquí lo que hizo cada agente.</Vacio>
        ) : (
          <Tarjeta className="p-0">
            <ul>
              {data.actividad.slice(0, 25).map((a, i) => (
                <li key={i} className="flex items-start gap-3 border-b border-line px-5 py-3 last:border-0">
                  <Avatar id={a.agente} tamano="size-8" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-ink"><span className="font-semibold">{AGENTE[a.agente]?.nombre ?? a.agente}</span> · {a.resumen}</p>
                    <p className="text-xs text-ink-3">{hace(a.fecha)} · {new Date(a.fecha).toLocaleString("es-PE")}</p>
                  </div>
                  {a.estado !== "ok" && (
                    <Insignia tono={a.estado === "error" ? "bad" : a.estado === "detenido" ? "neutro" : "warn"}>
                      {{ pausa: "Pausa", rechazo: "Rechazó", detenido: "Se detuvo", error: "Error" }[a.estado] ?? a.estado}
                    </Insignia>
                  )}
                </li>
              ))}
            </ul>
          </Tarjeta>
        )}
      </Seccion>
    </div>
  );
}
