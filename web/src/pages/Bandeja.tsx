import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, FilePen, Inbox, Radar, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { api, type ResultadoSabueso } from "../api";
import { useAvisos } from "../components/avisos";
import {
  Aviso, Boton, Cargando, Encabezado, Segmentado, TarjetaOferta, Vacio, nivelEncaje, plural,
} from "../components/ui";

type Filtro = "Todos" | "Encaje alto" | "Encaje medio" | "Encaje bajo";
type Orden = "Match Score" | "Más recientes";

export default function Bandeja() {
  const [filtro, setFiltro] = useState<Filtro>("Todos");
  const [orden, setOrden] = useState<Orden>("Match Score");
  const [busqueda, setBusqueda] = useState<ResultadoSabueso | null>(null);
  const qc = useQueryClient();
  const avisar = useAvisos();
  const navegar = useNavigate();

  const { data: ofertas, isLoading } = useQuery({ queryKey: ["ofertas"], queryFn: api.ofertas });

  const cambiar = useMutation({
    mutationFn: ({ id, estado, nota }: { id: number; estado: string; nota: string }) => api.cambiarEstado(id, estado, nota),
    onSuccess: (_, v) => {
      qc.invalidateQueries();
      avisar(v.estado === "Descartada" ? "Oferta descartada." : "Marcada como revisada.");
    },
    onError: (e) => avisar(String(e.message), true),
  });

  const buscar = useMutation({
    mutationFn: api.buscarOfertas,
    onSuccess: (r) => { setBusqueda(r); qc.invalidateQueries(); },
    onError: (e) => avisar(String(e.message), true),
  });

  let bandeja = (ofertas ?? []).filter((o) => o.estado === "Registrada");
  if (filtro !== "Todos") bandeja = bandeja.filter((o) => nivelEncaje(o.match_score).texto === filtro);
  bandeja = [...bandeja].sort((a, b) =>
    orden === "Más recientes"
      ? b.fecha_registro.localeCompare(a.fecha_registro)
      : (b.match_score ?? 0) - (a.match_score ?? 0),
  );

  return (
    <div className="aparecer">
      <Encabezado
        seccion="Ofertas"
        titulo="Bandeja"
        descripcion="Ofertas que aún no revisas: las que trajo Sabueso de Get on Board y las que analizaste tú. Adapta tu CV a las que te interesen y descarta el resto."
        acciones={
          <Boton variante="primario" icono={Radar} cargando={buscar.isPending} onClick={() => buscar.mutate()}>
            {buscar.isPending ? "Buscando..." : "Buscar ofertas nuevas"}
          </Boton>
        }
      />

      {buscar.isPending && (
        <div className="mb-5"><Aviso>Sabueso está buscando y Lupa analizando cada oferta nueva. Puede tardar unos minutos.</Aviso></div>
      )}
      {busqueda && (
        <div className="mb-5 flex flex-col gap-2">
          <Aviso tono="ok" titulo={`Sabueso revisó ${plural(busqueda.encontradas, "oferta", "ofertas")}`}>
            {plural(busqueda.registradas.length, "nueva registrada", "nuevas registradas")}, {busqueda.ya_registradas} ya
            estaban y {busqueda.fuera_de_filtro} no pasaron tu filtro.
            {busqueda.pendientes_por_tope > 0 && ` ${plural(busqueda.pendientes_por_tope, "quedó", "quedaron")} para la próxima búsqueda.`}
          </Aviso>
          {busqueda.errores.map((e) => <Aviso key={e} tono="warn">{e}</Aviso>)}
        </div>
      )}

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <Segmentado etiqueta="Filtrar por encaje" opciones={["Todos", "Encaje alto", "Encaje medio", "Encaje bajo"] as Filtro[]} valor={filtro} onChange={setFiltro} />
        <Segmentado etiqueta="Ordenar" opciones={["Match Score", "Más recientes"] as Orden[]} valor={orden} onChange={setOrden} />
        {!isLoading && <span className="text-sm text-ink-3">{plural(bandeja.length, "oferta", "ofertas")}</span>}
      </div>

      {isLoading ? <Cargando /> : bandeja.length === 0 ? (
        <Vacio icono={Inbox} titulo="No hay ofertas con ese filtro">Prueba otro filtro o busca ofertas nuevas.</Vacio>
      ) : (
        <div className="flex flex-col gap-3">
          {bandeja.map((o) => (
            <TarjetaOferta key={o.job_id} oferta={o} mostrarEstado={false} acciones={<>
              <Boton variante="primario" icono={FilePen} onClick={() => navegar(`/adaptar-cv?job=${o.job_id}`)}>Adaptar CV</Boton>
              <Boton icono={Check} title="Marcar como revisada"
                     onClick={() => cambiar.mutate({ id: o.job_id, estado: "Analizada", nota: "Revisada desde la bandeja" })}>
                Revisada
              </Boton>
              <Boton variante="peligro" icono={Trash2} aria-label={`Descartar ${o.puesto}`}
                     onClick={() => cambiar.mutate({ id: o.job_id, estado: "Descartada", nota: "Descartada desde la bandeja" })} />
            </>} />
          ))}
        </div>
      )}
    </div>
  );
}
