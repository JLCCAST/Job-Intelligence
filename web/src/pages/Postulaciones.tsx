import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban, Briefcase, Download, Eye, FilePen, Inbox, MessagesSquare, PartyPopper, Save, Send, Trash2, type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { api, urlArchivo, type Oferta } from "../api";
import { useAvisos } from "../components/avisos";
import {
  Boton, Campo, Cargando, Encabezado, Insignia, InsigniaEncaje, Seccion, Tarjeta, Vacio, claseCampo, cx, fechaCorta,
  formatoScore,
} from "../components/ui";

const ICONOS: Record<string, LucideIcon> = {
  Registrada: Inbox, Analizada: Eye, Postulada: Send, Entrevista: MessagesSquare,
  Oferta: PartyPopper, Rechazada: Ban, Descartada: Trash2,
};

export default function Postulaciones() {
  const { data: ofertas, isLoading } = useQuery({ queryKey: ["ofertas"], queryFn: api.ofertas });
  const { data: estados } = useQuery({ queryKey: ["estados"], queryFn: api.estados, staleTime: Infinity });
  const [filtro, setFiltro] = useState<string | null>(null);
  const [elegida, setElegida] = useState<number | null>(null);

  if (isLoading || !ofertas || !estados) return <Cargando />;
  if (!ofertas.length) {
    return <Vacio icono={Briefcase} titulo="Aún no tienes ofertas registradas">Analiza una en «Analizar oferta».</Vacio>;
  }

  const visibles = filtro ? ofertas.filter((o) => o.estado === filtro) : ofertas;
  const seleccion = ofertas.find((o) => o.job_id === elegida);

  return (
    <div className="aparecer">
      <Encabezado seccion="Ofertas" titulo="Postulaciones" descripcion="El estado de cada oferta, su historial y los CVs que enviaste." />

      {/* Embudo: también sirve de filtro */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
        {estados.map((e) => {
          const Icono = ICONOS[e] ?? Inbox;
          const n = ofertas.filter((o) => o.estado === e).length;
          const activo = filtro === e;
          return (
            <button key={e} onClick={() => setFiltro(activo ? null : e)} aria-pressed={activo}
                    className={cx(
                      "rounded-md border bg-surface p-4 text-left transition",
                      activo ? "border-primary ring-2 ring-primary/20" : "border-line hover:border-primary/40",
                    )}>
              <Icono className="size-5 text-primary" />
              <p className="mt-2 font-mono text-2xl font-semibold tabular-nums text-ink">{n}</p>
              <p className="text-xs text-ink-2">{e}</p>
            </button>
          );
        })}
      </div>

      <Seccion titulo={filtro ? `Ofertas: ${filtro}` : "Todas las ofertas"}
               extra={filtro && <Boton variante="fantasma" onClick={() => setFiltro(null)}>Ver todas</Boton>}>
        <div className="overflow-x-auto rounded-md border border-line bg-surface">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-2 text-xs text-ink-2 uppercase">
              <tr>
                <th className="px-4 py-3 font-semibold">Puesto</th>
                <th className="px-4 py-3 font-semibold">Empresa</th>
                <th className="px-4 py-3 font-semibold">Estado</th>
                <th className="px-4 py-3 font-semibold">Match</th>
                <th className="px-4 py-3 font-semibold">Registrada</th>
              </tr>
            </thead>
            <tbody>
              {visibles.map((o) => (
                <tr key={o.job_id} onClick={() => setElegida(o.job_id)}
                    className={cx("cursor-pointer border-t border-line transition hover:bg-surface-2",
                      elegida === o.job_id && "bg-primary-soft hover:bg-primary-soft")}>
                  <td className="px-4 py-3 font-medium text-ink">{o.puesto}</td>
                  <td className="px-4 py-3 text-ink-2">{o.empresa}</td>
                  <td className="px-4 py-3"><Insignia>{o.estado}</Insignia></td>
                  <td className="px-4 py-3 font-semibold text-ink">{formatoScore(o.match_score)}</td>
                  <td className="px-4 py-3 text-ink-2">{fechaCorta(o.fecha_registro)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-ink-3">Haz clic en una oferta para actualizarla y ver sus CVs.</p>
      </Seccion>

      {seleccion && <Detalle key={seleccion.job_id} oferta={seleccion} estados={estados} />}
    </div>
  );
}

function Detalle({ oferta, estados }: { oferta: Oferta; estados: string[] }) {
  const [estado, setEstado] = useState(oferta.estado);
  const [nota, setNota] = useState("");
  const qc = useQueryClient();
  const avisar = useAvisos();
  const navegar = useNavigate();
  const historial = useQuery({ queryKey: ["historial", oferta.job_id], queryFn: () => api.historial(oferta.job_id) });
  const cvs = useQuery({ queryKey: ["cvs", oferta.job_id], queryFn: () => api.versionesCV(oferta.job_id) });

  useEffect(() => {
    setEstado(oferta.estado);
  }, [oferta.estado]);

  const guardar = useMutation({
    mutationFn: () => api.cambiarEstado(oferta.job_id, estado, nota),
    onSuccess: () => { qc.invalidateQueries(); setNota(""); avisar(`Estado actualizado a ${estado}.`); },
    onError: (e) => avisar(e.message, true),
  });

  return (
    <Seccion titulo={oferta.puesto}
             extra={<Boton icono={FilePen} onClick={() => navegar(`/adaptar-cv?job=${oferta.job_id}`)}>Adaptar mi CV</Boton>}>
      <div className="grid gap-4 lg:grid-cols-2">
        <Tarjeta className="flex flex-col gap-4">
          <div className="flex items-center gap-2"><InsigniaEncaje score={oferta.match_score} /><span className="text-sm text-ink-2">{oferta.empresa}</span></div>
          <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
            <Campo etiqueta="Estado">
              <select className={claseCampo} value={estado} onChange={(e) => setEstado(e.target.value)}>
                {estados.map((e) => <option key={e}>{e}</option>)}
              </select>
            </Campo>
            <Campo etiqueta="Nota (opcional)">
              <input className={claseCampo} value={nota} onChange={(e) => setNota(e.target.value)}
                     placeholder="Ej.: entrevista el jueves con RR. HH." />
            </Campo>
            <div>
              <Boton type="submit" variante="primario" icono={Save} cargando={guardar.isPending}
                     disabled={estado === oferta.estado && !nota.trim()}>Guardar</Boton>
            </div>
            {estado === "Postulada" && oferta.estado !== "Postulada" && (
              <p className="text-xs text-ink-3">Al guardar, la última versión de tu CV para esta oferta queda registrada como la enviada.</p>
            )}
          </form>
          {!!historial.data?.length && (
            <div>
              <p className="mb-2 text-sm font-semibold text-ink">Historial</p>
              <ol className="relative border-l border-line pl-4">
                {historial.data.map((h, i) => (
                  <li key={i} className="mb-3 last:mb-0">
                    <span className="absolute -left-1.5 mt-1.5 size-3 rounded-full border-2 border-surface bg-primary" />
                    <p className="text-sm font-medium text-ink">{h.estado}</p>
                    <p className="text-xs text-ink-3">{new Date(h.fecha).toLocaleString("es-PE")}{h.nota && ` · ${h.nota}`}</p>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </Tarjeta>

        <Tarjeta>
          <p className="mb-3 text-sm font-semibold text-ink">CVs generados para esta oferta</p>
          {!cvs.data?.length ? (
            <p className="text-sm text-ink-2">Todavía no adaptaste tu CV a esta oferta.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {cvs.data.map((v) => (
                <li key={v.version} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line px-3 py-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-ink">Versión {v.version}</span>
                    <span className="text-xs text-ink-3">{new Date(v.fecha).toLocaleString("es-PE")}</span>
                    {v.enviado && <Insignia tono="ok" icono={Send}>Enviado {fechaCorta(v.fecha_envio)}</Insignia>}
                    {!v.usa_texto_de_pluma && <Insignia>Textos originales</Insignia>}
                  </div>
                  <div className="flex gap-1">
                    <a href={urlArchivo(v.ruta_cv)} className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-semibold text-primary hover:bg-primary-soft"><Download className="size-3.5" />CV</a>
                    <a href={urlArchivo(v.ruta_brechas)} className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-semibold text-primary hover:bg-primary-soft"><Download className="size-3.5" />Brechas</a>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>
      </div>
    </Seccion>
  );
}
