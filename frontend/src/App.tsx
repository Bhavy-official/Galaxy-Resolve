import { Routes, Route } from 'react-router-dom'
import { GalaxyShell } from '@/components/GalaxyShell'
import { HomePage } from '@/pages/HomePage'
import { DemoPage } from '@/pages/DemoPage'
import { FeaturesPage } from '@/pages/FeaturesPage'
import { MetricsPage } from '@/pages/MetricsPage'

export default function App() {
  return (
    <GalaxyShell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/demo" element={<DemoPage />} />
        <Route path="/features" element={<FeaturesPage />} />
        <Route path="/metrics" element={<MetricsPage />} />
      </Routes>
    </GalaxyShell>
  )
}
