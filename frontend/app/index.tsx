// pages/index.tsx
import Link from 'next/link'

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Navigation */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-900">🎓 WajhUni</h1>
            <div className="space-x-4">
              <Link href="/universities" className="text-gray-600 hover:text-gray-900">
                جميع الجامعات
              </Link>
              <Link href="/about" className="text-gray-600 hover:text-gray-900">
                عن الموقع
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="max-w-6xl mx-auto px-4 py-16 text-center">
        <h1 className="text-5xl font-bold text-gray-900 mb-6">
          دليلك لاختيار الجامعة المناسبة في تونس
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
          آراء حقيقية من الطلاب عن الجامعات، المقاصف، السكن، والحي الجامعي. 
          لا تختر جامعتك وأنت مغمض العينين!
        </p>
        
        {/* Search Bar */}
        <div className="max-w-2xl mx-auto">
          <div className="flex shadow-lg rounded-lg overflow-hidden">
            <input 
              type="text" 
              placeholder="ابحث عن جامعة (مثال: Tunis Business School, ENSI...)"
              className="flex-1 px-6 py-4 text-lg border-0 focus:ring-0"
            />
            <button className="bg-blue-600 text-white px-8 py-4 hover:bg-blue-700 transition">
              بحث
            </button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="max-w-6xl mx-auto px-4 py-16">
        <div className="grid md:grid-cols-3 gap-8">
          <div className="text-center p-6">
            <div className="text-3xl mb-4">⭐</div>
            <h3 className="text-xl font-semibold mb-2">تقييمات حقيقية</h3>
            <p className="text-gray-600">آراء من طلاب حقيقيين يدرسون في هذه الجامعات</p>
          </div>
          <div className="text-center p-6">
            <div className="text-3xl mb-4">🏫</div>
            <h3 className="text-xl font-semibold mb-2">معلومات مفصلة</h3>
            <p className="text-gray-600">عن المقاصف، السكن، النقل، والأنشطة الجامعية</p>
          </div>
          <div className="text-center p-6">
            <div className="text-3xl mb-4">🔒</div>
            <h3 className="text-xl font-semibold mb-2">مراجعات موثوقة</h3>
            <p className="text-gray-600">نضمن أن التقييمات تأتي من طلاب حقيقيين</p>
          </div>
        </div>
      </section>
    </div>
  )
}