// app/universities/[slug]/page.tsx
import Link from 'next/link'

// Mock data function
function getUniversityData(slug: string) {
  const universities: { [key: string]: any } = {
    'tunis-business-school': {
      name: 'Tunis Business School',
      location: 'Le Bardo, Tunis',
      description: 'A leading business school in Tunisia'
    },
    'ensi': {
      name: 'École Nationale des Sciences de l\'Informatique',
      location: 'Manouba',
      description: 'National School of Computer Science'
    },
    'isamm': {
      name: 'Institut Supérieur des Arts Multimédia de Manouba',
      location: 'Manouba',
      description: 'Higher Institute of Multimedia Arts of Manouba'
    },
    'fsegt': {
      name: 'Faculté des Sciences Économiques et de Gestion de Tunis',
      location: 'Tunis',
      description: 'Faculty of Economic Sciences and Management of Tunis'
    }
  }
  
  return universities[slug] || {
    name: 'University Not Found',
    location: 'Unknown',
    description: 'This university does not exist in our database'
  }
}

interface PageProps {
  params: {
    slug: string
  }
}

export default function UniversityPage({ params }: PageProps) {
  const { slug } = params
  const university = getUniversityData(slug)

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <Link href="/" className="text-blue-600 hover:text-blue-800">
            ← Back to Home
          </Link>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          {university.name}
        </h1>
        <p className="text-gray-600 mb-4">{university.location}</p>
        <p className="text-gray-700 mb-8">{university.description}</p>
        
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-2xl font-semibold mb-4">التقييمات</h2>
          <p className="text-gray-500">لا توجد تقييمات بعد. كن أول من يقيم!</p>
        </div>
      </div>
    </div>
  )
}