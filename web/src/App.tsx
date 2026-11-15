import * as React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { SessionProvider, useSession } from './hooks/useSession';
import { AppShell } from './components/AppShell';
import { Overview } from './views/Overview';
import { CrewConsole } from './views/CrewConsole';
import { CrewChecks } from './views/CrewChecks';
import { SurgeonQueue } from './views/SurgeonQueue';
import { OpsConsole } from './views/OpsConsole';
import { ResearchView } from './views/ResearchView';
import { WorkstationView } from './views/WorkstationView';
import { EmptyState } from './components/ui';
import type { Role } from './lib/types';

const HOME: Record<Role, string> = {
  crew: '/workstation',
  'flight-surgeon': '/workstation',
  ops: '/workstation',
  researcher: '/workstation',
};

function RoleGate({ allow, children }: { allow: Role[]; children: React.ReactNode }) {
  const { role } = useSession();
  if (!allow.includes(role)) {
    return (
      <EmptyState title="Not available for this role"
        detail={`This view needs one of: ${allow.join(', ')}. Use the role selector in the header. Roles here are a demo-grade switcher, not authentication.`} />
    );
  }
  return <>{children}</>;
}

function Home() {
  const { role, loading } = useSession();
  if (loading) return <EmptyState title="Loading session" detail="Contacting the API…" />;
  return <Navigate to={HOME[role]} replace />;
}

export function App() {
  return (
    <SessionProvider>
      <AppShell>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/workstation" element={<WorkstationView />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/crew" element={<RoleGate allow={['crew', 'flight-surgeon', 'ops']}><CrewConsole /></RoleGate>} />
          <Route path="/crew/checks" element={<RoleGate allow={['crew', 'flight-surgeon']}><CrewChecks /></RoleGate>} />
          <Route path="/surgeon" element={<RoleGate allow={['flight-surgeon', 'ops']}><SurgeonQueue /></RoleGate>} />
          <Route path="/ops" element={<RoleGate allow={['ops', 'flight-surgeon', 'crew']}><OpsConsole /></RoleGate>} />
          <Route path="/research" element={<ResearchView />} />
          <Route path="*" element={<EmptyState title="Page not found" detail="Use the navigation rail or press ⌘K." />} />
        </Routes>
      </AppShell>
    </SessionProvider>
  );
}
