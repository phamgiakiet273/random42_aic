import VideoGrid from './components/VideoGrid'
import QueryPanel from './components/QueryPanel'
import SettingsPanel from './components/SettingsPanel'
import FiltersPanel from './components/FiltersPanel'

export default function App() {
  return (
    <div className="min-h-screen bg-base-200">
      <header className="navbar bg-base-100 shadow-sm px-4">
        <span className="text-lg font-semibold">AIC Video Search</span>
      </header>
      <main className="flex flex-col lg:flex-row gap-4 p-4">
        <section className="flex-1 min-w-0">
          <VideoGrid />
        </section>
        <aside className="w-full lg:w-96 lg:shrink-0 flex flex-col gap-4 lg:h-[calc(100vh-6rem)] lg:overflow-y-auto">
          <QueryPanel />
          <SettingsPanel />
          <FiltersPanel />
        </aside>
      </main>
    </div>
  )
}
