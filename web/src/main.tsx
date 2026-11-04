import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import { ProveedorAvisos } from "./components/avisos";
import Layout from "./components/Layout";
import PaginaError from "./components/PaginaError";
import "./index.css";
import AdaptarCV from "./pages/AdaptarCV";
import Agentes from "./pages/Agentes";
import Analizar from "./pages/Analizar";
import Bandeja from "./pages/Bandeja";
import Inicio from "./pages/Inicio";
import Perfil from "./pages/Perfil";
import Postulaciones from "./pages/Postulaciones";
import QueEstudiar from "./pages/QueEstudiar";
import Revision from "./pages/Revision";
import { Cargando } from "./components/ui";

// Recharts es la librería más pesada: solo se descarga al abrir Análisis.
const Analisis = lazy(() => import("./pages/Analisis"));

// Las lecturas se guardan 2 minutos (cada consulta a Supabase tarda ~1 s);
// cualquier cambio hecho desde la app las invalida.
const cliente = new QueryClient({
  defaultOptions: { queries: { staleTime: 120_000, retry: 1, refetchOnWindowFocus: false } },
});

const router = createBrowserRouter([
  {
    element: <Layout />,
    errorElement: <PaginaError />,
    children: [
      { path: "/", element: <Inicio /> },
      { path: "/bandeja", element: <Bandeja /> },
      { path: "/analizar", element: <Analizar /> },
      { path: "/postulaciones", element: <Postulaciones /> },
      { path: "/adaptar-cv", element: <AdaptarCV /> },
      { path: "/perfil", element: <Perfil /> },
      { path: "/que-estudiar", element: <QueEstudiar /> },
      { path: "/analisis", element: <Suspense fallback={<Cargando />}><Analisis /></Suspense> },
      { path: "/revision", element: <Revision /> },
      { path: "/agentes", element: <Agentes /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={cliente}>
      <ProveedorAvisos>
        <RouterProvider router={router} />
      </ProveedorAvisos>
    </QueryClientProvider>
  </StrictMode>,
);
