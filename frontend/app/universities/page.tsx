// app/universities/page.tsx
import Link from 'next/link'

// Simple mock data
const universities = [
  { slug: 'tunis-business-school', name: 'Tunis Business School', location: 'Le Bardo' },
  { slug: 'ensi', name: 'ENSI', location: 'Manouba' },
  { slug: 'isamm', name: 'ISAMM', location: 'Manouba' },
  { slug: 'fsegt', name: 'FSEGT', location: 'Tunis' }
]

export default function UniversitiesPage() {
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">All Tunisian Universities</h1>
        
        <div className="space-y-4">
          {universities.map((uni) => (
            <Link 
              key={uni.slug}
              href={`/universities/${uni.slug}`}
              className="block bg-white p-6 rounded-lg shadow hover:shadow-md transition"
            >
              <h2 className="text-xl font-semibold">{uni.name}</h2>
              <p className="text-gray-600">{uni.location}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}