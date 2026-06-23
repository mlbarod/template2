import React, { Suspense, lazy } from "react";
import { ObserverShell } from "./components/ObserverShell";
import { PageLoader } from "./components/Loaders";

const ObserverPage = lazy(() => import("./pages/ObserverPage"));
const TkinPreventDashboardPage = lazy(() =>
  import("./pages/TkinPreventDashboardPage")
);

const ObserverRoute = () => (
  <Suspense fallback={<PageLoader label="Observer을 불러오는 중입니다" />}>
    <ObserverPage />
  </Suspense>
);

const TkinPreventDashboardRoute = () => (
  <Suspense fallback={<PageLoader label="T/K-IN Prevent를 불러오는 중입니다" />}>
    <TkinPreventDashboardPage />
  </Suspense>
);

export const observerRoutes = [
  {
    path: "observer",
    element: <ObserverShell />,
    children: [
      { index: true, element: <ObserverRoute /> },
      { path: "tkin-prevent", element: <TkinPreventDashboardRoute /> },
      { path: ":eqpId", element: <ObserverRoute /> },
    ],
  },
];
