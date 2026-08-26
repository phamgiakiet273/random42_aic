import VideoGrid from '../components/VideoGrid'
import QueryPanel from '../components/QueryPanel'
import SettingsPanel from '../components/SettingsPanel'
import FiltersPanel from '../components/FiltersPanel'

export default function HomePage() {
  return (
    <main className="flex flex-col lg:flex-row gap-4 p-4">
      <aside className="w-full lg:w-96 lg:shrink-0 flex flex-col gap-4">
        <QueryPanel />
        <FiltersPanel />
      </aside>
      <section className="flex-1 min-w-0 flex flex-col gap-4">
        <div className="flex justify-end">
          <SettingsPanel />
        </div>
        <VideoGrid />
      </section>
    </main>
  )
}
