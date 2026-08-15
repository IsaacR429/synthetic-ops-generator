import { Route, Routes } from 'react-router'

import { AppShell } from './layouts/AppShell'
import { EventInspectionPage } from './pages/EventInspectionPage'
import { OverviewPage } from './pages/OverviewPage'
import { RunConfigurationPage } from './pages/RunConfigurationPage'
import { RunDetailPage } from './pages/RunDetailPage'
import { RunsPage } from './pages/RunsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route
          index
          element={<OverviewPage />}
        />

        <Route
          path="configure"
          element={<RunConfigurationPage />}
        />

        <Route
          path="runs"
          element={<RunsPage />}
        />

        <Route
          path="runs/:runId"
          element={<RunDetailPage />}
        />

        <Route
          path="runs/:runId/events"
          element={<EventInspectionPage />}
        />
      </Route>
    </Routes>
  )
}