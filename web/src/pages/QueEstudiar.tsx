import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Compass, FileDown, GraduationCap, Plus, Sparkles } from "lucide-react";
import { useState } from "react";
import { api, urlArchivo } from "../api";
import { useAvisos } from "../components/avisos";
import {
  Aviso, Boton, Campo, Cargando, Encabezado, Insignia, Seccion, Tarjeta, Vacio, claseCampo, plural,
} from "../components/ui";

const MUESTRA_MINIMA = 10;

export default function QueEstudiar() {
  const { data, isLoading } = useQuery({ queryKey: ["brujula"], queryFn: api.brujula });
  const qc = useQueryClient();
  const avisar = useAvisos();

  const plan = useMutation({
    mutationFn: api.generarPlan,
    onSuccess: (r) => (r.error ? avisar(r.error, true) : qc.invalidateQueries({ queryKey: ["brujula"] })),
    onError: (e) => avisar(e.message, true),
  });
  const informe = useMutation({
    mutationFn: api.informeBrujula,
    onSuccess: (r) => { window.location.href = urlArchivo(r.ruta); },
    onError: (e) => avisar(e.message, true),
  });

  if (isLoading || !data) return <Cargando />;
  const max = Math.max(...data.prioridades.map((p) => p.prioridad), 0.0001);

  return (
    <div className="aparecer">
      <Encabezado
        seccion="Tú"
        titulo="Qué estudiar"
        descripcion="Brújula ordena lo que te falta según cuántas de tus ofertas lo piden, qué tan lejos estás y si su demanda sube."
        acciones={<Boton icono={FileDown} cargando={informe.isPending} onClick={() => informe.mutate()}>Informe en Word</Boton>}
      />

      {data.total_ofertas === 0 ? (
        <Vacio icono={Compass} titulo="Aún no hay ofertas">Analiza algunas o deja que Sabueso las traiga.</Vacio>
      ) : (
        <>
          {data.total_ofertas < MUESTRA_MINIMA && (
            <div className="mb-5">
              <Aviso tono="warn">
                Calculado con {plural(data.total_ofertas, "oferta", "ofertas")}. Con menos de {MUESTRA_MINIMA} el ranking refleja
                tus ofertas, no el mercado; la tendencia aparecerá cuando haya ofertas de al menos dos meses.
              </Aviso>
            </div>
          )}

          {data.prioridades.length === 0 ? (
            <Aviso tono="ok">Cubres todo lo que piden tus ofertas.</Aviso>
          ) : (
            <Tarjeta className="p-0">
              <ul>
                {data.prioridades.slice(0, 12).map((p, i) => (
                  <li key={p.tecnologia} className="flex flex-wrap items-center gap-4 border-b border-line px-5 py-3.5 last:border-0">
                    <span className="w-6 font-mono text-sm text-ink-3">{i + 1}</span>
                    <div className="min-w-40 flex-1">
                      <p className="font-semibold text-ink">{p.tecnologia}</p>
                      <p className="text-xs text-ink-2">
                        En {plural(p.ofertas, "oferta", "ofertas")} · obligatoria en {p.obligatoria_en} · tendencia: {p.tendencia_txt}
                      </p>
                    </div>
                    <Insignia tono={p.estado === "Te falta" ? "bad" : "warn"}>{p.estado}</Insignia>
                    <div className="flex w-36 items-center gap-2" title="Prioridad = demanda × distancia × tendencia">
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
                        <div className="h-full rounded-full bg-primary" style={{ width: `${(p.prioridad / max) * 100}%` }} />
                      </div>
                      <span className="w-9 text-right text-xs font-semibold text-ink-2">{p.prioridad.toFixed(2)}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </Tarjeta>
          )}

          <Seccion
            titulo="Plan de estudio"
            extra={<Boton variante="primario" icono={Sparkles} cargando={plan.isPending} onClick={() => plan.mutate()}>
              {data.plan ? "Actualizar con Gemini" : "Generar con Gemini"}
            </Boton>}
          >
            {data.plan ? (
              <>
                <p className="mb-1 text-xs text-ink-3">Generado el {new Date(data.plan.generado).toLocaleString("es-PE")}</p>
                <p className="mb-4 text-sm leading-relaxed text-ink-2">{data.plan.plan.resumen}</p>
                <div className="grid gap-4 md:grid-cols-2">
                  {data.plan.plan.items.map((it) => (
                    <Tarjeta key={it.tecnologia} className="flex flex-col gap-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="flex items-center gap-2 text-base font-semibold text-ink"><GraduationCap className="size-5 text-primary" />{it.tecnologia}</p>
                        <Insignia tono="info">~{it.semanas} semanas</Insignia>
                      </div>
                      <p className="text-sm text-ink-2">{it.por_que}</p>
                      <ul className="list-disc space-y-1 pl-5 text-sm text-ink">{it.que_aprender.map((t) => <li key={t}>{t}</li>)}</ul>
                      <p className="rounded-md bg-surface-2 px-3 py-2 text-sm text-ink"><b>Proyecto:</b> {it.proyecto}</p>
                    </Tarjeta>
                  ))}
                </div>
              </>
            ) : <p className="text-sm text-ink-2">Todavía no hay plan. Gemini lo arma para tus 5 primeras prioridades.</p>}
          </Seccion>

          {data.prioridades.length > 0 && <YaLoAprendi opciones={data.prioridades.map((p) => ({ tecnologia: p.tecnologia, categoria: p.categoria }))} />}
        </>
      )}
    </div>
  );
}

function YaLoAprendi({ opciones }: { opciones: { tecnologia: string; categoria: string }[] }) {
  const [tech, setTech] = useState(opciones[0].tecnologia);
  const [nivel, setNivel] = useState("basico");
  const [evidencia, setEvidencia] = useState("");
  const qc = useQueryClient();
  const avisar = useAvisos();
  const guardar = useMutation({
    mutationFn: () => api.guardarHabilidad({
      nombre: tech, categoria: opciones.find((o) => o.tecnologia === tech)!.categoria, nivel, evidencia: evidencia.trim(),
    }),
    onSuccess: () => { qc.invalidateQueries(); avisar(`${tech} agregado a tu perfil.`); setEvidencia(""); },
    onError: (e) => avisar(e.message, true),
  });
  return (
    <Seccion titulo="Ya lo aprendí">
      <Tarjeta>
        <p className="mb-4 text-sm text-ink-2">Marca solo lo que puedas demostrar. Se agrega a tu perfil y se recalculan tus Match Score.</p>
        <form className="grid gap-3 md:grid-cols-[1fr_160px_2fr_auto] md:items-end"
              onSubmit={(e) => { e.preventDefault(); if (evidencia.trim()) guardar.mutate(); }}>
          <Campo etiqueta="Tecnología">
            <select className={claseCampo} value={tech} onChange={(e) => setTech(e.target.value)}>
              {opciones.map((o) => <option key={o.tecnologia}>{o.tecnologia}</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Nivel">
            <select className={claseCampo} value={nivel} onChange={(e) => setNivel(e.target.value)}>
              <option value="basico">Básico</option><option value="intermedio">Intermedio</option><option value="avanzado">Avanzado</option>
            </select>
          </Campo>
          <Campo etiqueta="Evidencia">
            <input className={claseCampo} value={evidencia} onChange={(e) => setEvidencia(e.target.value)} placeholder="Proyecto en GitHub, curso con laboratorio..." />
          </Campo>
          <Boton type="submit" variante="primario" icono={Plus} cargando={guardar.isPending} disabled={!evidencia.trim()}>Agregar</Boton>
        </form>
      </Tarjeta>
    </Seccion>
  );
}
