import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

interface PageShellProps {
  title: string
  children: ReactNode
}

export function PageShell({ title, children }: PageShellProps) {
  return (
    <div className="flex h-screen w-full">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar title={title} />
        <main
          className="flex-1 overflow-auto p-4"
          style={{ backgroundColor: 'var(--color-bg-primary)' }}
        >
          {children}
        </main>
      </div>
    </div>
  )
}
