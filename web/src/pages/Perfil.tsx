import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Plus } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { useAvisos } from "../components/avisos";
import {
  Boton, Campo, Cargando, Encabezado, Insignia, Segmentado, Tarjeta, Vacio, claseCampo,
} from "../components/ui";
import { User } from "lucide-react";

const CATEGORIAS = ["Programming", "Database", "Cloud", "BI_Tool", "Automation_Tool", "Framework", "Methodology", "Soft_Skill", "Other"];
type Pestana = "Habilidades" | "CV base" | "Respuestas al Preguntón";

export default function Perfil() {
  const { data, isLoading } = useQuery({ queryKey: ["perfil"], queryFn: api.perfil });
  const [pestana, setPestana] = useState<Pestana>("Habilidades");

  if (isLoading || !data) return <Cargando />;

  return (
    <div className="aparecer">
      <Encabezado seccion="Tú" titulo="Mi perfil" descripcion="Tus habilidades, tu CV base y lo que respondiste al Preguntón." />
      <div className="mb-6">
        <Segmentado etiqueta="Sección del perfil" opciones={["Habilidades", "CV base", "Respuestas al Preguntón"] as Pestana[]}
                    valor={pestana} onChange={setPestana} />
      </div>

      {pestana === "Habilidades" && (
        <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
          <div className="overflow-x-auto rounded-md border border-line bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-2 text-xs text-ink-2 uppercase">
                <tr>
                  <th className="px-4 py-3 font-semibold">Tecnología</th>
                  <th className="px-4 py-3 font-semibold">Categoría</th>
                  <th className="px-4 py-3 font-semibold">Nivel</th>
                  <th className="px-4 py-3 font-semibold">Evidencia</th>
                </tr>
              </thead>
              <tbody>
                {data.habilidades.map((h) => (
                  <tr key={h.tecnologia} className="border-t border-line">
                    <td className="px-4 py-2.5 font-medium text-ink">{h.tecnologia}</td>
                    <td className="px-4 py-2.5 text-ink-2">{h.categoria.replace("_", " ")}</td>
                    <td className="px-4 py-2.5"><Insignia tono="info">{h.nivel}</Insignia></td>
                    <td className="px-4 py-2.5 text-ink-2">{h.evidencia}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <NuevaHabilidad />
        </div>
      )}

      {pestana === "CV base" && (data.cv ? (
        <div className="flex flex-col gap-4">
          <Tarjeta>
            <p className="text-lg font-semibold text-ink">{data.cv.nombre}</p>
            <p className="mt-2 text-sm leading-relaxed text-ink-2">{data.cv.perfil}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Insignia tono="info">{data.cv.experiencias} experiencia(s)</Insignia>
              <Insignia tono="info">{data.cv.proyectos.length} proyectos</Insignia>
              <Insignia tono="info">{data.cv.habilidades} habilidades</Insignia>
            </div>
            <p className="mt-4 text-xs text-ink-3">Pluma solo puede usar lo que está aquí. Se edita en data/cv_base.yaml.</p>
          </Tarjeta>
          {data.cv.proyectos.map((p) => (
            <details key={p.nombre} className="group rounded-md border border-line bg-surface p-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 font-semibold text-ink">
                {p.nombre}<ChevronDown className="size-4 shrink-0 text-ink-3 transition group-open:rotate-180" />
              </summary>
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-ink-2">{p.logros.map((l) => <li key={l}>{l}</li>)}</ul>
              <div className="mt-3 flex flex-wrap gap-1.5">{p.stack.map((s) => <Insignia key={s}>{s}</Insignia>)}</div>
            </details>
          ))}
        </div>
      ) : <Vacio icono={User} titulo="No hay CV base">Copia data/cv_base.example.yaml como data/cv_base.yaml y complétalo.</Vacio>)}

      {pestana === "Respuestas al Preguntón" && (data.respuestas.length ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.respuestas.map((r) => (
            <Tarjeta key={r.tecnologia} className="p-4">
              <div className="flex items-center justify-between gap-2">
                <p className="font-semibold text-ink">{r.tecnologia}</p>
                <Insignia tono={r.la_tengo ? "ok" : "neutro"}>{r.la_tengo ? `Sí · ${r.nivel ?? ""}` : "No la tengo"}</Insignia>
              </div>
              {r.donde && <p className="mt-1 text-sm text-ink-2">{r.donde}{r.detalle && ` — ${r.detalle}`}</p>}
            </Tarjeta>
          ))}
        </div>
      ) : <Vacio icono={User} titulo="Todavía no respondiste preguntas" />)}
    </div>
  );
}

function NuevaHabilidad() {
  const [f, setF] = useState({ nombre: "", categoria: "Programming", nivel: "basico", meses: "", evidencia: "" });
  const qc = useQueryClient();
  const avisar = useAvisos();
  const guardar = useMutation({
    mutationFn: () => api.guardarHabilidad({
      nombre: f.nombre.trim(), categoria: f.categoria, nivel: f.nivel, evidencia: f.evidencia.trim(),
      meses_experiencia: f.meses ? Number(f.meses) : undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries();
      avisar(`${f.nombre.trim()} guardado. Tus Match Score se recalcularon.`);
      setF({ ...f, nombre: "", meses: "", evidencia: "" });
    },
    onError: (e) => avisar(e.message, true),
  });
  const valido = f.nombre.trim() && f.evidencia.trim();

  return (
    <Tarjeta className="h-fit">
      <p className="mb-4 font-semibold text-ink">Agregar o actualizar una habilidad</p>
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (valido) guardar.mutate(); }}>
        <Campo etiqueta="Tecnología"><input className={claseCampo} value={f.nombre} placeholder="Ej.: dbt" onChange={(e) => setF({ ...f, nombre: e.target.value })} /></Campo>
        <div className="grid grid-cols-2 gap-3">
          <Campo etiqueta="Categoría">
            <select className={claseCampo} value={f.categoria} onChange={(e) => setF({ ...f, categoria: e.target.value })}>
              {CATEGORIAS.map((c) => <option key={c} value={c}>{c.replace("_", " ")}</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Nivel">
            <select className={claseCampo} value={f.nivel} onChange={(e) => setF({ ...f, nivel: e.target.value })}>
              <option value="basico">Básico</option><option value="intermedio">Intermedio</option><option value="avanzado">Avanzado</option>
            </select>
          </Campo>
        </div>
        <Campo etiqueta="Meses de experiencia (opcional)"><input type="number" min={0} className={claseCampo} value={f.meses} onChange={(e) => setF({ ...f, meses: e.target.value })} /></Campo>
        <Campo etiqueta="Evidencia" ayuda="Dónde lo usaste: es lo que te respalda en una entrevista.">
          <input className={claseCampo} value={f.evidencia} placeholder="Proyecto, trabajo o curso" onChange={(e) => setF({ ...f, evidencia: e.target.value })} />
        </Campo>
        <Boton type="submit" variante="primario" icono={Plus} cargando={guardar.isPending} disabled={!valido}>Guardar y recalcular</Boton>
      </form>
    </Tarjeta>
  );
}
